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
from bs4 import BeautifulSoup


SEARCH_ENDPOINT = "https://api.bilibili.com/x/web-interface/search/type"
VIEW_ENDPOINT = "https://api.bilibili.com/x/web-interface/view"
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2} \d{2}:\d{2}")


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


def parse_human_count(value: str | int | float | None) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"--", "-"}:
        return 0
    multiplier = 1
    if "万" in text or "涓" in text:
        multiplier = 10_000
    elif "亿" in text:
        multiplier = 100_000_000
    number = re.search(r"\d+(?:\.\d+)?", text)
    return int(round(float(number.group()) * multiplier)) if number else 0


def _fix_sina_text(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    try:
        repaired = text.encode("gb18030", errors="replace").decode("utf-8", errors="replace")
    except UnicodeError:
        return text
    suspicious = sum(text.count(token) for token in ("鏄", "銆", "鈥", "寰", "绔", "涓"))
    return repaired if suspicious else text


def collect_bilibili_related(
    seed_path: Path,
    output_path: Path,
    official_mid: int,
    max_official_videos: int = 450,
    max_requests: int = 260,
    request_interval_seconds: float = 0.12,
) -> list[dict[str, Any]]:
    seeds = json.loads(seed_path.read_text(encoding="utf-8"))
    videos = {item["bvid"]: item for item in seeds if item.get("bvid")}
    queue = list(videos)
    queued = set(queue)
    visited: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (ArknightsMerchAnalytics/0.2)"})
    requests_made = 0

    while queue and requests_made < max_requests and len(videos) < max_official_videos:
        bvid = queue.pop(0)
        if bvid in visited:
            continue
        visited.add(bvid)
        requests_made += 1
        response = session.get(
            "https://api.bilibili.com/x/web-interface/archive/related",
            params={"bvid": bvid},
            headers={"Referer": f"https://www.bilibili.com/video/{bvid}"},
            timeout=20,
        )
        if response.status_code in {412, 429}:
            raise SourceRateLimited(
                f"Bilibili returned HTTP {response.status_code}; cached output was not overwritten."
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            continue
        for item in payload.get("data") or []:
            owner = item.get("owner") or {}
            if int(owner.get("mid") or 0) != official_mid:
                continue
            related_bvid = item.get("bvid")
            if not related_bvid:
                continue
            stat = item.get("stat") or {}
            videos[related_bvid] = {
                "bvid": related_bvid,
                "title": clean_title(item.get("title", "")),
                "owner_mid": owner.get("mid"),
                "owner_name": owner.get("name"),
                "published_at": datetime.fromtimestamp(
                    item.get("pubdate", 0), tz=timezone.utc
                ).isoformat(),
                "view": stat.get("view", 0),
                "like": stat.get("like", 0),
                "coin": stat.get("coin", 0),
                "favorite": stat.get("favorite", 0),
                "share": stat.get("share", 0),
                "reply": stat.get("reply", 0),
                "danmaku": stat.get("danmaku", 0),
                "source_url": f"https://www.bilibili.com/video/{related_bvid}",
                "source_type": "official_public_aggregate",
                "metric_precision": "exact_api",
                "collected_at": datetime.now().astimezone().isoformat(),
            }
            if related_bvid not in queued and related_bvid not in visited:
                queue.append(related_bvid)
                queued.add(related_bvid)
        time.sleep(request_interval_seconds)

    operator_videos = [
        item
        for item in videos.values()
        if re.search(r"(?:限定)?干员[「『“\"]([^」』”\"]+)[」』”\"]", item["title"])
    ]
    operator_videos.sort(key=lambda item: item["published_at"], reverse=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(operator_videos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return operator_videos


def collect_weibo_sina_mirror(uid: str, output_path: Path) -> list[dict[str, Any]]:
    source_url = f"https://www.sina.cn/media/{uid}"
    response = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    document = response.content.decode("gb18030", errors="replace")
    soup = BeautifulSoup(document, "html.parser")
    rows: list[dict[str, Any]] = []
    for link in soup.select("a.post-link"):
        article = link.select_one("article.post")
        text_node = link.select_one(".post-text")
        actions = link.select(".post-actions .action")
        if article is None or text_node is None or len(actions) < 3:
            continue
        raw_text = article.get_text(" ", strip=True)
        date_match = DATE_RE.search(raw_text)
        if not date_match:
            continue
        body = _fix_sina_text(text_node.get_text(" ", strip=True))
        href = link.get("href", "")
        rows.append(
            {
                "post_id": Path(href).stem,
                "text": body,
                "published_at": datetime.strptime(
                    date_match.group(), "%Y-%m-%d %H:%M"
                ).astimezone().isoformat(),
                "repost": parse_human_count(actions[0].get_text(" ", strip=True)),
                "comment": parse_human_count(actions[1].get_text(" ", strip=True)),
                "like": parse_human_count(actions[2].get_text(" ", strip=True)),
                "source_url": f"https://www.sina.cn{href}",
                "canonical_account_url": "https://weibo.com/arknights",
                "source_type": "official_account_public_mirror",
                "metric_precision": "display_exact_or_rounded",
                "collected_at": datetime.now().astimezone().isoformat(),
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def collect_xhs_brand_snapshots(
    snapshots: Iterable[dict[str, Any]], output_path: Path, brand_name: str = "明日方舟"
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        response = requests.get(
            snapshot["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=20
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cells: list[str] | None = None
        for table_row in soup.select("tr"):
            values = [cell.get_text(" ", strip=True) for cell in table_row.select("td")]
            if any(brand_name in value for value in values):
                cells = values
                break
        if not cells or len(cells) < 7:
            continue
        rows.append(
            {
                "platform": "xiaohongshu",
                "scope": "brand_ecosystem",
                "window": snapshot["window"],
                "snapshot_date": snapshot["snapshot_date"],
                "rank": parse_human_count(cells[0]),
                "note_count": parse_human_count(cells[2]),
                "interaction_total": parse_human_count(cells[3]),
                "like_total": parse_human_count(cells[4]),
                "favorite_total": parse_human_count(cells[5]),
                "comment_total": parse_human_count(cells[6]),
                "source_url": snapshot["url"],
                "source_type": "public_third_party_brand_index",
                "metric_precision": "display_rounded",
                "collected_at": datetime.now().astimezone().isoformat(),
            }
        )
        time.sleep(0.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
