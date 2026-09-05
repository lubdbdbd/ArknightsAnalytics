from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


DEMAND_SCENARIOS = {
    "balanced": {"content": 0.32, "survey": 0.28, "skland": 0.25, "commerce": 0.15},
    "content_led": {"content": 0.50, "survey": 0.20, "skland": 0.20, "commerce": 0.10},
    "survey_led": {"content": 0.20, "survey": 0.50, "skland": 0.20, "commerce": 0.10},
    "community_led": {"content": 0.20, "survey": 0.20, "skland": 0.50, "commerce": 0.10},
    "commerce_led": {"content": 0.20, "survey": 0.20, "skland": 0.15, "commerce": 0.45},
}


def _percentile_available(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    result = pd.Series(np.nan, index=values.index, dtype=float)
    available = numeric.notna()
    if not available.any():
        return result
    if numeric.loc[available].nunique() <= 1:
        result.loc[available] = 50.0
    else:
        result.loc[available] = numeric.loc[available].rank(method="average", pct=True) * 100
    return result


def _row_weighted_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    numerator = pd.Series(0.0, index=frame.index)
    denominator = pd.Series(0.0, index=frame.index)
    for source, weight in weights.items():
        column = f"{source}_signal"
        available = frame[column].notna()
        numerator.loc[available] += frame.loc[available, column] * weight
        denominator.loc[available] += weight
    return numerator / denominator.replace(0, np.nan)


def build_operator_demand_fusion(
    heat: pd.DataFrame,
    survey: pd.DataFrame,
    skland: pd.DataFrame,
    commerce: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    heat_columns = [
        "operator",
        "cross_platform_heat",
        "merch_opportunity_score",
        "confidence_score",
        "bilibili_campaign_views",
        "bilibili_weighted_campaign_views",
    ]
    survey_columns = [
        "operator",
        "preference_mentions",
        "weighted_preference_score",
        "first_choice_count",
        "mention_share",
    ]
    commerce_columns = [
        "operator",
        "taobao_observed",
        "organic_sku_count",
        "sales_proxy_min",
        "median_price",
        "commercial_heat_score",
        "commerce_confidence_score",
    ]
    frame = heat[[column for column in heat_columns if column in heat]].merge(
        survey[[column for column in survey_columns if column in survey]], on="operator", how="outer"
    )
    frame = frame.merge(skland, on="operator", how="outer")
    frame = frame.merge(
        commerce[[column for column in commerce_columns if column in commerce]],
        on="operator",
        how="left",
    )

    frame["content_signal"] = (
        0.65 * _percentile_available(frame.get("cross_platform_heat"))
        + 0.35 * _percentile_available(frame.get("merch_opportunity_score"))
    )
    frame["survey_signal"] = (
        0.60 * _percentile_available(frame.get("weighted_preference_score"))
        + 0.25 * _percentile_available(frame.get("first_choice_count"))
        + 0.15 * _percentile_available(frame.get("mention_share"))
    )
    frame["skland_signal"] = (
        0.60 * _percentile_available(np.log1p(frame.get("skland_total_views")))
        + 0.25 * _percentile_available(np.log1p(frame.get("skland_total_engagement")))
        + 0.15 * _percentile_available(frame.get("skland_content_count"))
    )
    taobao_observed = (
        frame.get("taobao_observed", pd.Series(False, index=frame.index))
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    frame["commerce_signal"] = _percentile_available(
        frame.get("commercial_heat_score").where(taobao_observed)
    )

    sensitivity_rows: list[pd.DataFrame] = []
    for scenario, weights in DEMAND_SCENARIOS.items():
        scenario_frame = frame[["operator"]].copy()
        scenario_frame["scenario"] = scenario
        scenario_frame["scenario_score"] = _row_weighted_score(frame, weights)
        scenario_frame["scenario_rank"] = scenario_frame["scenario_score"].rank(
            method="min", ascending=False
        )
        sensitivity_rows.append(scenario_frame)
    sensitivity = pd.concat(sensitivity_rows, ignore_index=True)
    rank_stability = sensitivity.groupby("operator", as_index=False).agg(
        scenario_rank_best=("scenario_rank", "min"),
        scenario_rank_worst=("scenario_rank", "max"),
        scenario_rank_mean=("scenario_rank", "mean"),
        scenario_rank_std=("scenario_rank", "std"),
    )
    rank_stability["scenario_rank_range"] = (
        rank_stability["scenario_rank_worst"] - rank_stability["scenario_rank_best"]
    )
    frame = frame.merge(rank_stability, on="operator", how="left")
    balanced = sensitivity.loc[sensitivity["scenario"].eq("balanced"), ["operator", "scenario_score"]]
    frame = frame.merge(balanced, on="operator", how="left").rename(
        columns={"scenario_score": "demand_score"}
    )

    source_columns = ["content_signal", "survey_signal", "skland_signal", "commerce_signal"]
    frame["evidence_source_count"] = frame[source_columns].notna().sum(axis=1)
    content_conf = pd.to_numeric(frame.get("confidence_score"), errors="coerce")
    survey_conf = (35 + pd.to_numeric(frame.get("preference_mentions"), errors="coerce") * 2.5).clip(
        upper=100
    )
    skland_conf = (
        pd.to_numeric(frame.get("skland_content_count"), errors="coerce") / 20 * 100
    ).clip(upper=100)
    commerce_conf = pd.to_numeric(frame.get("commerce_confidence_score"), errors="coerce").where(
        taobao_observed
    )
    confidence_sources = pd.concat(
        [content_conf, survey_conf, skland_conf, commerce_conf], axis=1
    )
    frame["evidence_confidence"] = (
        0.6 * confidence_sources.mean(axis=1, skipna=True)
        + 0.4 * frame["evidence_source_count"] / len(source_columns) * 100
    ).round(2)
    frame["demand_score"] = frame["demand_score"].round(2)
    frame["demand_rank"] = frame["demand_score"].rank(method="min", ascending=False).astype("Int64")
    percentile_rank = frame["demand_score"].rank(method="average", pct=True, ascending=False)
    frame["demand_tier"] = np.select(
        [percentile_rank <= 0.15, percentile_rank <= 0.35, percentile_rank <= 0.65],
        ["核心商业角色", "增长验证角色", "小批量测试角色"],
        default="低成本观察角色",
    )
    frame["decision_note"] = np.select(
        [
            frame["evidence_source_count"].ge(4) & frame["scenario_rank_range"].le(8),
            frame["survey_signal"].ge(70) & frame["commerce_signal"].isna(),
            frame["content_signal"].ge(70) & frame["survey_signal"].lt(45),
        ],
        [
            "多源证据一致，可进入商品方案评审",
            "用户意愿较强但供给样本不足，优先补采正版SKU",
            "内容热度高于购买意愿，先做概念测试而非直接备货",
        ],
        default="保留观察并补充证据",
    )
    frame = frame.sort_values(["demand_score", "evidence_confidence"], ascending=False).reset_index(
        drop=True
    )
    sensitivity = sensitivity.merge(rank_stability, on="operator", how="left").sort_values(
        ["scenario", "scenario_rank"]
    )
    return frame, sensitivity


def build_category_price_architecture(
    category_summary: pd.DataFrame,
    category_prices: pd.DataFrame,
    taobao: pd.DataFrame,
    sku_master: pd.DataFrame,
) -> pd.DataFrame:
    prices = category_prices.copy()
    prices = prices.loc[~prices.get("is_simulated", False).astype(bool)]
    survey_price = prices.groupby("category", as_index=False).agg(
        survey_price_p25=("price_midpoint_proxy", lambda value: value.quantile(0.25)),
        survey_price_p50=("price_midpoint_proxy", "median"),
        survey_price_p75=("price_midpoint_proxy", lambda value: value.quantile(0.75)),
        price_response_count=("response_id", "nunique"),
    )
    observed = taobao.loc[
        (~taobao["is_simulated"].astype(bool)) & taobao["rights_type"].eq("官方/授权")
    ].copy()
    observed = observed.drop_duplicates(["item_id", "category"])
    market = observed.groupby("category", as_index=False).agg(
        observed_official_sku_count=("item_id", "nunique"),
        observed_market_price_min=("price", "min"),
        observed_market_price_median=("price", "median"),
        observed_market_price_max=("price", "max"),
        observed_sales_proxy_min=("sales_proxy_min", "sum"),
    )
    simulated_economics = sku_master.groupby("category", as_index=False).agg(
        simulated_sku_count=("sku_id", "nunique"),
        simulated_price_median=("price", "median"),
        simulated_unit_cost_median=("unit_cost", "median"),
    )
    simulated_economics["simulated_gross_margin_rate"] = (
        simulated_economics["simulated_price_median"]
        - simulated_economics["simulated_unit_cost_median"]
    ) / simulated_economics["simulated_price_median"].replace(0, np.nan)

    frame = category_summary.merge(survey_price, on="category", how="outer")
    frame = frame.merge(market, on="category", how="left").merge(
        simulated_economics, on="category", how="left"
    )
    frame["category_demand_score"] = (
        0.40 * _percentile_available(frame["high_intent_share"])
        + 0.25 * _percentile_available(frame["selection_share"])
        + 0.20 * _percentile_available(frame["purchase_intent_mean"])
        + 0.15 * _percentile_available(frame["buyer_share"])
    ).round(2)
    frame["market_vs_acceptance_gap_pct"] = (
        (frame["observed_market_price_median"] - frame["survey_price_p50"])
        / frame["survey_price_p50"].replace(0, np.nan)
        * 100
    ).round(2)
    frame["recommended_entry_price"] = frame["survey_price_p25"].round(0)
    frame["recommended_core_price"] = frame["survey_price_p50"].round(0)
    frame["recommended_premium_price"] = frame["survey_price_p75"].round(0)
    frame["market_evidence_grade"] = np.select(
        [
            frame["observed_official_sku_count"].fillna(0).ge(5),
            frame["observed_official_sku_count"].fillna(0).ge(2),
            frame["observed_official_sku_count"].fillna(0).ge(1),
        ],
        ["B", "C", "D"],
        default="N/A",
    )
    frame["pricing_action"] = np.select(
        [
            frame["observed_official_sku_count"].fillna(0).eq(0),
            frame["market_vs_acceptance_gap_pct"].gt(25),
            frame["market_vs_acceptance_gap_pct"].lt(-25),
            frame["high_intent_share"].ge(0.40),
        ],
        [
            "缺少正版市场样本，先补采报价与竞品价格",
            "市场价高于用户中位接受价，优先降规格或做入门款",
            "市场价低于用户接受区间，可测试材质升级或套装",
            "需求较强，按入门/核心/高配三档做概念验证",
        ],
        default="维持核心价，小批量验证",
    )
    frame["is_simulated_economics"] = True
    return frame.sort_values("category_demand_score", ascending=False).reset_index(drop=True)


def build_operator_category_portfolio(
    demand: pd.DataFrame, operator_category: pd.DataFrame
) -> pd.DataFrame:
    frame = operator_category.merge(
        demand[["operator", "demand_score", "demand_rank", "demand_tier", "evidence_confidence"]],
        on="operator",
        how="left",
    )
    frame["intent_signal"] = (
        0.65 * _percentile_available(frame["high_intent_share"])
        + 0.35 * _percentile_available(frame["purchase_intent_mean"])
    )
    sample_factor = np.minimum(pd.to_numeric(frame["respondent_count"], errors="coerce") / 8, 1.0)
    raw_score = 0.55 * frame["demand_score"] + 0.45 * frame["intent_signal"]
    frame["portfolio_score"] = (raw_score * (0.65 + 0.35 * sample_factor)).round(2)
    frame["portfolio_action"] = np.select(
        [
            frame["respondent_count"].lt(5),
            frame["portfolio_score"].ge(70) & frame["high_intent_share"].ge(0.4),
            frame["portfolio_score"].ge(55),
        ],
        ["样本不足，仅作定向访谈候选", "进入商品概念与供应商报价", "进入小批量意向验证"],
        default="暂缓开发",
    )
    return frame.sort_values(["portfolio_score", "respondent_count"], ascending=False).reset_index(
        drop=True
    )


def _weekly_demand_variability(inventory: pd.DataFrame) -> pd.DataFrame:
    frame = inventory.copy()
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"])
    frame["week"] = frame["snapshot_date"].dt.to_period("W").astype(str)
    weekly = frame.groupby(["sku_id", "week"], as_index=False)["requested_sales_units"].sum()
    variability = weekly.groupby("sku_id", as_index=False).agg(
        weekly_demand_mean=("requested_sales_units", "mean"),
        weekly_demand_std=("requested_sales_units", "std"),
    )
    variability["demand_cv"] = variability["weekly_demand_std"].fillna(0) / variability[
        "weekly_demand_mean"
    ].replace(0, np.nan)
    variability["xyz_class"] = np.select(
        [variability["demand_cv"].le(0.50), variability["demand_cv"].le(1.00)],
        ["X", "Y"],
        default="Z",
    )
    return variability


def build_erp_sku_diagnostics(
    financial: pd.DataFrame,
    order_lines: pd.DataFrame,
    inventory: pd.DataFrame,
    after_sales: pd.DataFrame,
) -> pd.DataFrame:
    frame = financial.copy()
    variability = _weekly_demand_variability(inventory)
    line_stats = order_lines.groupby("sku_id", as_index=False).agg(
        line_count=("order_line_id", "count"),
        order_count=("order_id", "nunique"),
        cancelled_line_count=("payment_status", lambda value: value.eq("cancelled").sum()),
        sold_quantity_requested=("quantity", "sum"),
        average_discount_rate=("discount_rate", "mean"),
    )
    line_stats["cancelled_line_rate"] = line_stats["cancelled_line_count"] / line_stats[
        "line_count"
    ].replace(0, np.nan)
    if after_sales.empty:
        after_stats = pd.DataFrame(columns=["sku_id", "after_sales_case_count", "resolution_days_mean"])
    else:
        cases = after_sales.copy()
        cases["resolution_days"] = (
            pd.to_datetime(cases["resolved_at"]) - pd.to_datetime(cases["requested_at"])
        ).dt.days
        after_stats = cases.groupby("sku_id", as_index=False).agg(
            after_sales_case_count=("case_id", "nunique"),
            resolution_days_mean=("resolution_days", "mean"),
        )
    frame = frame.merge(variability, on="sku_id", how="left")
    frame = frame.merge(line_stats, on="sku_id", how="left").merge(
        after_stats, on="sku_id", how="left"
    )
    frame = frame.sort_values("net_sales_after_refund", ascending=False).reset_index(drop=True)
    total_sales = frame["net_sales_after_refund"].sum()
    frame["sales_share"] = frame["net_sales_after_refund"] / total_sales if total_sales else 0
    frame["cumulative_sales_share"] = frame["sales_share"].cumsum()
    frame["abc_class"] = np.select(
        [frame["cumulative_sales_share"].le(0.80), frame["cumulative_sales_share"].le(0.95)],
        ["A", "B"],
        default="C",
    )
    frame["abc_xyz_class"] = frame["abc_class"] + frame["xyz_class"].fillna("Z")
    frame["average_inventory_value"] = frame["average_inventory"] * frame["unit_cost"]
    frame["gmroi"] = frame["gross_profit"] / frame["average_inventory_value"].replace(0, np.nan)
    frame["lost_sales_value_proxy"] = frame["stockout_units"] * frame["price"]
    frame["net_revenue_per_sold_unit"] = frame["net_sales_after_refund"] / frame[
        "sold_units"
    ].replace(0, np.nan)
    frame["operating_action"] = np.select(
        [
            frame["stockout_rate"].ge(0.02),
            frame["return_rate"].ge(0.08),
            frame["days_of_inventory"].ge(180),
            frame["abc_class"].eq("A") & frame["xyz_class"].eq("X"),
            frame["abc_class"].eq("A") & frame["xyz_class"].eq("Z"),
        ],
        [
            "缺货风险：提高安全库存并复核交期",
            "售后风险：复核质量、包装与详情页承诺",
            "滞销风险：停止补货并测试组合促销",
            "核心稳定SKU：滚动补货",
            "核心波动SKU：小批量高频补货",
        ],
        default="常规监控",
    )
    frame["is_simulated"] = True
    return frame


def build_erp_replenishment_plan(
    sku_master: pd.DataFrame,
    inventory: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    trailing_days: int = 28,
    review_period_days: int = 14,
) -> pd.DataFrame:
    inventory_frame = inventory.copy()
    inventory_frame["snapshot_date"] = pd.to_datetime(inventory_frame["snapshot_date"])
    cutoff = inventory_frame["snapshot_date"].max() - pd.Timedelta(days=trailing_days - 1)
    recent = inventory_frame.loc[inventory_frame["snapshot_date"].ge(cutoff)]
    demand = recent.groupby("sku_id", as_index=False).agg(
        trailing_requested_units=("requested_sales_units", "sum"),
        average_daily_demand_28d=("requested_sales_units", "mean"),
        daily_demand_std_28d=("requested_sales_units", "std"),
    )
    latest_date = inventory_frame["snapshot_date"].max()
    latest = inventory_frame.loc[inventory_frame["snapshot_date"].eq(latest_date), [
        "sku_id",
        "available_stock",
        "closing_stock",
        "locked_stock",
    ]]
    open_po = purchase_orders.loc[purchase_orders["purchase_status"].eq("open")].copy()
    open_po["open_po_units"] = open_po["quantity_ordered"] - open_po["quantity_received"]
    open_po = open_po.groupby("sku_id", as_index=False)["open_po_units"].sum()
    frame = sku_master[
        ["sku_id", "operator", "category", "purchase_lead_time_days", "unit_cost"]
    ].merge(demand, on="sku_id", how="left")
    frame = frame.merge(latest, on="sku_id", how="left").merge(open_po, on="sku_id", how="left")
    frame["open_po_units"] = frame["open_po_units"].fillna(0)
    frame["daily_demand_std_28d"] = frame["daily_demand_std_28d"].fillna(0)
    frame["calculated_safety_stock"] = np.ceil(
        1.65 * frame["daily_demand_std_28d"] * np.sqrt(frame["purchase_lead_time_days"])
    )
    frame["calculated_reorder_point"] = np.ceil(
        frame["average_daily_demand_28d"] * frame["purchase_lead_time_days"]
        + frame["calculated_safety_stock"]
    )
    frame["target_stock"] = np.ceil(
        frame["average_daily_demand_28d"]
        * (frame["purchase_lead_time_days"] + review_period_days)
        + frame["calculated_safety_stock"]
    )
    frame["suggested_po_quantity"] = np.maximum(
        0, frame["target_stock"] - frame["available_stock"] - frame["open_po_units"]
    ).astype(int)
    frame["inventory_position"] = frame["available_stock"] + frame["open_po_units"]
    frame["replenishment_priority"] = np.select(
        [
            frame["inventory_position"].le(frame["calculated_reorder_point"]),
            frame["inventory_position"].le(frame["target_stock"]),
        ],
        ["P0-立即补货", "P1-进入补货计划"],
        default="P2-暂不补货",
    )
    frame["suggested_purchase_amount"] = (
        frame["suggested_po_quantity"] * frame["unit_cost"]
    ).round(2)
    frame["is_simulated"] = True
    return frame.sort_values(
        ["replenishment_priority", "suggested_po_quantity"], ascending=[True, False]
    ).reset_index(drop=True)


def build_after_sales_pareto(after_sales: pd.DataFrame, sku_master: pd.DataFrame) -> pd.DataFrame:
    if after_sales.empty:
        return pd.DataFrame()
    cases = after_sales.merge(sku_master[["sku_id", "category", "operator"]], on="sku_id", how="left")
    cases["resolution_days"] = (
        pd.to_datetime(cases["resolved_at"]) - pd.to_datetime(cases["requested_at"])
    ).dt.days
    frame = cases.groupby(["category", "reason"], as_index=False).agg(
        case_count=("case_id", "nunique"),
        affected_units=("units", "sum"),
        refund_amount=("refund_amount", "sum"),
        average_resolution_days=("resolution_days", "mean"),
        affected_operator_count=("operator", "nunique"),
    )
    frame = frame.sort_values(["case_count", "refund_amount"], ascending=False).reset_index(drop=True)
    frame["case_share"] = frame["case_count"] / frame["case_count"].sum()
    frame["cumulative_case_share"] = frame["case_share"].cumsum()
    frame["pareto_priority"] = np.where(frame["cumulative_case_share"].le(0.80), "核心原因", "长尾原因")
    if not frame.empty:
        first_over = frame.index[frame["cumulative_case_share"].ge(0.80)]
        if len(first_over):
            frame.loc[first_over[0], "pareto_priority"] = "核心原因"
    frame["is_simulated"] = True
    return frame


def build_channel_profitability(
    order_headers: pd.DataFrame,
    order_lines: pd.DataFrame,
    after_sales: pd.DataFrame,
) -> pd.DataFrame:
    headers = order_headers.copy()
    base = headers.groupby("channel", as_index=False).agg(
        order_count=("order_id", "nunique"),
        paid_order_count=("payment_status", lambda value: value.eq("paid").sum()),
        cancelled_order_count=("payment_status", lambda value: value.eq("cancelled").sum()),
        paid_amount=("paid_amount", "sum"),
        discount_amount=("discount_amount", "sum"),
        shipping_fee_collected=("shipping_fee", "sum"),
    )
    paid_lines = order_lines.loc[order_lines["payment_status"].eq("paid")].merge(
        headers[["order_id", "channel"]], on="order_id", how="left"
    )
    economics = paid_lines.groupby("channel", as_index=False).agg(
        product_net_revenue=("net_revenue", "sum"),
        product_cogs=("line_cost", "sum"),
        sold_units=("quantity", "sum"),
    )
    if after_sales.empty:
        refunds = pd.DataFrame(columns=["channel", "after_sales_cases", "refund_amount"])
    else:
        refunds = after_sales.merge(headers[["order_id", "channel"]], on="order_id", how="left")
        refunds = refunds.groupby("channel", as_index=False).agg(
            after_sales_cases=("case_id", "nunique"),
            refund_amount=("refund_amount", "sum"),
        )
    frame = base.merge(economics, on="channel", how="left").merge(refunds, on="channel", how="left")
    frame[["after_sales_cases", "refund_amount"]] = frame[
        ["after_sales_cases", "refund_amount"]
    ].fillna(0)
    frame["payment_rate"] = frame["paid_order_count"] / frame["order_count"].replace(0, np.nan)
    frame["average_order_value"] = frame["paid_amount"] / frame["paid_order_count"].replace(0, np.nan)
    frame["refund_amount_rate"] = frame["refund_amount"] / frame["product_net_revenue"].replace(
        0, np.nan
    )
    frame["gross_profit_after_refund_proxy"] = (
        frame["product_net_revenue"] - frame["product_cogs"] - frame["refund_amount"]
    )
    frame["gross_margin_after_refund_proxy"] = frame[
        "gross_profit_after_refund_proxy"
    ] / (frame["product_net_revenue"] - frame["refund_amount"]).replace(0, np.nan)
    frame["is_simulated"] = True
    return frame.sort_values("gross_profit_after_refund_proxy", ascending=False).reset_index(drop=True)


def build_erp_category_diagnostics(diagnostics: pd.DataFrame) -> pd.DataFrame:
    frame = diagnostics.groupby("category", as_index=False).agg(
        sku_count=("sku_id", "nunique"),
        sold_units=("sold_units", "sum"),
        net_sales_after_refund=("net_sales_after_refund", "sum"),
        gross_profit=("gross_profit", "sum"),
        return_units=("return_units", "sum"),
        stockout_units=("stockout_units", "sum"),
        lost_sales_value_proxy=("lost_sales_value_proxy", "sum"),
        average_days_of_inventory=("days_of_inventory", "mean"),
        average_gmroi=("gmroi", "mean"),
        a_class_sku_count=("abc_class", lambda value: value.eq("A").sum()),
        high_return_sku_count=("return_rate", lambda value: value.ge(0.08).sum()),
    )
    frame["gross_margin_rate"] = frame["gross_profit"] / frame[
        "net_sales_after_refund"
    ].replace(0, np.nan)
    frame["return_rate"] = frame["return_units"] / frame["sold_units"].replace(0, np.nan)
    frame["stockout_rate"] = frame["stockout_units"] / (
        frame["sold_units"] + frame["stockout_units"]
    ).replace(0, np.nan)
    frame["category_action"] = np.select(
        [
            frame["return_rate"].ge(0.07),
            frame["stockout_rate"].ge(0.01),
            frame["average_days_of_inventory"].ge(120),
        ],
        ["优先复盘质量与商品描述", "提高安全库存并复核供应周期", "减少补货并测试促销"],
        default="维持经营节奏",
    )
    frame["is_simulated"] = True
    return frame.sort_values("gross_profit", ascending=False).reset_index(drop=True)


def build_erp_daily_kpis(
    order_headers: pd.DataFrame,
    order_lines: pd.DataFrame,
    inventory: pd.DataFrame,
    after_sales: pd.DataFrame,
) -> pd.DataFrame:
    headers = order_headers.copy()
    headers["date"] = pd.to_datetime(headers["order_date"])
    orders = headers.groupby("date", as_index=False).agg(
        order_count=("order_id", "nunique"),
        paid_order_count=("payment_status", lambda value: value.eq("paid").sum()),
        cancelled_order_count=("payment_status", lambda value: value.eq("cancelled").sum()),
        paid_amount=("paid_amount", "sum"),
    )
    paid_lines = order_lines.loc[order_lines["payment_status"].eq("paid")].copy()
    paid_lines["date"] = pd.to_datetime(paid_lines["order_date"])
    sales = paid_lines.groupby("date", as_index=False).agg(
        product_net_revenue=("net_revenue", "sum"),
        sold_units=("quantity", "sum"),
    )
    stock = inventory.copy()
    stock["date"] = pd.to_datetime(stock["snapshot_date"])
    stock = stock.groupby("date", as_index=False).agg(
        requested_units=("requested_sales_units", "sum"),
        fulfilled_units=("sold_units", "sum"),
        stockout_units=("stockout_units", "sum"),
        closing_stock=("closing_stock", "sum"),
    )
    if after_sales.empty:
        cases = pd.DataFrame(columns=["date", "after_sales_case_count", "refund_amount"])
    else:
        case_frame = after_sales.copy()
        case_frame["date"] = pd.to_datetime(case_frame["requested_at"])
        cases = case_frame.groupby("date", as_index=False).agg(
            after_sales_case_count=("case_id", "nunique"),
            refund_amount=("refund_amount", "sum"),
        )
    frame = orders.merge(sales, on="date", how="outer").merge(stock, on="date", how="outer")
    frame = frame.merge(cases, on="date", how="outer").sort_values("date").fillna(0)
    frame["payment_rate"] = frame["paid_order_count"] / frame["order_count"].replace(0, np.nan)
    frame["average_order_value"] = frame["paid_amount"] / frame["paid_order_count"].replace(0, np.nan)
    frame["fill_rate"] = frame["fulfilled_units"] / frame["requested_units"].replace(0, np.nan)
    frame["rolling_7d_revenue"] = frame["product_net_revenue"].rolling(7, min_periods=1).sum()
    frame["rolling_7d_units"] = frame["sold_units"].rolling(7, min_periods=1).sum()
    frame["rolling_7d_refund_amount"] = frame["refund_amount"].rolling(7, min_periods=1).sum()
    frame["date"] = frame["date"].dt.date.astype(str)
    frame["is_simulated"] = True
    return frame.reset_index(drop=True)


def build_evidence_inventory(
    bilibili_archive: pd.DataFrame,
    bilibili_campaigns: pd.DataFrame,
    weibo_count: int,
    xiaohongshu_count: int,
    skland_snapshot: pd.DataFrame,
    survey_responses: pd.DataFrame,
    survey_rankings: pd.DataFrame,
    survey_prices: pd.DataFrame,
    taobao: pd.DataFrame,
    order_headers: pd.DataFrame,
    order_lines: pd.DataFrame,
    inventory: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    after_sales: pd.DataFrame,
) -> pd.DataFrame:
    skland_relevant = skland_snapshot.loc[skland_snapshot["direct_name_match"].astype(bool)]
    official_taobao = taobao.loc[taobao["rights_type"].eq("官方/授权")]
    rows = [
        ("Bilibili", "官号历史内容", len(bilibili_archive), bilibili_archive["bvid"].nunique(), "公开真实快照", "内容供给与传播"),
        ("Bilibili", "角色上线Campaign关联", len(bilibili_campaigns), bilibili_campaigns["bvid"].nunique(), "公开真实快照", "角色内容曝光"),
        ("Weibo", "官号近期内容", weibo_count, weibo_count, "公开真实快照", "近期角色交叉验证"),
        ("Xiaohongshu", "品牌生态窗口", xiaohongshu_count, xiaohongshu_count, "公开真实快照", "平台生态校准"),
        ("Skland", "攻略站角色-内容关联", len(skland_relevant), skland_relevant["item_id"].nunique(), "公开真实快照", "深度兴趣与攻略需求"),
        ("Survey", "匿名受访者", len(survey_responses), survey_responses["response_id"].nunique(), "真实匿名问卷", "角色、品类、价格、渠道意愿"),
        ("Survey", "角色Top-3排序", len(survey_rankings), survey_rankings["operator"].nunique(), "真实匿名问卷", "角色偏好"),
        ("Survey", "七品类价格观测", len(survey_prices), survey_prices["category"].nunique(), "真实匿名问卷", "价格带"),
        ("Taobao", "公开商品快照", len(taobao), taobao["item_id"].nunique(), "公开真实快照", "供给、价格与销量代理"),
        ("Taobao", "明确官方/授权商品", len(official_taobao), official_taobao["item_id"].nunique(), "公开真实快照", "正版价格校准"),
        ("ERP", "订单头", len(order_headers), order_headers["order_id"].nunique(), "模拟", "订单与渠道分析"),
        ("ERP", "订单明细", len(order_lines), order_lines["sku_id"].nunique(), "模拟", "SKU收入与毛利"),
        ("ERP", "库存日快照", len(inventory), inventory["sku_id"].nunique(), "模拟", "库存、缺货与补货"),
        ("ERP", "采购单", len(purchase_orders), purchase_orders["supplier_id"].nunique(), "模拟", "采购交期与到货"),
        ("ERP", "售后单", len(after_sales), after_sales["reason"].nunique(), "模拟", "退款、退货、换货与原因Pareto"),
    ]
    return pd.DataFrame(
        rows,
        columns=["source", "scope", "record_count", "entity_count", "data_nature", "decision_use"],
    )


def export_operational_outputs(
    tables: dict[str, pd.DataFrame],
    output_dir: Path,
    database_path: Path,
    views_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        for name, frame in tables.items():
            frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
            frame.to_sql(name, connection, if_exists="replace", index=False)
        connection.executescript(views_path.read_text(encoding="utf-8"))


def write_operational_report(tables: dict[str, pd.DataFrame], output_path: Path) -> None:
    evidence = tables["evidence_inventory"]
    demand = tables["operator_demand_fusion"]
    category = tables["category_price_architecture"]
    diagnostics = tables["erp_sku_diagnostics"]
    replenishment = tables["erp_replenishment_plan"]
    pareto = tables["erp_after_sales_pareto"]
    channels = tables["erp_channel_profitability"]
    category_diagnostics = tables["erp_category_diagnostics"]
    daily_kpis = tables["erp_daily_kpis"]
    top_demand = demand.head(15)[
        [
            "demand_rank",
            "operator",
            "demand_score",
            "demand_tier",
            "content_signal",
            "survey_signal",
            "skland_signal",
            "commerce_signal",
            "evidence_confidence",
            "scenario_rank_range",
        ]
    ]
    category_columns = [
        "category",
        "category_demand_score",
        "respondent_count",
        "high_intent_share",
        "recommended_entry_price",
        "recommended_core_price",
        "recommended_premium_price",
        "observed_official_sku_count",
        "observed_market_price_median",
        "market_evidence_grade",
        "pricing_action",
    ]
    top_stockout = diagnostics.sort_values("lost_sales_value_proxy", ascending=False).head(10)[
        [
            "sku_id",
            "abc_xyz_class",
            "net_sales_after_refund",
            "stockout_rate",
            "lost_sales_value_proxy",
            "days_of_inventory",
            "return_rate",
            "operating_action",
        ]
    ]
    lines = [
        "# Arknights Analytics｜用户需求、商品组合与 ERP 经营诊断",
        "",
        "> 数据边界：243份问卷为用户确认的真实匿名回收结果；B站、微博、森空岛攻略站与淘宝为公开快照；ERP订单、库存、采购、财务和售后为可复现模拟数据，不代表真实经营业绩。",
        "",
        "## 0. 数据证据盘点",
        "",
        evidence.to_markdown(index=False),
        "",
        "## 1. 用户需求与角色热度",
        "",
        f"- 覆盖角色：{len(demand)}名；森空岛有有效角色级结果：{int(demand['skland_content_count'].notna().sum())}名。",
        f"- 森空岛清洗后聚合角色-内容关联：{int(demand['skland_content_count'].fillna(0).sum()):,}条，归因浏览量合计：{int(demand['skland_total_views'].fillna(0).sum()):,}。",
        "- Demand Score 对内容热度、真实问卷偏好、森空岛攻略浏览和淘宝商业信号按可用证据动态归一；缺失来源不按0分惩罚。",
        "- 使用5套权重做敏感性分析，Scenario Rank Range越小，说明角色结论越不依赖单一权重设定。",
        "",
        top_demand.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 2. 周边品类与价格带",
        "",
        "- 价格梯度来自243份真实问卷对七类正版周边的接受价格分布，分别使用P25/P50/P75形成入门款、核心款和高配款。",
        "- 淘宝仅纳入公开快照中明确标注为官方/授权的SKU；样本不足的品类保留N/A，不用未标明或同人商品补齐。",
        "- 模拟ERP价格与成本只用于检验毛利和库存决策逻辑，不能作为市场成交价证据。",
        "",
        category[category_columns].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 3. ERP订单、库存与售后",
        "",
        f"- 模拟经营规模：{int(channels['order_count'].sum()):,}张订单、{int(diagnostics['line_count'].sum()):,}条订单明细、{int(diagnostics['sold_units'].sum()):,}件销售、{int(diagnostics['after_sales_case_count'].fillna(0).sum()):,}个售后单。",
        f"- ABC-XYZ：A类高收入SKU {int(diagnostics['abc_class'].eq('A').sum())}个；AX核心稳定SKU {int(diagnostics['abc_xyz_class'].eq('AX').sum())}个；AZ核心波动SKU {int(diagnostics['abc_xyz_class'].eq('AZ').sum())}个。",
        f"- 缺货销售额代理损失：¥{diagnostics['lost_sales_value_proxy'].sum():,.2f}；建议立即/计划补货SKU：{int(replenishment['replenishment_priority'].ne('P2-暂不补货').sum())}个，建议采购金额：¥{replenishment['suggested_purchase_amount'].sum():,.2f}。",
        "- 售后按品类×原因做Pareto排序，以案例数、退款金额和平均处理时长识别质量、包装、详情页承诺或履约问题。",
        "",
        "### 缺货与库存风险 Top 10",
        "",
        top_stockout.to_markdown(index=False, floatfmt=".2f"),
        "",
        "### 售后原因 Pareto",
        "",
        pareto.head(15).to_markdown(index=False, floatfmt=".2f"),
        "",
        "### 渠道经营对比",
        "",
        channels.to_markdown(index=False, floatfmt=".2f"),
        "",
        "### 品类经营诊断",
        "",
        category_diagnostics.to_markdown(index=False, floatfmt=".2f"),
        "",
        f"### 订单周期趋势摘要（{len(daily_kpis)}天）",
        "",
        f"- 日均订单：{daily_kpis['order_count'].mean():.2f}；峰值日订单：{int(daily_kpis['order_count'].max())}。",
        f"- 日均商品净收入：¥{daily_kpis['product_net_revenue'].mean():,.2f}；最高7日滚动收入：¥{daily_kpis['rolling_7d_revenue'].max():,.2f}。",
        f"- 平均履约满足率：{daily_kpis['fill_rate'].mean():.2%}；售后退款金额最高7日窗口：¥{daily_kpis['rolling_7d_refund_amount'].max():,.2f}。",
        "",
        "## 决策结论",
        "",
        "1. 角色：优先评审多源证据一致且权重敏感性低的核心角色；内容热但问卷弱的角色先做概念测试，不能直接备货。",
        "2. 品类：以真实问卷P25/P50/P75建立价格梯度，并用正版市场样本验证；市场样本不足时先补竞品和供应商报价。",
        "3. ERP：AX采用滚动补货，AZ采用小批量高频补货；高退货和长库存周转SKU优先进入质量复盘或促销清理。",
        "",
        "## 方法限制",
        "",
        "- 森空岛指标来自攻略站公开搜索Top 20快照，不等于全站角色总浏览量；单字角色、异格同名已按标题实体规则清洗。",
        "- 公开平台曝光受发布时间、推荐算法和内容类型影响，只能作为需求代理变量。",
        "- 问卷为便利抽样，适合比较样本内偏好，不外推为全体玩家比例。",
        "- ERP全部为模拟数据，重点展示SQL、指标体系和运营决策能力。",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_operational_workbook(tables: dict[str, pd.DataFrame], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = {
        "evidence_inventory": "证据盘点",
        "operator_demand_fusion": "角色需求融合",
        "operator_rank_sensitivity": "角色权重敏感性",
        "category_price_architecture": "品类价格带",
        "operator_category_portfolio": "角色品类组合",
        "erp_sku_diagnostics": "ERP SKU诊断",
        "erp_replenishment_plan": "ERP补货计划",
        "erp_after_sales_pareto": "ERP售后Pareto",
        "erp_channel_profitability": "ERP渠道经营",
        "erp_category_diagnostics": "ERP品类诊断",
        "erp_daily_kpis": "ERP每日KPI",
    }
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, frame in tables.items():
            frame.to_excel(writer, sheet_name=sheet_names[name], index=False)
            worksheet = writer.sheets[sheet_names[name]]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions


def write_operational_figures(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    demand = tables["operator_demand_fusion"].head(15).sort_values("demand_score")
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.barh(demand["operator"], demand["demand_score"], color="#2f855a")
    ax.set_xlabel("Demand Score")
    ax.set_title("角色多源需求融合 Top 15")
    fig.tight_layout()
    fig.savefig(output_dir / "operator_demand_fusion.png", dpi=180)
    plt.close(fig)

    category = tables["category_price_architecture"].sort_values("category_demand_score")
    fig, ax = plt.subplots(figsize=(11, 7))
    y = np.arange(len(category))
    ax.hlines(
        y,
        category["recommended_entry_price"],
        category["recommended_premium_price"],
        color="#90cdf4",
        linewidth=8,
    )
    ax.scatter(category["recommended_core_price"], y, color="#2b6cb0", label="问卷P50核心价")
    ax.scatter(
        category["observed_market_price_median"], y, color="#dd6b20", marker="x", label="淘宝正版样本中位价"
    )
    ax.set_yticks(y, category["category"])
    ax.set_xlabel("Price (CNY)")
    ax.set_title("七类正版周边价格带：问卷接受区间 vs 公开市场快照")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "category_price_architecture.png", dpi=180)
    plt.close(fig)

    diagnostics = tables["erp_sku_diagnostics"]
    matrix = pd.crosstab(diagnostics["abc_class"], diagnostics["xyz_class"]).reindex(
        index=["A", "B", "C"], columns=["X", "Y", "Z"], fill_value=0
    )
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(matrix.values, cmap="YlGnBu")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(column, row, int(matrix.iloc[row, column]), ha="center", va="center")
    ax.set_xticks(range(3), matrix.columns)
    ax.set_yticks(range(3), matrix.index)
    ax.set_xlabel("Demand variability (XYZ)")
    ax.set_ylabel("Revenue contribution (ABC)")
    ax.set_title("模拟 ERP SKU ABC-XYZ 矩阵")
    fig.colorbar(image, ax=ax, label="SKU count")
    fig.tight_layout()
    fig.savefig(output_dir / "erp_abc_xyz_matrix.png", dpi=180)
    plt.close(fig)

    pareto = tables["erp_after_sales_pareto"].head(15).copy()
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = pareto["category"] + "-" + pareto["reason"]
    ax.bar(range(len(pareto)), pareto["case_count"], color="#e53e3e", alpha=0.75)
    ax.set_xticks(range(len(pareto)), labels, rotation=55, ha="right")
    ax.set_ylabel("Case count")
    second = ax.twinx()
    second.plot(range(len(pareto)), pareto["cumulative_case_share"] * 100, color="#2b6cb0", marker="o")
    second.axhline(80, color="#718096", linestyle="--")
    second.set_ylabel("Cumulative case share (%)")
    ax.set_title("模拟 ERP 售后原因 Pareto")
    fig.tight_layout()
    fig.savefig(output_dir / "erp_after_sales_pareto.png", dpi=180)
    plt.close(fig)
