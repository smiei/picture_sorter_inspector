#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import mimetypes
import shutil
import subprocess
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).parent
HOST, PORT = "0.0.0.0", 8000
IMAGES_DIR = ROOT / "images"
STATIC_DIR = ROOT / "static"
MANIFEST_PATH = STATIC_DIR / "images.json"
OUTPUT_FILE = ROOT / "output" / "bildentscheidungen.json"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
SERVER_LOG = LOG_DIR / "server.log"
CLIENT_LOG = LOG_DIR / "frontend.log"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SERVER_LOG, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pic_sorter")

exiftool_error: str | None = None


# ---------------- Manifest ---------------- #
def _latest_image_mtime() -> float | None:
    latest: float | None = None
    for path in IMAGES_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            mtime = path.stat().st_mtime
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def _ensure_exiftool() -> str | None:
    return shutil.which("exiftool")


def _parse_dt_obj(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace(":", "-", 2).replace(" ", "T", 1)
    try:
        return datetime.fromisoformat(normalized)
    except Exception:  # noqa: BLE001 - broad on purpose
        try:
            return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None


def _dt_to_iso(dt: datetime | None, fallback: datetime) -> str:
    return (dt or fallback).isoformat()


def _build_manifest_with_exiftool(exiftool_path: str) -> list[dict[str, Any]]:
    files = [str(p) for p in IMAGES_DIR.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        return []
    cmd = [
        exiftool_path,
        "-json",
        "-n",
        "-r",
        "-DateTimeOriginal",
        "-CreateDate",
        "-GPSLatitude",
        "-GPSLongitude",
        "-FileModifyDate",
        *files,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Exiftool exit {result.returncode}: {result.stderr.strip()}")
    raw_entries: list[dict[str, Any]] = json.loads(result.stdout)
    mapped: list[dict[str, Any]] = []
    for entry in raw_entries:
        src = Path(entry["SourceFile"])
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        fallback_dt = datetime.fromtimestamp(src.stat().st_mtime)
        dto = _parse_dt_obj(entry.get("DateTimeOriginal"))
        created = _parse_dt_obj(entry.get("CreateDate"))
        file_dt = _parse_dt_obj(entry.get("FileModifyDate"))

        # dateTaken: prefer DateTimeOriginal, then CreateDate, then FileModifyDate
        primary_dt = dto or created or file_dt or fallback_dt
        # originalDate: explicit original if present, else oldest of available, else fallback
        candidates = [dt for dt in (dto, created, file_dt) if dt is not None]
        original_dt = dto or (min(candidates) if candidates else None) or fallback_dt
        mapped.append(
            {
                "filename": src.name,
                "src": f"/images/{src.relative_to(IMAGES_DIR).as_posix()}",
                "dateTaken": _dt_to_iso(primary_dt, fallback_dt),
                "originalDate": _dt_to_iso(original_dt, fallback_dt),
                "lat": float(entry["GPSLatitude"]) if entry.get("GPSLatitude") is not None else None,
                "lon": float(entry["GPSLongitude"]) if entry.get("GPSLongitude") is not None else None,
            }
        )
    mapped.sort(key=lambda x: x["dateTaken"], reverse=True)
    return mapped


def _build_manifest_fallback() -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for path in IMAGES_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            mtime_iso = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            mapped.append(
                {
                    "filename": path.name,
                    "src": f"/images/{path.relative_to(IMAGES_DIR).as_posix()}",
                    "dateTaken": mtime_iso,
                    "originalDate": mtime_iso,
                    "lat": None,
                    "lon": None,
                }
            )
    mapped.sort(key=lambda x: x["dateTaken"], reverse=True)
    return mapped


def build_manifest(force: bool = False) -> tuple[list[dict[str, Any]], str | None]:
    """Create manifest file if needed. Returns (data, error)."""
    global exiftool_error
    needs_build = force or not MANIFEST_PATH.exists()
    if not needs_build:
        latest = _latest_image_mtime()
        if latest is not None and MANIFEST_PATH.stat().st_mtime < latest:
            needs_build = True
    if not needs_build:
        try:
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = []
        return data, exiftool_error

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: list[dict[str, Any]] = []
    exiftool_path = _ensure_exiftool()
    try:
        if exiftool_path:
            data = _build_manifest_with_exiftool(exiftool_path)
            exiftool_error = None
        else:
            exiftool_error = "Exiftool fehlt, verwende Dateisystem-Daten (ohne GPS)."
            data = _build_manifest_fallback()
    except Exception as exc:  # noqa: BLE001
        exiftool_error = f"Fehler beim Manifest: {exc}"
        data = _build_manifest_fallback()

    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data, exiftool_error


# ---------------- HTTP Handler ---------------- #
class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".json": "application/json",
        "": "application/octet-stream",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # Request routing
    def _normalized_path(self) -> str:
        parsed = urlparse(self.path).path or "/"
        if parsed != "/" and parsed.endswith("/"):
            parsed = parsed.rstrip("/")
        return parsed

    def do_GET(self):
        path = self._normalized_path()
        if path == "/api/status":
            self._handle_status()
            return
        if path == "/api/images":
            self._handle_images()
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        path = self._normalized_path()
        if path == "/save-decisions":
            self._handle_save()
            return
        if path == "/api/rebuild-manifest":
            self._handle_rebuild_manifest()
            return
        if path == "/api/client-log":
            self._handle_client_log()
            return
        self.send_error(404, "Not Found")

    # Logging
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.info("%s - %s", self.client_address[0], format % args)

    def _send_json(self, payload: dict[str, Any], status: int = 200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # Handlers
    def _handle_status(self):
        _, error = build_manifest(force=False)
        self._send_json({"ok": error is None, "exiftoolError": error, "manifestExists": MANIFEST_PATH.exists()})

    def _handle_images(self):
        data, error = build_manifest(force=False)
        if error:
            self._send_json({"ok": False, "error": error, "images": data}, status=500)
            return
        self._send_json({"ok": True, "images": data, "count": len(data)})

    def _handle_rebuild_manifest(self):
        data, error = build_manifest(force=True)
        if error:
            self._send_json({"ok": False, "error": error, "images": data}, status=500)
            return
        self._send_json({"ok": True, "count": len(data)})

    def _handle_save(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
            decisions = payload.get("decisions")
            if not isinstance(decisions, list):
                raise ValueError("decisions muss ein Array sein")
        except Exception as exc:  # noqa: BLE001
            self.send_error(400, f"Ungültige JSON: {exc}")
            return

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
        self._send_json({"status": "ok", "path": str(OUTPUT_FILE.relative_to(ROOT)), "count": len(decisions)})

    def _handle_client_log(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
            message = payload.get("message", "")
            level = payload.get("level", "info").upper()
            context = payload.get("context", {})
            line = f"[CLIENT] {message} | ctx={context}"
            with CLIENT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            logger.log(getattr(logging, level, logging.INFO), line)
            self._send_json({"ok": True})
        except Exception as exc:  # noqa: BLE001
            logger.error("Client log error: %s", exc)
            self._send_json({"ok": False, "error": str(exc)}, status=400)


def main(argv: Iterable[str] | None = None):
    build_manifest(force=False)
    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        print(f"Serving {ROOT} at http://{HOST}:{PORT}")
        print("GET  /api/status")
        print("GET  /api/images")
        print("POST /api/rebuild-manifest")
        print("POST /save-decisions")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server...")


if __name__ == "__main__":
    main()
