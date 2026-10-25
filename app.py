###########################################################################
# Created : 2026-10-09 GB
# Purpose : Serve the read-only TSOLive observatory dashboard.
# Notes   : Most code was generated with assistance from ChatGPT.
#           Chat title: Astrophotography
#           OpenAI model/version: GPT-6
###########################################################################

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

def _poll_interval():
    try:
        return max(1000, int(os.getenv("ROOFRUNNER_POLL_FREQ_MS", "5000"))) / 1000
    except ValueError:
        return 5.0


def _roof_position(t, controller):
    if controller.get("state") == "HALTED":
        return "HALTED"
    if t.get("open_limit_active") and not t.get("closed_limit_active"):
        return "OPEN"
    if t.get("closed_limit_active") and not t.get("open_limit_active"):
        return "CLOSED"
    if t.get("open_limit_active") and t.get("closed_limit_active"):
        return "HALTED"
    speed = t.get("current_speed")
    if isinstance(speed, (int, float)):
        if speed > 0:
            return "OPENING"
        if speed < 0:
            return "CLOSING"
    return "HALTED"


def _flag(value):
    return ("ACTIVE" if value else "INACTIVE") if isinstance(value, bool) else "—"


def _fixed(value, divisor, digits, unit):
    return f"{value / divisor:.{digits}f} {unit}" if isinstance(value, (int, float)) else "—"


def _uptime(ms):
    if not isinstance(ms, (int, float)):
        return "—"
    seconds = max(0, int(ms // 1000))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return (f"{days}d " if days else "") + f"{hours}h {minutes}m {seconds}s"


def _roof_display(payload):
    t = payload["telemetry"]
    c = payload.get("controller") or {}
    return {
        "system": "roof",
        "online": True,
        "timestamp": payload["timestamp_utc"],
        "position": _roof_position(t, c),
        "details": {
            "controller-state": c.get("state"),
            "movement-allowed": ("YES" if c["movement_allowed"] else "NO") if isinstance(c.get("movement_allowed"), bool) else "—",
            "controller-reason": c.get("reason") or "None",
            "error-status": t.get("error_status"),
            "open-limit": _flag(t.get("open_limit_active")),
            "closed-limit": _flag(t.get("closed_limit_active")),
            "limit-status": t.get("limit_status"),
            "target-speed": t.get("target_speed"),
            "current-speed": t.get("current_speed"),
            "motor-current": _fixed(t.get("motor_current_ma"), 1, 0, "mA"),
            "input-voltage": _fixed(t.get("input_voltage_mv"), 1000, 3, "V"),
            "temperature": _fixed(t.get("temperature_tenths_c"), 10, 1, "°C"),
            "uptime": _uptime(t.get("uptime_ms")),
        },
    }


async def _poll_roofrunner(app):
    while True:
        try:
            display = _roof_display(await asyncio.to_thread(_read_roofrunner))
        except (OSError, ValueError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError):
            display = {"system": "roof", "online": False}
        app.state.roof_display = display
        for queue in tuple(app.state.subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(display)
        await asyncio.sleep(_poll_interval())


@asynccontextmanager
async def lifespan(app):
    app.state.roof_display = {"system": "roof", "online": False}
    app.state.subscribers = set()
    task = asyncio.create_task(_poll_roofrunner(app))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(title="TSOLive", description="Read-only observatory telemetry", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Detail views share a common layout; each system supplies its own panels and telemetry adapter.
DETAIL_SYSTEMS = {
    "roof": {"template": "roof-details.html", "label": "Roof", "source": "RoofRunner"},
}


# Homepage ordering and metadata live here. Shared markup is in _system_tile.html;
# each system's overview-specific content is in templates/tiles/.
OVERVIEW_SYSTEMS = [
    {"id": "roof", "name": "Roof", "icon": "⌂", "source": "RoofRunner",
     "last_update": "—", "live": True, "details_enabled": True,
     "aria_label": "Roof system", "body_template": "tiles/roof.html"},
    {"id": "telescope", "name": "Telescope", "icon": "◎", "source": "Sequence Generator Pro",
     "last_update": "2026-10-10 00:39:55Z", "live": False, "details_enabled": False,
     "aria_label": "Telescope system details, coming soon", "body_template": "tiles/telescope.html"},
    {"id": "camera", "name": "Camera", "icon": "▣", "source": "Sequence Generator Pro",
     "last_update": "2026-10-10 00:39:57Z", "live": False, "details_enabled": False,
     "aria_label": "Camera system details, coming soon", "body_template": "tiles/camera.html"},
    {"id": "filter-wheel", "name": "Filter Wheel", "icon": "◉", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Filter Wheel integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "weather", "name": "Weather", "icon": "☁", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Weather integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "allsky", "name": "AllSky", "icon": "✦", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "AllSky integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "guiding", "name": "Guiding", "icon": "⊕", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Guiding integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "session", "name": "Session", "icon": "◷", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Session integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "rigrunner-switch", "name": "RigRunner Switch", "icon": "⚡", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "RigRunner Switch integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "system10", "name": "System 10", "icon": "◇", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Future observatory system placeholder",
     "body_template": "tiles/placeholder.html"},
    {"id": "system11", "name": "System 11", "icon": "◇", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Future observatory system placeholder",
     "body_template": "tiles/placeholder.html"},
    {"id": "system12", "name": "System 12", "icon": "◇", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Future observatory system placeholder",
     "body_template": "tiles/placeholder.html"},
]


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"systems": OVERVIEW_SYSTEMS}
    )


def _read_roofrunner():
    base = os.getenv("ROOFRUNNER_API_URL", "").rstrip("/")
    if not base:
        raise ValueError("ROOFRUNNER_API_URL is not configured")
    request = URLRequest(base + "/api/dome/telemetry", method="GET")
    with urlopen(request, timeout=3) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("RoofRunner did not return successful telemetry")
    if not isinstance(payload.get("telemetry"), dict) or not payload.get("timestamp_utc"):
        raise ValueError("RoofRunner response is missing telemetry fields")
    return payload


@app.get("/events")
async def events(request: Request):
    async def stream():
        queue = asyncio.Queue(maxsize=1)
        request.app.state.subscribers.add(queue)
        try:
            yield f"data: {json.dumps(request.app.state.roof_display)}\n\n"
            while True:
                try:
                    display = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {json.dumps(display)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            request.app.state.subscribers.discard(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/details", response_class=HTMLResponse)
async def details(request: Request, system: str = ""):
    config = DETAIL_SYSTEMS.get(system)
    if config is None:
        return HTMLResponse("Unknown system", status_code=404)
    return templates.TemplateResponse(
        request=request,
        name=config["template"],
        context={"system_label": config["label"], "source_name": config["source"]},
    )
