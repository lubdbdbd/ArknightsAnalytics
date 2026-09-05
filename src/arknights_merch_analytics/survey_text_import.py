from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


QUESTION_PATTERN = re.compile(r"^q(?P<number>\d+)\.(?P<answer>.*)$", re.MULTILINE)
SAMPLE_PATTERN = re.compile(
    r"^===== 样本(?P<number>\d+)｜(?P<player_status>[^=]+) =====$",
    re.MULTILINE,
)

CATEGORY_ALIASES = {
    "亚克力制品（立牌、摇摇乐等）": "亚克力制品",
    "通行证/通行认证卡": "通行证",
    "吧唧（徽章）": "吧唧（徽章）",
    "毛绒玩偶（如山山兔、龙泡泡）": "毛绒玩偶",
    "手办模玩": "手办模玩",
    "装饰摆件（挂件、色纸、灯具等）": "装饰摆件",
    "日用生活（服饰、箱包、杯具、文具等）": "日用生活",
    "日用生活（服饰、杯具、文具等）": "日用生活",
}

TENURE_MONTHS = {
    "不到3个月": 2,
    "3～12个月": 7,
    "1～3年": 24,
    "3～5年": 48,
    "开服至今": 84,
    "平时不玩游戏，但会关注角色或周边": 0,
}
ACTIVITY_DAYS = {
    "几乎每天": 28,
    "每周3～5天": 16,
    "每周1～2天": 6,
    "偶尔上线或看看内容": 2,
    "最近基本没关注": 0,
}
FREQUENCY = {
    "没买过": 0,
    "过去一年没买过": 0,
    "1～2次": 2,
    "3～5次": 4,
    "6～10次": 8,
    "10次以上": 12,
}
ANNUAL_SPEND = {
    "0元": 0,
    "1～200元": 100,
    "201～500元": 350,
    "501～1000元": 750,
    "1001～3000元": 2000,
    "3000元以上": 3500,
    "记不清了": np.nan,
}
MONTHLY_BUDGET = {
    "暂时没有预算": 0,
    "100元以内": 50,
    "101～300元": 200,
    "301～500元": 400,
    "501～1000元": 750,
    "1000元以上": 1200,
    "看商品再决定": np.nan,
}
PURCHASE_INTENT = {
    "很想买": 5,
    "比较想买": 4,
    "要看价格和成品效果": 3,
    "要看价格和成品": 3,
    "大概不会买": 2,
    "完全不会买": 1,
}
LIMITED_PREFERENCE = {
    "会明显增加购买意愿": 5,
    "会有一点吸引力": 4,
    "影响不大": 3,
    "反而会因为难买而放弃": 1,
}
PREORDER_DAYS = {
    "只考虑现货": 0,
    "1个月以内": 30,
    "1～2个月": 45,
    "2～3个月": 75,
    "3～6个月": 135,
    "只要喜欢，时间不是主要问题": 365,
}
CONCEPT_APPEAL = {
    "非常喜欢": 5,
    "比较喜欢": 4,
    "感觉一般": 3,
    "不太喜欢": 2,
    "完全不喜欢": 1,
}


@dataclass(frozen=True)
class QuestionnaireImport:
    responses: pd.DataFrame
    operator_rankings: pd.DataFrame
    category_prices: pd.DataFrame
    audit: pd.DataFrame


def _split_ranked(answer: str) -> list[str]:
    values: list[str] = []
    for part in answer.split("｜"):
        _, separator, value = part.partition("=")
        if separator and value.strip():
            values.append(value.strip())
    return values


