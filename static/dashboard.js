// Dashboard clock and independent, read-only RoofRunner telemetry polling.
(function () {
  "use strict";
  const clock = document.getElementById("clock");
  function updateClock() {
    if (!clock) return;
    clock.textContent = new Date().toISOString().slice(0, 19).replace("T", " ") + " UTC";
  }
  updateClock();
  setInterval(updateClock, 1000);

  const position = document.getElementById("roof-position");
  const updated = document.getElementById("roof-last-update");
  const connection = document.getElementById("roof-connection");
  const connectionText = document.getElementById("roof-connection-text");
  const connectionDot = document.getElementById("roof-connection-dot");
  if (!position || !updated || !connection) return;

  function setConnection(online) {
    connectionText.textContent = online ? "ONLINE" : "OFFLINE";
    connection.classList.toggle("offline", !online);
    if (connectionDot) connectionDot.classList.toggle("offline-dot", !online);
  }

  function roofPosition(t, controller) {
    if (controller && controller.state === "HALTED") return "HALTED";
    if (t.open_limit_active && !t.closed_limit_active) return "OPEN";
    if (t.closed_limit_active && !t.open_limit_active) return "CLOSED";
    if (t.open_limit_active && t.closed_limit_active) return "HALTED";
    // RoofRunner motor convention: positive opens, negative closes.
    if (t.current_speed > 0) return "OPENING";
    if (t.current_speed < 0) return "CLOSING";
    return "HALTED";
  }

  async function pollRoof() {
    try {
      const response = await fetch("/api/roofrunner/telemetry", {cache: "no-store"});
      if (!response.ok) throw new Error("RoofRunner unavailable");
      const data = await response.json();
      if (data.success !== true || !data.telemetry || !data.timestamp_utc) throw new Error("Invalid telemetry");
      position.textContent = roofPosition(data.telemetry, data.controller);
      updated.textContent = "Last Update : " + data.timestamp_utc.slice(0, 19).replace("T", " ") + "Z";
      setConnection(true);
    } catch (_) {
      setConnection(false);
      // Retain the last confirmed position and source timestamp.
    }
  }

  async function startRoofPolling() {
    let interval = 5000;
    try {
      const response = await fetch("/api/dashboard-config", {cache: "no-store"});
      if (response.ok) {
        const config = await response.json();
        if (Number.isFinite(config.roofrunner_poll_freq_ms)) interval = Math.max(1000, config.roofrunner_poll_freq_ms);
      }
    } catch (_) {}
    await pollRoof();
    setInterval(pollRoof, interval);
  }
  startRoofPolling();
})();

// Weather Station V2: independent, read-only polling.
(function () {
  "use strict";
  const el = (id) => document.getElementById(id);
  const tag = el("weather-connection");
  if (!tag) return;
  function setConnection(online) {
    el("weather-connection-text").textContent = online ? "ONLINE" : "OFFLINE";
    tag.classList.toggle("offline", !online);
    el("weather-connection-dot").classList.toggle("offline-dot", !online);
  }
  function show(id, value) {
    el(id).textContent = typeof value === "number" && Number.isFinite(value)
      ? value.toFixed(1) + " °C" : "—";
  }
  async function poll() {
    try {
      const response = await fetch("/api/weather/telemetry", {cache: "no-store"});
      if (!response.ok) throw new Error("Weather unavailable");
      const data = await response.json();
      if (!data.status || data.status.system !== "available" || !data.timestamp) throw new Error("Invalid weather telemetry");
      setConnection(true);
      const bme = data.status.bme280 === "available";
      show("weather-temp", bme ? data.temperature_c : null);
      el("weather-humidity").textContent = bme && typeof data.humidity_pct === "number" && Number.isFinite(data.humidity_pct)
        ? data.humidity_pct.toFixed(1) + " %" : "—";
      show("weather-dewpoint", bme ? data.dew_point_c : null);
      el("weather-last-update").textContent = "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
    } catch (_) {
      setConnection(false);
      // Preserve last confirmed readings and source timestamp on connection loss.
    }
  }
  async function start() {
    let interval = 5000;
    try {
      const response = await fetch("/api/dashboard-config", {cache: "no-store"});
      if (response.ok) {
        const config = await response.json();
        if (Number.isFinite(config.weather_poll_freq_ms)) interval = Math.max(1000, config.weather_poll_freq_ms);
      }
    } catch (_) {}
    await poll();
    setInterval(poll, interval);
  }
  start();
})();
