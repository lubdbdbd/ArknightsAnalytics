from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.collector import collect_bilibili, load_config


def main() -> None:
    config = load_config(ROOT / "config" / "sources.json")
    output = ROOT / "data" / "raw" / "bilibili_videos.json"
    rows = collect_bilibili(config, output)
    print(f"Collected {len(rows)} public video records -> {output}")


if __name__ == "__main__":
    main()

