#!/usr/bin/env python3
"""Driver for the laser pulser board."""

import asyncio
import enum
import time
from enum import IntEnum
from typing import Protocol

from .cypress_usb import CypressI2cDataConfig, CypressUSB


class _LaserPulserGpio(IntEnum):
    """Laser pulser board GPIOs."""

    POWER_EN = 1
    DRIVER_EN = 2
    PULSE = 5


class _LaserSafePulserGpio(IntEnum):
    """Laser safe pulser board GPIOs."""

    PULSE = 1


class LaserPulserType(enum.StrEnum):
    """Enumerate the supported laser pulser hardware."""

    HIGH_POWER = "high-power"
    LOW_POWER = "low-power"
    NONE = "none"


class LaserPulserError(Exception):
    """Raised in case of an error with the Laser Pulser Board."""

    pass


class LaserPulser:
    """Driver for the laser pulser board."""

    def __init__(self, safe_pulse_duration: float) -> None:
        """Create a driver instance."""
        self._usb = CypressUSB()

        self.is_safe_board = "Safe" in self._usb.get_name()

        self._safe_pulse_duration = safe_pulse_duration

    def set_power(self, en: bool) -> None:
        """Set the value of the POWER_EN signal."""
        if self.is_safe_board:
            return
        self._usb.gpio_set(_LaserPulserGpio.POWER_EN, en)

    def set_driver_en(self, en: bool) -> None:
        """Enable or disable the switch driver."""
        if self.is_safe_board:
            return
        self._usb.gpio_set(_LaserPulserGpio.DRIVER_EN, not en)

    def pulse(self) -> None:
        """Send a laser pulse."""
        if self.is_safe_board:
            io = _LaserSafePulserGpio.PULSE.value
            self._usb.gpio_set(io, True)
            time.sleep(self._safe_pulse_duration)
            self._usb.gpio_set(io, False)
        else:
            io = _LaserPulserGpio.PULSE.value
            self._usb.gpio_set(io, True)
            self._usb.gpio_set(io, False)

    def _set_potentiometer_step(self, step: int) -> None:
        config = CypressI2cDataConfig(
            slave_address=0b0101110, is_stop_bit=True, is_nak_bit=False
        )
        self._usb.i2c_write(config, bytes([0, step]))

    def set_supply_voltage(self, voltage: float) -> None:
        """Set the capacitor bank voltage value.

        Args:
            voltage (float): The voltage, expressed in V.

        """
        if self.is_safe_board:
            return

        vref = 1.2  # V
        rhigh = 619  # kOhms
        rlow = 10  # kOhms
        rpot = 100  # kOhms

        step = int(127 * (rhigh / (voltage / vref - 1) - rlow) / rpot)

        step = max(0, min(127, step))

        self._set_potentiometer_step(step)


class AsyncLaserPulserProtocol(Protocol):
    """Protocol for the laser pulser board driver."""

    async def setup(self) -> None:
        """Configure the laser pulser board."""
        ...

    async def set_power(self, en: bool) -> None:
        """Set the value of the POWER_EN signal."""
        ...

    async def set_driver_en(self, en: bool) -> None:
        """Enable or disable the switch driver."""
        ...

    async def pulse(self) -> None:
        """Send a laser pulse."""
        ...

    async def set_supply_voltage(self, voltage: float) -> None:
        """Set the capacitor bank voltage value.

        Args:
            voltage (float): The voltage, expressed in V.

        """
        ...

    def get_type(self) -> LaserPulserType:
        """Return the type of laser hardware connected to the platform."""
        ...


class DummyAsyncLaserPulser:
    """Dummy Async driver for the laser pulser board."""

    async def setup(self) -> None:
        """Configure the laser pulser board."""
        ...

    async def set_power(self, en: bool) -> None:
        """Set the value of the POWER_EN signal."""
        ...

    async def set_driver_en(self, en: bool) -> None:
        """Enable or disable the switch driver."""
        ...

    async def pulse(self) -> None:
        """Send a laser pulse."""
        ...

    async def set_supply_voltage(self, voltage: float) -> None:
        """Set the capacitor bank voltage value.

        Args:
            voltage (float): The voltage, expressed in V.

        """
        ...

    def get_type(self) -> LaserPulserType:
        """Return the type of laser hardware connected to the platform."""
        return LaserPulserType.NONE


class AsyncLaserPulser:
    """Async driver for the laser pulser board."""

    def __init__(self, safe_pulse_duration: float) -> None:
        """Create an Async driver for the laser pulser board."""
        self._laser_pulser: LaserPulser | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._safe_pulse_duration = safe_pulse_duration

    async def setup(self) -> None:
        """Configure the laser pulser board."""
        self._laser_pulser = LaserPulser(safe_pulse_duration=self._safe_pulse_duration)
        self._loop = asyncio.get_running_loop()

        await self.set_driver_en(False)
        await self.set_power(False)

    async def set_power(self, en: bool) -> None:
        """Set the value of the POWER_EN signal."""
        if self._laser_pulser is None or self._loop is None:
            raise LaserPulserError("Setup has failed")

        self._loop.run_in_executor(None, self._laser_pulser.set_power, en)

    async def set_driver_en(self, en: bool) -> None:
        """Enable or disable the switch driver."""
        if self._laser_pulser is None or self._loop is None:
            raise LaserPulserError("Setup has failed")

        await self._loop.run_in_executor(None, self._laser_pulser.set_driver_en, en)

    async def pulse(self) -> None:
        """Send a laser pulse."""
        if self._laser_pulser is None or self._loop is None:
            raise LaserPulserError("Setup has failed")

        await self._loop.run_in_executor(None, self._laser_pulser.pulse)

    async def set_supply_voltage(self, voltage: float) -> None:
        """Set the capacitor bank voltage value.

        Args:
            voltage (float): The voltage, expressed in V.

        """
        if self._laser_pulser is None or self._loop is None:
            raise LaserPulserError("Setup has failed")

        await self._loop.run_in_executor(
            None, self._laser_pulser.set_supply_voltage, voltage
        )

    def get_type(self) -> LaserPulserType:
        """Return the type of laser hardware connected to the platform."""
        if self._laser_pulser is None or self._loop is None:
            raise LaserPulserError("Setup has failed")

        if self._laser_pulser.is_safe_board:
            return LaserPulserType.LOW_POWER

        return LaserPulserType.HIGH_POWER
