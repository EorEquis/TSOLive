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

  const airlineLogo = document.getElementById("adsb-airline-logo");
  let airlineLogoCode = null;
  function updateAirlineLogo(callsign) {
    const code = typeof callsign === "string" ? /^([A-Z]{3})\d/i.exec(callsign.trim())?.[1].toUpperCase() : null;
    if (code === airlineLogoCode) return;
    airlineLogoCode = code;
    airlineLogo.hidden = true;
    airlineLogo.removeAttribute("src");
    if (code) airlineLogo.src = "/static/airline-logos/" + code + ".png";
  }
  airlineLogo.onload = () => { airlineLogo.hidden = false; };
  airlineLogo.onerror = () => { airlineLogo.hidden = true; };

  const events = new EventSource("/events");
  events.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.system === "roof") {
      setConnection(data.online === true);
      if (!data.online) return;
      position.textContent = data.position;
      updated.textContent = "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
    } else if (data.system === "allsky") {
      const tag = document.getElementById("allsky-connection");
      const dot = document.getElementById("allsky-connection-dot");
      const label = document.getElementById("allsky-connection-text");
      const online = data.online === true;
      tag.classList.toggle("offline", !online);
      dot.classList.toggle("offline-dot", !online);
      label.textContent = online ? "ONLINE" : "OFFLINE";
      if (data.timestamp) document.getElementById("allsky-last-update").textContent =
        "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
      const img = document.getElementById("allsky-current-image");
      const unavailable = document.getElementById("allsky-image-unavailable");
      if (data.image_version != null && img.dataset.version !== String(data.image_version)) {
        const version = String(data.image_version);
        const preload = new Image();
        preload.onload = () => {
          img.src = preload.src;
          img.dataset.version = version;
          img.hidden = false;
          unavailable.hidden = true;
        };
        preload.src = "/allsky/current.jpg?v=" + encodeURIComponent(version);
      }
    } else if (data.system === "adsb") {
      const online = data.online === true;
      const tag = document.getElementById("adsb-connection");
      tag.classList.toggle("offline", !online);
      document.getElementById("adsb-connection-dot").classList.toggle("offline-dot", !online);
      document.getElementById("adsb-connection-text").textContent = online ? "ONLINE" : "OFFLINE";
      const nearest = online ? data.nearest : null;
      updateAirlineLogo(nearest?.callsign);
      const values = {
        "aircraft-count": online ? data.aircraft_count : "—",
        "position-count": online ? data.position_count : "—",
        "nearest-callsign": nearest?.callsign ?? "—",
        "nearest-distance": nearest?.distance ?? "—",
        "nearest-altitude": nearest?.altitude ?? "—",
        "nearest-speed": nearest?.speed ?? "—"
      };
      for (const [field, value] of Object.entries(values)) {
        document.getElementById("adsb-" + field).textContent = value;
      }
      if (online && data.timestamp) document.getElementById("adsb-last-update").textContent =
        "Last Update : " + data.timestamp.slice(0, 19).replace("T", " ") + "Z";
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
    updateAirlineLogo(null);
    document.getElementById("adsb-connection").classList.add("offline");
    document.getElementById("adsb-connection-dot").classList.add("offline-dot");
    document.getElementById("adsb-connection-text").textContent = "OFFLINE";
    document.getElementById("allsky-connection").classList.add("offline");
    document.getElementById("allsky-connection-dot").classList.add("offline-dot");
    document.getElementById("allsky-connection-text").textContent = "OFFLINE";
    const tag = document.getElementById("weather-connection");
    tag.classList.add("offline");
    document.getElementById("weather-connection-dot").classList.add("offline-dot");
    document.getElementById("weather-connection-text").textContent = "OFFLINE";
  };
})();
