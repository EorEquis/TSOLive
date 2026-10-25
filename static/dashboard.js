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


  function setConnection(online) {
    connectionText.textContent = online ? "ONLINE" : "OFFLINE";
    connection.classList.toggle("offline", !online);
    if (connectionDot) connectionDot.classList.toggle("offline-dot", !online);
  }

  const events = new EventSource("/events");
  events.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.system === "roof") {
      setConnection(data.online === true);
      if (!data.online) return;
      position.textContent = data.position;
      updated.textContent = "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
    } else if (data.system === "weather") {
      const tag = document.getElementById("weather-connection");
      const dot = document.getElementById("weather-connection-dot");
      const label = document.getElementById("weather-connection-text");
      const online = data.online === true;
      tag.classList.toggle("offline", !online);
      dot.classList.toggle("offline-dot", !online);
      label.textContent = online ? "ONLINE" : "OFFLINE";
      for (const field of ["temperature", "wind", "sky", "moisture", "time_of_day", "pressure", "pressure_trend"]) {
        const el = document.getElementById("weather-" + field.replaceAll("_", "-"));
        if (el) el.textContent = online ? (data[field] ?? "N/A") : "N/A";
      }
      if (online && data.timestamp) document.getElementById("weather-last-update").textContent = "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
    }
  };
  events.onerror = () => {
    setConnection(false);
    const tag = document.getElementById("weather-connection");
    tag.classList.add("offline");
    document.getElementById("weather-connection-dot").classList.add("offline-dot");
    document.getElementById("weather-connection-text").textContent = "OFFLINE";
  };
})();
