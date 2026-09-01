from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.metrics import build_operator_heat, build_sku_recommendations
from arknights_merch_analytics.database import export_sqlite
from arknights_merch_analytics.reporting import save_figures, write_report, write_workbook
from arknights_merch_analytics.simulation import simulate_erp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-fixture", action="store_true", help="Run with bundled pipeline fixture")
    parser.add_argument("--as-of", default=None, help="ISO timestamp used for reproducible age calculations")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = (
        ROOT / "data" / "fixtures" / "bilibili_videos.json"
        if args.use_fixture
        else (
            ROOT / "data" / "raw" / "bilibili_videos.json"
            if (ROOT / "data" / "raw" / "bilibili_videos.json").exists()
            else ROOT / "data" / "public" / "bilibili_official_pv_snapshot.json"
        )
    )
    if not input_path.exists():
        raise SystemExit(f"Missing {input_path}. Run scripts/collect_bilibili.py or use --use-fixture.")
    videos = pd.DataFrame(json.loads(input_path.read_text(encoding="utf-8")))
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    operator_heat = build_operator_heat(videos, as_of=as_of)
    categories = pd.read_csv(ROOT / "data" / "manual" / "product_categories.csv")
    erp = simulate_erp(operator_heat, categories)
    sku = build_sku_recommendations(erp)

    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    operator_heat.to_csv(processed / "operator_heat.csv", index=False, encoding="utf-8-sig")
    erp.to_csv(processed / "erp_mock.csv", index=False, encoding="utf-8-sig")
    sku.to_csv(processed / "sku_recommendations.csv", index=False, encoding="utf-8-sig")
    save_figures(operator_heat, sku, ROOT / "reports" / "figures")
    write_report(operator_heat, sku, ROOT / "reports" / "generated" / "analysis_report.md")
    write_workbook(
        operator_heat,
        erp,
        sku,
        ROOT / "reports" / "generated" / "operations_dashboard.xlsx",
    )
    export_sqlite(
        videos,
        operator_heat,
        erp,
        sku,
        ROOT / "reports" / "generated" / "operations.db",
    )
    print(f"Pipeline completed with {len(operator_heat)} operators and {len(sku)} simulated SKUs")


if __name__ == "__main__":
    main()
