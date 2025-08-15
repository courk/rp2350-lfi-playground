#!/usr/bin/env python3
"""HTTP Interface to the demo supervisor."""
import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, AsyncGenerator

import jinja2
import psutil
import pygments
from fastapi import APIRouter, FastAPI, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pygments.formatters import HtmlFormatter
from pygments.lexers import CLexer

from .camera import Camera
from .config import DemoConfig
from .demo_supervisor import (
    DemoSupervisor,
    DemoSupervisorEvent,
    DemoSupervisorLogMessage,
)
from .ina219 import Ina219Readings
from .markdown_helper import markdown_to_html
from .stream_dispatcher import StreamDispatcher
from .system_utils import SystemUtilsError, get_cpu_temp, get_version_string

router = APIRouter()


class _LogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for route in ("/health_status", "/system_temp", " /system_load"):
            if route in record.getMessage():
                return False
        return True


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(_LogFilter())


@dataclass
class _AppContext:
    """Store a global context for the HTTP demo server."""

    config: DemoConfig
    supervisor: DemoSupervisor
    supervisor_task: asyncio.Task
    stream_dispatcher: StreamDispatcher
    templates: jinja2.Environment
    camera: Camera
    pulse_counter: int = 0
    success_counter: int = 0


_context: _AppContext | None = None


@router.get("/")
async def root() -> HTMLResponse:
    """Return the root content of the HTTP server."""
    assert _context is not None

    state = _context.supervisor.get_control_state()

    target_source_code = _context.config.server.target_source_code.read_text()
    highlighted_target_source_code = pygments.highlight(
        target_source_code,
        lexer=CLexer(),
        formatter=HtmlFormatter(
            noclasses=True,
            nobackground=True,
            style="github-dark",
        ),
    )

    template = _context.templates.get_template("index.html")
    return HTMLResponse(
        template.render(
            {
                "n_current_samples": _context.config.server.n_current_samples,
                "current_sampling_rate": _context.config.current_monitoring.rate,
                "laser_arm": state.laser_armed,
                "illumination_en": state.illumination_led_en,
                "laser_power": int(state.laser_power * 100.0),
                "illumination_power": int(state.illumination_led_power * 100.0),
                "target_en": state.target_en,
                "target_source_code": highlighted_target_source_code,
                "camera_enhance": _context.camera.get_filter_en(),
                "about_content": markdown_to_html(
                    Path("src/lfi_demo_server/assets/about.md")
                ),
                "laser_type": _context.supervisor.get_laser_type(),
                "admin_mode": _context.config.dev.admin_mode,
                "enable_audio": _context.config.server.enable_audio,
                "version_string": await get_version_string(),
            }
        )
    )


@router.get("/health_status")
async def health_status() -> HTMLResponse:
    """Return the HTML code showing the health status of the system."""
    assert _context is not None

    template = _context.templates.get_template("health.html")
    return HTMLResponse(
        template.render(
            {
                "healthy": _context.supervisor.is_healthy(),
            }
        )
    )


@router.get("/system_temp")
async def system_temp() -> HTMLResponse:
    """Return the HTML code showing the temperature of the system."""
    try:
        temp = await get_cpu_temp()
    except SystemUtilsError:
        return HTMLResponse("??°C")
    return HTMLResponse(f"{temp:02.0f}°C")


@router.get("/system_load")
async def system_load() -> HTMLResponse:
    """Return the HTML code showing the load of the system."""
    percent = int(psutil.cpu_percent())
    return HTMLResponse(f"{percent:02}%")


async def _gen_multipart_frames() -> AsyncGenerator[bytes, None]:
    """Format MJPEG frames for streaming."""
    assert _context is not None

    async for raw_frame in _context.camera.get_camera_frames():
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + raw_frame + b"\r\n")


