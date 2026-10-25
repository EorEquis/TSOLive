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

  const events = new EventSource("/events");
  events.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.system !== "roof") return;
    setConnection(data.online === true);
    if (!data.online) return;
    position.textContent = data.position;
    updated.textContent = "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
  };
  events.onerror = () => setConnection(false);
})();
