#!/usr/bin/python3
"""Real-time image processing algorithm."""
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np


class FrameRingBuffer:
    """Ring buffer storing the latest captured grayscale frames."""

    def __init__(self, frame_size: Tuple[int, int], depth: int) -> None:
        """Create a ring buffer.

        Args:
            frame_size (Tuple[int, int]): The size of the captured frames
            depth (int): The depth of the buffer

        """
        super().__init__()

        self._mem = np.zeros(shape=(depth, *frame_size), dtype=np.uint8)
        self._index = 0
        self._depth = depth

    def push(self, frame: np.ndarray) -> None:
        """Push a new grayscale frame to the buffer.

        Args:
            frame (np.ndarray): The grayscale frame

        """
        self._mem[self._index, :, :] = frame
        self._index = (self._index + 1) % self._depth

    def __len__(self) -> int:
        return self._depth

    def __getitem__(self, i: int) -> np.ndarray:
        target_index = (self._index - self._depth + i) % self._depth
        return self._mem[target_index]


class FrameAveragingFilter:
    """Implement a Frame Averaging filter."""

    def __init__(self, frame_size: Tuple[int, int], n_frames: int) -> None:
        """Create a simple moving average filter for grayscale frames.

        Args:
            frame_size (Tuple[int, int]): The size of each frame
            n_frames (int): The number of frames to average

        """
        self._buffer = FrameRingBuffer(frame_size=frame_size, depth=n_frames)
        self._sum = np.zeros(shape=frame_size, dtype=np.float32)
        self._freshsum = np.zeros_like(self._sum)
        self._n_frames = n_frames
        self._count = 0

    def process(self, frame: np.ndarray) -> None:
        """Process in-place the provided frame.

        Args:
            frame (np.ndarray): The frame

        """
        self._buffer.push(frame)

        self._sum -= self._buffer[0]
        self._sum += frame
        self._freshsum += frame

        self._count += 1

        if self._count == self._n_frames:
            self._sum = self._freshsum
            self._freshsum = np.zeros_like(self._sum)
            self._count = 0

        frame[...] = (self._sum / self._n_frames).astype(dtype=np.uint8)


class FrameNormalisingFilter:
    """Implement a Frame Normalizing filter."""

    def __init__(self, frame_size: Tuple[int, int], alpha: float) -> None:
        """Create a Frame Normalizing filter for grayscale frames.

        Args:
            frame_size (Tuple[int, int]): The size of each frame
            alpha (float): The filter's time constant

        """
        self._max = 0xFF
        self._min = 0
        self._alpha = alpha
        self._output = np.zeros(shape=frame_size, dtype=np.int16)

    def process(self, frame: np.ndarray) -> None:
        """Process in-place the provided frame.

        Args:
            frame (np.ndarray): The frame

        """
        frame_max = frame.max()
        frame_min = frame.min()

        self._max = (1 - self._alpha) * frame_max + self._alpha * self._max
        self._min = (1 - self._alpha) * frame_min + self._alpha * self._min

        self._output[...] = (frame - self._min) / (self._max - self._min) * 0xFF

        np.clip(self._output, a_min=0, a_max=0xFF, out=self._output)

        frame[...] = self._output.astype(dtype=np.uint8)


class FrameProcessor:
    """Implement the Frame Processor algorithm."""

    def __init__(
        self,
        frame_size: Tuple[int, int],
        n_averaging_frames: int,
        normalization_alpha: float,
        scale_image_file: Path | None = None,
    ) -> None:
        """Create a Frame Processor.

        Args:
            frame_size (Tuple[int, int]): The size of each frame
            n_averaging_frames (int): The number of frames to average
            normalization_alpha (float): The normalization filter's time constant
            scale_image_file (Path | None, optional): Image of the scale indicator. Defaults to None.

        """
        self._averaging_filter = FrameAveragingFilter(
            frame_size=frame_size, n_frames=n_averaging_frames
        )
        self._normalizing_filter = FrameNormalisingFilter(
            frame_size=frame_size, alpha=normalization_alpha
        )
        self._output = np.zeros(shape=frame_size, dtype=np.uint8)

        self._scale_image: np.ndarray | None = None
        if scale_image_file is not None:
            self._scale_image = cv2.imread(str(scale_image_file))

        self._filtering_enabled = True

    def process(self, frame: np.ndarray) -> None:
        """Process in place an RGB frame.

        Args:
            frame (np.ndarray): The RGB frame to process

        """
        # Filter frame if needed
        if self._filtering_enabled:
            # Extract grayscale
            self._output[...] = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            # Filter
            self._averaging_filter.process(self._output)

            # Normalize
            self._normalizing_filter.process(self._output)

            # Convert back to RGB (needed to use hardware MJPEG encoding?)
            frame[...] = cv2.cvtColor(self._output, cv2.COLOR_GRAY2RGB)

        # Draw scale if needed
        if self._scale_image is not None:
            frame[: self._scale_image.shape[0] :, -self._scale_image.shape[1] :, :] = (
                self._scale_image
            )

    def set_filter_en(self, en: bool) -> None:
        """Enable or disable image filtering.

        Args:
            en (bool): True to enable filtering, False otherwise

        """
        self._filtering_enabled = en

    def get_filter_en(self) -> bool:
        """Return whether images are being filtered."""
        return self._filtering_enabled
