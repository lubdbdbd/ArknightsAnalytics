from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import requests


SEARCH_ENDPOINT = "https://api.bilibili.com/x/web-interface/search/type"
VIEW_ENDPOINT = "https://api.bilibili.com/x/web-interface/view"
TAG_RE = re.compile(r"<[^>]+>")


class SourceRateLimited(RuntimeError):
    """Raised when a public source requests that collection stop."""


@dataclass(frozen=True)
class BilibiliConfig:
    official_mid: int
    official_name: str
    search_queries: tuple[str, ...]
    max_pages_per_query: int = 3
    page_size: int = 50
    request_interval_seconds: float = 1.5
    start_date: str = "2024-01-01"


def clean_title(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value or "")).strip()


def _request_json(session: requests.Session, url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=20)
    if response.status_code in {412, 429}:
        raise SourceRateLimited(
            f"Bilibili returned HTTP {response.status_code}; stop collection and retry later."
        )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in {0, None}:
        raise RuntimeError(f"Bilibili API error: {payload.get('code')} {payload.get('message')}")
    return payload


def collect_bilibili(config: BilibiliConfig, output_path: Path) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; ArknightsMerchAnalytics/0.1; research)",
            "Referer": "https://search.bilibili.com/",
        }
    )
    candidates: dict[str, dict[str, Any]] = {}
    for query in config.search_queries:
        for page in range(1, config.max_pages_per_query + 1):
            payload = _request_json(
                session,
                SEARCH_ENDPOINT,
                {
                    "search_type": "video",
                    "keyword": query,
                    "page": page,
                    "page_size": config.page_size,
                    "order": "pubdate",
                },
            )
            results = payload.get("data", {}).get("result") or []
            if not results:
                break
            for item in results:
                if int(item.get("mid") or 0) != config.official_mid:
                    continue
                bvid = item.get("bvid")
                if bvid:
                    candidates[bvid] = item
            time.sleep(config.request_interval_seconds)

    collected: list[dict[str, Any]] = []
    start_timestamp = datetime.fromisoformat(config.start_date).replace(tzinfo=timezone.utc).timestamp()
    for bvid in sorted(candidates):
        summary = candidates[bvid]
        if float(summary.get("pubdate") or 0) < start_timestamp:
            continue
        payload = _request_json(session, VIEW_ENDPOINT, {"bvid": bvid})
        item = payload["data"]
        stat = item.get("stat") or {}
        published = datetime.fromtimestamp(item["pubdate"], tz=timezone.utc).astimezone()
        collected.append(
            {
                "bvid": bvid,
                "title": clean_title(item.get("title", "")),
                "owner_mid": item.get("owner", {}).get("mid"),
                "owner_name": item.get("owner", {}).get("name"),
                "published_at": published.isoformat(),
                "view": stat.get("view", 0),
                "like": stat.get("like", 0),
                "coin": stat.get("coin", 0),
                "favorite": stat.get("favorite", 0),
                "share": stat.get("share", 0),
                "reply": stat.get("reply", 0),
                "danmaku": stat.get("danmaku", 0),
                "source_url": f"https://www.bilibili.com/video/{bvid}",
                "source_type": "public_aggregate",
                "collected_at": datetime.now().astimezone().isoformat(),
            }
        )
        time.sleep(config.request_interval_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")
    return collected


def load_config(path: Path) -> BilibiliConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))["bilibili"]
    return BilibiliConfig(
        official_mid=int(raw["official_mid"]),
        official_name=str(raw["official_name"]),
        search_queries=tuple(raw["search_queries"]),
        max_pages_per_query=int(raw.get("max_pages_per_query", 3)),
        page_size=int(raw.get("page_size", 50)),
        request_interval_seconds=float(raw.get("request_interval_seconds", 1.5)),
        start_date=str(raw.get("start_date", "2024-01-01")),
    )

