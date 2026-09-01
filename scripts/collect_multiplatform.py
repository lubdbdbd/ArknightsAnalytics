from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.collector import (
    SourceRateLimited,
    collect_bilibili_related,
    collect_weibo_sina_mirror,
    collect_xhs_brand_snapshots,
)


def main() -> None:
    config = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    public_dir = ROOT / "data" / "public"
    bilibili = config["bilibili"]
    try:
        rows = collect_bilibili_related(
            public_dir / "bilibili_official_pv_snapshot.json",
            public_dir / "bilibili_official_operator_posts.json",
            official_mid=int(bilibili["official_mid"]),
            max_official_videos=int(bilibili["related_max_official_videos"]),
            max_requests=int(bilibili["related_max_requests"]),
            request_interval_seconds=float(bilibili["request_interval_seconds"]),
        )
        print(f"Bilibili: {len(rows)} operator posts")
    except SourceRateLimited as error:
        print(f"Bilibili skipped: {error}")

    weibo = config["weibo"]
    rows = collect_weibo_sina_mirror(
        str(weibo["official_uid"]), public_dir / "weibo_official_recent_posts.json"
    )
    print(f"Weibo: {len(rows)} recent official posts")

    xhs = config["xiaohongshu"]
    rows = collect_xhs_brand_snapshots(
        xhs["brand_snapshot_pages"], public_dir / "xiaohongshu_brand_snapshots.json"
    )
    print(f"Xiaohongshu ecosystem: {len(rows)} snapshots")


if __name__ == "__main__":
    main()
