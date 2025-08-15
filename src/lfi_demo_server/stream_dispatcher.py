#!/usr/bin/env python3
"""Async data stream combiner and dispatcher."""
import asyncio
from typing import AsyncIterable, List, Set

from .demo_supervisor import DemoSupervisorEvent, DemoSupervisorLogMessage
from .ina219 import Ina219Readings

Sample = DemoSupervisorLogMessage | bytes | Ina219Readings | DemoSupervisorEvent
SampleIterable = (
    AsyncIterable[DemoSupervisorLogMessage]
    | AsyncIterable[bytes]
    | AsyncIterable[Ina219Readings]
    | AsyncIterable[DemoSupervisorEvent]
)


class StreamDispatcher:
    """Combine and dispatch the data from several generators on demand."""

    def __init__(self) -> None:
        """Create a stream dispatcher."""
        self._workers: List[asyncio.Task] = []
        self._output_queues: Set[asyncio.Queue[Sample]] = set()

    async def _worker(self, generator: SampleIterable) -> None:
        """Dispatch data to available clients."""
        async for item in generator:
            for queue in self._output_queues:
                queue.put_nowait(item)

    def register_generator(self, generator: SampleIterable) -> None:
        """Register a generator to dispatch."""
        worker = asyncio.create_task(self._worker(generator))
        self._workers.append(worker)

    async def get(self) -> AsyncIterable[Sample]:
        """Get the combined generator over all registered generators."""
        queue: asyncio.Queue[Sample] = asyncio.Queue()
        self._output_queues.add(queue)

        try:
            while True:
                item = await queue.get()
                yield item
        except GeneratorExit:
            self._output_queues.remove(queue)
