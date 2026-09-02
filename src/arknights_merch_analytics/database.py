from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def export_sqlite(
    videos: pd.DataFrame,
    operator_heat: pd.DataFrame,
    erp: pd.DataFrame,
    sku: pd.DataFrame,
    output_path: Path,
    content_scores: pd.DataFrame | None = None,
    xhs_snapshots: pd.DataFrame | None = None,
    taobao_listings: pd.DataFrame | None = None,
    taobao_market_signals: pd.DataFrame | None = None,
    content_commerce: pd.DataFrame | None = None,
    targeted_query_summary: pd.DataFrame | None = None,
    tracking_registry: pd.DataFrame | None = None,
    timeseries_metrics: pd.DataFrame | None = None,
    survey_audit: pd.DataFrame | None = None,
    survey_summary: pd.DataFrame | None = None,
    selection_case_evidence: pd.DataFrame | None = None,
    selection_case_categories: pd.DataFrame | None = None,
    bilibili_archive: pd.DataFrame | None = None,
    bilibili_campaign_content: pd.DataFrame | None = None,
    bilibili_campaign_summary: pd.DataFrame | None = None,
    bilibili_content_types: pd.DataFrame | None = None,
    bilibili_yearly_summary: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as connection:
        videos.to_sql("public_videos", connection, if_exists="replace", index=False)
        operator_heat.to_sql("operator_heat", connection, if_exists="replace", index=False)
        erp.to_sql("erp_mock", connection, if_exists="replace", index=False)
        sku.to_sql("sku_recommendations", connection, if_exists="replace", index=False)
        if content_scores is not None and not content_scores.empty:
            content_scores.to_sql("official_content_scores", connection, if_exists="replace", index=False)
        if xhs_snapshots is not None and not xhs_snapshots.empty:
            xhs_snapshots.to_sql("xiaohongshu_ecosystem", connection, if_exists="replace", index=False)
        if taobao_listings is not None and not taobao_listings.empty:
            taobao_listings.to_sql("taobao_public_snapshots", connection, if_exists="replace", index=False)
        if taobao_market_signals is not None and not taobao_market_signals.empty:
            taobao_market_signals.to_sql("taobao_role_signals", connection, if_exists="replace", index=False)
        if content_commerce is not None and not content_commerce.empty:
            content_commerce.to_sql("content_commerce_matrix", connection, if_exists="replace", index=False)
        if targeted_query_summary is not None and not targeted_query_summary.empty:
            targeted_query_summary.to_sql("taobao_target_query_qa", connection, if_exists="replace", index=False)
        if tracking_registry is not None and not tracking_registry.empty:
            tracking_registry.to_sql("sku_tracking_registry", connection, if_exists="replace", index=False)
        if timeseries_metrics is not None and not timeseries_metrics.empty:
            timeseries_metrics.to_sql("sku_timeseries_metrics", connection, if_exists="replace", index=False)
        if survey_audit is not None:
            survey_audit.to_sql("survey_response_audit", connection, if_exists="replace", index=False)
        if survey_summary is not None:
            survey_summary.to_sql("survey_operator_category_summary", connection, if_exists="replace", index=False)
        if selection_case_evidence is not None and not selection_case_evidence.empty:
            selection_case_evidence.to_sql("selection_case_evidence", connection, if_exists="replace", index=False)
        if selection_case_categories is not None and not selection_case_categories.empty:
            selection_case_categories.to_sql("selection_case_categories", connection, if_exists="replace", index=False)
        if bilibili_archive is not None and not bilibili_archive.empty:
            bilibili_archive.to_sql("bilibili_official_archive", connection, if_exists="replace", index=False)
        else:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bilibili_official_archive (
                    bvid TEXT, publication_year INTEGER, content_type TEXT,
                    view REAL, weighted_engagement_rate REAL, intent_rate REAL,
                    views_per_day REAL
                )
                """
            )
        if bilibili_campaign_content is not None and not bilibili_campaign_content.empty:
            bilibili_campaign_content.to_sql("bilibili_operator_campaign_content", connection, if_exists="replace", index=False)
        if bilibili_campaign_summary is not None and not bilibili_campaign_summary.empty:
            bilibili_campaign_summary.to_sql("bilibili_operator_campaign_summary", connection, if_exists="replace", index=False)
        else:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bilibili_operator_campaign_summary (
                    operator TEXT,
                    bilibili_campaign_content_count INTEGER,
                    bilibili_direct_content_count INTEGER,
                    bilibili_window_content_count INTEGER,
                    bilibili_campaign_content_types INTEGER,
                    bilibili_weighted_campaign_views REAL,
                    bilibili_weighted_intent_actions REAL,
                    bilibili_campaign_exposure_score REAL,
                    bilibili_campaign_depth_score REAL
                )
                """
            )
        if bilibili_content_types is not None and not bilibili_content_types.empty:
            bilibili_content_types.to_sql("bilibili_content_type_summary", connection, if_exists="replace", index=False)
        else:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bilibili_content_type_summary (
                    content_type TEXT, content_count INTEGER, total_views REAL,
                    median_views REAL, average_engagement_rate REAL,
                    average_intent_rate REAL, average_momentum REAL
                )
                """
            )
        if bilibili_yearly_summary is not None and not bilibili_yearly_summary.empty:
            bilibili_yearly_summary.to_sql("bilibili_yearly_summary", connection, if_exists="replace", index=False)
        else:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bilibili_yearly_summary (
                    publication_year INTEGER, content_count INTEGER,
                    operator_pv_count INTEGER, music_ep_count INTEGER,
                    event_pv_count INTEGER, total_views REAL,
                    median_views REAL, average_engagement_rate REAL
                )
                """
            )
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_public_videos_bvid ON public_videos(bvid);
            CREATE INDEX IF NOT EXISTS idx_operator_heat_operator ON operator_heat(operator);
            CREATE INDEX IF NOT EXISTS idx_erp_mock_operator_category ON erp_mock(operator, category);
            CREATE INDEX IF NOT EXISTS idx_sku_score ON sku_recommendations(selection_score DESC);
            CREATE INDEX IF NOT EXISTS idx_sku_operator_score
                ON sku_recommendations(operator, selection_score DESC);
            CREATE INDEX IF NOT EXISTS idx_sku_category_score
                ON sku_recommendations(category, selection_score DESC);
            """
        )
        commerce_frames = (taobao_listings, taobao_market_signals, content_commerce)
        if all(frame is not None and not frame.empty for frame in commerce_frames):
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_taobao_item_snapshot
                    ON taobao_public_snapshots(item_id, snapshot_at);
                CREATE INDEX IF NOT EXISTS idx_taobao_scope_ip_category
                    ON taobao_public_snapshots(query_scope, ip_scope, category);
                CREATE INDEX IF NOT EXISTS idx_taobao_role_observed_rank
                    ON taobao_role_signals(taobao_observed, commerce_rank);
                CREATE INDEX IF NOT EXISTS idx_content_commerce_priority
                    ON content_commerce_matrix(commercial_validation_priority DESC);
                """
            )
            if tracking_registry is not None and not tracking_registry.empty:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tracking_due ON sku_tracking_registry(tracking_status, next_capture_due)"
                )
            if timeseries_metrics is not None and not timeseries_metrics.empty:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_timeseries_grade ON sku_timeseries_metrics(timeseries_evidence_grade, operator)"
                )
            if bilibili_archive is not None and not bilibili_archive.empty:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bilibili_archive_year_type ON bilibili_official_archive(publication_year, content_type)"
                )
            if bilibili_campaign_content is not None and not bilibili_campaign_content.empty:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bilibili_campaign_operator_type ON bilibili_operator_campaign_content(operator, association_type, content_type)"
                )
            views_path = ROOT / "sql" / "business_views.sql"
            if views_path.exists():
                connection.executescript(views_path.read_text(encoding="utf-8"))
