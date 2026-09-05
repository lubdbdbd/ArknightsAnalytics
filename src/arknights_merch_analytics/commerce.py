from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from arknights_merch_analytics.metrics import percentile_score


CATEGORY_PATTERNS = {
    "通行证": ("通行证", "通行认证", "身份认证卡"),
    "吧唧（徽章）": ("徽章", "吧唧", "纽扣章"),
    "毛绒玩偶": ("毛绒", "棉花娃娃", "玩偶", "山山兔", "龙泡泡", "团子", "抱枕", "靠枕"),
    "手办模玩": ("手办", "模型", "模玩", "雕像", "景品", "盲盒"),
    "亚克力制品": ("亚克力", "压克力", "立牌", "摇摇乐", "流沙砖"),
    "装饰摆件": ("摆件", "挂件", "钥匙扣", "色纸", "明信片", "挂画", "灯", "桌面装饰"),
    "日用生活": ("短袖", "卫衣", "服装", "衣服", "裙", "箱包", "书包", "水杯", "马克杯", "餐具", "文具", "笔记本", "鼠标垫", "桌垫", "键帽", "雨伞", "毛巾"),
}

OPERATOR_ALIASES = {
    "新约能天使": ("新约能天使", "圣约能天使", "能天使", "阿能"),
    "凯尔希·思衡托": ("凯尔希", "凯尔西"),
    "予愿安洁莉娜": ("安洁莉娜",),
    "维娜·维多利亚": ("维娜", "推进之王"),
    "纯烬艾雅法拉": ("艾雅法拉", "小羊"),
    "赤刃明霄陈": ("赤刃明霄陈", "陈"),
    "凛御银灰": ("银灰",),
    "归溟幽灵鲨": ("幽灵鲨",),
    "荒芜拉普兰德": ("荒芜拉普兰德", "拉普兰德"),
    "缄默德克萨斯": ("德克萨斯",),
    "斩业星熊": ("斩业星熊", "星熊"),
    "Mon3tr": ("Mon3tr", "mon3tr", "M3", "m3"),
}


def parse_price(text: str) -> float | None:
    match = re.search(r"¥\s*(\d+)(?:\s*\.\s*(\d{1,2}))?", str(text))
    if not match:
        return None
    decimals = match.group(2) or ""
    return float(f"{match.group(1)}.{decimals}" if decimals else match.group(1))


def parse_sales_proxy(text: str) -> tuple[float | None, bool]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万|千)?\s*(\+)?人收货", str(text))
    if not match:
        return None, False
    multiplier = {None: 1, "千": 1_000, "万": 10_000}[match.group(2)]
    return float(match.group(1)) * multiplier, bool(match.group(3))


def classify_category(text: str) -> str:
    lowered = str(text).lower()
    for category, keywords in CATEGORY_PATTERNS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return category
    return "其他正版周边"


def classify_rights(text: str) -> str:
    value = str(text)
    if "同人" in value or "原创" in value:
        return "同人原创"
    if any(
        keyword in value
        for keyword in ("官方正版", "官方旗舰店", "正版官谷", "正版周边", "正版卡游", "万代")
    ):
        return "官方/授权"
    return "未标明"


def classify_fulfillment(text: str) -> str:
    value = str(text)
    if any(keyword in value for keyword in ("预售", "补款", "尾款")):
        return "预售/补款"
    if any(keyword in value for keyword in ("现货", "在售", "48小时内发")):
        return "现货/在售"
    return "未标明"


def _operator_mentions(text: str, roster: Iterable[str]) -> list[str]:
    value = str(text)
    matches: list[str] = []
    for operator in roster:
        aliases = OPERATOR_ALIASES.get(operator, (operator,))
        for alias in aliases:
            if len(alias) >= 2 and alias.lower() in value.lower():
                matches.append(operator)
                break
            if len(alias) == 1 and re.search(
                rf"(?:^|[\s、，,/|]){re.escape(alias)}(?:$|[\s、，,/|])", value
            ):
                matches.append(operator)
                break
    return sorted(set(matches), key=lambda name: (-len(name), name))


def _target_relevance(text: str, target: str | None) -> float:
    if not target:
        return 1.0 if "明日方舟" in str(text) else 0.0
    value = str(text)
    aliases = {target}
    if target == "新约能天使":
        aliases.add("圣约能天使")
    if any(alias in value for alias in aliases):
        return 1.0
    if target.endswith("能天使") and "能天使" in value:
        return 0.45
    return 0.0