@router.get("/stream")
async def stream() -> StreamingResponse:
    """Provide a real-time MJPEG video stream."""
    return StreamingResponse(
        _gen_multipart_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


class _StageCoordinatesForm(BaseModel):
    """Fields of the /stage/coordinates POST request."""

    x_coord: int
    y_coord: int
    z_coord: int


class _StageStepsForm(BaseModel):
    """Fields of the /stage/steps POST request."""

    x_step: int
    y_step: int
    z_step: int


@router.post("/stage/coordinates")
async def handle_stage_coordinates_form(
    form: Annotated[_StageCoordinatesForm, Form()],
) -> HTMLResponse:
    """Handle a set coordinates request."""
    assert _context is not None

    _context.supervisor.stage_target_coordinates_request(
        form.x_coord, form.y_coord, form.z_coord
    )

    return HTMLResponse()


@router.post("/stage/steps")
async def handle_stage_steps_form(
    form: Annotated[_StageStepsForm, Form()],
) -> HTMLResponse:
    """Handle a set steps request."""
    assert _context is not None

    _context.supervisor.set_stage_steps(
        x_step=form.x_step, y_step=form.y_step, z_step=form.z_step
    )

    return HTMLResponse()


@router.get("/stage")
async def get_stage_control_block() -> HTMLResponse:
    """Return the HTML corresponding to the Stage Control block."""
    assert _context is not None

    template = _context.templates.get_template("coordinates.html")

    state = _context.supervisor.get_control_state().stage

    return HTMLResponse(
        template.render(
            {
                "x_coord": f"{state.coordinates[0]:+06}",
                "y_coord": f"{state.coordinates[1]:+06}",
                "z_coord": f"{state.coordinates[2]:+06}",
                "x_step": state.x_step,
                "y_step": state.y_step,
                "z_step": state.z_step,
                "x_endstop": state.endstops[0],
                "y_endstop": state.endstops[1],
                "z_endstop": state.endstops[2],
                "x_steps": _context.config.stage.x_steps,
                "y_steps": _context.config.stage.y_steps,
                "z_steps": _context.config.stage.z_steps,
                "state": state.status.name.lower(),
                "admin_mode": _context.config.dev.admin_mode,
                "bypass_endstops": state.bypass_endstops,
            }
        )
    )


@router.get("/stage/{action}")
async def handle_stage_action(action: str, value: int | None = None) -> HTMLResponse:
    """Handle an action related to the delta stage."""
    assert _context is not None

    if action == "lock":
        await _context.supervisor.set_stage_lock(True)
    elif action == "unlock":
        await _context.supervisor.set_stage_lock(False)
    elif action in ("up", "down", "left", "right", "in", "out"):
        _context.supervisor.move_stage_request(direction=action)
    elif action == "reset_steps":
        _context.supervisor.set_stage_steps(
            x_step=_context.config.stage.default_x_step,
            y_step=_context.config.stage.default_y_step,
            z_step=_context.config.stage.default_z_step,
        )
    elif action == "bypass_endstops":
        _context.supervisor.set_bypass_endstops(value is not None)
    elif action == "zero_position":
        await _context.supervisor.zero_stage_position()
    elif action == "center":
        _context.supervisor.stage_target_coordinates_request(0, 0, 0)
    else:
        logging.error(f"Unhandled stage action: {action = }")
        return HTMLResponse(status_code=501)

    return HTMLResponse()


@router.get("/control/{target}")
async def control(target: str, value: int | None = None) -> HTMLResponse:
    """Apply the requested control."""
    assert _context is not None

    if target == "target_reset":
        _context.supervisor.request_target_reset()
    elif target == "target_en":
        await _context.supervisor.set_target_en(value is not None)
    elif target == "illumination_en":
        await _context.supervisor.set_illumination_led_en(value is not None)
    elif target == "illumination_power" and isinstance(value, int):
        await _context.supervisor.set_illumination_led_power(value / 100.0)
    elif target == "laser_arm":
        await _context.supervisor.set_laser_arm(value is not None)
    elif target == "pulse_laser":
        pulsed = await _context.supervisor.pulse_laser()
        if pulsed:
            _context.pulse_counter += 1
    elif target == "laser_power" and isinstance(value, int):
        await _context.supervisor.set_laser_power(value / 100.0)
    elif target == "camera_enhance":
        _context.camera.set_filter_en(value is not None)
    else:
        logging.error(f"Unhandled control request: {target = } {value = }")
        return HTMLResponse(status_code=501)

    return HTMLResponse()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle websockets connections."""
    assert _context is not None

    try:
        await websocket.accept()

        control_state = _context.supervisor.get_control_state()

        await websocket.send_json(
            {"action": "set_pulse_counter", "value": f"{_context.pulse_counter}"}
        )

        await websocket.send_json(
            {"action": "set_success_counter", "value": f"{_context.success_counter}"}
        )

        if control_state.laser_armed:
            await websocket.send_json({"action": "enable_pulse_button"})

        if control_state.target_en:
            await websocket.send_json({"action": "enable_reset_button"})

        if control_state.target_powered:
            await websocket.send_json({"action": "set_target_power_enabled"})

        if control_state.serial_connected:
            await websocket.send_json({"action": "set_serial_connected"})

        async for item in _context.stream_dispatcher.get():
            if isinstance(item, Ina219Readings):
                if item.current is not None:
                    await websocket.send_json({"current": item.current * 1e3})
            elif isinstance(item, bytes):
                await websocket.send_json({"serial": item.decode(errors="replace")})
            elif isinstance(item, DemoSupervisorLogMessage):
                await websocket.send_json(
                    {
                        "log": {
                            "level": item.level.name,
                            "message": item.message,
                            "date": item.date.strftime("%H:%M:%S"),
                        }
                    }
                )
            elif isinstance(item, DemoSupervisorEvent):
                if item == DemoSupervisorEvent.GLITCH_SUCCESS:
                    await websocket.send_json({"action": "success"})
                    _context.success_counter += 1
                    await websocket.send_json(
                        {
                            "action": "set_success_counter",
                            "value": f"{_context.success_counter}",
                        }
                    )
                elif item == DemoSupervisorEvent.PULSE:
                    await websocket.send_json({"action": "pulse"})
                    _context.pulse_counter += 1
                    await websocket.send_json(
                        {
                            "action": "set_pulse_counter",
                            "value": f"{_context.pulse_counter}",
                        }
                    )
                elif item == DemoSupervisorEvent.LASER_ARMED:
                    await websocket.send_json({"action": "enable_pulse_button"})
                elif item == DemoSupervisorEvent.LASER_DISARMED:
                    await websocket.send_json({"action": "disable_pulse_button"})
                elif item == DemoSupervisorEvent.TARGET_ENABLED:
                    await websocket.send_json({"action": "enable_reset_button"})
                elif item == DemoSupervisorEvent.TARGET_DISABLED:
                    await websocket.send_json({"action": "disable_reset_button"})
                    await websocket.send_json({"action": "set_target_en_toggle_off"})
                elif item == DemoSupervisorEvent.SERIAL_CONNECTED:
                    await websocket.send_json({"action": "set_serial_connected"})
                elif item == DemoSupervisorEvent.SERIAL_DISCONNECTED:
                    await websocket.send_json({"action": "set_serial_disconnected"})
                elif item == DemoSupervisorEvent.TARGET_POWER_ENABLED:
                    await websocket.send_json({"action": "set_target_power_enabled"})
                elif item == DemoSupervisorEvent.TARGET_POWER_DISABLED:
                    await websocket.send_json({"action": "set_target_power_disabled"})

                elif item in (
                    DemoSupervisorEvent.STAGE_LOCKED,
                    DemoSupervisorEvent.STAGE_IDLE,
                    DemoSupervisorEvent.STAGE_MOVING,
                    DemoSupervisorEvent.STAGE_STEPS_UPDATE,
                    DemoSupervisorEvent.STAGE_ZEROED,
                ):
                    await websocket.send_json({"action": "refresh_coordinates"})
                else:
                    logging.warning(f"Unhandled supervistor event: {item}")

    except WebSocketDisconnect:
        pass


def generate_server_app(supervisor: DemoSupervisor, config: DemoConfig) -> FastAPI:
    """Generate the main FastAPI server."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan handler of the server App."""
        global _context
        async with supervisor:
            dispatcher = StreamDispatcher()

            dispatcher.register_generator(supervisor.get_current_readings())
            dispatcher.register_generator(supervisor.get_serial_data())
            dispatcher.register_generator(supervisor.get_logs())
            dispatcher.register_generator(supervisor.get_events())

            _context = _AppContext(
                config=config,
                supervisor=supervisor,
                supervisor_task=asyncio.create_task(supervisor.run()),
                templates=jinja2.Environment(
                    loader=jinja2.FileSystemLoader(
                        "src/lfi_demo_server/assets/templates/"
                    )
                ),
                stream_dispatcher=dispatcher,
                camera=Camera(config=config.camera),
            )

            async def display_logs() -> None:
                async for item in dispatcher.get():
                    if isinstance(item, DemoSupervisorLogMessage):
                        logging.log(level=item.level.value, msg=item.message)

            logger_task = asyncio.create_task(display_logs())

            yield

            logger_task.cancel()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)

    app.mount(
        "/static",
        StaticFiles(directory="src/lfi_demo_server/assets/static/"),
        name="static",
    )

    return app
