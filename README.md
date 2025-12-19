# Photo Sorter

An interactive web tool to triage photos and videos from the `images/` folder. It shows each item, lets you mark it (favorite/keep/later/delete), displays capture date and location (if available), and can export your decisions as JSON.

## Features
- Supports images and videos (jpg/jpeg/png/gif/bmp/webp/heic/heif/tif/tiff/mp4/mov/m4v).
- Reads metadata via Exiftool when available (dates, GPS). Falls back to filesystem timestamps if Exiftool is missing.
- Map view for GPS-tagged items.
- Original date display, manifest rebuild button, and filter (images/videos/all).
- Keyboard and gamepad controls (A=Keep, B=Delete, X=Later, Y=Favorite; arrows to navigate; Z/Backspace undo).
- Exports decisions to `output/bildentscheidungen.json`.

## Prerequisites
- Python 3.10+ (used for the lightweight HTTP server).
- Optional: Exiftool in PATH to extract GPS and original dates from media files. Without it, the server uses file timestamps and omits GPS.

## Running
1. Place your media files in `images/`.
2. Start the server:
   - Windows: double-click or run `start_server.bat`.
   - Cross-platform: `python3 server.py`
3. Open http://localhost:8000 in your browser.

## Usage
- On load, the server builds/uses `static/images.json` (the manifest). Use “Rebuild manifest” if you add/remove files.
- Choose a filter (Images/Videos/All), then mark each item with buttons, keyboard, or controller.
- “Save decisions” posts to `/save-decisions` and writes `output/bildentscheidungen.json`.
- The status bar shows progress and decisions made; map and original date appear on the right when available.

## Notes
- Logs are written to `logs/server.log` (server) and `logs/frontend.log` (client events).
- The server auto-sets MIME types for JS/JSON and serves everything from the repo root. The app assets live in `static/`.
