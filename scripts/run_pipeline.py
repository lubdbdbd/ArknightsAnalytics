from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.metrics import build_character_heat_matrix, build_sku_recommendations
from arknights_merch_analytics.commerce import (
    build_content_commerce_matrix,
    build_taobao_market_signals,
    build_targeted_query_summary,
    load_taobao_snapshots,
)
from arknights_merch_analytics.database import export_sqlite
from arknights_merch_analytics.reporting import (
    save_commerce_figures,
    save_figures,
    write_commerce_report,
    write_report,
    write_workbook,
)
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
            ROOT / "data" / "public" / "bilibili_official_operator_posts.json"
            if (ROOT / "data" / "public" / "bilibili_official_operator_posts.json").exists()
            else ROOT / "data" / "public" / "bilibili_official_pv_snapshot.json"
        )
    )
    if not input_path.exists():
        raise SystemExit(f"Missing {input_path}. Run scripts/collect_bilibili.py or use --use-fixture.")
    videos = pd.DataFrame(json.loads(input_path.read_text(encoding="utf-8")))
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    weibo_path = ROOT / "data" / "public" / "weibo_official_recent_posts.json"
    weibo = pd.DataFrame(json.loads(weibo_path.read_text(encoding="utf-8"))) if weibo_path.exists() else pd.DataFrame()
    operator_heat, content_scores = build_character_heat_matrix(videos, weibo, as_of=as_of)
    xhs_path = ROOT / "data" / "public" / "xiaohongshu_brand_snapshots.json"
    xhs = pd.DataFrame(json.loads(xhs_path.read_text(encoding="utf-8"))) if xhs_path.exists() else pd.DataFrame()
    if not xhs.empty:
        xhs["interaction_per_note"] = xhs["interaction_total"] / xhs["note_count"].clip(lower=1)
        xhs["favorite_rate"] = xhs["favorite_total"] / xhs["interaction_total"].clip(lower=1)
        xhs["comment_rate"] = xhs["comment_total"] / xhs["interaction_total"].clip(lower=1)
    categories = pd.read_csv(ROOT / "data" / "manual" / "product_categories.csv")
    erp = simulate_erp(operator_heat, categories)
    sku = build_sku_recommendations(erp)
    taobao_paths = sorted((ROOT / "data" / "public").glob("taobao_*.json"))
    taobao_listings = pd.DataFrame()
    taobao_market_signals = pd.DataFrame()
    targeted_query_summary = pd.DataFrame()
    content_commerce = pd.DataFrame()
    if taobao_paths:
        roster = operator_heat["operator"].tolist()
        taobao_listings = load_taobao_snapshots(taobao_paths, roster)
        taobao_market_signals = build_taobao_market_signals(taobao_listings, roster)
        targeted_query_summary = build_targeted_query_summary(taobao_listings)
        content_commerce = build_content_commerce_matrix(operator_heat, taobao_market_signals)

    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    operator_heat.to_csv(processed / "operator_heat.csv", index=False, encoding="utf-8-sig")
    operator_heat.to_csv(processed / "character_heat_matrix.csv", index=False, encoding="utf-8-sig")
    content_scores.to_csv(processed / "official_content_scores.csv", index=False, encoding="utf-8-sig")
    if not xhs.empty:
        xhs.to_csv(processed / "platform_ecosystem.csv", index=False, encoding="utf-8-sig")
    erp.to_csv(processed / "erp_mock.csv", index=False, encoding="utf-8-sig")
    sku.to_csv(processed / "sku_recommendations.csv", index=False, encoding="utf-8-sig")
    if not taobao_listings.empty:
        taobao_listings.to_csv(processed / "taobao_public_snapshots.csv", index=False, encoding="utf-8-sig")
        taobao_market_signals.to_csv(processed / "taobao_role_signals.csv", index=False, encoding="utf-8-sig")
        targeted_query_summary.to_csv(processed / "taobao_target_query_qa.csv", index=False, encoding="utf-8-sig")
        content_commerce.to_csv(processed / "content_commerce_matrix.csv", index=False, encoding="utf-8-sig")
    save_figures(operator_heat, sku, ROOT / "reports" / "figures", xhs)
    if not taobao_listings.empty:
        save_commerce_figures(
            taobao_listings,
            taobao_market_signals,
            content_commerce,
            ROOT / "reports" / "figures",
        )
    write_report(operator_heat, sku, ROOT / "reports" / "generated" / "analysis_report.md", xhs)
    if not taobao_listings.empty:
        write_commerce_report(
            taobao_listings,
            taobao_market_signals,
            content_commerce,
            targeted_query_summary,
            ROOT / "reports" / "generated" / "taobao_commerce_report.md",
        )
    write_workbook(
        operator_heat,
        erp,
        sku,
        ROOT / "reports" / "generated" / "operations_dashboard.xlsx",
        content_scores,
        xhs,
        taobao_listings,
        taobao_market_signals,
        content_commerce,
        targeted_query_summary,
    )
    export_sqlite(
        videos,
        operator_heat,
        erp,
        sku,
        ROOT / "reports" / "generated" / "operations.db",
        content_scores,
        xhs,
        taobao_listings,
        taobao_market_signals,
        content_commerce,
        targeted_query_summary,
    )
    print(
        f"Pipeline completed with {len(operator_heat)} operators, "
        f"{len(content_scores)} scored content rows, {len(sku)} simulated SKUs "
        f"and {len(taobao_listings)} Taobao public listing snapshots"
    )


if __name__ == "__main__":
    main()
