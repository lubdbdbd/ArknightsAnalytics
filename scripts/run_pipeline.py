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
from arknights_merch_analytics.case_study import (
    build_selection_case,
    write_selection_case_report,
)
from arknights_merch_analytics.bilibili_archive import (
    build_bilibili_archive,
    build_bilibili_archive_summaries,
    build_bilibili_campaign_attribution,
    build_bilibili_campaign_summary,
    save_bilibili_archive_figures,
    write_bilibili_archive_report,
)
from arknights_merch_analytics.database import export_sqlite
from arknights_merch_analytics.sql_reporting import build_sql_analysis_outputs
from arknights_merch_analytics.reporting import (
    save_commerce_figures,
    save_figures,
    write_commerce_report,
    write_report,
    write_workbook,
)
from arknights_merch_analytics.simulation import simulate_erp
from arknights_merch_analytics.survey import (
    build_survey_barrier_summary,
    build_survey_price_summary,
    build_survey_segment_summary,
    build_survey_summary,
    validate_survey_responses,
    write_survey_report,
)
from arknights_merch_analytics.tracking import (
    build_sku_timeseries_metrics,
    build_tracking_registry,
    write_tracking_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-fixture", action="store_true", help="Run with bundled pipeline fixture")
    parser.add_argument("--as-of", default=None, help="ISO timestamp used for reproducible age calculations")
    parser.add_argument("--case-operator", default="新约能天使", help="Operator used for the verifiable selection case")
    parser.add_argument("--skip-workbook", action="store_true", help="Skip XLSX regeneration")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = (
        ROOT / "data" / "fixtures" / "bilibili_videos.json"
        if args.use_fixture
        else (
            ROOT / "data" / "public" / "bilibili_official_archive.json"
            if (ROOT / "data" / "public" / "bilibili_official_archive.json").exists()
            else (
                ROOT / "data" / "public" / "bilibili_official_operator_posts.json"
                if (ROOT / "data" / "public" / "bilibili_official_operator_posts.json").exists()
                else ROOT / "data" / "public" / "bilibili_official_pv_snapshot.json"
            )
        )
    )
    if not input_path.exists():
        raise SystemExit(f"Missing {input_path}. Run scripts/collect_bilibili.py or use --use-fixture.")
    videos = pd.DataFrame(json.loads(input_path.read_text(encoding="utf-8")))
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    bilibili_archive = build_bilibili_archive(videos, as_of=as_of)
    bilibili_campaign_content = build_bilibili_campaign_attribution(bilibili_archive)
    bilibili_campaign_summary = build_bilibili_campaign_summary(bilibili_campaign_content)
    bilibili_content_types, bilibili_yearly_summary = build_bilibili_archive_summaries(
        bilibili_archive
    )
    weibo_path = ROOT / "data" / "public" / "weibo_official_recent_posts.json"
    weibo = pd.DataFrame(json.loads(weibo_path.read_text(encoding="utf-8"))) if weibo_path.exists() else pd.DataFrame()
    operator_heat, content_scores = build_character_heat_matrix(videos, weibo, as_of=as_of)
    if not bilibili_campaign_summary.empty:
        operator_heat = operator_heat.merge(
            bilibili_campaign_summary, on="operator", how="left"
        )
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
    tracking_registry = pd.DataFrame()
    timeseries_metrics = pd.DataFrame()
    if taobao_paths:
        roster = operator_heat["operator"].tolist()
        taobao_listings = load_taobao_snapshots(taobao_paths, roster)
        taobao_market_signals = build_taobao_market_signals(taobao_listings, roster)
        targeted_query_summary = build_targeted_query_summary(taobao_listings)
        content_commerce = build_content_commerce_matrix(operator_heat, taobao_market_signals)
        tracking_registry = build_tracking_registry(taobao_listings)
        timeseries_metrics = build_sku_timeseries_metrics(taobao_listings)

    survey_path = ROOT / "data" / "manual" / "user_survey_responses.csv"
    raw_survey = pd.read_csv(survey_path) if survey_path.exists() else pd.DataFrame()
    if raw_survey.empty and not survey_path.exists():
        survey_valid = pd.DataFrame()
        survey_audit = pd.DataFrame(columns=["response_id", "valid", "exclusion_reason"])
    else:
        survey_valid, survey_audit = validate_survey_responses(raw_survey)
    survey_summary = build_survey_summary(survey_valid)
    survey_segment_summary = build_survey_segment_summary(survey_valid)
    survey_barrier_summary = build_survey_barrier_summary(survey_valid)
    survey_price_summary = build_survey_price_summary(survey_valid)
    selection_case_evidence = pd.DataFrame()
    selection_case_categories = pd.DataFrame()
    if not content_commerce.empty and args.case_operator in set(content_commerce["operator"]):
        selection_case_evidence, selection_case_categories = build_selection_case(
            args.case_operator,
            content_commerce,
            targeted_query_summary,
            taobao_listings,
            sku,
            survey_summary,
            timeseries_metrics,
        )

    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    operator_heat.to_csv(processed / "operator_heat.csv", index=False, encoding="utf-8-sig")
    operator_heat.to_csv(processed / "character_heat_matrix.csv", index=False, encoding="utf-8-sig")
    content_scores.to_csv(processed / "official_content_scores.csv", index=False, encoding="utf-8-sig")
    bilibili_archive.to_csv(processed / "bilibili_official_archive.csv", index=False, encoding="utf-8-sig")
    bilibili_campaign_content.to_csv(processed / "bilibili_operator_campaign_content.csv", index=False, encoding="utf-8-sig")
    bilibili_campaign_summary.to_csv(processed / "bilibili_operator_campaign_summary.csv", index=False, encoding="utf-8-sig")
    bilibili_content_types.to_csv(processed / "bilibili_content_type_summary.csv", index=False, encoding="utf-8-sig")
    bilibili_yearly_summary.to_csv(processed / "bilibili_yearly_summary.csv", index=False, encoding="utf-8-sig")
    if not xhs.empty:
        xhs.to_csv(processed / "platform_ecosystem.csv", index=False, encoding="utf-8-sig")
    erp.to_csv(processed / "erp_mock.csv", index=False, encoding="utf-8-sig")
    sku.to_csv(processed / "sku_recommendations.csv", index=False, encoding="utf-8-sig")
    if not taobao_listings.empty:
        taobao_listings.to_csv(processed / "taobao_public_snapshots.csv", index=False, encoding="utf-8-sig")
        taobao_market_signals.to_csv(processed / "taobao_role_signals.csv", index=False, encoding="utf-8-sig")
        targeted_query_summary.to_csv(processed / "taobao_target_query_qa.csv", index=False, encoding="utf-8-sig")
        content_commerce.to_csv(processed / "content_commerce_matrix.csv", index=False, encoding="utf-8-sig")
        tracking_registry.to_csv(processed / "sku_tracking_registry.csv", index=False, encoding="utf-8-sig")
        timeseries_metrics.to_csv(processed / "sku_timeseries_metrics.csv", index=False, encoding="utf-8-sig")
    survey_audit.to_csv(processed / "survey_response_audit.csv", index=False, encoding="utf-8-sig")
    survey_summary.to_csv(processed / "survey_operator_category_summary.csv", index=False, encoding="utf-8-sig")
    survey_segment_summary.to_csv(processed / "survey_segment_summary.csv", index=False, encoding="utf-8-sig")
    survey_barrier_summary.to_csv(processed / "survey_barrier_summary.csv", index=False, encoding="utf-8-sig")
    survey_price_summary.to_csv(processed / "survey_price_summary.csv", index=False, encoding="utf-8-sig")
    if not selection_case_evidence.empty:
        selection_case_evidence.to_csv(processed / "selection_case_evidence.csv", index=False, encoding="utf-8-sig")
        selection_case_categories.to_csv(processed / "selection_case_categories.csv", index=False, encoding="utf-8-sig")
    save_figures(operator_heat, sku, ROOT / "reports" / "figures", xhs)
    save_bilibili_archive_figures(
        bilibili_content_types,
        bilibili_yearly_summary,
        bilibili_campaign_summary,
        ROOT / "reports" / "figures",
    )
    if not taobao_listings.empty:
        save_commerce_figures(
            taobao_listings,
            taobao_market_signals,
            content_commerce,
            ROOT / "reports" / "figures",
        )
    write_report(operator_heat, sku, ROOT / "reports" / "generated" / "analysis_report.md", xhs)
    write_bilibili_archive_report(
        bilibili_archive,
        bilibili_content_types,
        bilibili_yearly_summary,
        bilibili_campaign_content,
        bilibili_campaign_summary,
        ROOT / "reports" / "generated" / "bilibili_archive_report.md",
    )
    if not taobao_listings.empty:
        write_commerce_report(
            taobao_listings,
            taobao_market_signals,
            content_commerce,
            targeted_query_summary,
            ROOT / "reports" / "generated" / "taobao_commerce_report.md",
        )
        write_tracking_report(
            tracking_registry,
            timeseries_metrics,
            ROOT / "reports" / "generated" / "sku_timeseries_report.md",
        )
    write_survey_report(
        survey_valid,
        survey_audit,
        survey_summary,
        ROOT / "reports" / "generated" / "user_research_report.md",
        survey_segment_summary,
        survey_barrier_summary,
        survey_price_summary,
    )
    if not selection_case_evidence.empty:
        write_selection_case_report(
            args.case_operator,
            selection_case_evidence,
            selection_case_categories,
            sku,
            ROOT / "reports" / "generated" / "selection_case_study.md",
        )
    if not args.skip_workbook:
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
            tracking_registry,
            timeseries_metrics,
            survey_audit,
            survey_summary,
            selection_case_evidence,
            selection_case_categories,
            bilibili_archive,
            bilibili_campaign_content,
            bilibili_campaign_summary,
            bilibili_content_types,
            bilibili_yearly_summary,
            survey_segment_summary,
            survey_barrier_summary,
            survey_price_summary,
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
        tracking_registry,
        timeseries_metrics,
        survey_audit,
        survey_summary,
        selection_case_evidence,
        selection_case_categories,
        bilibili_archive,
        bilibili_campaign_content,
        bilibili_campaign_summary,
        bilibili_content_types,
        bilibili_yearly_summary,
        survey_segment_summary,
        survey_barrier_summary,
        survey_price_summary,
    )
    build_sql_analysis_outputs(
        ROOT / "reports" / "generated" / "operations.db",
        processed,
        ROOT / "reports" / "generated" / "sql_analysis_report.md",
    )
    print(
        f"Pipeline completed with {len(operator_heat)} operators, "
        f"{len(content_scores)} scored content rows, {len(sku)} simulated SKUs "
        f"and {len(taobao_listings)} Taobao public listing snapshots"
    )


if __name__ == "__main__":
    main()
