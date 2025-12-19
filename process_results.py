#!/usr/bin/env python3
"""
Verarbeitet die exportierte bildentscheidungen.json und sortiert Bilder
in Unterordner nach Status.

Standardverzeichnisse:
- JSON: output/bildentscheidungen.json
- Quellbilder: images/
- Ausgabe: output/sorted/<status>/
"""

import argparse
import json
import shutil
from pathlib import Path

STATUSES = {
    "favorite": "favorite",
    "like": "like",
    "later": "later",
    "delete": "delete",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Sortiert Bilder basierend auf JSON-Entscheidungen.")
    parser.add_argument(
        "--json",
        default=Path("output") / "bildentscheidungen.json",
        type=Path,
        help="Pfad zur exportierten JSON-Datei (Default: output/bildentscheidungen.json)",
    )
    parser.add_argument(
        "--images",
        default=Path("images"),
        type=Path,
        help="Verzeichnis mit den Quellbildern (Default: images/)",
    )
    parser.add_argument(
        "--out",
        default=Path("output") / "sorted",
        type=Path,
        help="Zielverzeichnis für sortierte Kopien (Default: output/sorted/)",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Statt Verschieben werden Dateien kopiert.",
    )
    return parser.parse_args()


def load_data(json_path: Path):
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs(base_out: Path):
    for folder in set(STATUSES.values()):
        (base_out / folder).mkdir(parents=True, exist_ok=True)


def resolve_status(status):
    if status is None or status == "null":
        return None  # unbeurteilt -> bleibt im images-Ordner
    if status in STATUSES:
        return STATUSES[status]
    # unbekannte Stati bleiben liegen
    return None


def main():
    args = parse_args()

    if not args.json.exists():
        raise SystemExit(f"JSON nicht gefunden: {args.json}")
    if not args.images.exists():
        raise SystemExit(f"Bildordner nicht gefunden: {args.images}")

    decisions = load_data(args.json)
    ensure_dirs(args.out)

    copy_fn = shutil.copy2 if args.copy else shutil.move
    skipped = 0

    for entry in decisions:
        name = entry.get("name")
        status = resolve_status(entry.get("status"))
        if not name:
            skipped += 1
            continue
        if not status:
            # Unentschiedene oder unbekannte Einträge bleiben im images-Ordner
            continue

        src = args.images / name
        dest = args.out / status / name

        if not src.exists():
            print(f"[WARN] Datei fehlt, übersprungen: {src}")
            skipped += 1
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_fn(src, dest)

    print(f"Fertig. Dateien in {args.out} abgelegt. Übersprungen: {skipped}")


if __name__ == "__main__":
    main()
