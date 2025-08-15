#!/usr/bin/env python3
"""Driver for the SX1509 I/O Expander."""
import asyncio
from dataclasses import dataclass
from enum import IntEnum

import gpiod
from gpiod.line import Direction, Value
from smbus2_asyncio import SMBus2Asyncio

from .hw_def import I2cAddr, RpiIo, Sx1509Io


class Sx1509Error(Exception):
    """Raised in case of an SX1509 error."""

    pass


class Sx1509Register(IntEnum):
    """Partial enum of the SX1509 registers."""

    INPUT_DISABLE_B = 0x00
    INPUT_DISABLE_A = 0x01
    PULL_UP_B = 0x06
    PULL_UP_A = 0x07
    PULL_DOWN_B = 0x08
    PULL_DOWN_A = 0x09
    OPEN_DRAIN_B = 0x0A
    OPEN_DRAIN_A = 0x0B
    DIR_B = 0x0E
    DIR_A = 0x0F
    DATA_B = 0x10
    DATA_A = 0x11
    CLOCK = 0x1E
    MISC = 0x1F
    LED_DRIVER_EN_B = 0x20
    LED_DRIVER_EN_A = 0x21
    REG_I_ON_0 = 0x2A
    REG_I_ON_1 = 0x2D
    REG_I_ON_2 = 0x30
    REG_I_ON_3 = 0x33
    REG_I_ON_4 = 0x36
    REG_I_ON_5 = 0x3B
    REG_I_ON_6 = 0x40
    REG_I_ON_7 = 0x45
    REG_I_ON_8 = 0x4A
    REG_I_ON_9 = 0x4D
    REG_I_ON_10 = 0x50
    REG_I_ON_11 = 0x53
    REG_I_ON_12 = 0x56
    REG_I_ON_13 = 0x5B
    REG_I_ON_14 = 0x60
    REG_I_ON_15 = 0x65

    @staticmethod
    def reg_i_on(io: Sx1509Io) -> "Sx1509Register":
        """Get the address of the reg_t_on register for the given I/O."""
        regs = [
            Sx1509Register.REG_I_ON_0,
            Sx1509Register.REG_I_ON_1,
            Sx1509Register.REG_I_ON_2,
            Sx1509Register.REG_I_ON_3,
            Sx1509Register.REG_I_ON_4,
            Sx1509Register.REG_I_ON_5,
            Sx1509Register.REG_I_ON_6,
            Sx1509Register.REG_I_ON_7,
            Sx1509Register.REG_I_ON_8,
            Sx1509Register.REG_I_ON_9,
            Sx1509Register.REG_I_ON_10,
            Sx1509Register.REG_I_ON_11,
            Sx1509Register.REG_I_ON_12,
            Sx1509Register.REG_I_ON_13,
            Sx1509Register.REG_I_ON_14,
            Sx1509Register.REG_I_ON_15,
        ]
        return regs[io.value]


@dataclass
class Sx1509IoConfiguration:
    """I/O configuration."""

    oe: bool
    od: bool = False
    pu: bool = False
    pd: bool = False
    led: bool = False


