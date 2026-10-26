###########################################################################
# Created : 2026-10-09 GB
# Purpose : Serve the read-only TSOLive observatory dashboard.
# Notes   : Most code was generated with assistance from ChatGPT.
#           Chat title: Astrophotography
#           OpenAI model/version: GPT-6
###########################################################################

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import json
import os
import secrets
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

from astral import Observer
from astral.sun import elevation
import pymysql

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, Response
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



def _weather_interval():
    try:
        return max(1000, int(os.getenv("WEATHER_POLL_FREQ_MS", "5000"))) / 1000
    except ValueError:
        return 5.0


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _weather_value(value, fmt):
    return format(value, fmt) if value is not None else "N/A"


def _weather_daytime():
    try:
        observer = Observer(latitude=float(os.environ["OBSERVATORY_LAT"]),
                            longitude=float(os.environ["OBSERVATORY_LON"]))
        return "DAY" if elevation(observer, datetime.now(timezone.utc)) >= -12 else "NIGHT"
    except (KeyError, ValueError, TypeError):
        return "N/A"


def _pressure_trend():
    """Compare the first and last valid readings from the previous 30 UTC minutes."""
    connection = pymysql.connect(
        host=os.environ["WEATHER_DB_HOST"],
        port=int(os.getenv("WEATHER_DB_PORT", "3306")),
        user=os.environ["WEATHER_DB_USER"],
        password=os.environ["WEATHER_DB_PASSWORD"],
        database=os.environ["WEATHER_DB_NAME"],
        connect_timeout=3, read_timeout=3, write_timeout=3,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pressure_sealevel_hpa FROM observations "
                "WHERE obs_timestamp >= UTC_TIMESTAMP(6) - INTERVAL 30 MINUTE "
                "AND obs_timestamp <= UTC_TIMESTAMP(6) "
                "AND pressure_sealevel_hpa IS NOT NULL "
                "ORDER BY obs_timestamp ASC"
            )
            values = [row[0] for row in cursor.fetchall()]
        values = [v for v in values if _number(v) is not None]
        if len(values) < 2:
            return "N/A"
        delta = values[-1] - values[0]
        return "RISING" if delta > 0.2 else "FALLING" if delta < -0.2 else "STEADY"
    finally:
        connection.close()


def _read_weather():
    url = os.environ["WEATHER_API_URL"]
    with urlopen(URLRequest(url, method="GET"), timeout=3) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not payload.get("timestamp"):
        raise ValueError("Invalid weather response")
    return payload


def _sky_clear_delta():
    return float(os.getenv("SKY_CLEAR_DELTA_C", "18"))


