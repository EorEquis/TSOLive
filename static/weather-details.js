// Weather Station V2 details adapter; shared polling/layout from details.js.
(function () {
  "use strict";
  const sensorState = (data, key) => data.status?.[key] || "unavailable";
  const status = (data, key) => sensorState(data, key) === "available";
  const missing = (data, key) => sensorState(data, key) === "error" ? "ERROR" : "UNAVAILABLE";
  const reading = (value, unit, digits = 1) =>
    typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) + " " + unit : "UNAVAILABLE";
  const flag = (value) => typeof value === "boolean" ? (value ? "YES" : "NO") : "UNAVAILABLE";
  window.TSOLiveDetailsAdapter = {
    endpoint: "/api/weather/telemetry",
    configKey: "weather_poll_freq_ms",
    timestamp: (data) => data.timestamp,
    valid: (data) => !!(data.status && data.status.system === "available"),
    render(data, put) {
      const set = (id, value) => put("weather-" + id, value);
      const valueFor = (key, value) => status(data, key) ? value : missing(data, key);
      set("temperature", valueFor("bme280", reading(data.temperature_c, "°C")));
      set("humidity", valueFor("bme280", reading(data.humidity_pct, "%")));
      set("dewpoint", valueFor("bme280", reading(data.dew_point_c, "°C")));
      set("pressure", valueFor("bme280", reading(typeof data.pressure_hpa === "number" ? data.pressure_hpa * 0.0295299830714 : null, "inHg", 2)));
      put("details-primary", valueFor("bme280", reading(data.temperature_c, "°C")));
      set("cloud-condition", "—");
      set("sky-temperature", valueFor("mlx90614_1", reading(data.sky_temperature_c, "°C")));
      set("ground-temperature", valueFor("mlx90614_2", reading(data.ground_temperature_c, "°C")));
      set("is-dark", valueFor("lm393_light", flag(data.is_dark)));
      set("light-value", valueFor("lm393_light", reading(data.light_value, "", 0).trim()));
      set("is-wet", valueFor("lm393_rain", flag(data.is_wet)));
      set("wet-value", valueFor("lm393_rain", reading(data.wet_value, "", 0).trim()));
      set("rain-amount", valueFor("rainbucket", reading(data.rain_amount_mm, "mm", 2)));
      set("wind-speed", valueFor("anemometer", reading(data.wind_speed_mps, "m/s", 2)));
      set("wind-direction", valueFor("windvane", reading(data.wind_dir_deg, "°", 0)));
      for (const key of ["bme280", "lm393_light", "lm393_rain", "mlx90614_1", "mlx90614_2", "anemometer", "windvane", "rainbucket"]) {
        const state = sensorState(data, key);
        set("status-" + key, state.toUpperCase());
        const element = document.getElementById("weather-status-" + key);
        if (element) {
          element.classList.remove("sensor-available", "sensor-unavailable", "sensor-error");
          if (["available", "unavailable", "error"].includes(state)) element.classList.add("sensor-" + state);
        }
      }
    }
  };
})();