def _split_key_values(answer: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in answer.split("｜"):
        key, separator, value = part.partition("=")
        if separator:
            result[key.strip()] = value.strip()
    return result


def _parse_yuan(answer: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", answer.replace(",", ""))
    return float(match.group(1)) if match else np.nan


def _price_band_bounds(label: str) -> tuple[float, float | None, float]:
    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", label)]
    if not numbers:
        return np.nan, None, np.nan
    if "以内" in label or "以下" in label:
        upper = numbers[0]
        return 0.0, upper, round(upper * 0.75, 2)
    if "以上" in label:
        lower = numbers[0]
        return lower, None, round(lower * 1.25, 2)
    if len(numbers) >= 2:
        lower, upper = numbers[:2]
        return lower, upper, round((lower + upper) / 2, 2)
    return numbers[0], numbers[0], numbers[0]


def _response_fingerprint(answers: dict[int, str]) -> str:
    payload = "\n".join(f"q{number}:{answers.get(number, '')}" for number in range(1, 26))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_questionnaire_text(
    source_path: Path,
    batch_id: str = "ARK-SURVEY-20260903",
) -> QuestionnaireImport:
    text = source_path.read_text(encoding="utf-8")
    matches = list(SAMPLE_PATTERN.finditer(text))
    if not matches:
        raise ValueError("No questionnaire sample blocks were found")

    response_rows: list[dict[str, object]] = []
    ranking_rows: list[dict[str, object]] = []
    price_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    fingerprints: set[str] = set()

    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : block_end]
        answers = {
            int(question.group("number")): question.group("answer").strip()
            for question in QUESTION_PATTERN.finditer(block)
        }
        sample_number = int(match.group("number"))
        response_id = f"REAL-{batch_id}-{sample_number:03d}"
        reasons: list[str] = []
        missing_questions = [number for number in range(1, 26) if number not in answers]
        if missing_questions:
            reasons.append("missing_questions:" + ",".join(map(str, missing_questions)))

        fingerprint = _response_fingerprint(answers)
        if fingerprint in fingerprints:
            reasons.append("duplicate_answer_pattern")
        fingerprints.add(fingerprint)

        operators = _split_ranked(answers.get(12, ""))
        if not operators:
            reasons.append("missing_operator_ranking")
        category = CATEGORY_ALIASES.get(answers.get(13, ""), answers.get(13, "").strip())
        if category not in set(CATEGORY_ALIASES.values()):
            reasons.append("invalid_category")
        purchase_intent = PURCHASE_INTENT.get(answers.get(14, ""))
        if purchase_intent is None:
            reasons.append("invalid_purchase_intent")
        acceptable_price = _parse_yuan(answers.get(23, ""))
        non_numeric_acceptable_price = pd.isna(acceptable_price)
        if not non_numeric_acceptable_price and not 1 <= acceptable_price <= 5000:
            reasons.append("invalid_acceptable_price")

        category_price_map = _split_key_values(answers.get(22, ""))
        selected_price_band = category_price_map.get(category, "")
        _, _, selected_price_midpoint = _price_band_bounds(selected_price_band)
        purchase_history = answers.get(4, "")
        has_purchased = purchase_history.startswith("买过《明日方舟》")
        variant = answers.get(20, "")
        randomization_group = "A" if "A款" in variant else "B" if "B款" in variant else "tie"

        response_rows.append(
            {
                "response_id": response_id,
                "respondent_id": response_id,
                "submitted_at": "",
                "consent": True,
                "consent_source": "batch_owner_attestation",
                "response_source": "anonymous_questionnaire_batch",
                "validation_profile": "anonymous_batch_without_timing",
                "completion_seconds": np.nan,
                "questionnaire_version": "v2.2-paper-batch",
                "randomization_group": randomization_group,
                "age_band": answers.get(1, ""),
                "activity_days_30d": ACTIVITY_DAYS.get(answers.get(3, ""), np.nan),
                "player_tenure_months": TENURE_MONTHS.get(answers.get(2, ""), np.nan),
                "player_status": match.group("player_status").strip(),
                "monthly_merch_budget": MONTHLY_BUDGET.get(answers.get(7, ""), np.nan),
                "has_purchased_merch": has_purchased,
                "purchase_history": purchase_history,
                "annual_merch_spend": ANNUAL_SPEND.get(answers.get(6, ""), np.nan),
                "purchase_frequency_12m": FREQUENCY.get(answers.get(5, ""), np.nan),
                "preferred_operator_1": operators[0] if len(operators) > 0 else "",
                "preferred_operator_2": operators[1] if len(operators) > 1 else "",
                "preferred_operator_3": operators[2] if len(operators) > 2 else "",
                "operator": operators[0] if operators else "",
                "category": category,
                "purchase_intent": purchase_intent,
                "acceptable_price": acceptable_price,
                "channel": answers.get(8, ""),
                "limited_preference": LIMITED_PREFERENCE.get(answers.get(15, ""), np.nan),
                "purchase_motivation": answers.get(9, ""),
                "purchase_barrier": answers.get(10, ""),
                "promotion_preference": answers.get(11, ""),
                "preorder_tolerance_days": PREORDER_DAYS.get(answers.get(16, ""), np.nan),
                "price_good_value": selected_price_midpoint,
                "concept_appeal": CONCEPT_APPEAL.get(answers.get(17, ""), np.nan),
                "concept_strength": answers.get(18, ""),
                "concept_concern": answers.get(19, ""),
                "concept_variant": variant,
                "attribute_priority": answers.get(21, ""),
                "product_improvement": answers.get(24, ""),
                "open_feedback": answers.get(25, ""),
                "is_simulated": False,
                "is_real_survey_response": True,
                "data_type": "real_anonymous_survey_user_attested",
                "source_batch_id": batch_id,
                "source_note": "Batch owner confirmed real responses; source TXT header was mislabeled.",
            }
        )

        for rank, operator in enumerate(operators, start=1):
            ranking_rows.append(
                {
                    "response_id": response_id,
                    "operator": operator,
                    "preference_rank": rank,
                    "preference_weight": 4 - rank,
                    "is_simulated": False,
                }
            )

        for price_category, price_band in category_price_map.items():
            canonical_category = CATEGORY_ALIASES.get(price_category, price_category)
            lower, upper, midpoint = _price_band_bounds(price_band)
            price_rows.append(
                {
                    "response_id": response_id,
                    "category": canonical_category,
                    "price_band": price_band,
                    "price_lower_bound": lower,
                    "price_upper_bound": upper,
                    "price_midpoint_proxy": midpoint,
                    "is_simulated": False,
                }
            )

        audit_rows.append(
            {
                "response_id": response_id,
                "question_count": len(answers),
                "valid": not reasons,
                "exclusion_reason": "|".join(reasons),
                "duplicate_fingerprint": "duplicate_answer_pattern" in reasons,
                "submitted_at_available": False,
                "completion_seconds_available": False,
                "acceptable_price_numeric": not non_numeric_acceptable_price,
            }
        )

    responses = pd.DataFrame(response_rows)
    rankings = pd.DataFrame(
        ranking_rows,
        columns=["response_id", "operator", "preference_rank", "preference_weight", "is_simulated"],
    )
    prices = pd.DataFrame(
        price_rows,
        columns=[
            "response_id",
            "category",
            "price_band",
            "price_lower_bound",
            "price_upper_bound",
            "price_midpoint_proxy",
            "is_simulated",
        ],
    )
    audit = pd.DataFrame(audit_rows)
    valid_ids = set(audit.loc[audit["valid"], "response_id"])
    return QuestionnaireImport(
        responses=responses.loc[responses["response_id"].isin(valid_ids)].reset_index(drop=True),
        operator_rankings=rankings.loc[
            lambda frame: frame["response_id"].isin(valid_ids)
        ].reset_index(drop=True),
        category_prices=prices.loc[
            lambda frame: frame["response_id"].isin(valid_ids)
        ].reset_index(drop=True),
        audit=audit,
    )


def build_questionnaire_summaries(imported: QuestionnaireImport) -> dict[str, pd.DataFrame]:
    responses = imported.responses.copy()
    rankings = imported.operator_rankings.copy()
    prices = imported.category_prices.copy()
    if responses.empty:
        return {}

    responses["user_segment"] = np.select(
        [
            responses["has_purchased_merch"]
            & (responses["annual_merch_spend"].fillna(0).ge(500)
               | responses["purchase_frequency_12m"].fillna(0).ge(4)),
            responses["has_purchased_merch"],
            ~responses["has_purchased_merch"] & responses["purchase_intent"].ge(4),
        ],
        ["core_buyer", "occasional_buyer", "potential_buyer"],
        default="observer",
    )

    profile = pd.DataFrame(
        [
            {
                "response_count": len(responses),
                "valid_response_count": int(imported.audit["valid"].sum()),
                "played_arknights_count": int(responses["player_status"].eq("玩过《明日方舟》").sum()),
                "arknights_merch_buyer_count": int(responses["has_purchased_merch"].sum()),
                "high_intent_count": int(responses["purchase_intent"].ge(4).sum()),
                "high_intent_share": responses["purchase_intent"].ge(4).mean(),
                "median_annual_spend": responses["annual_merch_spend"].median(),
                "median_monthly_budget": responses["monthly_merch_budget"].median(),
                "median_acceptable_price": responses["acceptable_price"].median(),
            }
        ]
    )
    age = responses.groupby("age_band", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        buyer_share=("has_purchased_merch", "mean"),
        high_intent_share=("purchase_intent", lambda values: values.ge(4).mean()),
        median_monthly_budget=("monthly_merch_budget", "median"),
    )
    age["respondent_share"] = age["respondent_count"] / len(responses)
    segment = responses.groupby("user_segment", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        buyer_share=("has_purchased_merch", "mean"),
        high_intent_share=("purchase_intent", lambda values: values.ge(4).mean()),
        median_annual_spend=("annual_merch_spend", "median"),
        median_monthly_budget=("monthly_merch_budget", "median"),
        median_acceptable_price=("acceptable_price", "median"),
    )
    segment["respondent_share"] = segment["respondent_count"] / len(responses)
    category = responses.groupby("category", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        buyer_share=("has_purchased_merch", "mean"),
        purchase_intent_mean=("purchase_intent", "mean"),
        high_intent_share=("purchase_intent", lambda values: values.ge(4).mean()),
        median_acceptable_price=("acceptable_price", "median"),
        median_preorder_days=("preorder_tolerance_days", "median"),
    )
    category["selection_share"] = category["respondent_count"] / len(responses)
    operator = rankings.groupby("operator", as_index=False).agg(
        preference_mentions=("response_id", "nunique"),
        weighted_preference_score=("preference_weight", "sum"),
        first_choice_count=("preference_rank", lambda values: values.eq(1).sum()),
    )
    operator["mention_share"] = operator["preference_mentions"] / len(responses)
    operator["operator_rank"] = operator["weighted_preference_score"].rank(
        method="min", ascending=False
    ).astype(int)
    operator = operator.sort_values(["operator_rank", "first_choice_count"])

    channel = responses.groupby("channel", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        buyer_share=("has_purchased_merch", "mean"),
        median_monthly_budget=("monthly_merch_budget", "median"),
    )
    channel["respondent_share"] = channel["respondent_count"] / len(responses)

    barrier_rows: list[tuple[str, str]] = []
    for row in responses[["response_id", "purchase_barrier"]].itertuples(index=False):
        for barrier in str(row.purchase_barrier).split("｜"):
            if barrier and barrier != "-":
                barrier_rows.append((row.response_id, barrier))
    barrier_long = pd.DataFrame(barrier_rows, columns=["response_id", "purchase_barrier"])
    barrier = barrier_long.groupby("purchase_barrier", as_index=False).agg(
        respondent_count=("response_id", "nunique")
    )
    barrier["respondent_share"] = barrier["respondent_count"] / len(responses)
    barrier = barrier.sort_values("respondent_count", ascending=False)

    attribute_rows: list[tuple[str, str, int]] = []
    for row in responses[["response_id", "attribute_priority"]].itertuples(index=False):
        for attribute, rank in _split_key_values(str(row.attribute_priority)).items():
            if rank.isdigit():
                attribute_rows.append((row.response_id, attribute, int(rank)))
    attribute_long = pd.DataFrame(
        attribute_rows, columns=["response_id", "attribute", "priority_rank"]
    )
    attribute = attribute_long.groupby("attribute", as_index=False).agg(
        average_rank=("priority_rank", "mean"),
        top1_count=("priority_rank", lambda values: values.eq(1).sum()),
        top3_share=("priority_rank", lambda values: values.le(3).mean()),
    )
    attribute = attribute.sort_values("average_rank")

    price = prices.groupby(["category", "price_band"], as_index=False).agg(
        respondent_count=("response_id", "nunique"),
        price_midpoint_proxy=("price_midpoint_proxy", "median"),
    )
    price["category_share"] = price["respondent_count"] / price.groupby("category")[
        "respondent_count"
    ].transform("sum")
    return {
        "profile": profile,
        "age": age.sort_values("respondent_count", ascending=False),
        "segment": segment.sort_values("respondent_count", ascending=False),
        "category": category.sort_values("respondent_count", ascending=False),
        "operator": operator,
        "channel": channel.sort_values("respondent_count", ascending=False),
        "barrier": barrier,
        "attribute": attribute,
        "price": price.sort_values(["category", "respondent_count"], ascending=[True, False]),
    }


def write_questionnaire_report(
    imported: QuestionnaireImport,
    summaries: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile = summaries["profile"].iloc[0]
    top_operators = summaries["operator"].head(15)
    top_barriers = summaries["barrier"].head(10)
    lines = [
        "# 《明日方舟》正版周边用户调研分析",
        "",
        "> 数据来源：243份匿名回收答卷。源TXT标题曾误标为模拟数据，项目维护者已确认该批次为真实回收；原始导出未包含提交时间和填写时长，因此这两项不参与清洗，也不虚构补全。",
        "",
        "## 数据质量与样本边界",
        "",
        f"- 原始答卷：{len(imported.audit)} 份；结构完整且通过字段校验：{int(imported.audit['valid'].sum())} 份。",
        f"- 角色偏好排序：{len(imported.operator_rankings)} 条；全品类价格观测：{len(imported.category_prices)} 条。",
        "- 问卷为便利抽样，适合验证方向、品类和价格假设，不应外推为全体玩家比例。",
        "- 未采集姓名、手机号、账号、IP或住址；分析表仅保留批次内匿名编号。",
        "",
        "## 核心发现",
        "",
        f"- 玩过《明日方舟》的受访者为 {int(profile['played_arknights_count'])} 人；购买过《明日方舟》正版周边的受访者为 {int(profile['arknights_merch_buyer_count'])} 人。",
        f"- 对随机展示商品表达较高购买意愿的受访者为 {int(profile['high_intent_count'])} 人，占 {float(profile['high_intent_share']):.2%}。",
        f"- 过去一年ACG周边支出中位数代理为 {float(profile['median_annual_spend']):.0f} 元，月度预算中位数代理为 {float(profile['median_monthly_budget']):.0f} 元，可接受最高价格中位数为 {float(profile['median_acceptable_price']):.0f} 元。",
        "- 角色偏好采用 Top-3 加权计分：第一名3分、第二名2分、第三名1分，避免只统计第一选择。",
        "",
        "## 角色偏好 Top 15",
        "",
        top_operators.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 正版周边品类需求",
        "",
        summaries["category"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 用户分群",
        "",
        summaries["segment"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 购买渠道",
        "",
        summaries["channel"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 主要购买阻力",
        "",
        top_barriers.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 商品属性优先级",
        "",
        summaries["attribute"].to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 运营解释",
        "",
        "- 调研结果先用于角色、品类、价格带和渠道的方向筛选，再进入固定SKU小批量验证；不能直接据此大规模备货。",
        "- ERP 模拟层使用调研中的角色Top-3、品类选择和渠道占比作为需求权重，订单、库存、采购、售后与财务数值仍明确标记为模拟数据。",
        "- 后续真实业务验证应继续观察曝光、收藏、加购、付款、退款、履约时长、复购和库存周转，形成从意愿到成交的漏斗闭环。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
