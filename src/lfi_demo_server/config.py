#!/usr/bin/env python3
"""Configuration data."""
from pathlib import Path
from typing import List, Pattern, Self, Tuple

import tomli
from pydantic import (
    BaseModel,
    Field,
    FilePath,
    PositiveFloat,
    PositiveInt,
    model_validator,
)


class CameraConfig(BaseModel):
    """Store camera-related configuration parameters."""

    resolution: Tuple[PositiveInt, PositiveInt]
    sps: int = Field(gt=0)  # SPS

    analog_gain: float = Field(ge=1.0, le=16.0)
    contrast: float = Field(ge=0.0, le=32.0)
    sharpness: float = Field(ge=0.0, le=16.0)
    exposure_time: float = Field(gt=0.0)  # s
    color_gains: List[PositiveFloat]

    n_buffered_samples: PositiveInt

    n_averaging_samples: PositiveInt
    normalization_alpha: float = Field(gt=0.0, lt=1.0)

    tuning_file: FilePath

    scale_image: FilePath | None = None

    @model_validator(mode="after")
    def check_exposure_and_sps(self) -> Self:
        if 1 / self.sps < self.exposure_time:
            raise ValueError("Camera SPS too fast for the exposure time")
        return self


class StageConfig(BaseModel):
    """Store configuration related to the delta stage."""

    x_steps: List[PositiveInt]  # Possible steps for the X axis
    y_steps: List[PositiveInt]  # Possible steps for the Y axis
    z_steps: List[PositiveInt]  # Possible steps for the Z axis

    default_x_step: PositiveInt  # Default step for the X axis
    default_y_step: PositiveInt  # Default step for the Y axis
    default_z_step: PositiveInt  # Default step for the Z axis

    x_limits: Tuple[int, int]  # X axis endstops definition
    y_limits: Tuple[int, int]  # Y axis endstops definition
    z_limits: Tuple[int, int]  # Z axis endstops definition

    autolock_timeout: PositiveFloat  # Seconds - Idle time to wait before automatically locking the stage


class DevConfig(BaseModel):
    """Store dev-related configuration parameters."""

    admin_mode: bool = False
    use_dummy_delta_stage: bool = False
    use_dummy_lfi_board: bool = False
    skip_firmware_flash: bool = False
    force_dummy_laser_pulser: bool = False


class TargetFirmwareConfig(BaseModel):
    """Store firmware-related configuration parameters."""

    image: FilePath  # Target firmware image
    flash_retries: int = Field(ge=1)  # Number of firmware flash attempts


class CurrentMonitoringConfig(BaseModel):
    """Store parameters related to current monitoring."""

    limit: float = Field(gt=0.0)  # mA - Target current limit
    rate: float = Field(gt=0.0)  # SPS - Number of current readings per second


class TimingConfig(BaseModel):
    """Store timing-related parameters."""

    reset_cooldown: float = Field(
        gt=0.0
    )  # s - How long to keep the target off during a power cycle
    serial_timeout: float = Field(gt=0.0)  # s - Serial new data timeout
    serial_open_cooldown: (
        float  # s - How long to wait between each Serial interface open attempt
    ) = Field(gt=0.0)


class SerialHardwareConfig(BaseModel):
    """Store parameters related to the serial interface.."""

    name: str
    open_retries: int = Field(ge=1)  # Number of serial interface open attempt


class SerialDataConfig(BaseModel):
    """Store parameters related to serial data monitoring."""

    no_success_regex: (
        Pattern  # Pattern of the serial output when not glitch is detected
    )
    success_regex: (
        Pattern  # Pattern of the serial output when a successful glitch is detected
    )


class IlluminationConfig(BaseModel):
    """Store illumination-related parameters."""

    default_power: float = Field(ge=0.0, le=1.0)


class LaserConfig(BaseModel):
    """Store laser-related parameters."""

    default_power: float = Field(ge=0.0, le=1.0)
    min_voltage: float = Field(gt=0.0)  # V - Min voltage of the laser pulser
    max_voltage: float = Field(gt=0.0)  # V - Max voltage of the laser pulser
    pulse_rate_limit: float = Field(
        gt=0.0
    )  # pulses/s - Max number of laser pulses per second
    safe_pulse_duration: (
        PositiveFloat  # Seconds - Pulse duration of the Laser-Pulser-Board red LD
    )


class ServerConfig(BaseModel):
    """Store server-related parameters."""

    host: str = Field(pattern=r"^\d+\.\d+\.\d+\.\d+$")
    port: int = Field(ge=1, le=0xFFFF)

    n_current_samples: int = Field(ge=1)  # Number of current readings to plot

    target_source_code: FilePath

    enable_audio: bool


class ResetConfig(BaseModel):
    """Store parameters related to the way the target is reset."""

    illumination_warning_count_threshold: PositiveInt
    target_disable_count_threshold: PositiveInt


class DemoConfig(BaseModel):
    """Configuration of the entire Demo system."""

    target_firmware: TargetFirmwareConfig
    current_monitoring: CurrentMonitoringConfig
    timing: TimingConfig
    reset: ResetConfig
    serial_hardware: SerialHardwareConfig
    serial_data: SerialDataConfig
    illumination: IlluminationConfig
    laser: LaserConfig
    server: ServerConfig
    stage: StageConfig
    camera: CameraConfig
    dev: DevConfig = DevConfig()


def load_config(file: Path) -> DemoConfig:
    """Load a DemoConfig from a TOML file.

    Args:
        file (Path): The configuration file

    Returns:
        DemoConfig: The loaded configuration

    """
    config_data = tomli.load(file.open("rb"))

    return DemoConfig(**config_data)