class Sx1509:
    """Driver for the SX1509 I/O Expander."""

    def __init__(self, i2c_bus_handler: SMBus2Asyncio):
        """Create a SX1509 Driver."""
        self._i2c_bus_handler = i2c_bus_handler
        self._output_cache = 0

    async def reset(self) -> None:
        """Reset the SX1509."""
        with gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="sx1509",
            config={
                RpiIo.SX1509_NRESET: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.INACTIVE
                )
            },
        ) as request:
            await asyncio.sleep(0.1)
            request.set_value(RpiIo.SX1509_NRESET, Value.ACTIVE)
            await asyncio.sleep(0.1)

    async def setup(self) -> None:
        """Initialize the SX1509 Driver."""
        await self.reset()

        # Use internal 2MHz oscillator
        await self._set_reg(reg=Sx1509Register.CLOCK, value=0b10 << 5)

        # Enable PWM engine
        await self._set_reg(reg=Sx1509Register.MISC, value=0b111 << 4)

    async def _set_reg(self, reg: Sx1509Register, value: int) -> None:
        """Set the value of a given register.

        Args:
            reg (Sx1509Register): The register
            value (int): The value

        """
        await self._i2c_bus_handler.write_byte_data(
            i2c_addr=I2cAddr.SX1509, register=reg.value, value=value
        )

    async def _set_reg_bit(self, reg: Sx1509Register, bit_index: int) -> None:
        """Set a given bit of the given register.

        Args:
            reg (Sx1509Register): The register
            bit_index (int): The bit

        """
        assert bit_index < 8
        reg_value = await self._i2c_bus_handler.read_byte_data(
            i2c_addr=I2cAddr.SX1509, register=reg.value
        )
        reg_value |= 1 << bit_index
        await self._i2c_bus_handler.write_byte_data(
            i2c_addr=I2cAddr.SX1509, register=reg.value, value=reg_value
        )

    async def _clear_reg_bit(self, reg: Sx1509Register, bit_index: int) -> None:
        """Clear a given bit of the given register.

        Args:
            reg (Sx1509Register): The register
            bit_index (int): The bit

        """
        assert bit_index < 8
        reg_value = await self._i2c_bus_handler.read_byte_data(
            i2c_addr=I2cAddr.SX1509, register=reg.value
        )
        reg_value &= ~(1 << bit_index)
        await self._i2c_bus_handler.write_byte_data(
            i2c_addr=I2cAddr.SX1509, register=reg.value, value=reg_value
        )

    async def set(self, io: Sx1509Io, value: bool) -> None:
        """Set the output value of the give I/O.

        Args:
            io (Sx1509Io): The I/O
            value (bool): The output level

        """
        if io.value & (1 << 3):
            output_reg = Sx1509Register.DATA_B
            cache_offset = 8
        else:
            output_reg = Sx1509Register.DATA_A
            cache_offset = 0

        if value:
            self._output_cache |= 1 << (cache_offset + (io.value & 0b111))
        else:
            self._output_cache &= ~(1 << (cache_offset + (io.value & 0b111)))

        await self._set_reg(
            reg=output_reg, value=(self._output_cache >> cache_offset) & 0xFF
        )

    async def set_pwm(self, io: Sx1509Io, value: float) -> None:
        """Set the duty cycle of a PWM-enabled I/O.

        Args:
            io (Sx1509Io): The I/O
            value (float): The duty cycle, expected to be between 0.0 and 1.0

        """
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Invalid duty cycle: {value}")

        raw_value = int(0xFF * (1.0 - value))

        await self._set_reg(reg=Sx1509Register.reg_i_on(io), value=raw_value)

    async def configure(
        self, io: Sx1509Io, configuration: Sx1509IoConfiguration
    ) -> None:
        if io.value & (1 << 3):
            dir_reg = Sx1509Register.DIR_B
            od_reg = Sx1509Register.OPEN_DRAIN_B
            pd_reg = Sx1509Register.PULL_DOWN_B
            pu_reg = Sx1509Register.PULL_UP_B
            led_reg = Sx1509Register.LED_DRIVER_EN_B
            input_dis_reg = Sx1509Register.INPUT_DISABLE_B
        else:
            dir_reg = Sx1509Register.DIR_A
            od_reg = Sx1509Register.OPEN_DRAIN_A
            pd_reg = Sx1509Register.PULL_DOWN_A
            pu_reg = Sx1509Register.PULL_UP_A
            led_reg = Sx1509Register.LED_DRIVER_EN_A
            input_dis_reg = Sx1509Register.INPUT_DISABLE_A

        if configuration.oe:
            await self._clear_reg_bit(dir_reg, io.value & 0b111)
        else:
            await self._set_reg_bit(dir_reg, io.value & 0b111)

        if configuration.od:
            await self._set_reg_bit(od_reg, io.value & 0b111)
        else:
            await self._clear_reg_bit(od_reg, io.value & 0b111)

        if configuration.pd:
            await self._set_reg_bit(pd_reg, io.value & 0b111)
        else:
            await self._clear_reg_bit(pd_reg, io.value & 0b111)

        if configuration.pu:
            await self._set_reg_bit(pu_reg, io.value & 0b111)
        else:
            await self._clear_reg_bit(pu_reg, io.value & 0b111)

        if configuration.led:
            await self._set_reg_bit(input_dis_reg, io.value & 0b111)
            await self._set_reg_bit(led_reg, io.value & 0b111)
            await self.set(io, False)
        else:
            await self._clear_reg_bit(led_reg, io.value & 0b111)
            await self._clear_reg_bit(input_dis_reg, io.value & 0b111)
