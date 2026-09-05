from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.erp import (
    export_erp_tables,
    simulate_erp_operations,
    write_erp_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a simulated auditable ERP operations dataset")
    parser.add_argument("--orders", type=int, default=6000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260903)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_skus = pd.read_csv(ROOT / "data" / "processed" / "erp_mock.csv")
    responses = pd.read_csv(ROOT / "data" / "survey" / "anonymous_responses_243.csv")
    rankings = pd.read_csv(ROOT / "data" / "survey" / "anonymous_operator_rankings_243.csv")
    tables = simulate_erp_operations(
        base_skus,
        responses,
        rankings,
        days=args.days,
        order_count=args.orders,
        seed=args.seed,
    )
    database_path = ROOT / "reports" / "generated" / "operations.db"
    export_erp_tables(
        tables,
        ROOT / "data" / "processed",
        database_path,
        ROOT / "sql" / "erp_views.sql",
    )
    write_erp_report(
        tables,
        database_path,
        ROOT / "reports" / "generated" / "erp_operations_report.md",
    )
    print(
        "Built ERP operations dataset: "
        + ", ".join(f"{name}={len(frame)}" for name, frame in tables.items())
    )


if __name__ == "__main__":
    main()
