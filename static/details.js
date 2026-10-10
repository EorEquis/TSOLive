// Shared details-page clock, polling, connectivity and timestamps.
// Each system provides window.TSOLiveDetailsAdapter with endpoint, configKey, and render(data, put).
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const adapter = window.TSOLiveDetailsAdapter;
  if (!adapter) return;
  const put = (id, value) => {
    const element = $(id);
    if (element) element.textContent = value === null || value === undefined ? "—" : String(value);
  };
  function clock() {
    put("clock", new Date().toISOString().slice(0, 19).replace("T", " ") + " UTC");
  }
  clock();
  setInterval(clock, 1000);
  function connection(online) {
    put("details-connection-text", online ? "ONLINE" : "OFFLINE");
    $("details-connection").classList.toggle("offline", !online);
    $("details-connection-dot").classList.toggle("offline-dot", !online);
  }
  async function poll() {
    try {
      const response = await fetch(adapter.endpoint, {cache: "no-store"});
      if (!response.ok) throw new Error("Telemetry unavailable");
      const data = await response.json();
      if (data.success !== true || !data.timestamp_utc || !adapter.valid(data)) throw new Error("Invalid telemetry");
      adapter.render(data, put);
      put("details-last-update", data.timestamp_utc.slice(0, 19).replace("T", " ") + "Z");
      connection(true);
    } catch (_) {
      connection(false); // Retain last confirmed values and timestamp.
    }
  }
  async function start() {
    let interval = 5000;
    try {
      const response = await fetch("/api/dashboard-config", {cache: "no-store"});
      if (response.ok) {
        const config = await response.json();
        if (Number.isFinite(config[adapter.configKey])) interval = Math.max(1000, config[adapter.configKey]);
      }
    } catch (_) {}
    await poll();
    setInterval(poll, interval);
  }
  start();
})();
