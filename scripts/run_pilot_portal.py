from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.pilot_portal import create_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local commercial pilot portal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "data" / "manual" / "commercial_pilot" / "pilot_capture.db",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_path = args.database.resolve()
    server = create_server(args.host, args.port, database_path, ROOT / "web" / "pilot")
    print(f"Survey: http://{args.host}:{args.port}/")
    print(f"Admin:  http://{args.host}:{args.port}/admin")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
