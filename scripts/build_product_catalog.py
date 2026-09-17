from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.product_catalog import (
    build_internal_product_master,
    build_product_category_health,
    build_product_change_log,
    build_product_field_dictionary,
    build_product_maintenance_queue,
    build_public_listing_master,
    export_product_catalog,
    write_product_catalog_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product master-data maintenance outputs")
    parser.add_argument("--event-at", default="2026-09-05T00:00:00+08:00")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    internal_source = pd.read_csv(ROOT / "data" / "processed" / "erp_sku_master.csv")
    public_source = pd.read_csv(ROOT / "data" / "processed" / "taobao_public_snapshots.csv")
    internal = build_internal_product_master(internal_source)
    public = build_public_listing_master(public_source)
    tables = {
        "product_catalog_internal": internal,
        "product_catalog_public": public,
        "product_maintenance_queue": build_product_maintenance_queue(public),
        "product_category_health": build_product_category_health(internal, public),
        "product_change_log": build_product_change_log(internal, public, args.event_at),
        "product_field_dictionary": build_product_field_dictionary(),
    }
    export_product_catalog(
        tables,
        ROOT / "data" / "processed",
        ROOT / "reports" / "generated" / "operations.db",
        ROOT / "sql" / "product_catalog_views.sql",
    )
    write_product_catalog_report(
        tables, ROOT / "reports" / "generated" / "product_catalog_maintenance_report.md"
    )
    print("Built product catalog: " + ", ".join(f"{name}={len(frame)}" for name, frame in tables.items()))


if __name__ == "__main__":
    main()
