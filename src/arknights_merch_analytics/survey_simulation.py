from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from arknights_merch_analytics.survey import (
    build_survey_barrier_summary,
    build_survey_price_summary,
    build_survey_segment_summary,
    build_survey_summary,
    validate_survey_responses,
)


SIMULATION_SEED = 20260903
EXCLUDED_OPERATOR_ENTITIES = {"丰川祥子"}
AGE_PROFILE = {
    "18～22岁": 0.76,
    "23～26岁": 0.13,
    "27～30岁": 0.06,
    "31～35岁": 0.03,
    "36岁及以上": 0.02,
}
CATEGORY_WEIGHTS = {
    "亚克力制品": 0.24,
    "通行证": 0.11,
    "吧唧（徽章）": 0.20,
    "毛绒玩偶": 0.16,
    "手办模玩": 0.09,
    "装饰摆件": 0.10,
    "日用生活": 0.10,
}
CATEGORY_PREORDER_BASE = {
    "亚克力制品": 45,
    "通行证": 35,
    "吧唧（徽章）": 30,
    "毛绒玩偶": 75,
    "手办模玩": 150,
    "装饰摆件": 55,
    "日用生活": 60,
}
CHANNEL_WEIGHTS = {
    "淘宝": 0.34,
    "官方商城": 0.25,
    "B站会员购": 0.19,
    "线下展会或快闪店": 0.10,
    "品牌直播间": 0.08,
    "其他": 0.04,
}
MOTIVATION_WEIGHTS = {
    "喜爱角色": 0.30,
    "视觉设计或立绘表现": 0.19,
    "收藏完整度": 0.14,
    "限定或联名属性": 0.12,
    "支持IP或创作者": 0.10,
    "实用功能": 0.07,
    "价格与性价比": 0.05,
    "社交展示或社区认同": 0.03,
}
BARRIER_WEIGHTS = {
    "价格偏高": 0.22,
    "设计不符合预期": 0.16,
    "品质或材质不确定": 0.14,
    "预售周期过长": 0.13,
    "发货进度不透明": 0.09,
    "运费偏高": 0.08,
    "已有同类商品过多": 0.07,
    "商品缺乏实用性": 0.05,
    "售后不便": 0.04,
    "担心盗版": 0.02,
}


def _exact_profile(size: int, shares: dict[str, float], rng: np.random.Generator) -> list[str]:
    labels = list(shares)
    raw_counts = np.array([shares[label] * size for label in labels])
    counts = np.floor(raw_counts).astype(int)
    remainder = size - int(counts.sum())
    order = np.argsort(-(raw_counts - counts))
    for index in order[:remainder]:
        counts[index] += 1
    values = [label for label, count in zip(labels, counts, strict=True) for _ in range(count)]
    rng.shuffle(values)
    return values


def _sample_without_replacement(
    rng: np.random.Generator,
    weighted_options: dict[str, float],
    count: int,
) -> list[str]:
    options = np.array(list(weighted_options), dtype=object)
    probabilities = np.array(list(weighted_options.values()), dtype=float)
    probabilities /= probabilities.sum()
    return [str(value) for value in rng.choice(options, size=count, replace=False, p=probabilities)]


def _load_operator_weights(operator_heat_path: Path) -> dict[str, float]:
    frame = pd.read_csv(operator_heat_path)
    if frame.empty or "operator" not in frame.columns:
        raise ValueError("Operator heat data is empty or missing operator column")
    frame = frame.loc[~frame["operator"].astype(str).isin(EXCLUDED_OPERATOR_ENTITIES)].copy()
    heat = pd.to_numeric(frame.get("heat_score"), errors="coerce").fillna(0.0).clip(lower=0.0)
    normalized = (heat - heat.min()) / max(float(heat.max() - heat.min()), 1.0)
    blended = 0.35 / len(frame) + 0.65 * (normalized + 0.20) / float((normalized + 0.20).sum())
    return dict(zip(frame["operator"].astype(str), blended, strict=True))


