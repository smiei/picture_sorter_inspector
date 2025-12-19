(() => {
  const progressEl = document.getElementById("progress");
  const appEl = document.getElementById("app");
  const imageEl = document.getElementById("currentImage");
  const filenameEl = document.getElementById("filename");
  const dateEl = document.getElementById("dateInfo");
  const gpsEl = document.getElementById("gpsStatus");
  const mapEl = document.getElementById("map");
  const mapMessageEl = document.getElementById("mapMessage");
  const exportBtn = document.getElementById("exportBtn");
  const rebuildBtn = document.getElementById("rebuildBtn");

  let images = [];
  let currentIndex = 0;
  let history = [];
  let map;
  let marker;
  const originalDateEl = document.getElementById("originalDate");

  function setProgress(msg) {
    progressEl.textContent = msg;
  }

  function logClient(message, context = {}, level = "info") {
    console.log("[client]", level, message, context);
    fetch("/api/client-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context, level }),
    }).catch(() => {});
  }

  async function fetchJSON(url, options = {}) {
    const res = await fetch(url, { cache: "no-cache", ...options });
    const data = await res.json();
    return { res, data };
  }

  function normalizeEntry(entry) {
    const name = entry.filename || entry.name || (entry.src ? entry.src.split("/").pop() : "");
    const url = entry.src
      ? entry.src.startsWith("/") ? entry.src : "/" + entry.src
      : entry.name ? `/images/${entry.name}` : "";
    return {
      name,
      url,
      status: null,
      lat: entry.lat ?? null,
      lon: entry.lon ?? null,
      dateTaken: entry.dateTaken ?? null,
      originalDate: entry.originalDate ?? null,
    };
  }

  async function loadManifest() {
    setProgress("Lade Manifest ...");
    try {
      const { res, data } = await fetchJSON(`/api/images?ts=${Date.now()}`);
      if (!res.ok || !data.ok) throw new Error(data.error || `HTTP ${res.status}`);
      images = Array.isArray(data.images) ? data.images.map(normalizeEntry) : [];
      images.sort((a, b) => (b.dateTaken || "").localeCompare(a.dateTaken || ""));
      currentIndex = 0;
      history = [];
      if (!images.length) {
        setProgress("Keine Bilder gefunden. Manifest neu erstellen?");
        appEl.classList.add("hidden");
        return;
      }
      appEl.classList.remove("hidden");
      render();
    } catch (err) {
      logClient("manifest_error", { error: String(err) }, "error");
      setProgress("Manifest laden fehlgeschlagen. Prüfe Server/Manifest.");
      appEl.classList.add("hidden");
    }
  }

  function ensureMap() {
    if (typeof L === "undefined") {
      mapMessageEl.classList.remove("hidden");
      mapEl.classList.add("hidden");
      gpsEl.textContent = "GPS: –";
      mapMessageEl.textContent = "Karte konnte nicht geladen werden.";
      return null;
    }
    if (!map) {
      map = L.map("map");
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap-Mitwirkende",
      }).addTo(map);
    }
    return map;
  }

  function updateMap(image) {
    if (image.lat != null && image.lon != null) {
      if (!ensureMap()) return;
      mapEl.classList.remove("hidden");
      mapMessageEl.classList.add("hidden");
      gpsEl.textContent = `GPS: ${image.lat.toFixed(5)}, ${image.lon.toFixed(5)}`;
      map.setView([image.lat, image.lon], 14);
      if (marker) marker.remove();
      marker = L.marker([image.lat, image.lon]).addTo(map);
      setTimeout(() => map.invalidateSize(), 50);
    } else {
      mapMessageEl.classList.remove("hidden");
      mapEl.classList.add("hidden");
      mapMessageEl.textContent = "Kein Aufnahmeort vorhanden";
      gpsEl.textContent = "GPS: –";
    }
  }

  function render() {
    if (!images.length) return;
    const img = images[currentIndex];
    imageEl.src = img.url;
    imageEl.alt = img.name;
    filenameEl.textContent = img.name || "–";
    dateEl.textContent = img.dateTaken ? new Date(img.dateTaken).toLocaleString() : "kein Datum";
    originalDateEl.textContent = img.originalDate
      ? new Date(img.originalDate).toLocaleString()
      : "kein Original-Datum";
    const decided = images.filter((i) => i.status !== null).length;
    setProgress(`Bild ${currentIndex + 1}/${images.length} – Entscheidungen: ${decided}/${images.length}`);
    logClient("render", { index: currentIndex, name: img.name });
    updateMap(img);
  }

  function setStatus(action) {
    if (!images.length) return;
    const img = images[currentIndex];
    const prev = img.status;
    if (prev !== action) {
      img.status = action;
      history.push({ index: currentIndex, prev });
      logClient("set_status", { index: currentIndex, action });
    }
    next();
  }

  function next() {
    if (currentIndex < images.length - 1) {
      currentIndex += 1;
      render();
    }
  }

  function prev() {
    if (currentIndex > 0) {
      currentIndex -= 1;
      render();
    }
  }

  function undo() {
    const last = history.pop();
    if (!last) return;
    images[last.index].status = last.prev;
    currentIndex = last.index;
    render();
    logClient("undo", { index: last.index });
  }

  document.getElementById("decisionButtons").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    setStatus(btn.getAttribute("data-action"));
  });

  window.addEventListener("keydown", (e) => {
    if (!images.length) return;
    switch (e.key) {
      case "1":
        setStatus("favorite");
        break;
      case "2":
        setStatus("like");
        break;
      case "3":
        setStatus("later");
        break;
      case "4":
        setStatus("delete");
        break;
      case "ArrowRight":
        next();
        break;
      case "ArrowLeft":
        prev();
        break;
      case "Backspace":
      case "z":
      case "Z":
        e.preventDefault();
        undo();
        break;
      default:
        break;
    }
  });

  exportBtn.addEventListener("click", async () => {
    if (!images.length) return;
    const payload = images.map((img, idx) => ({
      index: idx,
      name: img.name,
      status: img.status,
      lat: img.lat,
      lon: img.lon,
      dateTaken: img.dateTaken,
    }));
    exportBtn.disabled = true;
    exportBtn.textContent = "Exportiere ...";
    setProgress("Speichere Entscheidungen ...");
    try {
      const { res } = await fetchJSON("/save-decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions: payload }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setProgress(`Gespeichert (${payload.length} Einträge)`);
      logClient("export_ok", { count: payload.length });
    } catch (err) {
      setProgress("Export fehlgeschlagen.");
      logClient("export_error", { error: String(err) }, "error");
      alert("Export fehlgeschlagen. Details in der Konsole.");
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = "Entscheidungen exportieren";
    }
  });

  rebuildBtn.addEventListener("click", async () => {
    rebuildBtn.disabled = true;
    setProgress("Manifest wird neu erstellt ...");
    try {
      const { res, data } = await fetchJSON("/api/rebuild-manifest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok || !data.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setProgress(`Manifest aktualisiert (${data.count || 0} Einträge)`);
      await loadManifest();
    } catch (err) {
      setProgress("Manifest-Fehler. Siehe Konsole.");
      logClient("rebuild_error", { error: String(err) }, "error");
    } finally {
      rebuildBtn.disabled = false;
    }
  });

  // Start
  setProgress("Starte ...");
  loadManifest();
})();
