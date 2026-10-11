// Weather Station V2 details adapter; shared polling/layout from details.js.
(function () {
  "use strict";
  const status = (data, key) => data.status && data.status[key] === "available";
  const reading = (value, unit, digits = 1) =>
    typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) + " " + unit : "UNAVAILABLE";
  const flag = (value) => typeof value === "boolean" ? (value ? "YES" : "NO") : "UNAVAILABLE";
  window.TSOLiveDetailsAdapter = {
    endpoint: "/api/weather/telemetry",
    configKey: "weather_poll_freq_ms",
    timestamp: (data) => data.timestamp,
    valid: (data) => !!(data.status && data.status.system === "available"),
    render(data, put) {
      const bme = status(data, "bme280");
      const set = (id, value) => put("weather-" + id, value);
      set("temperature", bme ? reading(data.temperature_c, "°C") : "UNAVAILABLE");
      set("humidity", bme ? reading(data.humidity_pct, "%") : "UNAVAILABLE");
      set("dewpoint", bme ? reading(data.dew_point_c, "°C") : "UNAVAILABLE");
      set("pressure", bme ? reading(data.pressure_hpa, "hPa", 2) : "UNAVAILABLE");
      put("details-primary", bme ? reading(data.temperature_c, "°C") : "UNAVAILABLE");
      set("sky-temperature", status(data, "mlx90614_1") ? reading(data.sky_temperature_c, "°C") : "UNAVAILABLE");
      set("ground-temperature", status(data, "mlx90614_2") ? reading(data.ground_temperature_c, "°C") : "UNAVAILABLE");
      set("is-dark", status(data, "lm393_light") ? flag(data.is_dark) : "UNAVAILABLE");
      set("light-value", status(data, "lm393_light") ? reading(data.light_value, "", 0).trim() : "UNAVAILABLE");
      set("is-wet", status(data, "lm393_rain") ? flag(data.is_wet) : "UNAVAILABLE");
      set("wet-value", status(data, "lm393_rain") ? reading(data.wet_value, "", 0).trim() : "UNAVAILABLE");
      set("rain-amount", status(data, "rainbucket") ? reading(data.rain_amount_mm, "mm", 2) : "UNAVAILABLE");
      set("wind-speed", status(data, "anemometer") ? reading(data.wind_speed_mps, "m/s", 2) : "UNAVAILABLE");
      set("wind-direction", status(data, "windvane") ? reading(data.wind_dir_deg, "°", 0) : "UNAVAILABLE");
      for (const key of ["bme280", "lm393_light", "lm393_rain", "mlx90614_1", "mlx90614_2", "anemometer", "windvane", "rainbucket"]) {
        set("status-" + key, data.status[key] === "available" ? "AVAILABLE" : "UNAVAILABLE");
      }
    }
  };
})();
