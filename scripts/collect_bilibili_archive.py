from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.collector import collect_bilibili_related


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a low-frequency public Bilibili official archive")
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--interval", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))["bilibili"]
    output = ROOT / "data" / "public" / "bilibili_official_archive.json"
    seed = (
        output
        if output.exists()
        else ROOT / "data" / "public" / "bilibili_official_pv_snapshot.json"
    )
    rows = collect_bilibili_related(
        seed,
        output,
        official_mid=int(config["official_mid"]),
        max_official_videos=args.max_videos or int(config["related_max_official_videos"]),
        max_requests=args.max_requests or int(config["related_max_requests"]),
        request_interval_seconds=args.interval
        if args.interval is not None
        else float(config["request_interval_seconds"]),
        operator_only=False,
    )
    print(f"Collected {len(rows)} official public videos -> {output}")


if __name__ == "__main__":
    main()
