import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tif", ".tiff"}


class ExiftoolNotFoundError(RuntimeError):
    """Raised when exiftool is not available on the system."""


def _ensure_exiftool_available() -> str:
    path = shutil.which("exiftool")
    if path:
        return path
    message = (
        "Exiftool ist nicht installiert oder nicht im PATH.\n"
        "Installationshinweise:\n"
        "- Linux (Debian/Ubuntu): sudo apt-get install libimage-exiftool-perl\n"
        "- macOS (Homebrew): brew install exiftool\n"
        "- Windows (Chocolatey): choco install exiftool\n"
        "Füge exiftool anschließend deinem PATH hinzu."
    )
    raise ExiftoolNotFoundError(message)


def _parse_exif_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip().replace(":", "-", 2)
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    try:
        return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _collect_files(images_dir: Path) -> List[Path]:
    files: List[Path] = []
    for root, _, filenames in os.walk(images_dir):
        for name in filenames:
            if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(Path(root) / name)
    return files


def _get_best_date(
    entry: Dict[str, Any], file_path: Path, file_mtime: Optional[float] = None
) -> datetime:
    for key in ("DateTimeOriginal", "CreateDate", "FileModifyDate"):
        parsed = _parse_exif_datetime(entry.get(key))
        if parsed:
            return parsed
    if file_mtime is None:
        file_mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(file_mtime)


def _build_entry(images_dir: Path, entry: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    source = Path(entry["SourceFile"])
    relative = source.relative_to(images_dir).as_posix()
    date_taken = _get_best_date(entry, source).isoformat()
    lat = entry.get("GPSLatitude")
    lon = entry.get("GPSLongitude")
    has_gps = lat is not None and lon is not None
    mapped = {
        "filename": source.name,
        "src": f"/images/{relative}",
        "dateTaken": date_taken,
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
    }
    return mapped, has_gps


def build_manifest(images_dir: Path, output_path: Path) -> List[Dict[str, Any]]:
    images_dir = images_dir.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exiftool_path = _ensure_exiftool_available()
    files = _collect_files(images_dir)
    if not files:
        data: List[Dict[str, Any]] = []
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Keine Bilder gefunden unter {images_dir}. Leere Manifestdatei erstellt.")
        return data

    cmd = [
        exiftool_path,
        "-r",
        "-n",
        "-json",
        "-DateTimeOriginal",
        "-CreateDate",
        "-GPSLatitude",
        "-GPSLongitude",
        "-FileModifyDate",
    ] + [str(path) for path in files]

    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Exiftool-Aufruf fehlgeschlagen (Exit {result.returncode}): {result.stderr.strip()}"
        )

    try:
        raw_entries: List[Dict[str, Any]] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Exiftool lieferte ungültiges JSON: {exc}") from exc

    mapped_entries: List[Dict[str, Any]] = []
    gps_count = 0
    for entry in raw_entries:
        if Path(entry["SourceFile"]).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        mapped, has_gps = _build_entry(images_dir, entry)
        mapped_entries.append(mapped)
        if has_gps:
            gps_count += 1

    mapped_entries.sort(key=lambda item: item["dateTaken"], reverse=True)
    output_path.write_text(json.dumps(mapped_entries, indent=2), encoding="utf-8")

    print(
        f"Manifest erstellt: {len(mapped_entries)} Bilder, davon {gps_count} mit GPS. "
        f"Output: {output_path}"
    )
    return mapped_entries


def main(argv: Optional[Iterable[str]] = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    base_dir = Path(__file__).resolve().parent.parent
    images_dir = base_dir / "images"
    output_path = base_dir / "static" / "images.json"
    try:
        build_manifest(images_dir, output_path)
    except ExiftoolNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net
        print(f"Fehler beim Erzeugen des Manifests: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