def _category_probabilities(has_purchased: bool, monthly_budget: int) -> np.ndarray:
    probabilities = np.array(list(CATEGORY_WEIGHTS.values()), dtype=float)
    names = list(CATEGORY_WEIGHTS)
    if not has_purchased:
        probabilities[names.index("吧唧（徽章）")] *= 1.35
        probabilities[names.index("通行证")] *= 1.20
        probabilities[names.index("手办模玩")] *= 0.35
    if monthly_budget < 150:
        probabilities[names.index("手办模玩")] *= 0.20
        probabilities[names.index("日用生活")] *= 0.65
        probabilities[names.index("吧唧（徽章）")] *= 1.25
        probabilities[names.index("通行证")] *= 1.15
        probabilities[names.index("亚克力制品")] *= 1.15
    elif monthly_budget >= 300:
        probabilities[names.index("毛绒玩偶")] *= 1.20
        probabilities[names.index("手办模玩")] *= 1.55
        probabilities[names.index("日用生活")] *= 1.25
        probabilities[names.index("装饰摆件")] *= 1.15
    return probabilities / probabilities.sum()


def _build_purchase_profile(
    rng: np.random.Generator,
    age_band: str,
    activity_days: int,
) -> tuple[bool, int, int, int]:
    student = age_band == "18～22岁"
    buyer_probability = 0.64 + (0.08 if activity_days >= 20 else 0.0) + (0.02 if student else 0.07)
    has_purchased = bool(rng.random() < min(buyer_probability, 0.88))
    if not has_purchased:
        monthly_budget = int(rng.choice([0, 50, 100, 150, 200, 300], p=[0.08, 0.17, 0.27, 0.23, 0.18, 0.07]))
        return False, 0, 0, monthly_budget
    frequency_lambda = 4.1 if student else 5.4
    purchase_frequency = int(np.clip(rng.poisson(frequency_lambda) + 1, 1, 24))
    spend_per_purchase = float(rng.lognormal(mean=4.15 if student else 4.55, sigma=0.55))
    annual_spend = int(np.clip(round(purchase_frequency * spend_per_purchase / 10) * 10, 80, 12000))
    monthly_budget = int(
        np.clip(
            round((annual_spend / 12 * rng.uniform(0.9, 1.7) + rng.normal(45, 25)) / 10) * 10,
            50,
            2000,
        )
    )
    return True, purchase_frequency, annual_spend, monthly_budget


