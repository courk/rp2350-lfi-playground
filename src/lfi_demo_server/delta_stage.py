#!/usr/bin/env python3
"""Delta Stage support with the SangaBoard, adapted from openflexure-microscope-server."""
import asyncio
import logging
import time
from typing import Protocol, Tuple, TypeVar

import numpy as np

from .sangaboard import Sangaboard, extensible_serial_instrument

PositionT = TypeVar(
    "PositionT",
    bound=Tuple[int, int, int] | extensible_serial_instrument.QueriedProperty,
)


class _SangaBoardProtocol(Protocol[PositionT]):

    position: PositionT

    def move_abs(self, final: Tuple[int, int, int]) -> None: ...
    def zero_position(self) -> None: ...
    def release_motors(self) -> None: ...


class _DummySangaBoard:

    position = (0, 0, 0)

    def move_abs(self, final: Tuple[int, int, int]) -> None:
        logging.info(f"Raw stage coordinates: {final}")
        time.sleep(1.0)  # This call is blocking while the motors are moving
        self.position = final

    def zero_position(self) -> None:
        self.position = (0, 0, 0)

    def release_motors(self) -> None:
        logging.info("Released motors")


class _BlockingDeltaStage:
    """Blocking Delta Stage Driver."""

    def __init__(
        self,
        flex_h: int = 80,
        flex_a: int = 50,
        flex_b: int = 50,
        camera_angle: float = 0,
        dummy: bool = False,
    ):
        self._board: _SangaBoardProtocol
        if not dummy:
            self._board = Sangaboard()
        else:
            self._board = _DummySangaBoard()

        # Set up camera rotation relative to stage
        camera_theta: float = (camera_angle / 180) * np.pi
        self._r_camera: np.ndarray = np.array(
            [
                [np.cos(camera_theta), -np.sin(camera_theta), 0],
                [np.sin(camera_theta), np.cos(camera_theta), 0],
                [0, 0, 1],
            ]
        )

        # Transformation matrix converting delta into cartesian
        x_fac: float = -1 * np.multiply(
            np.divide(2, np.sqrt(3)), np.divide(flex_b, flex_h)
        )
        y_fac: float = -1 * np.divide(flex_b, flex_h)
        z_fac: float = np.multiply(np.divide(1, 3), np.divide(flex_b, flex_a))

        self._tvd: np.ndarray = np.array(
            [
                [-x_fac, x_fac, 0],
                [0.5 * y_fac, 0.5 * y_fac, -y_fac],
                [z_fac, z_fac, z_fac],
            ]
        )

        self._tdv: np.ndarray = np.linalg.inv(self._tvd)

    def get_position(self) -> Tuple[int, int, int]:
        """Get the position of the Delta Stage.

        Returns:
            Tuple[int, int, int]: The X, Y and Z coordinates

        """
        raw_position = self._board.position

        camera_coordinates: np.ndarray = np.dot(self._tvd, raw_position)

        delta_coordinates: np.ndarray = np.round(
            np.dot(np.linalg.inv(self._r_camera), camera_coordinates)
        )

        return tuple(int(n) for n in delta_coordinates)  # type: ignore[return-value]

    def set_position(self, coordinates: Tuple[int, int, int]) -> None:
        """Set the position of the Delta Stage.

        Args:
            coordinates (Tuple[int, int, int]): The X, Y and Z coordinates

        """
        camera_coordinates: np.ndarray = np.dot(self._r_camera, coordinates)

        final_coordinates: np.ndarray = np.round(np.dot(self._tdv, camera_coordinates))

        self._board.move_abs(tuple(int(n) for n in final_coordinates))  # type: ignore[arg-type]

    def zero_positions(self) -> None:
        """Set the current position to zero."""
        self._board.zero_position()

    def release_motors(self) -> None:
        """De-energise the stepper motor coils."""
        self._board.release_motors()


class DeltaStageError(Exception):
    """Raised in case of an error with the Delta Stage driver."""

    pass


class DeltaStage:
    """Driver for the Delta Stage."""

    def __init__(self, dummy: bool = False) -> None:
        """Create a driver for the Delta Stage.

        Args:
            dummy (bool, optional): Mock hardware. Defaults to False.

        """
        self._lock = asyncio.Lock()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._stage: _BlockingDeltaStage | None = None

        self._dummy = dummy

    async def setup(self) -> None:
        """Configure the Delta State driver."""
        self._stage = _BlockingDeltaStage(dummy=self._dummy)
        self._loop = asyncio.get_running_loop()

    async def set_position(self, coordinates: Tuple[int, int, int]) -> None:
        """Set the position of the Delta Stage.

        Args:
            coordinates (Tuple[int, int, int]): The X, Y and Z coordinates

        """
        if self._stage is None or self._loop is None:
            raise DeltaStageError("Setup has failed")

        async with self._lock:
            await self._loop.run_in_executor(
                None, self._stage.set_position, coordinates
            )

    async def get_position(self) -> Tuple[int, int, int]:
        """Get the position of the Delta Stage. May block if the stage is moving.

        Returns:
            Tuple[int, int, int]: The X, Y and Z coordinates

        """
        if self._stage is None or self._loop is None:
            raise DeltaStageError("Setup has failed")

        async with self._lock:
            ret = await self._loop.run_in_executor(None, self._stage.get_position)

        return ret

    async def zero_position(self) -> None:
        """Set the current position to zero."""
        if self._stage is None or self._loop is None:
            raise DeltaStageError("Setup has failed")

        async with self._lock:
            await self._loop.run_in_executor(None, self._stage.zero_positions)

    async def release_motors(self) -> None:
        """De-energise the stepper motor coils."""
        if self._stage is None or self._loop is None:
            raise DeltaStageError("Setup has failed")

        async with self._lock:
            await self._loop.run_in_executor(None, self._stage.release_motors)
