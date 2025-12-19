const state = {
  images: [],
  index: 0,
};

let map;
let marker;

const statusEl = document.getElementById("statusMessage");
const photoEl = document.getElementById("photo");
const filenameEl = document.getElementById("filename");
const dateEl = document.getElementById("date");
const mapEl = document.getElementById("map");
const mapMessageEl = document.getElementById("mapMessage");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const rebuildBtn = document.getElementById("rebuildBtn");

function setStatus(message = "", isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b23b30" : "#1f2933";
}

function ensureMap() {
  if (!map) {
    map = L.map("map");
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap-Mitwirkende",
    }).addTo(map);
  }
}

function showNoGpsMessage() {
  mapMessageEl.textContent = "Kein Aufnahmeort in Metadaten";
  mapMessageEl.classList.remove("hidden");
  mapEl.classList.add("hidden");
}

function showGpsOnMap(lat, lon) {
  mapEl.classList.remove("hidden");
  mapMessageEl.classList.add("hidden");
  ensureMap();
  map.setView([lat, lon], 14);
  if (marker) {
    marker.remove();
  }
  marker = L.marker([lat, lon]).addTo(map);
  setTimeout(() => map.invalidateSize(), 0);
}

function updateMapForCurrent(image) {
  if (image.lat != null && image.lon != null) {
    showGpsOnMap(image.lat, image.lon);
  } else {
    showNoGpsMessage();
  }
}

function updateControls() {
  prevBtn.disabled = state.index <= 0;
  nextBtn.disabled = state.index >= state.images.length - 1;
}

function renderCurrent() {
  if (!state.images.length) {
    showEmptyState("Keine Bilder gefunden. Lege Dateien in den Ordner images/.");
    return;
  }

  const current = state.images[state.index];
  photoEl.src = current.src;
  photoEl.alt = current.filename;
  filenameEl.textContent = current.filename;
  const date = current.dateTaken ? new Date(current.dateTaken) : null;
  dateEl.textContent = date ? date.toLocaleString() : "kein Datum";

  updateControls();
  updateMapForCurrent(current);
}

function showEmptyState(message) {
  setStatus(message, true);
  photoEl.removeAttribute("src");
  photoEl.alt = "Kein Bild";
  filenameEl.textContent = "";
  dateEl.textContent = "";
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  mapMessageEl.textContent = message;
  mapMessageEl.classList.remove("hidden");
  mapEl.classList.add("hidden");
}

function goNext() {
  if (state.index < state.images.length - 1) {
    state.index += 1;
    renderCurrent();
  }
}

function goPrev() {
  if (state.index > 0) {
    state.index -= 1;
    renderCurrent();
  }
}

function attachEvents() {
  nextBtn.addEventListener("click", goNext);
  prevBtn.addEventListener("click", goPrev);
  rebuildBtn.addEventListener("click", rebuildManifest);

  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") {
      goNext();
    } else if (event.key === "ArrowLeft") {
      goPrev();
    }
  });
}

async function rebuildManifest() {
  rebuildBtn.disabled = true;
  setStatus("Manifest wird neu erstellt...");
  try {
    const response = await fetch("/api/rebuild_manifest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }
    setStatus("Manifest aktualisiert.");
    document.body.dataset.exiftoolError = "";
    await loadImages(true);
  } catch (error) {
    console.error(error);
    setStatus(`Fehler beim Erzeugen des Manifests: ${error}`, true);
    document.body.dataset.exiftoolError = String(error);
  } finally {
    rebuildBtn.disabled = false;
  }
}

async function loadImages(skipStatus = false) {
  const exiftoolError = document.body.dataset.exiftoolError?.trim();
  if (exiftoolError && !skipStatus) {
    setStatus(exiftoolError, true);
  }

  try {
    const response = await fetch("/static/images.json", { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    state.images = data;
    state.index = 0;

    if (!data.length) {
      showEmptyState("Keine Bilder gefunden. Lege Dateien in den Ordner images/.");
      return;
    }

    renderCurrent();
  } catch (error) {
    console.error(error);
    showEmptyState("Konnte Manifest (images.json) nicht laden.");
    if (!statusEl.textContent) {
      setStatus(String(error), true);
    }
  }
}

attachEvents();
loadImages();
