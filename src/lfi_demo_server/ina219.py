#!/usr/bin/env python3
"""Driver for the INA219 Sensor."""
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from smbus2_asyncio import SMBus2Asyncio

from .hw_def import SENSING_RESITOR_VALUE, I2cAddr


class Ina219Register(IntEnum):
    """Enum of the INA219 registers."""

    CONFIGURATION = 0x00
    SHUNT_VOLTAGE = 0x01
    BUS_VOLTAGE = 0x02
    POWER = 0x03
    CURRENT = 0x04
    CALIBRATION = 0x05


@dataclass
class Ina219Readings:
    """Readings from the INA219, all fields are S.I. units."""

    shunt_voltage: float
    bus_voltage: float
    power: Optional[float]
    current: Optional[float]
    overflow: bool = False


class Ina219:
    """Driver for the INA219 Sensor."""

    SHUNT_VOLTAGE_LSB = 10e-6  # A
    BUS_VOLTAGE_LSB = 4e-3  # V

    def __init__(
        self, i2c_bus_handler: SMBus2Asyncio, max_expected_current: float = 250e-3
    ):
        """Create an INA219 driver.

        Args:
            i2c_bus_handler (SMBus2Asyncio): The I2C bus the sensor is on
            max_expected_current (float, optional): The maximum expected current, expressed in Amps. Defaults to 250 mA.

        """
        self._i2c_bus_handler = i2c_bus_handler

        self._current_lsb = max_expected_current / (2**15)
        self._power_lsb = 20 * self._current_lsb
        self._calibration_reg_value = int(
            0.04096 / (self._current_lsb * SENSING_RESITOR_VALUE)
        )

    async def _write_reg(self, reg: Ina219Register, value: int) -> None:
        """Write a INA219 register."""
        await self._i2c_bus_handler.write_i2c_block_data(
            i2c_addr=I2cAddr.INA219,
            register=reg.value,
            data=bytes([(value >> 8) & 0xFF, value & 0xFF]),
        )

    async def setup(self) -> None:
        """Initialize the INA219 Driver."""
        await self._write_reg(Ina219Register.CONFIGURATION, (1 << 15))  # Software reset

        # Configuration:
        #     - 16V FSR
        #     - gain /2
        #     - 12-bit resolution
        #     - Shunt and bus, continuous measurements
        await self._write_reg(
            Ina219Register.CONFIGURATION,
            (1 << 11) | (0b1000 << 7) | (0b1000 < 3) | 0b111,
        )

        await self._write_reg(Ina219Register.CALIBRATION, self._calibration_reg_value)

    async def read(self) -> Ina219Readings:
        """Read data from the INA219.

        Returns:
            Ina219Readings: The data

        """
        raw_data = b""
        for reg in range(4):
            raw_chunk = await self._i2c_bus_handler.read_i2c_block_data(
                i2c_addr=I2cAddr.INA219,
                register=Ina219Register.SHUNT_VOLTAGE + reg,
                length=2,
            )
            raw_data += bytes(raw_chunk)

        raw_shunt_voltage, raw_bus_voltage, raw_power, raw_current = struct.unpack(
            ">hHHh", raw_data
        )

        shunt_voltage = raw_shunt_voltage * self.SHUNT_VOLTAGE_LSB
        bus_voltage = (raw_bus_voltage >> 3) * self.BUS_VOLTAGE_LSB

        if raw_bus_voltage & (1 << 0):
            # Overflow has been detected, power and current readings are meaningless
            return Ina219Readings(
                shunt_voltage=shunt_voltage,
                bus_voltage=bus_voltage,
                current=None,
                power=None,
                overflow=True,
            )

        power = raw_power * self._power_lsb
        current = raw_current * self._current_lsb

        return Ina219Readings(
            shunt_voltage=shunt_voltage,
            bus_voltage=bus_voltage,
            current=current,
            power=power,
        )
