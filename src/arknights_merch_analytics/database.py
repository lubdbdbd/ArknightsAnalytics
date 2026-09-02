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
            views_path = ROOT / "sql" / "business_views.sql"
            if views_path.exists():
                connection.executescript(views_path.read_text(encoding="utf-8"))
