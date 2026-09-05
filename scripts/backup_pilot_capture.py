from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up the local commercial pilot database")
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "data" / "manual" / "commercial_pilot" / "pilot_capture.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "backups" / "commercial_pilot",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database.exists():
        raise FileNotFoundError(f"Pilot database does not exist: {args.database}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = args.output_dir / f"pilot_capture-{timestamp}.db"
    with sqlite3.connect(args.database) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {integrity}")
    print(f"Pilot database backup created: {target}")


if __name__ == "__main__":
    main()