def load_taobao_snapshots(paths: Iterable[Path], roster: Iterable[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    operator_roster = list(roster)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        target = payload.get("target_operator")
        for item in payload.get("items", []):
            raw_text = str(item.get("title", ""))
            sales_proxy, sales_censored = parse_sales_proxy(raw_text)
            mentions = _operator_mentions(raw_text, operator_roster)
            rows.append(
                {
                    "snapshot_at": payload.get("snapshot_at"),
                    "query": payload.get("query"),
                    "query_scope": "targeted" if target else "market_baseline",
                    "target_operator": target,
                    "sort": payload.get("sort"),
                    "collection_method": payload.get("collection_method"),
                    "item_id": str(item.get("item_id", "")),
                    "url": item.get("url"),
                    "rank": int(item.get("rank", 0)),
                    "raw_text": raw_text,
                    "price": parse_price(raw_text),
                    "sales_proxy_min": sales_proxy,
                    "sales_proxy_censored": sales_censored,
                    "category": classify_category(raw_text),
                    "rights_type": classify_rights(raw_text),
                    "fulfillment_type": classify_fulfillment(raw_text),
                    "free_shipping": "包邮" in raw_text,
                    "return_insurance": "退货宝" in raw_text,
                    "fast_dispatch": "48小时内发" in raw_text,
                    "operator_mentions": "|".join(mentions),
                    "operator_mention_count": len(mentions),
                    "target_relevance": _target_relevance(raw_text, target),
                    "ip_scope": "endfield"
                    if "终末地" in raw_text
                    else ("arknights" if "明日方舟" in raw_text else "other"),
                    "source_file": path.name,
                    "is_simulated": False,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["sales_proxy_min"] = pd.to_numeric(frame["sales_proxy_min"], errors="coerce")
    frame["rank_weight"] = 1 / np.log2(frame["rank"].clip(lower=1) + 1)
    frame["numeric_sales_available"] = frame["sales_proxy_min"].notna()
    return frame.sort_values(["query_scope", "rank"]).reset_index(drop=True)


def build_targeted_query_summary(listings: pd.DataFrame) -> pd.DataFrame:
    targeted = listings[listings["query_scope"] == "targeted"].copy()
    if targeted.empty:
        return pd.DataFrame()
    summaries: list[dict[str, object]] = []
    for target, group in targeted.groupby("target_operator", dropna=False):
        relevant = group[group["target_relevance"] >= 0.75].copy()
        licensed = relevant[relevant["rights_type"] == "官方/授权"].copy()
        numeric = licensed[licensed["numeric_sales_available"]]
        total_sales = float(numeric["sales_proxy_min"].sum())
        top_ten_sales = float(numeric[numeric["rank"] <= 10]["sales_proxy_min"].sum())
        summaries.append(
            {
                "operator": target,
                "search_results": len(group),
                "relevant_results": len(relevant),
                "search_precision": len(relevant) / max(len(group), 1),
                "licensed_relevant_results": len(licensed),
                "licensed_share_of_relevant": len(licensed) / max(len(relevant), 1),
                "numeric_sales_coverage": len(numeric) / max(len(licensed), 1),
                "sales_proxy_min_total": total_sales,
                "sales_proxy_is_lower_bound": bool(numeric["sales_proxy_censored"].any()),
                "median_price": licensed["price"].median(),
                "price_p25": licensed["price"].quantile(0.25),
                "price_p75": licensed["price"].quantile(0.75),
                "category_breadth": licensed["category"].nunique(),
                "official_share": (relevant["rights_type"] == "官方/授权").mean(),
                "fanmade_share": (relevant["rights_type"] == "同人原创").mean(),
                "presale_share": (relevant["fulfillment_type"] == "预售/补款").mean(),
                "free_shipping_rate": relevant["free_shipping"].mean(),
                "return_insurance_rate": relevant["return_insurance"].mean(),
                "top10_sales_concentration": top_ten_sales / max(total_sales, 1),
            }
        )
    return pd.DataFrame(summaries)


def build_taobao_market_signals(listings: pd.DataFrame, roster: Iterable[str]) -> pd.DataFrame:
    baseline = listings[
        (listings["query_scope"] == "market_baseline")
        & (listings["ip_scope"] == "arknights")
        & (listings["rights_type"] == "官方/授权")
    ].copy()
    associations: list[dict[str, object]] = []
    for _, row in baseline.iterrows():
        mentions = [name for name in str(row["operator_mentions"]).split("|") if name]
        if not mentions:
            continue
        allocation = 1 / len(mentions)
        for operator in mentions:
            associations.append(
                {
                    "operator": operator,
                    "item_id": row["item_id"],
                    "rank": row["rank"],
                    "rank_weight": row["rank_weight"] * allocation,
                    "price": row["price"],
                    "sales_proxy_min": (row["sales_proxy_min"] or 0) * allocation
                    if pd.notna(row["sales_proxy_min"])
                    else 0,
                    "numeric_sales_available": row["numeric_sales_available"],
                    "category": row["category"],
                    "rights_type": row["rights_type"],
                    "fulfillment_type": row["fulfillment_type"],
                }
            )
    association_frame = pd.DataFrame(associations)
    roster_frame = pd.DataFrame({"operator": list(roster)})
    if association_frame.empty:
        output = roster_frame.copy()
        output["taobao_observed"] = False
        return output
    grouped = association_frame.groupby("operator", as_index=False).agg(
        organic_sku_count=("item_id", "nunique"),
        sales_proxy_min=("sales_proxy_min", "sum"),
        numeric_sales_coverage=("numeric_sales_available", "mean"),
        median_price=("price", "median"),
        average_rank=("rank", "mean"),
        market_visibility=("rank_weight", "sum"),
        category_breadth=("category", "nunique"),
        official_share=("rights_type", lambda values: (values == "官方/授权").mean()),
        fanmade_share=("rights_type", lambda values: (values == "同人原创").mean()),
        presale_share=("fulfillment_type", lambda values: (values == "预售/补款").mean()),
    )
    output = roster_frame.merge(grouped, on="operator", how="left")
    output["taobao_observed"] = output["organic_sku_count"].notna()
    numeric_columns = [
        "organic_sku_count",
        "sales_proxy_min",
        "numeric_sales_coverage",
        "median_price",
        "market_visibility",
        "category_breadth",
        "official_share",
        "fanmade_share",
        "presale_share",
    ]
    output[numeric_columns] = output[numeric_columns].fillna(0)
    observed_mask = output["taobao_observed"]
    output["supply_score"] = 0.0
    output["demand_proxy_score"] = 0.0
    output["visibility_score"] = 0.0
    output["price_power_score"] = 0.0
    output.loc[observed_mask, "supply_score"] = percentile_score(
        output.loc[observed_mask, "organic_sku_count"]
    )
    output.loc[observed_mask, "demand_proxy_score"] = percentile_score(
        np.log1p(output.loc[observed_mask, "sales_proxy_min"])
    )
    output.loc[observed_mask, "visibility_score"] = percentile_score(
        output.loc[observed_mask, "market_visibility"]
    )
    output.loc[observed_mask, "price_power_score"] = percentile_score(
        output.loc[observed_mask, "median_price"]
    )
    output["assortment_score"] = (output["category_breadth"] / len(CATEGORY_PATTERNS) * 100).clip(upper=100)
    output["commercial_heat_score"] = (
        0.35 * output["demand_proxy_score"]
        + 0.25 * output["supply_score"]
        + 0.20 * output["visibility_score"]
        + 0.10 * output["price_power_score"]
        + 0.10 * output["assortment_score"]
    )
    output["commerce_confidence_score"] = (
        10
        + 20 * output["taobao_observed"].astype(int)
        + 30 * output["numeric_sales_coverage"]
        + 40 * np.minimum(output["organic_sku_count"], 5) / 5
    ).clip(upper=100)
    output["commerce_data_grade"] = pd.cut(
        output["commerce_confidence_score"],
        bins=[-np.inf, 45, 65, 80, np.inf],
        labels=["D", "C", "B", "A"],
    ).astype(str)
    output = output.sort_values(
        ["commercial_heat_score", "commerce_confidence_score"], ascending=False
    ).reset_index(drop=True)
    output["commerce_rank"] = np.arange(1, len(output) + 1)
    return output


def build_content_commerce_matrix(
    content_heat: pd.DataFrame, commerce_signals: pd.DataFrame
) -> pd.DataFrame:
    frame = content_heat.merge(commerce_signals, on="operator", how="left")
    frame["taobao_observed"] = frame["taobao_observed"].fillna(False)
    frame["commercial_heat_score"] = frame["commercial_heat_score"].fillna(0)
    observed = frame[frame["taobao_observed"]]
    commerce_threshold = observed["commercial_heat_score"].median() if not observed.empty else 50
    content_threshold = frame["cross_platform_heat"].median()
    frame["business_quadrant"] = np.select(
        [
            (frame["cross_platform_heat"] >= content_threshold)
            & (frame["commercial_heat_score"] >= commerce_threshold),
            (frame["cross_platform_heat"] >= content_threshold)
            & (frame["commercial_heat_score"] < commerce_threshold),
            (frame["cross_platform_heat"] < content_threshold)
            & (frame["commercial_heat_score"] >= commerce_threshold),
        ],
        ["核心商业角色", "内容热、商业供给待验证", "内容长尾但商品信号较强"],
        default="低成本观察",
    )
    frame["content_commerce_gap"] = (
        frame["cross_platform_heat"] - frame["commercial_heat_score"]
    )
    frame["commercial_validation_priority"] = (
        0.45 * frame["cross_platform_heat"]
        + 0.25 * frame["intent_score"]
        + 0.20 * (100 - frame["commercial_heat_score"])
        + 0.10 * (100 - frame["commerce_confidence_score"].fillna(25))
    )
    return frame.sort_values("commercial_validation_priority", ascending=False).reset_index(drop=True)
