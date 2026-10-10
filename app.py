###########################################################################
# Created : 2026-10-09 GB
# Purpose : Serve the read-only TSOLive observatory dashboard.
# Notes   : Most code was generated with assistance from ChatGPT.
#           Chat title: Astrophotography
#           OpenAI model/version: GPT-6
###########################################################################

import asyncio
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="TSOLive", description="Read-only observatory telemetry")
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "TSOLive"}


@app.get("/api/dashboard-config")
async def dashboard_config():
    try:
        interval = int(os.getenv("ROOFRUNNER_POLL_FREQ_MS", "5000"))
    except ValueError:
        interval = 5000
    return {"roofrunner_poll_freq_ms": max(1000, interval)}


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


@app.get("/api/roofrunner/telemetry")
async def roofrunner_telemetry():
    try:
        return await asyncio.to_thread(_read_roofrunner)
    except (OSError, ValueError, HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return JSONResponse(status_code=503, content={"success": False})


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
