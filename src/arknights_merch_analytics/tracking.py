from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _prepare_observations(listings: pd.DataFrame) -> pd.DataFrame:
    if listings.empty:
        return listings.copy()
    frame = listings.copy()
    frame["snapshot_at"] = pd.to_datetime(frame["snapshot_at"], errors="coerce", utc=True)
    frame = frame[
        frame["item_id"].fillna("").astype(str).ne("")
        & frame["snapshot_at"].notna()
        & frame["ip_scope"].eq("arknights")
        & (
            frame["query_scope"].ne("targeted")
            | frame["target_relevance"].fillna(0).ge(0.50)
        )
    ].copy()
    frame["item_id"] = frame["item_id"].astype(str)
    frame["observed_date"] = frame["snapshot_at"].dt.date.astype(str)
    frame = frame.sort_values(
        ["item_id", "snapshot_at", "target_relevance", "rank"],
        ascending=[True, True, False, True],
    )
    return frame.drop_duplicates(["item_id", "observed_date"], keep="first")


def build_tracking_registry(
    listings: pd.DataFrame, cadence_days: int = 7
) -> pd.DataFrame:
    observations = _prepare_observations(listings)
    if observations.empty:
        return pd.DataFrame()
    latest = observations.sort_values("snapshot_at").groupby("item_id", as_index=False).tail(1)
    first_seen = observations.groupby("item_id")["snapshot_at"].min()
    observation_count = observations.groupby("item_id")["observed_date"].nunique()
    latest = latest.copy()
    latest["first_seen_at"] = latest["item_id"].map(first_seen)
    latest["observation_count"] = latest["item_id"].map(observation_count).astype(int)
    latest["operator"] = latest["target_operator"].fillna("")
    missing_operator = latest["operator"].eq("")
    latest.loc[missing_operator, "operator"] = (
        latest.loc[missing_operator, "operator_mentions"].fillna("").str.split("|").str[0]
    )
    latest["operator"] = latest["operator"].replace("", "未归因")
    latest["next_capture_due"] = (
        latest["snapshot_at"] + pd.to_timedelta(cadence_days, unit="D")
    ).dt.date.astype(str)
    latest["tracking_status"] = np.where(
        latest["observation_count"].ge(2), "tracking_active", "baseline_pending_recapture"
    )
    latest["sales_metric_note"] = np.where(
        latest["sales_proxy_censored"].fillna(False),
        "displayed_lower_bound_censored",
        "displayed_public_proxy",
    )
    columns = [
        "item_id",
        "operator",
        "category",
        "raw_text",
        "url",
        "query",
        "query_scope",
        "first_seen_at",
        "snapshot_at",
        "observation_count",
        "rank",
        "price",
        "sales_proxy_min",
        "sales_metric_note",
        "rights_type",
        "fulfillment_type",
        "next_capture_due",
        "tracking_status",
    ]
    output = latest[columns].copy()
    output["first_seen_at"] = output["first_seen_at"].map(
        lambda value: value.isoformat() if pd.notna(value) else ""
    )
    output["snapshot_at"] = output["snapshot_at"].map(
        lambda value: value.isoformat() if pd.notna(value) else ""
    )
    return output.sort_values(
        ["tracking_status", "sales_proxy_min", "rank"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def build_sku_timeseries_metrics(listings: pd.DataFrame) -> pd.DataFrame:
    observations = _prepare_observations(listings)
    if observations.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for item_id, group in observations.groupby("item_id"):
        ordered = group.sort_values("snapshot_at")
        first = ordered.iloc[0]
        last = ordered.iloc[-1]
        days_observed = max((last["snapshot_at"] - first["snapshot_at"]).days, 0)
        price_delta = (
            float(last["price"] - first["price"])
            if pd.notna(first["price"]) and pd.notna(last["price"])
            else np.nan
        )
        sales_delta = (
            float(last["sales_proxy_min"] - first["sales_proxy_min"])
            if pd.notna(first["sales_proxy_min"]) and pd.notna(last["sales_proxy_min"])
            else np.nan
        )
        if ordered["observed_date"].nunique() == 1:
            lifecycle = "baseline_pending_recapture"
        elif pd.isna(sales_delta):
            lifecycle = "insufficient_sales_signal"
        elif sales_delta < 0:
            lifecycle = "data_anomaly_review"
        elif sales_delta > 0:
            lifecycle = "growth_observed"
        else:
            lifecycle = "stable_lower_bound"
        observation_count = int(ordered["observed_date"].nunique())
        if observation_count >= 4 and days_observed >= 21:
            evidence_grade = "A"
        elif observation_count >= 3 and days_observed >= 14:
            evidence_grade = "B"
        elif observation_count >= 2 and days_observed >= 7:
            evidence_grade = "C"
        else:
            evidence_grade = "D"
        target_operator = last["target_operator"]
        operator = (
            str(target_operator)
            if pd.notna(target_operator) and str(target_operator).strip()
            else str(last["operator_mentions"]).split("|")[0]
        )
        if not operator or operator.lower() == "nan":
            operator = "未归因"
        rows.append(
            {
                "item_id": item_id,
                "operator": operator,
                "category": last["category"],
                "first_seen_at": first["snapshot_at"].isoformat(),
                "last_seen_at": last["snapshot_at"].isoformat(),
                "observation_count": observation_count,
                "days_observed": days_observed,
                "first_price": first["price"],
                "last_price": last["price"],
                "price_delta": price_delta,
                "price_change_rate": price_delta / first["price"]
                if pd.notna(price_delta) and first["price"] != 0
                else np.nan,
                "first_sales_proxy_min": first["sales_proxy_min"],
                "last_sales_proxy_min": last["sales_proxy_min"],
                "sales_proxy_delta": sales_delta,
                "sales_proxy_delta_per_day": sales_delta / days_observed
                if pd.notna(sales_delta) and days_observed > 0
                else np.nan,
                "first_rank": first["rank"],
                "last_rank": last["rank"],
                "rank_improvement": first["rank"] - last["rank"],
                "sales_proxy_censored_any": bool(ordered["sales_proxy_censored"].fillna(False).any()),
                "lifecycle_signal": lifecycle,
                "timeseries_evidence_grade": evidence_grade,
                "is_real_public_data": True,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["timeseries_evidence_grade", "sales_proxy_delta", "last_sales_proxy_min"],
        ascending=[True, False, False],
        na_position="last",
    ).reset_index(drop=True)


def write_tracking_report(
    registry: pd.DataFrame, metrics: pd.DataFrame, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grade_counts = (
        metrics["timeseries_evidence_grade"].value_counts().sort_index().to_dict()
        if not metrics.empty
        else {}
    )
    active = metrics[metrics["observation_count"] >= 2] if not metrics.empty else metrics
    lines = [
        "# 固定 SKU 时间序列追踪报告",
        "",
        "> 数据仅来自低频人工核验的公开商品快照；销量字段是公开展示下界代理，不是精确成交量。",
        "",
        "## 当前状态",
        "",
        f"- 固定商品注册表：{len(registry)} 个 SKU。",
        f"- 已完成至少两期复采：{len(active)} 个 SKU。",
        f"- 证据等级分布：{grade_counts or {'D': len(metrics)}}。",
        "- A/B/C 级分别要求至少 4/3/2 期且跨越 21/14/7 天；单期样本只能标记为 D 级基线。",
        "",
        "## 采样规范",
        "",
        "1. 固定商品 ID 和 URL，每 7 天在相同地区、账号和排序条件下复采。",
        "2. 记录价格、公开收货人数档位、自然排名、在售状态和服务标签。",
        "3. 同一商品同一天出现多次时保留相关性最高、自然排名最靠前的一条。",
        "4. 公开人数下降、商品 ID 变化或跨 IP 命中进入数据异常队列，不直接解释为销量下降。",
        "5. 至少达到 C 级后才讨论增长方向，达到 B 级后才进入选品验证证据。",
        "",
        "## 可复采队列 Top 20",
        "",
        registry.head(20).to_markdown(index=False, floatfmt=".2f") if not registry.empty else "暂无可追踪商品。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
