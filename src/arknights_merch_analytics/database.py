from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def export_sqlite(
    videos: pd.DataFrame,
    operator_heat: pd.DataFrame,
    erp: pd.DataFrame,
    sku: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as connection:
        videos.to_sql("public_videos", connection, if_exists="replace", index=False)
        operator_heat.to_sql("operator_heat", connection, if_exists="replace", index=False)
        erp.to_sql("erp_mock", connection, if_exists="replace", index=False)
        sku.to_sql("sku_recommendations", connection, if_exists="replace", index=False)
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_public_videos_bvid ON public_videos(bvid);
            CREATE INDEX IF NOT EXISTS idx_operator_heat_operator ON operator_heat(operator);
            CREATE INDEX IF NOT EXISTS idx_erp_mock_operator_category ON erp_mock(operator, category);
            CREATE INDEX IF NOT EXISTS idx_sku_score ON sku_recommendations(selection_score DESC);
            """
        )

