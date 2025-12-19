# Lokale Foto-Diashow mit Karte

Minimalistische Flask-App, die Bilder aus `images/` als Diashow zeigt und – falls GPS vorhanden – eine Leaflet-Karte mit Marker anzeigt.

## Voraussetzungen
- Python 3.10+
- `exiftool` im `PATH`
  - Linux (Debian/Ubuntu): `sudo apt-get install libimage-exiftool-perl`
  - macOS (Homebrew): `brew install exiftool`
  - Windows (Chocolatey): `choco install exiftool`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Bilder hinzufügen
- Lege deine Fotos in den Ordner `images/`. Unterstützt: jpg, jpeg, heic, heif, png, tif, tiff.

## Manifest erzeugen (optional manuell)
Das Manifest wird beim Serverstart automatisch gebaut, wenn es fehlt oder Bilder neuer sind:
```bash
python scripts/build_manifest.py
```
Ergebnis liegt in `static/images.json`.

## Server starten
```bash
python app.py
```
Auf Windows optional per Batch:
```bat
start_server.bat
```
Öffne anschließend `http://127.0.0.1:5000`.

## Bedienung
- Navigation per Buttons „Zurück/Weiter“ oder Pfeiltasten links/rechts.
- Karte zeigt Marker, wenn GPS-Metadaten vorhanden sind; sonst eine Hinweis-Meldung.
- Sortierung: DateTimeOriginal → CreateDate → Dateisystem-MTime (absteigend).

## Hinweise bei fehlendem `exiftool`
- Im Terminal und im Browser erscheint eine klare Fehlermeldung.
- Manifest bleibt leer, bis `exiftool` installiert und der Server neu gestartet wurde.
