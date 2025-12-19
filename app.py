import os
import sys
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, send_from_directory

from scripts.build_manifest import (
    ExiftoolNotFoundError,
    SUPPORTED_EXTENSIONS,
    build_manifest,
)

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
STATIC_DIR = BASE_DIR / "static"
MANIFEST_PATH = STATIC_DIR / "images.json"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

exiftool_error: Optional[str] = None


def _latest_image_mtime() -> Optional[float]:
    latest: Optional[float] = None
    for root, _, files in os.walk(IMAGES_DIR):
        for name in files:
            if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            full_path = Path(root) / name
            mtime = full_path.stat().st_mtime
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def _manifest_needs_refresh() -> bool:
    if not MANIFEST_PATH.exists():
        return True
    latest_image = _latest_image_mtime()
    if latest_image is None:
        return False
    return latest_image > MANIFEST_PATH.stat().st_mtime


def ensure_manifest() -> None:
    global exiftool_error
    try:
        if not MANIFEST_PATH.exists() or _manifest_needs_refresh():
            build_manifest(IMAGES_DIR, MANIFEST_PATH)
        exiftool_error = None
    except ExiftoolNotFoundError as exc:
        exiftool_error = str(exc)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not MANIFEST_PATH.exists():
            MANIFEST_PATH.write_text("[]", encoding="utf-8")
        print(exiftool_error, file=sys.stderr)
    except Exception as exc:  # pragma: no cover - safety net
        exiftool_error = f"Fehler beim Erzeugen des Manifests: {exc}"
        print(exiftool_error, file=sys.stderr)


@app.route("/")
def index():
    ensure_manifest()
    return render_template("index.html", exiftool_error=exiftool_error)


@app.route("/images/<path:filename>")
def serve_image(filename: str):
    return send_from_directory(str(IMAGES_DIR), filename)


@app.route("/api/rebuild_manifest", methods=["POST"])
def api_rebuild_manifest():
    global exiftool_error
    try:
        data = build_manifest(IMAGES_DIR, MANIFEST_PATH)
        exiftool_error = None
        return jsonify({"ok": True, "count": len(data)})
    except ExiftoolNotFoundError as exc:
        exiftool_error = str(exc)
        return jsonify({"ok": False, "error": exiftool_error}), 500
    except Exception as exc:  # pragma: no cover - safety net
        exiftool_error = f"Fehler beim Erzeugen des Manifests: {exc}"
        return jsonify({"ok": False, "error": exiftool_error}), 500


if __name__ == "__main__":
    ensure_manifest()
    app.run(debug=False)
