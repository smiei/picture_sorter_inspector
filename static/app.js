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
  const filterSelect = document.getElementById("filterSelect");

  let allItems = [];
  let images = [];
  let currentIndex = 0;
  let history = [];
  let map;
  let marker;
  const originalDateEl = document.getElementById("originalDate");
  let gamepadIndex = null;
  let lastButtonStates = [];

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
      type: entry.type || "image",
    };
  }

  async function loadManifest() {
    setProgress("Loading manifest ...");
    try {
      const { res, data } = await fetchJSON(`/api/images?ts=${Date.now()}`);
      if (!res.ok || !data.ok) throw new Error(data.error || `HTTP ${res.status}`);
      allItems = Array.isArray(data.images) ? data.images.map(normalizeEntry) : [];
      allItems.sort((a, b) => (b.dateTaken || "").localeCompare(a.dateTaken || ""));
      currentIndex = 0;
      history = [];
      applyFilter(filterSelect.value || "all");
    } catch (err) {
      logClient("manifest_error", { error: String(err) }, "error");
      setProgress("Failed to load manifest. Check server/manifest.");
      appEl.classList.add("hidden");
    }
  }

  function applyFilter(mode) {
    const previousItem = images[currentIndex];
    if (mode === "image") {
      images = allItems.filter((item) => item.type !== "video");
    } else if (mode === "video") {
      images = allItems.filter((item) => item.type === "video");
    } else {
      images = [...allItems];
    }
    if (!images.length) {
      appEl.classList.add("hidden");
      setProgress(mode === "video" ? "No videos available." : mode === "image" ? "No images available." : "No entries found.");
      return;
    }
    appEl.classList.remove("hidden");
    const idx = previousItem ? images.indexOf(previousItem) : -1;
    currentIndex = idx >= 0 ? idx : 0;
    render();
  }

  function ensureMap() {
    if (typeof L === "undefined") {
      mapMessageEl.classList.remove("hidden");
      mapEl.classList.add("hidden");
      gpsEl.textContent = "GPS: –";
      mapMessageEl.textContent = "Map library could not be loaded.";
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
      mapMessageEl.textContent = "No location available";
      gpsEl.textContent = "GPS: –";
    }
  }

  function render() {
    if (!images.length) return;
    const img = images[currentIndex];
    imageEl.src = img.url;
    imageEl.alt = img.name;
    const isVideo = img.type === "video";
    imageEl.classList.toggle("hidden", isVideo);
    let videoEl = document.getElementById("currentVideo");
    if (!videoEl) {
      videoEl = document.createElement("video");
      videoEl.id = "currentVideo";
      videoEl.controls = true;
      videoEl.playsInline = true;
      videoEl.preload = "metadata";
      videoEl.classList.add("hidden");
      document.getElementById("imageFrame").appendChild(videoEl);
    }
    videoEl.classList.toggle("hidden", !isVideo);
    if (isVideo) {
      videoEl.src = img.url;
      videoEl.load();
    } else {
      videoEl.removeAttribute("src");
      videoEl.load();
    }

    filenameEl.textContent = img.name || "–";
    dateEl.textContent = img.dateTaken ? new Date(img.dateTaken).toLocaleString() : "no date";
    originalDateEl.textContent = img.originalDate
      ? new Date(img.originalDate).toLocaleString()
      : "no original date";
    const decided = images.filter((i) => i.status !== null).length;
    setProgress(`Item ${currentIndex + 1}/${images.length} – decisions: ${decided}/${images.length}`);
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
    const advanced = next();
    if (!advanced) {
      render();
    }
  }

  function next() {
    if (currentIndex < images.length - 1) {
      currentIndex += 1;
      render();
      return true;
    }
    return false;
  }

  function prev() {
    if (currentIndex > 0) {
      currentIndex -= 1;
      render();
      return true;
    }
    return false;
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
    const payload = allItems.map((img, idx) => ({
      index: idx,
      name: img.name,
      status: img.status,
      lat: img.lat,
      lon: img.lon,
      dateTaken: img.dateTaken,
      originalDate: img.originalDate,
      type: img.type,
    }));
    exportBtn.disabled = true;
    exportBtn.textContent = "Saving ...";
    setProgress("Saving decisions ...");
    try {
      const { res } = await fetchJSON("/save-decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions: payload }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setProgress(`Saved (${payload.length} entries)`);
      logClient("export_ok", { count: payload.length });
    } catch (err) {
      setProgress("Export failed.");
      logClient("export_error", { error: String(err) }, "error");
      alert("Export failed. See console for details.");
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = "Save decisions";
    }
  });

  rebuildBtn.addEventListener("click", async () => {
    rebuildBtn.disabled = true;
    setProgress("Rebuilding manifest ...");
    try {
      const { res, data } = await fetchJSON("/api/rebuild-manifest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok || !data.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setProgress(`Manifest updated (${data.count || 0} entries)`);
      await loadManifest();
    } catch (err) {
      setProgress("Manifest error. See console.");
      logClient("rebuild_error", { error: String(err) }, "error");
    } finally {
      rebuildBtn.disabled = false;
    }
  });

  filterSelect.addEventListener("change", (e) => {
    applyFilter(e.target.value);
  });

  window.addEventListener("gamepadconnected", (e) => {
    gamepadIndex = e.gamepad.index;
    lastButtonStates = [];
    requestAnimationFrame(pollGamepad);
  });

  window.addEventListener("gamepaddisconnected", (e) => {
    if (gamepadIndex === e.gamepad.index) {
      gamepadIndex = null;
    }
  });

  function pollGamepad() {
    if (gamepadIndex !== null) {
      const pads = navigator.getGamepads();
      const gp = pads[gamepadIndex];
      if (gp) {
        gp.buttons.forEach((btn, idx) => {
          const was = lastButtonStates[idx] || false;
          const is = btn.pressed;
          if (is && !was) handleGamepadButton(idx);
          lastButtonStates[idx] = is;
        });
      }
    }
    requestAnimationFrame(pollGamepad);
  }

  function handleGamepadButton(index) {
    // Standard mapping: 0=A,1=B,2=X,3=Y, 14=Left,15=Right
    switch (index) {
      case 0:
        setStatus("like");
        break;
      case 1:
        setStatus("delete");
        break;
      case 2:
        setStatus("later");
        break;
      case 3:
        setStatus("favorite");
        break;
      case 15:
        next();
        break;
      case 14:
        prev();
        break;
      default:
        break;
    }
  }

  // Start
  setProgress("Starting ...");
  loadManifest();
})();
