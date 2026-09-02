from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.collector import BilibiliConfig, collect_bilibili


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect historical official operator videos through public search")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--interval", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))["bilibili"]
    config = BilibiliConfig(
        official_mid=int(source["official_mid"]),
        official_name=str(source["official_name"]),
        search_queries=tuple(source["historical_search_queries"]),
        max_pages_per_query=args.max_pages or int(source["historical_max_pages_per_query"]),
        page_size=50,
        request_interval_seconds=args.interval
        if args.interval is not None
        else float(source["request_interval_seconds"]),
        start_date=str(source["historical_start_date"]),
    )
    output = ROOT / "data" / "public" / "bilibili_official_historical_search.json"
    rows = collect_bilibili(config, output)
    print(f"Collected {len(rows)} historical official search records -> {output}")


if __name__ == "__main__":
    main()
