from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a fixed-SKU public recapture queue")
    parser.add_argument("--operator", default=None)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "manual" / "sku_recapture_queue.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry_path = ROOT / "data" / "processed" / "sku_tracking_registry.csv"
    if not registry_path.exists():
        raise SystemExit("Missing tracking registry. Run scripts/run_pipeline.py first.")
    frame = pd.read_csv(registry_path, dtype={"item_id": str})
    if args.operator:
        frame = frame[frame["operator"] == args.operator]
    frame = frame.sort_values(["next_capture_due", "sales_proxy_min", "rank"], ascending=[True, False, True])
    queue = frame.head(args.limit).rename(columns={"raw_text": "title"})
    queue = queue[["item_id", "rank", "title", "url"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Exported {len(queue)} fixed-SKU rows to {args.output}")


if __name__ == "__main__":
    main()