def _weather_display(payload, trend):
    status = payload.get("status") or {}
    sky_clear_delta = _sky_clear_delta()
    def available(sensor):
        return status.get(sensor) == "available"

    temp = _number(payload.get("temp_c")) if available("bme280") else None
    sky = _number(payload.get("sky_temperature_c")) if available("mlx90614_1") else None
    wind = _number(payload.get("wind_speed_mps")) if available("anemometer") else None
    direction = _number(payload.get("wind_dir_deg")) if available("windvane") else None
    pressure = _number(payload.get("pressure_sealevel_hpa")) if available("bme280") else None
    station_pressure = _number(payload.get("pressure_hpa")) if available("bme280") else None
    rain = _number(payload.get("rain_rate_mm_hr")) if available("rainbucket") else None
    wet = payload.get("is_wet") if available("lm393_rain") else None
    compass = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
               "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    wind_text = "N/A"
    if wind is not None:
        wind_text = f"{wind * 2.2369362921:.1f} mph"
        wind_text += " " + compass[int((direction % 360 + 11.25) // 22.5) % 16] if direction is not None else " N/A"
    moisture = "RAINING" if rain is not None and rain > 0 else "WET" if wet is True else "DRY" if wet is False else "N/A"
    def val(key, sensor, precision=1, unit=""):
        n = _number(payload.get(key)) if available(sensor) else None
        return f"{n:.{precision}f}{unit}" if n is not None else "N/A"
    def mph(key):
        n = _number(payload.get(key)) if available("anemometer") else None
        return f"{n * 2.2369362921:.1f} mph" if n is not None else "N/A"
    dark = payload.get("is_dark") if available("lm393_light") else None
    details = {
        "air-temperature": val("temp_c", "bme280", 1, "°C"),
        "humidity": val("humidity_pct", "bme280", 1, "%"),
        "dew-point": val("dew_point_c", "bme280", 1, "°C"),
        "station-pressure": f"{station_pressure * 0.0295299831:.2f} inHg" if station_pressure is not None else "N/A",
        "sea-pressure": f"{pressure * 0.0295299831:.2f} inHg" if pressure is not None else "N/A",
        "pressure-trend": trend,
        "wind-speed": mph("wind_speed_mps"),
        "wind-direction": f"{compass[int((direction % 360 + 11.25) // 22.5) % 16]} ({direction:.1f}°)" if direction is not None else "N/A",
        "gust-10min": mph("wind_gust_10min"),
        "gust-hour": mph("wind_gust_hour"),
        "gust-today": mph("wind_gust_today"),
        "sky-temperature": val("sky_temperature_c", "mlx90614_1", 1, "°C"),
        "sky-delta": f"{temp - sky:.1f}°C" if temp is not None and sky is not None else "N/A",
        "sky-assessment": ("CLEAR" if temp - sky > sky_clear_delta else "CLOUDY") if temp is not None and sky is not None else "N/A",
        "ground-temperature": val("ground_temperature_c", "mlx90614_2", 1, "°C"),
        "time-of-day": _weather_daytime(),
        "light-value": val("light_value", "lm393_light", 0),
        "light-state": ("DARK" if dark else "LIGHT") if isinstance(dark, bool) else "N/A",
        "moisture-state": moisture,
        "wet-value": val("wet_value", "lm393_rain", 0),
        "rain-rate": val("rain_rate_mm_hr", "rainbucket", 2, " mm/hr"),
        "rain-hourly": val("rain_hourly_mm", "rainbucket", 2, " mm"),
        "rain-daily": val("rain_daily_mm", "rainbucket", 2, " mm"),
    }
    return {
        "system": "weather", "online": True, "timestamp": payload["timestamp"],
        "temperature": f"{temp:.1f}°C" if temp is not None else "N/A",
        "wind": wind_text,
        "sky": ("CLEAR" if temp - sky > sky_clear_delta else "CLOUDY") if temp is not None and sky is not None else "N/A",
        "moisture": moisture,
        "time_of_day": _weather_daytime(),
        "pressure": f"{pressure * 0.0295299831:.2f} inHg" if pressure is not None else "N/A",
        "pressure_trend": trend,
        "details": details,
    }



def _allsky_timeout():
    try:
        return max(1, int(os.getenv("ALLSKY_HEARTBEAT_SECONDS", "300")))
    except ValueError:
        return 300


def _allsky_status(app):
    last = app.state.allsky_last
    online = last is not None and (datetime.now(timezone.utc) - last).total_seconds() < _allsky_timeout()
    return {"system": "allsky", "online": online,
            "timestamp": last.isoformat().replace("+00:00", "Z") if last else None,
            "image_version": app.state.allsky_version if app.state.allsky_image is not None else None}


async def _monitor_allsky(app):
    previous = None
    while True:
        display = _allsky_status(app)
        if display["online"] != previous:
            _publish(app, display)
            previous = display["online"]
        await asyncio.sleep(5)


async def _poll_weather(app):
    trend = "N/A"
    next_trend = 0.0
    loop = asyncio.get_running_loop()
    while True:
        if loop.time() >= next_trend:
            try:
                trend = await asyncio.to_thread(_pressure_trend)
            except (OSError, ValueError, KeyError, TypeError, pymysql.MySQLError):
                trend = "N/A"
            next_trend = loop.time() + 60
        try:
            display = _weather_display(await asyncio.to_thread(_read_weather), trend)
        except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            display = {"system": "weather", "online": False}
        app.state.weather_display = display
        _publish(app, display)
        await asyncio.sleep(_weather_interval())


def _publish(app, display):
    for queue in tuple(app.state.subscribers):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(display)


async def _poll_roofrunner(app):
    while True:
        try:
            display = _roof_display(await asyncio.to_thread(_read_roofrunner))
        except (OSError, ValueError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError):
            display = {"system": "roof", "online": False}
        app.state.roof_display = display
        _publish(app, display)
        await asyncio.sleep(_poll_interval())


@asynccontextmanager
async def lifespan(app):
    app.state.roof_display = {"system": "roof", "online": False}
    app.state.weather_display = {"system": "weather", "online": False}
    app.state.subscribers = set()
    app.state.allsky_last = None
    app.state.allsky_image = None
    app.state.allsky_version = 0
    tasks = [asyncio.create_task(_poll_roofrunner(app)), asyncio.create_task(_poll_weather(app)), asyncio.create_task(_monitor_allsky(app))]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(title="TSOLive", description="Read-only observatory telemetry", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Detail views share a common layout; each system supplies its own panels and telemetry adapter.
DETAIL_SYSTEMS = {
    "roof": {"template": "roof-details.html", "label": "Roof", "source": "RoofRunner"},
    "weather": {"template": "weather-details.html", "label": "Weather", "source": "Weather Station"},
}


# Homepage ordering and metadata live here. Shared markup is in _system_tile.html;
# each system's overview-specific content is in templates/tiles/.
OVERVIEW_SYSTEMS = [
    {"id": "adsb", "name": "ADS-B", "icon": "✈", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "ADS-B integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "allsky", "name": "AllSky", "icon": "✦", "source": "AllSky Camera",
     "last_update": "—", "live": True, "details_enabled": False,
     "aria_label": "Current AllSky image", "body_template": "tiles/allsky.html"},
    {"id": "camera", "name": "Camera", "icon": "▣", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Camera integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "filter-wheel", "name": "Filter Wheel", "icon": "◉", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Filter Wheel integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "guiding", "name": "Guiding", "icon": "⊕", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Guiding integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "rigrunner-switch", "name": "RigRunner Switch", "icon": "⚡", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "RigRunner Switch integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "roof", "name": "Roof", "icon": "⌂", "source": "RoofRunner",
     "last_update": "—", "live": True, "details_enabled": True,
     "aria_label": "Roof system", "body_template": "tiles/roof.html"},
    {"id": "session", "name": "Session", "icon": "◷", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Session integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "telescope", "name": "Telescope", "icon": "◎", "source": None,
     "last_update": "—", "live": False, "details_enabled": False,
     "placeholder": True, "aria_label": "Telescope integration planned",
     "body_template": "tiles/placeholder.html"},
    {"id": "weather", "name": "Weather", "icon": "☁", "source": "Weather Station",
     "last_update": "—", "live": True, "details_enabled": True,
     "aria_label": "Weather system", "body_template": "tiles/weather.html"},
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



def _fetch_allsky_image():
    host = os.getenv("ALLSKY_IP", "").strip()
    if not host:
        raise ValueError("ALLSKY_IP is not configured")
    with urlopen(URLRequest("http://" + host + "/current/image.jpg", method="GET"), timeout=8) as upstream:
        if not upstream.headers.get("Content-Type", "").lower().startswith("image/jpeg"):
            raise ValueError("AllSky did not return a JPEG")
        image = upstream.read(12 * 1024 * 1024 + 1)
    if len(image) > 12 * 1024 * 1024:
        raise ValueError("AllSky image exceeds size limit")
    return image


@app.post("/allsky/notify/{token}")
async def allsky_notify(token: str, request: Request):
    """Allsky Publish Data POST triggers a new image fetch and heartbeat."""
    expected = os.getenv("ALLSKY_POST_TOKEN", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid AllSky token")
    try:
        image = await asyncio.to_thread(_fetch_allsky_image)
    except (OSError, ValueError, HTTPError, URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="Unable to retrieve AllSky image") from exc
    request.app.state.allsky_image = image
    request.app.state.allsky_last = datetime.now(timezone.utc)
    request.app.state.allsky_version += 1
    _publish(request.app, _allsky_status(request.app))
    return {"ok": True}


@app.get("/allsky/current.jpg")
async def allsky_current(request: Request):
    image = request.app.state.allsky_image
    if image is None:
        return Response(status_code=503, headers={"Cache-Control": "no-store"})
    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/events")
async def events(request: Request):
    async def stream():
        queue = asyncio.Queue(maxsize=1)
        request.app.state.subscribers.add(queue)
        try:
            yield f"data: {json.dumps(request.app.state.roof_display)}\n\n"
            yield f"data: {json.dumps(request.app.state.weather_display)}\n\n"
            yield f"data: {json.dumps(_allsky_status(request.app))}\n\n"
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
