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
from urllib.request import Request, urlopen

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="TSOLive", description="Read-only observatory telemetry")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def homepage():
    return (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")


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
    request = Request(base + "/api/dome/telemetry", method="GET")
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
async def details(system: str = ""):
    if system != "roof":
        return HTMLResponse("Unknown system", status_code=404)
    return (BASE_DIR / "templates" / "roof-details.html").read_text(encoding="utf-8")
