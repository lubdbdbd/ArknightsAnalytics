from __future__ import annotations

from datetime import datetime

import pandas as pd

from arknights_merch_analytics.bilibili_archive import (
    build_bilibili_archive,
    build_bilibili_archive_summaries,
    build_bilibili_campaign_attribution,
    build_bilibili_campaign_summary,
    classify_bilibili_content,
    save_bilibili_archive_figures,
    write_bilibili_archive_report,
)


def test_archive_classification_and_campaign_attribution(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            {
                "bvid": "BV1",
                "title": "《明日方舟》限定干员「甲」前瞻PV",
                "published_at": "2026-01-10T03:00:00+00:00",
                "view": 1000,
                "like": 100,
                "coin": 20,
                "favorite": 30,
                "share": 10,
                "reply": 8,
                "danmaku": 12,
            },
            {
                "bvid": "BV2",
                "title": "《明日方舟》SideStory「测试活动」活动宣传PV",
                "published_at": "2026-01-05T03:00:00+00:00",
                "view": 2000,
                "like": 150,
                "coin": 30,
                "favorite": 40,
                "share": 15,
                "reply": 10,
                "danmaku": 20,
            },
            {
                "bvid": "BV3",
                "title": "《明日方舟》EP - Test Song",
                "published_at": "2026-03-01T03:00:00+00:00",
                "view": 500,
                "like": 50,
                "coin": 10,
                "favorite": 10,
                "share": 3,
                "reply": 2,
                "danmaku": 4,
            },
        ]
    )
    archive = build_bilibili_archive(raw, datetime.fromisoformat("2026-04-01T12:00:00+08:00"))
    attributed = build_bilibili_campaign_attribution(archive)
    campaign = build_bilibili_campaign_summary(attributed)
    by_type, by_year = build_bilibili_archive_summaries(archive)

    assert classify_bilibili_content(raw.iloc[0]["title"]) == "operator_pv"
    assert classify_bilibili_content(raw.iloc[1]["title"]) == "event_pv"
    assert len(attributed) == 2
    assert set(attributed["association_type"]) == {"direct_operator", "campaign_window"}
    assert campaign.iloc[0]["bilibili_campaign_content_count"] == 2
    assert by_type["content_count"].sum() == 3
    assert by_year.iloc[0]["content_count"] == 3

    save_bilibili_archive_figures(by_type, by_year, campaign, tmp_path / "figures")
    report_path = tmp_path / "archive_report.md"
    write_bilibili_archive_report(
        archive, by_type, by_year, attributed, campaign, report_path
    )
    assert (tmp_path / "figures" / "bilibili_yearly_content_supply.png").exists()
    assert (tmp_path / "figures" / "bilibili_content_type_performance.png").exists()
    assert (tmp_path / "figures" / "bilibili_campaign_exposure.png").exists()
    assert "官号公开视频：3 条" in report_path.read_text(encoding="utf-8")


def test_archive_quarantines_known_cross_project_entity() -> None:
    raw = pd.DataFrame(
        [
            {
                "bvid": "BV-invalid",
                "title": "《明日方舟》干员「丰川祥子」技能展示PV",
                "published_at": "2026-01-10T03:00:00+00:00",
                "view": 1000,
                "like": 100,
                "coin": 20,
                "favorite": 30,
                "share": 10,
                "reply": 8,
                "danmaku": 12,
            },
            {
                "bvid": "BV-valid",
                "title": "《明日方舟》限定干员「甲」前瞻PV",
                "published_at": "2026-01-11T03:00:00+00:00",
                "view": 1000,
                "like": 100,
                "coin": 20,
                "favorite": 30,
                "share": 10,
                "reply": 8,
                "danmaku": 12,
            },
        ]
    )

    archive = build_bilibili_archive(raw)

    assert archive["bvid"].tolist() == ["BV-valid"]
