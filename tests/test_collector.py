from __future__ import annotations

import json

import pytest

from arknights_merch_analytics.collector import SourceRateLimited, _request_json, clean_title


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

