from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a manually verified Taobao public snapshot")
    parser.add_argument("input", type=Path, help="CSV with item_id, rank, title and url")
    parser.add_argument("--query", required=True)
    parser.add_argument("--target-operator", default=None)
    parser.add_argument("--sort", default="销量")
    parser.add_argument("--snapshot-at", default=None, help="ISO timestamp")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.input, dtype={"item_id": str})
    required = {"item_id", "rank", "title", "url"}
    missing = required.difference(frame.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")
    snapshot_at = args.snapshot_at or datetime.now().astimezone().isoformat(timespec="seconds")
    target_slug = args.target_operator or "market_baseline"
    default_name = f"taobao_{target_slug}_{snapshot_at[:10]}.json"
    output = args.output or ROOT / "data" / "public" / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform": "taobao",
        "query": args.query,
        "target_operator": args.target_operator,
        "sort": args.sort,
        "snapshot_at": snapshot_at,
        "collection_method": "manual_verified_public_snapshot",
        "metric_note": "公开展示收货人数是销量代理，不等同于精确成交量",
        "items": frame[["item_id", "rank", "title", "url"]]
        .sort_values("rank")
        .to_dict("records"),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(frame)} rows to {output}")


if __name__ == "__main__":
    main()