def generate_simulated_survey_responses(
    operator_heat_path: Path,
    category_path: Path,
    size: int = 200,
    seed: int = SIMULATION_SEED,
) -> pd.DataFrame:
    if size <= 0:
        raise ValueError("Simulation size must be positive")
    rng = np.random.default_rng(seed)
    ages = _exact_profile(size, AGE_PROFILE, rng)
    operator_weights = _load_operator_weights(operator_heat_path)
    categories = pd.read_csv(category_path).set_index("category")
    category_names = np.array(list(CATEGORY_WEIGHTS), dtype=object)
    rows: list[dict[str, object]] = []
    for index, age_band in enumerate(ages, start=1):
        student = age_band == "18～22岁"
        activity_days = int(np.clip(round(rng.normal(21 if student else 17, 6)), 1, 30))
        player_tenure = int(np.clip(round(rng.normal(43 if student else 57, 22)), 3, 96))
        has_purchased, frequency, annual_spend, monthly_budget = _build_purchase_profile(
            rng, age_band, activity_days
        )
        preferred_operators = _sample_without_replacement(rng, operator_weights, 3)
        operator = preferred_operators[0]
        category = str(
            rng.choice(
                category_names,
                p=_category_probabilities(has_purchased, monthly_budget),
            )
        )
        reference_price = float(categories.loc[category, "reference_price"])
        affordable = monthly_budget >= reference_price or category in {"吧唧（徽章）", "通行证"}
        intent_latent = (
            2.55
            + 0.62 * has_purchased
            + 0.35 * (activity_days >= 20)
            + 0.34 * affordable
            + 0.12 * student
            + rng.normal(0, 0.68)
        )
        purchase_intent = int(np.clip(round(intent_latent), 1, 5))
        price_capacity = 0.78 + 0.10 * purchase_intent + 0.12 * has_purchased
        budget_cap = max(monthly_budget * (1.15 if has_purchased else 0.80), reference_price * 0.55)
        acceptable_price = int(
            max(1, round(min(reference_price * price_capacity * rng.uniform(0.90, 1.12), budget_cap)))
        )
        good_value = max(1, int(round(acceptable_price * rng.uniform(0.76, 0.91))))
        too_cheap = max(1, int(round(good_value * rng.uniform(0.45, 0.68))))
        expensive = max(good_value, int(round(acceptable_price * rng.uniform(1.10, 1.35))))
        too_expensive = max(expensive, int(round(expensive * rng.uniform(1.22, 1.55))))
        limited_preference = int(
            np.clip(round(2.4 + 0.28 * purchase_intent + 0.30 * has_purchased + rng.normal(0, 0.75)), 1, 5)
        )
        preorder_tolerance = int(
            np.clip(
                round(
                    CATEGORY_PREORDER_BASE[category]
                    * (1.18 if has_purchased else 0.76)
                    * rng.uniform(0.65, 1.35)
                ),
                7,
                240,
            )
        )
        feedback_options = [
            "希望角色立绘还原准确，材质和尺寸说明写清楚。",
            "可以先做小批量预售，并及时同步生产和发货进度。",
            "更愿意购买有实用性的联名商品，不希望只换图重复销售。",
            "价格合理的情况下，希望同系列角色能够持续补全。",
            "希望官方增加实物细节图，并说明售后和补款规则。",
            "",
        ]
        submitted_at = pd.Timestamp("2026-09-03T09:00:00+08:00") + pd.Timedelta(
            minutes=index * 7 + int(rng.integers(0, 6))
        )
        rows.append(
            {
                "response_id": f"SYN-{index:04d}",
                "respondent_id": f"SYN-U-{index:04d}",
                "submitted_at": submitted_at.isoformat(),
                "consent": True,
                "response_source": str(rng.choice(
                    ["simulated_bilibili", "simulated_weibo", "simulated_player_community"],
                    p=[0.42, 0.26, 0.32],
                )),
                "completion_seconds": int(np.clip(round(rng.normal(315, 75)), 90, 600)),
                "questionnaire_version": "v2.2-synthetic",
                "merch_scope": "official_or_licensed_only",
                "randomization_group": str(rng.choice(["A", "B"])),
                "age_band": age_band,
                "region_tier": str(rng.choice(
                    ["一线", "新一线", "二线", "三线及以下"], p=[0.18, 0.34, 0.28, 0.20]
                )),
                "activity_days_30d": activity_days,
                "player_tenure_months": player_tenure,
                "monthly_merch_budget": monthly_budget,
                "has_purchased_merch": has_purchased,
                "annual_merch_spend": annual_spend,
                "purchase_frequency_12m": frequency,
                "fandom_identity": "大学生玩家" if student else "青年玩家",
                "preferred_operator_1": preferred_operators[0],
                "preferred_operator_2": preferred_operators[1],
                "preferred_operator_3": preferred_operators[2],
                "operator": operator,
                "category": category,
                "purchase_intent": purchase_intent,
                "acceptable_price": acceptable_price,
                "channel": str(rng.choice(list(CHANNEL_WEIGHTS), p=list(CHANNEL_WEIGHTS.values()))),
                "limited_preference": limited_preference,
                "purchase_motivation": "|".join(_sample_without_replacement(
                    rng, MOTIVATION_WEIGHTS, int(rng.integers(2, 4))
                )),
                "purchase_barrier": "|".join(_sample_without_replacement(
                    rng, BARRIER_WEIGHTS, int(rng.integers(2, 4))
                )),
                "authenticity_importance": int(np.clip(round(4.35 + rng.normal(0, 0.55)), 1, 5)),
                "design_importance": int(np.clip(round(4.45 + rng.normal(0, 0.50)), 1, 5)),
                "practicality_importance": int(np.clip(round(3.35 + rng.normal(0, 0.85)), 1, 5)),
                "preorder_tolerance_days": preorder_tolerance,
                "price_too_cheap": too_cheap,
                "price_good_value": good_value,
                "price_expensive": expensive,
                "price_too_expensive": too_expensive,
                "concept_appeal": int(np.clip(round(purchase_intent + rng.normal(0.15, 0.60)), 1, 5)),
                "concept_uniqueness": int(np.clip(round(3.3 + rng.normal(0, 0.75)), 1, 5)),
                "product_improvement": str(rng.choice(feedback_options)),
                "open_feedback": str(rng.choice(feedback_options)),
                "is_simulated": True,
                "data_type": "synthetic_persona",
                "simulation_seed": seed,
            }
        )
    return pd.DataFrame(rows)


