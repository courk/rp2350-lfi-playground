#!/usr/bin/env python3
"""LFI Platform Demo Supervisor Tool."""

import asyncio
import enum
import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.logging import RichHandler

from lfi_demo_server import DemoSupervisor, generate_server_app
from lfi_demo_server.config import load_config

app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)


class SupervisorRunnerMode(str, enum.Enum):
    """How to run the supervisor."""

    CLI = "cli"
    SERVER = "server"


@app.command()
def main(
    config_filename: Annotated[
        Path, typer.Option(help="Configuration file of the supervisor")
    ] = Path("supervisor_config.toml"),
    runner_mode: Annotated[
        SupervisorRunnerMode, typer.Option(help="How to run the supervisor")
    ] = SupervisorRunnerMode.SERVER,
) -> None:
    """Launch the Demo Supervisor."""
    logging.info(
        f'Starting Demo Supervisor in {runner_mode.name} mode with configuration "{config_filename}"'
    )

    config = load_config(config_filename)

    supervisor = DemoSupervisor(config=config)

    if runner_mode == SupervisorRunnerMode.SERVER:
        server_app = generate_server_app(supervisor=supervisor, config=config)
        uvicorn.run(
            server_app,
            host=config.server.host,
            port=config.server.port,
            log_config=None,
        )
        return

    async def _display_logs(supervisor: DemoSupervisor) -> None:
        while True:
            async for msg in supervisor.get_logs():
                logging.log(level=msg.level.value, msg=msg.message)

    async def _display_current(supervisor: DemoSupervisor) -> None:
        while True:
            async for readings in supervisor.get_current_readings():
                if readings.current is not None:
                    logging.info(f"Current = {readings.current * 1e3:0.1f} mA")

    async def _display_serial(supervisor: DemoSupervisor) -> None:
        while True:
            async for raw_data in supervisor.get_serial_data():
                data = raw_data.decode(errors="replace").strip()
                logging.info(f"Serial output = {data}")

    async def _coro() -> None:
        async with supervisor:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_display_logs(supervisor))
                tg.create_task(_display_current(supervisor))
                tg.create_task(_display_serial(supervisor))
                await supervisor.run()

    asyncio.run(_coro())


if __name__ == "__main__":
    app()
