#!/usr/bin/env python3
"""High-level support for the LFI-Demo-Board."""

import asyncio
import enum
from pathlib import Path
from typing import List, Protocol, Tuple

import serial_asyncio
from serial.tools.list_ports import comports
from smbus2_asyncio import SMBus2Asyncio

from .hw_def import I2C_BUS_INDEX, Sx1509Io
from .ina219 import Ina219, Ina219Readings
from .sx1509 import Sx1509, Sx1509IoConfiguration


async def _get_i2c_bus_handler() -> SMBus2Asyncio:
    """Get an I2C bus instance."""
    bus = SMBus2Asyncio(I2C_BUS_INDEX)
    await bus.open()
    return bus


class LfiDemoBoardTargetMode(enum.Enum):
    """Possible operating modes of the target."""

    OFF = enum.auto()
    RUNNING = enum.auto()
    BOOTLOADER = enum.auto()


class LfiDemoBoardError(Exception):
    """Raised in case of an error with the LFI Demo Board."""

    pass


class LfiDemoBoardProtocol(Protocol):
    """Protocol for the High-level interface to the LFI-Demo-Board."""

    async def setup(self) -> None:
        """Configure the LFI-Demo-Board."""
        ...

    async def set_illumination_led_power(self, power: float) -> None:
        """Control the Illumination LED.

        Args:
            power (float): The power, expected to be between 0.0 and 1.0

        """
        ...

    async def configure_led_ring(self, power: List[float]) -> None:
        """Control the illumination LED ring.

        Args:
            power (List[float]): A list of power for each LED of the ring, expected to be between 0.0 and 1.0

        """
        ...

    async def get_current_readings(self) -> Ina219Readings:
        """Get readings from the on-board INA219 sensor."""
        return Ina219Readings(shunt_voltage=0, bus_voltage=0, power=0, current=0)

    async def set_target_mode(self, mode: LfiDemoBoardTargetMode) -> None:
        """Play the correct sequence of I/O to force the target to enter the given state."""
        ...

    async def flash_target(self, uf2_firmware: Path, n_retries: int = 3) -> None:
        """Flash the target with the provided firmware image.

        Args:
            uf2_firmware (Path): The firmware image, expected to be a UF2 file
            n_retries (int, optional): Number of times to attempt to flash the device. Defaults to 3.

        """
        ...

    async def get_target_serial_reader(
        self, serial_if_name: str
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Open the target serial interface.

        Args:
            serial_if_name (str): The target serial interface name

        Returns:
            Tuple[asyncio.StreamReader, asyncio.StreamWriter]: Streams to read and write data

        """
        ...


class LfiDemoBoard:
    """High-level interface to the LFI-Demo-Board."""

    def __init__(self) -> None:
        """Create a LFI-Demo-Board interface."""
        self._io_expander: Sx1509 | None = None
        self._current_sensor: Ina219 | None = None

    async def setup(self) -> None:
        """Configure the LFI-Demo-Board."""
        self._current_target_mode = LfiDemoBoardTargetMode.OFF

        i2c_bus_handler = await _get_i2c_bus_handler()

        self._io_expander = Sx1509(i2c_bus_handler)
        self._current_sensor = Ina219(i2c_bus_handler)

        await self._io_expander.setup()
        await self._current_sensor.setup()

        # Configure target Signals
        await self._io_expander.set(Sx1509Io.DUT_PWR_EN, False)
        await self._io_expander.configure(
            io=Sx1509Io.DUT_PWR_EN, configuration=Sx1509IoConfiguration(oe=True)
        )

        await self._io_expander.set(Sx1509Io.DUT_RUN, True)
        await self._io_expander.configure(
            io=Sx1509Io.DUT_RUN, configuration=Sx1509IoConfiguration(oe=True, od=True)
        )

        await self._io_expander.set(Sx1509Io.DUT_BOOTSEL, True)
        await self._io_expander.configure(
            io=Sx1509Io.DUT_BOOTSEL,
            configuration=Sx1509IoConfiguration(oe=True, od=True),
        )

        # Configure LED driver
        await self._io_expander.set_pwm(Sx1509Io.CC_DIM, 0.0)
        await self._io_expander.configure(
            io=Sx1509Io.CC_DIM, configuration=Sx1509IoConfiguration(oe=True, led=True)
        )

        # Configure LED ring
        for led_ring_index in range(8):
            led_io = Sx1509Io.get_illumination_ring_io(led_ring_index)
            await self._io_expander.set_pwm(led_io, 0.0)
            await self._io_expander.configure(
                io=led_io, configuration=Sx1509IoConfiguration(oe=True, led=True)
            )

    async def set_illumination_led_power(self, power: float) -> None:
        """Control the Illumination LED.

        Args:
            power (float): The power, expected to be between 0.0 and 1.0

        """
        if self._io_expander is None:
            raise LfiDemoBoardError("Setup has failed")

        await self._io_expander.set_pwm(Sx1509Io.CC_DIM, power)

    async def configure_led_ring(self, power: List[float]) -> None:
        """Control the illumination LED ring.

        Args:
            power (List[float]): A list of power for each LED of the ring, expected to be between 0.0 and 1.0

        """
        if self._io_expander is None:
            raise LfiDemoBoardError("Setup has failed")

        for i, p in enumerate(power):
            await self._io_expander.set_pwm(
                io=Sx1509Io.get_illumination_ring_io(i), value=p
            )

    async def get_current_readings(self) -> Ina219Readings:
        """Get readings from the on-board INA219 sensor."""
        if self._current_sensor is None:
            raise LfiDemoBoardError("Setup has failed")

        ret = await self._current_sensor.read()
        return ret

    async def set_target_mode(self, mode: LfiDemoBoardTargetMode) -> None:
        """Play the correct sequence of I/O to force the target to enter the given state."""
        if self._io_expander is None:
            raise LfiDemoBoardError("Setup has failed")

        if mode == self._current_target_mode:
            return

        if mode == LfiDemoBoardTargetMode.OFF:
            await self._io_expander.set(Sx1509Io.DUT_PWR_EN, False)
            await self._io_expander.set(Sx1509Io.DUT_RUN, True)
            await self._io_expander.set(Sx1509Io.DUT_BOOTSEL, True)

        elif mode == LfiDemoBoardTargetMode.RUNNING:
            # Start by ensuring the target is OFF
            await self._io_expander.set(Sx1509Io.DUT_PWR_EN, False)
            await self._io_expander.set(Sx1509Io.DUT_RUN, True)
            await self._io_expander.set(Sx1509Io.DUT_BOOTSEL, True)
            await asyncio.sleep(0.2)

            # Turn it back on
            await self._io_expander.set(Sx1509Io.DUT_PWR_EN, True)

        elif mode == LfiDemoBoardTargetMode.BOOTLOADER:
            # Start by ensuring the target is OFF, and force BOOTSEL low
            await self._io_expander.set(Sx1509Io.DUT_PWR_EN, False)
            await self._io_expander.set(Sx1509Io.DUT_RUN, True)
            await self._io_expander.set(Sx1509Io.DUT_BOOTSEL, False)
            await asyncio.sleep(0.2)

            # Turn it back on, with BOOTSEL still low
            await self._io_expander.set(Sx1509Io.DUT_PWR_EN, True)
            await asyncio.sleep(0.2)

            # Release BOOTSEL
            await self._io_expander.set(Sx1509Io.DUT_BOOTSEL, True)

        self._current_target_mode = mode

    async def flash_target(self, uf2_firmware: Path, n_retries: int = 3) -> None:
        """Flash the target with the provided firmware image.

        Args:
            uf2_firmware (Path): The firmware image, expected to be a UF2 file
            n_retries (int, optional): Number of times to attempt to flash the device. Defaults to 3.

        """
        await self.set_target_mode(LfiDemoBoardTargetMode.BOOTLOADER)
        await asyncio.sleep(1.0)

        cmd = f"picotool load -v -x {uf2_firmware}"

        for _ in range(n_retries):
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                break

            await asyncio.sleep(0.5)

        await self.set_target_mode(LfiDemoBoardTargetMode.OFF)

        if proc.returncode != 0:
            msg = stdout.decode(errors="replace") + stderr.decode(errors="replace")
            msg = msg.strip()
            raise LfiDemoBoardError(f"Cannot flash target ({msg})")

    async def get_target_serial_reader(
        self, serial_if_name: str
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Open the target serial interface.

        Args:
            serial_if_name (str): The target serial interface name

        Returns:
            Tuple[asyncio.StreamReader, asyncio.StreamWriter]: Streams to read and write data

        """
        # Find serial path, assume only the target is connected
        serial_path = None
        for path, desc, _ in comports():
            if desc == serial_if_name:
                serial_path = path
                break

        if serial_path is None:
            raise LfiDemoBoardError(f'Cannot find "{serial_if_name}" serial interface')

        # Open serial
        try:
            stream = await serial_asyncio.open_serial_connection(
                url=serial_path, baudrate=115_200
            )
        except Exception as e:
            raise LfiDemoBoardError(f"Cannot open target serial interface: {e}")

        return stream


class DummyLfiDemoBoard:
    """Dummy High-level interface to the LFI-Demo-Board."""

    def __init__(self) -> None:
        """Create a LFI-Demo-Board interface."""
        self._counter = 0

    async def setup(self) -> None:
        """Configure the LFI-Demo-Board."""
        ...

    async def set_illumination_led_power(self, power: float) -> None:
        """Control the Illumination LED.

        Args:
            power (float): The power, expected to be between 0.0 and 1.0

        """
        ...

    async def configure_led_ring(self, power: List[float]) -> None:
        """Control the illumination LED ring.

        Args:
            power (List[float]): A list of power for each LED of the ring, expected to be between 0.0 and 1.0

        """
        ...

    async def get_current_readings(self) -> Ina219Readings:
        """Get readings from the on-board INA219 sensor."""
        self._counter = (self._counter + 1) % 10
        return Ina219Readings(
            shunt_voltage=0, bus_voltage=0, power=0, current=self._counter * 1e-3
        )

    async def set_target_mode(self, mode: LfiDemoBoardTargetMode) -> None:
        """Play the correct sequence of I/O to force the target to enter the given state."""
        ...

    async def flash_target(self, uf2_firmware: Path, n_retries: int = 3) -> None:
        """Flash the target with the provided firmware image.

        Args:
            uf2_firmware (Path): The firmware image, expected to be a UF2 file
            n_retries (int, optional): Number of times to attempt to flash the device. Defaults to 3.

        """
        ...

    async def get_target_serial_reader(
        self, serial_if_name: str
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Open the target serial interface.

        Args:
            serial_if_name (str): The target serial interface name

        Returns:
            Tuple[asyncio.StreamReader, asyncio.StreamWriter]: Streams to read and write data

        """
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        transport = _DummySerialTransport()
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)

        return (reader, writer)


class _DummySerialTransport(asyncio.Transport):
    def is_closing(self) -> bool:
        return False

    def close(self) -> None:
        pass
