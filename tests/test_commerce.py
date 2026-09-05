from __future__ import annotations

import json

import pandas as pd

from arknights_merch_analytics.commerce import (
    build_content_commerce_matrix,
    build_taobao_market_signals,
    build_targeted_query_summary,
    classify_category,
    load_taobao_snapshots,
    parse_price,
    parse_sales_proxy,
)
from arknights_merch_analytics.reporting import write_commerce_report


def test_parse_public_price_and_censored_sales_proxy() -> None:
    text = "新约能天使 亚克力 ¥ 38 .32 补贴后 100+人收货"
    assert parse_price(text) == 38.32
    assert parse_sales_proxy(text) == (100.0, True)
    assert parse_sales_proxy("1.2万+人收货") == (12000.0, True)


def test_classify_merchandise_category() -> None:
    assert classify_category("明日方舟徽章吧唧") == "吧唧（徽章）"
    assert classify_category("亚克力立牌摇摇乐") == "亚克力制品"
    assert classify_category("10cm棉花娃娃毛绒玩偶") == "毛绒玩偶"
    assert classify_category("罗德岛通行认证卡") == "通行证"
    assert classify_category("明日方舟角色手办模型") == "手办模玩"
    assert classify_category("角色色纸桌面摆件") == "装饰摆件"
    assert classify_category("罗德岛水杯和鼠标垫") == "日用生活"


def test_snapshot_quality_gate_and_market_signals(tmp_path) -> None:
    targeted_payload = {
        "query": "明日方舟 新约能天使 周边",
        "target_operator": "新约能天使",
        "sort": "销量",
        "snapshot_at": "2026-09-02T12:00:00+08:00",
        "collection_method": "test",
        "items": [
            {
                "item_id": "1",
                "rank": 1,
                "url": "https://item.taobao.com/item.htm?id=1",
                "title": "明日方舟官方正版 新约能天使 亚克力立牌 ¥ 38 100+人收货 包邮",
            },
            {
                "item_id": "2",
                "rank": 2,
                "url": "https://item.taobao.com/item.htm?id=2",
                "title": "凯尔希 毛绒玩偶 ¥ 88 20人收货",
            },
        ],
    }
    baseline_payload = {
        "query": "明日方舟 周边",
        "target_operator": None,
        "sort": "销量",
        "snapshot_at": "2026-09-02T12:00:00+08:00",
        "collection_method": "test",
        "items": [
            {
                "item_id": "3",
                "rank": 1,
                "url": "https://item.taobao.com/item.htm?id=3",
                "title": "明日方舟 官方正版 凯尔希 毛绒玩偶 ¥ 88 200人收货 包邮",
            },
            {
                "item_id": "4",
                "rank": 2,
                "url": "https://item.taobao.com/item.htm?id=4",
                "title": "明日方舟 希望系列亚克力立牌 ¥ 20 10人收货",
            },
        ],
    }
    targeted_path = tmp_path / "taobao_targeted.json"
    baseline_path = tmp_path / "taobao_baseline.json"
    targeted_path.write_text(json.dumps(targeted_payload), encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline_payload), encoding="utf-8")

    roster = ["新约能天使", "凯尔希", "望"]
    listings = load_taobao_snapshots([targeted_path, baseline_path], roster)
    targeted_summary = build_targeted_query_summary(listings)
    signals = build_taobao_market_signals(listings, roster)

    assert targeted_summary.iloc[0]["search_precision"] == 0.5
    assert targeted_summary.iloc[0]["licensed_relevant_results"] == 1
    assert targeted_summary.iloc[0]["sales_proxy_min_total"] == 100
    assert signals.loc[signals["operator"] == "凯尔希", "taobao_observed"].item()
    assert not signals.loc[signals["operator"] == "望", "taobao_observed"].item()

    content = pd.DataFrame(
        {
            "operator": roster,
            "cross_platform_heat": [80.0, 60.0, 45.0],
            "intent_score": [75.0, 55.0, 40.0],
        }
    )
    matrix = build_content_commerce_matrix(content, signals)
    assert set(matrix["business_quadrant"])
    assert matrix["commercial_validation_priority"].notna().all()

    report_path = tmp_path / "commerce_report.md"
    write_commerce_report(listings, signals, matrix, targeted_summary, report_path)
    assert "淘宝公开商品快照" in report_path.read_text(encoding="utf-8")
