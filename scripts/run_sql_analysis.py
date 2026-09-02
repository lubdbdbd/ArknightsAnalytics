from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.sql_reporting import build_sql_analysis_outputs


def main() -> None:
    database_path = ROOT / "reports" / "generated" / "operations.db"
    if not database_path.exists():
        raise SystemExit("Missing operations.db. Run scripts/run_pipeline.py first.")
    results = build_sql_analysis_outputs(
        database_path,
        ROOT / "data" / "processed",
        ROOT / "reports" / "generated" / "sql_analysis_report.md",
    )
    print(
        "SQL analysis completed with "
        f"{len(results)} result datasets and {sum(len(frame) for frame in results.values())} rows"
    )


if __name__ == "__main__":
    main()
