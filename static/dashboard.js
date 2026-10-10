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
  const connectionDot = document.getElementById("roof-connection-dot");
  if (!position || !updated || !connection) return;

  function setConnection(online) {
    connection.textContent = online ? "ONLINE" : "OFFLINE";
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
