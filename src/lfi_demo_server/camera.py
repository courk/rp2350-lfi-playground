#!/usr/bin/python3
"""Interface to the Camera."""
import asyncio
import io
from typing import AsyncGenerator

try:
    from picamera2 import MappedArray, Picamera2
    from picamera2.encoders import MJPEGEncoder, Quality
    from picamera2.outputs import FileOutput
except ModuleNotFoundError:
    print("Cannot load picamera")

from .camera_process import FrameProcessor
from .config import CameraConfig

_LOCK = asyncio.Lock()  # Used to make sure only one Camera instance is used


class _EncodedFrameBuffer(io.BufferedIOBase):
    """Simple buffer storing encoded binary frames."""

    def __init__(self, maxsize: int = 0):
        super().__init__()
        self._frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize)

    def write(self, frame: bytes) -> int:  # type: ignore[override]
        try:
            self._frames.put_nowait(frame)
        except asyncio.QueueFull:
            pass  # Drop samples if needed
        return len(frame)

    async def get_frames(self) -> AsyncGenerator[bytes, None]:
        while True:
            frame = await self._frames.get()
            yield frame


class Camera:
    """Interface to the camera."""

    def __init__(self, config: CameraConfig) -> None:
        """Create a camera interface.

        Args:
            config (CameraConfig): The camera configuration

        """
        self._config = config

        try:
            self._encoder = MJPEGEncoder()
        except NameError:
            pass  # Dirty, but allow quick tests from a x86 machine ...

        self._frame_buffer = _EncodedFrameBuffer(maxsize=config.n_buffered_samples)

        self._frame_processor = FrameProcessor(
            frame_size=config.resolution[::-1],
            n_averaging_frames=config.n_averaging_samples,
            normalization_alpha=config.normalization_alpha,
            scale_image_file=config.scale_image,
        )

    async def get_camera_frames(self) -> AsyncGenerator[bytes, None]:
        """Get raw frames from the camera."""
        async with _LOCK:
            with Picamera2(tuning=str(self._config.tuning_file.resolve())) as cam:
                cam.configure(
                    cam.create_video_configuration(
                        main={"size": self._config.resolution, "format": "RGB888"},
                        controls={
                            "AnalogueGain": self._config.analog_gain,
                            "AwbEnable": False,
                            "ColourGains": self._config.color_gains,
                            "Contrast": self._config.contrast,
                            "ExposureTime": int(self._config.exposure_time * 1e6),
                            "Sharpness": self._config.sharpness,
                            "FrameDurationLimits": (
                                int(1e6 / self._config.sps),
                                int(1e6 / self._config.sps),
                            ),
                        },
                    )
                )

                def frame_processor_callback(request) -> None:
                    with MappedArray(request, "main") as m:
                        self._frame_processor.process(m.array)

                cam.pre_callback = frame_processor_callback

                cam.start_recording(
                    self._encoder, FileOutput(self._frame_buffer), quality=Quality.HIGH
                )

                async for frame in self._frame_buffer.get_frames():
                    yield frame

    def set_filter_en(self, en: bool) -> None:
        """Enable or disable image filtering.

        Args:
            en (bool): True to enable filtering, False otherwise

        """
        self._frame_processor.set_filter_en(en)

    def get_filter_en(self) -> bool:
        """Return whether images are being filtered."""
        return self._frame_processor.get_filter_en()
