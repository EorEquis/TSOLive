// Shared details-page clock and server-driven display updates.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
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
  const events = new EventSource("/events");
  events.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.system !== "roof") return;
    connection(data.online === true);
    if (!data.online) return;
    put("details-primary", data.position);
    put("details-last-update", data.timestamp.slice(0, 19).replace("T", " ") + "Z");
    for (const [id, value] of Object.entries(data.details)) put(id, value);
  };
  events.onerror = () => connection(false);
})();
