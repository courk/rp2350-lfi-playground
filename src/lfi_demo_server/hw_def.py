#!/usr/bin/env python3
"""Hardware definitions."""
from enum import IntEnum

I2C_BUS_INDEX = 1

SENSING_RESITOR_VALUE = 300e-3  # Ohms


class I2cAddr(IntEnum):
    """Address of the I2C peripherals."""

    SX1509 = 0x3E
    INA219 = 0x40


class RpiIo(IntEnum):
    """I/Os connected to the RPI."""

    SX1509_NRESET = 4


class Sx1509Io(IntEnum):
    """I/Os connected to the SX1509 GPIO expander."""

    DRV0 = 0
    DRV1 = 1
    DRV2 = 2
    DRV3 = 3
    DRV4 = 4
    DRV5 = 5
    DRV6 = 6
    DRV7 = 7
    DUT_PWR_EN = 8
    DUT_RUN = 9
    DUT_BOOTSEL = 10
    CC_DIM = 11

    @staticmethod
    def get_illumination_ring_io(index: int) -> "Sx1509Io":
        """Get the I/O corresponding to the corresponding illumination ring LED."""
        if index not in range(8):
            raise ValueError(f"Invalid LED index: {index}")
        return Sx1509Io(Sx1509Io.DRV0.value + index)
