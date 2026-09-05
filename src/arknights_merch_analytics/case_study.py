from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_selection_case(
    operator: str,
    content_commerce: pd.DataFrame,
    targeted_summary: pd.DataFrame,
    listings: pd.DataFrame,
    sku_recommendations: pd.DataFrame,
    survey_summary: pd.DataFrame | None = None,
    timeseries_metrics: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    role_rows = content_commerce[content_commerce["operator"] == operator]
    if role_rows.empty:
        raise ValueError(f"Unknown operator: {operator}")
    role = role_rows.iloc[0]
    targeted = targeted_summary[targeted_summary["operator"] == operator]
    target = targeted.iloc[0] if not targeted.empty else None
    relevant = listings[
        listings["target_operator"].eq(operator) & listings["target_relevance"].ge(0.75)
    ].copy()
    category_evidence = (
        relevant.groupby("category", as_index=False).agg(
            public_sku_count=("item_id", "nunique"),
            sales_proxy_lower_bound=("sales_proxy_min", "sum"),
            median_price=("price", "median"),
            official_share=("rights_type", lambda values: (values == "官方/授权").mean()),
            fanmade_share=("rights_type", lambda values: (values == "同人原创").mean()),
        )
        if not relevant.empty
        else pd.DataFrame()
    )
    survey = survey_summary if survey_summary is not None else pd.DataFrame()
    survey_role = survey[survey["operator"] == operator] if not survey.empty else survey
    timeseries = timeseries_metrics if timeseries_metrics is not None else pd.DataFrame()
    timeseries_role = timeseries[timeseries["operator"] == operator] if not timeseries.empty else timeseries
    timeseries_ready = bool(
        not timeseries_role.empty
        and timeseries_role["timeseries_evidence_grade"].isin(["A", "B", "C"]).any()
    )
    survey_ready = bool(
        not survey_role.empty and survey_role["respondent_count"].ge(30).any()
    )
    evidence_rows = [
        {
            "evidence_layer": "content_heat",
            "metric": "cross_platform_heat",
            "value": float(role["cross_platform_heat"]),
            "threshold": 60.0,
            "gate_passed": float(role["cross_platform_heat"]) >= 60,
            "data_type": "real_public_aggregate",
            "interpretation": "角色公开内容关注度",
        },
        {
            "evidence_layer": "content_intent",
            "metric": "intent_score",
            "value": float(role["intent_score"]),
            "threshold": 70.0,
            "gate_passed": float(role["intent_score"]) >= 70,
            "data_type": "real_public_aggregate",
            "interpretation": "收藏、转发等深层互动意向",
        },
        {
            "evidence_layer": "taobao_query_quality",
            "metric": "search_precision",
            "value": float(target["search_precision"]) if target is not None else 0.0,
            "threshold": 0.60,
            "gate_passed": bool(target is not None and target["search_precision"] >= 0.60),
            "data_type": "real_public_snapshot",
            "interpretation": "定向搜索样本相关率",
        },
        {
            "evidence_layer": "taobao_demand_proxy",
            "metric": "sales_proxy_lower_bound",
            "value": float(target["sales_proxy_min_total"]) if target is not None else 0.0,
            "threshold": 100.0,
            "gate_passed": bool(target is not None and target["sales_proxy_min_total"] >= 100),
            "data_type": "real_public_lower_bound",
            "interpretation": "公开收货人数下界代理，不是精确销量",
        },
        {
            "evidence_layer": "fixed_sku_timeseries",
            "metric": "grade_c_or_above_available",
            "value": float(timeseries_ready),
            "threshold": 1.0,
            "gate_passed": timeseries_ready,
            "data_type": "real_public_longitudinal",
            "interpretation": "至少两期且跨越7天的固定商品复采",
        },
        {
            "evidence_layer": "user_research",
            "metric": "n_30_segment_available",
            "value": float(survey_ready),
            "threshold": 1.0,
            "gate_passed": survey_ready,
            "data_type": "real_anonymous_survey",
            "interpretation": "至少30名有效受访者的角色品类分层",
        },
    ]
    evidence = pd.DataFrame(evidence_rows)
    sku_rows = sku_recommendations[sku_recommendations["operator"] == operator].copy()
    sku_rows["source_role"] = "simulated_erp_method_only"
    sku_rows["commercial_decision_allowed"] = False
    status = "validated_candidate" if evidence["gate_passed"].all() else "conditional_pilot"
    evidence["case_status"] = status
    if not category_evidence.empty:
        category_evidence["evidence_layer"] = "taobao_category"
        category_evidence["data_type"] = "real_public_snapshot"
    return evidence, category_evidence


def write_selection_case_report(
    operator: str,
    evidence: pd.DataFrame,
    category_evidence: pd.DataFrame,
    sku_recommendations: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    status = evidence["case_status"].iloc[0]
    role_skus = sku_recommendations[sku_recommendations["operator"] == operator].copy()
    role_skus = role_skus.sort_values("selection_score", ascending=False).head(6)
    columns = [
        "category",
        "price",
        "selection_score",
        "recommendation",
        "production_risk",
        "inventory_risk",
        "is_simulated",
    ]
    lines = [
        f"# {operator} 周边选品验证案例",
        "",
        f"> 当前案例状态：`{status}`。只有内容、淘宝横截面、固定 SKU 时间序列和真实用户调研全部过门禁后，才升级为已验证选品。",
        "",
        "## 决策假设",
        "",
        f"{operator}具备较强内容关注和深层互动信号，但公开淘宝样本仍受搜索个性化、销量档位截断和非官方供给影响。当前建议不是大规模备货，而是先用低生产风险商品完成小批量验证，同时补齐固定 SKU 周期复采与真实用户调研。",
        "",
        "## 证据门禁",
        "",
        evidence.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 淘宝品类证据",
        "",
        category_evidence.to_markdown(index=False, floatfmt=".2f") if not category_evidence.empty else "暂无有效定向搜索样本。",
        "",
        "## 模拟 ERP 方案（仅用于方法演示）",
        "",
        role_skus[columns].to_markdown(index=False, floatfmt=".2f") if not role_skus.empty else "暂无模拟SKU。",
        "",
        "## 可执行选品建议",
        "",
        "1. 低风险首发：吧唧（徽章）、通行证或亚克力制品小批量组合，用预售收藏、加购和付款转化验证真实需求。",
        "2. 中风险承接：若连续两周固定 SKU 需求代理增长且用户调研价格接受度匹配，再增加装饰摆件、日用生活或毛绒玩偶。",
        "3. 高风险限制：手办模玩在缺少真实订单、退款和履约数据时不做现货重仓；日用生活需额外验证规格和退换风险。",
        "4. 验收指标：预售转化、售罄率、退款率、客诉率、库存周转和复购意愿；公开内容热度不作为最终验收指标。",
        "",
        "## 当前缺口",
        "",
        "- 真实用户调研尚未达到每个角色×品类30份有效样本。",
        "- 固定商品尚未达到至少两期、跨越7天的C级时间序列证据。",
        "- 缺少授权订单、收藏加购、退款、库存和履约数据，因此不能声称真实商业转化。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