def validate_simulated_responses(responses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid, audit = validate_survey_responses(responses)
    valid["is_real_survey_response"] = False
    valid["is_simulated"] = True
    valid["data_type"] = "synthetic_persona"
    valid["simulation_seed"] = responses["simulation_seed"].iloc[0]
    return valid, audit


def build_simulation_outputs(valid: pd.DataFrame) -> dict[str, pd.DataFrame]:
    age_summary = valid.groupby("age_band", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        prior_buyer_share=("has_purchased_merch", "mean"),
        monthly_budget_median=("monthly_merch_budget", "median"),
        purchase_intent_mean=("purchase_intent", "mean"),
    )
    age_summary["respondent_share"] = age_summary["respondent_count"] / len(valid)
    channel_summary = valid.groupby("channel", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        purchase_intent_mean=("purchase_intent", "mean"),
        monthly_budget_median=("monthly_merch_budget", "median"),
    )
    channel_summary["respondent_share"] = channel_summary["respondent_count"] / len(valid)
    category_summary = valid.groupby("category", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        high_intent_share=("purchase_intent", lambda values: values.ge(4).mean()),
        acceptable_price_median=("acceptable_price", "median"),
        preorder_tolerance_days_median=("preorder_tolerance_days", "median"),
    )
    category_summary["respondent_share"] = category_summary["respondent_count"] / len(valid)
    return {
        "operator_category": build_survey_summary(valid),
        "segment": build_survey_segment_summary(valid),
        "barrier": build_survey_barrier_summary(valid),
        "price": build_survey_price_summary(valid),
        "age": age_summary.sort_values("respondent_count", ascending=False).reset_index(drop=True),
        "channel": channel_summary.sort_values("respondent_count", ascending=False).reset_index(drop=True),
        "category": category_summary.sort_values("respondent_count", ascending=False).reset_index(drop=True),
    }


def write_simulated_survey_report(
    valid: pd.DataFrame,
    audit: pd.DataFrame,
    outputs: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    student_count = int(valid["age_band"].eq("18～22岁").sum())
    lines = [
        "# 200份模拟用户画像问卷分析",
        "",
        "> **重要说明：本报告基于程序生成的模拟画像答卷，仅用于验证问卷结构、数据清洗、用户分群和分析代码。它不是真实用户调研结果，不可作为市场事实、真实购买率或正式选品结论。**",
        "",
        "## 模拟口径",
        "",
        f"- 固定随机种子：`{int(valid['simulation_seed'].iloc[0])}`，可重复生成。",
        f"- 模拟答卷：{len(audit)} 份；通过同一质量校验链路：{int(audit['valid'].sum())} 份。",
        f"- 18～22岁大学生画像：{student_count} 人，占 {student_count / len(valid):.2%}。",
        "- 生成时保留购买经历、购买频次、年度支出、月度预算、品类价格与购买意愿之间的方向性关联，不使用真实个人信息。",
        "- 所有记录均带有 `is_simulated=true`、`data_type=synthetic_persona` 和 `simulation_seed` 标记，并与真实答卷目录隔离。",
        "",
        "## 模拟结果概览",
        "",
        f"- 有历史周边购买经历：{valid['has_purchased_merch'].mean():.2%}。",
        f"- 购买意愿4～5分：{valid['purchase_intent'].ge(4).mean():.2%}。",
        f"- 月度周边预算中位数：{valid['monthly_merch_budget'].median():.0f} 元。",
        f"- 过去12个月ACG周边支出中位数：{valid['annual_merch_spend'].median():.0f} 元。",
        "",
        "## 年龄画像",
        "",
        outputs["age"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 用户分群",
        "",
        outputs["segment"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 品类需求",
        "",
        outputs["category"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 购买渠道",
        "",
        outputs["channel"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 购买阻力",
        "",
        outputs["barrier"].head(10).to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 使用边界",
        "",
        "- 这批数据适合演示 SQL、Pandas、分群、价格阶梯和报告自动化，不适合声称‘调研发现大学生真实购买意愿为某个比例’。",
        "- 正式结论仍需使用多渠道招募的真实匿名答卷，并将模拟数据从统计口径中完全排除。",
        "- 模拟分布是可解释假设，不是从真实玩家总体中估计出的概率分布。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
