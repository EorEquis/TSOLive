// SGP camera-specific detail fields; shared lifecycle and breadcrumb in details-base/details.js.
(function () {
  "use strict";
  const displayState = (state) => state === "READY" ? "IDLE" : state;
  const optionCount = (values) => Array.isArray(values) ? String(values.length) : "—";
  window.TSOLiveDetailsAdapter = {
    endpoint: "/api/sgp/camera",
    configKey: "sgp_poll_freq_ms",
    valid: (data) => typeof data.state === "string" && typeof data.connected === "boolean",
    online: (data) => data.connected,
    render(data, put) {
      const activity = displayState(data.state);
      const props = data.properties || {};
      put("details-primary", activity);
      put("camera-detail-connection", data.connected ? "CONNECTED" : "DISCONNECTED");
      put("camera-detail-activity", activity);
      put("camera-detail-raw-state", data.state);
      put("camera-detail-temperature", Number.isFinite(data.temperature_c) ? data.temperature_c.toFixed(1) + " °C" : "—");
      put("camera-detail-resolution", Number.isFinite(props.NumPixelsX) && Number.isFinite(props.NumPixelsY) ? props.NumPixelsX + " × " + props.NumPixelsY : "—");
      put("camera-detail-subframe", typeof props.SupportsSubframe === "boolean" ? (props.SupportsSubframe ? "YES" : "NO") : "—");
      put("camera-detail-exposure", activity);
      put("camera-detail-gain", optionCount(props.GainValues));
      put("camera-detail-iso", optionCount(props.IsoValues));
    }
  };
})();
