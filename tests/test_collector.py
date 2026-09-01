from __future__ import annotations

import json
from pathlib import Path

import pytest

from arknights_merch_analytics.collector import (
    SourceRateLimited,
    _request_json,
    clean_title,
    collect_bilibili_related,
    collect_weibo_sina_mirror,
    collect_xhs_brand_snapshots,
    parse_human_count,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, *_args, **_kwargs) -> FakeResponse:
        return self.response


def test_clean_title_removes_highlight_markup() -> None:
    assert clean_title('《<em class="keyword">明日方舟</em>》') == "《明日方舟》"


def test_request_stops_on_rate_limit() -> None:
    with pytest.raises(SourceRateLimited):
        _request_json(FakeSession(FakeResponse(412, {})), "https://example.test", {})


def test_request_rejects_api_error() -> None:
    with pytest.raises(RuntimeError, match="Bilibili API error"):
        _request_json(
            FakeSession(FakeResponse(200, {"code": -1, "message": "bad request"})),
            "https://example.test",
            {},
        )


def test_parse_human_count_supports_rounded_display_values() -> None:
    assert parse_human_count("2.3万") == 23_000
    assert parse_human_count("2.3涓�") == 23_000
    assert parse_human_count("1,024") == 1_024


class StaticResponse:
    def __init__(self, text: str, payload: dict[str, object] | None = None) -> None:
        self.status_code = 200
        self.text = text
        self.content = text.encode("gb18030")
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_collect_weibo_public_mirror(monkeypatch, tmp_path: Path) -> None:
    html = """
    <a class="post-link" href="/news/detail/123.html"><article class="post">
      <div>明日方舟Arknights 2026-08-01 11:00</div>
      <div class="post-text">《明日方舟》干员「甲」技能展示PV</div>
      <div class="post-actions"><div class="action">100</div><div class="action">20</div><div class="action">2.3万</div></div>
    </article></a>
    """
    monkeypatch.setattr("arknights_merch_analytics.collector.requests.get", lambda *_a, **_k: StaticResponse(html))
    output = tmp_path / "weibo.json"
    rows = collect_weibo_sina_mirror("1", output)
    assert rows[0]["like"] == 23_000
    assert json.loads(output.read_text(encoding="utf-8"))[0]["post_id"] == "123"


def test_collect_xhs_brand_snapshot(monkeypatch, tmp_path: Path) -> None:
    html = """
    <table><tr><td>7</td><td>明日方舟</td><td>34540</td><td>464.92万</td>
    <td>392.09万</td><td>48.63万</td><td>24.20万</td><td>详情</td></tr></table>
    """
    response = StaticResponse("")
    response.text = html
    monkeypatch.setattr("arknights_merch_analytics.collector.requests.get", lambda *_a, **_k: response)
    rows = collect_xhs_brand_snapshots(
        [{"window": "weekly", "snapshot_date": "2026-08-09", "url": "https://example.test"}],
        tmp_path / "xhs.json",
    )
    assert rows[0]["interaction_total"] == 4_649_200


def test_collect_bilibili_related_operator_post(monkeypatch, tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([{"bvid": "BVseed", "title": "seed"}]), encoding="utf-8")
    payload = {
        "code": 0,
        "data": [
            {
                "bvid": "BVoperator",
                "title": "《明日方舟》干员「甲」技能展示PV",
                "pubdate": 1_700_000_000,
                "owner": {"mid": 161775300, "name": "明日方舟"},
                "stat": {"view": 1000, "like": 100, "coin": 10, "favorite": 20, "share": 5, "reply": 6, "danmaku": 7},
            }
        ],
    }

    class RelatedSession:
        headers: dict[str, str] = {}

        def get(self, *_args, **_kwargs) -> StaticResponse:
            return StaticResponse("", payload)

    monkeypatch.setattr("arknights_merch_analytics.collector.requests.Session", RelatedSession)
    output = tmp_path / "bilibili.json"
    rows = collect_bilibili_related(seed, output, 161775300, max_requests=1, request_interval_seconds=0)
    assert rows[0]["bvid"] == "BVoperator"
