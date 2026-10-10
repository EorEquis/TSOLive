// RoofRunner-specific fields and formatting. Shared page lifecycle lives in details.js.
(function () {
  "use strict";
  function position(t, controller) {
    if (controller && controller.state === "HALTED") return "HALTED";
    if (t.open_limit_active && !t.closed_limit_active) return "OPEN";
    if (t.closed_limit_active && !t.open_limit_active) return "CLOSED";
    if (t.open_limit_active && t.closed_limit_active) return "HALTED";
    if (t.current_speed > 0) return "OPENING";
    if (t.current_speed < 0) return "CLOSING";
    return "HALTED";
  }
  function flag(value) {
    return typeof value === "boolean" ? (value ? "ACTIVE" : "INACTIVE") : "—";
  }
  function uptime(ms) {
    if (!Number.isFinite(ms)) return "—";
    let seconds = Math.floor(ms / 1000);
    const days = Math.floor(seconds / 86400);
    seconds %= 86400;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    seconds %= 60;
    return (days ? days + "d " : "") + hours + "h " + minutes + "m " + seconds + "s";
  }
  function fixed(value, divisor, digits, unit) {
    return Number.isFinite(value) ? (value / divisor).toFixed(digits) + " " + unit : "—";
  }
  window.TSOLiveDetailsAdapter = {
    endpoint: "/api/roofrunner/telemetry",
    configKey: "roofrunner_poll_freq_ms",
    valid: (data) => !!data.telemetry,
    render(data, put) {
      const t = data.telemetry;
      const c = data.controller || {};
      put("roof-position", position(t, c));
      put("roof-last-update", data.timestamp_utc.slice(0, 19).replace("T", " ") + "Z");
      put("controller-state", c.state);
      put("movement-allowed", typeof c.movement_allowed === "boolean" ? (c.movement_allowed ? "YES" : "NO") : "—");
      put("controller-reason", c.reason || "None");
      put("error-status", t.error_status);
      put("open-limit", flag(t.open_limit_active));
      put("closed-limit", flag(t.closed_limit_active));
      put("limit-status", t.limit_status);
      put("target-speed", t.target_speed);
      put("current-speed", t.current_speed);
      put("motor-current", fixed(t.motor_current_ma, 1, 0, "mA"));
      put("input-voltage", fixed(t.input_voltage_mv, 1000, 3, "V"));
      put("temperature", fixed(t.temperature_tenths_c, 10, 1, "°C"));
      put("uptime", uptime(t.uptime_ms));
    }
  };
})();
