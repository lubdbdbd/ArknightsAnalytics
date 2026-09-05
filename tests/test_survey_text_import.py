from __future__ import annotations

from pathlib import Path

from arknights_merch_analytics.survey_text_import import (
    build_questionnaire_summaries,
    parse_questionnaire_text,
)


def test_imports_questionnaire_text_and_price_matrix(tmp_path: Path) -> None:
    answers = "\n".join(
        [
            "q1.18～22岁",
            "q2.开服至今",
            "q3.几乎每天",
            "q4.买过《明日方舟》官方或正版授权周边",
            "q5.3～5次",
            "q6.501～1000元",
            "q7.101～300元",
            "q8.官方商城",
            "q9.很喜欢这个角色｜价格合适",
            "q10.价格比预期高｜预售周期过长",
            "q11.包邮",
            "q12.第1名=能天使｜第2名=凯尔希｜第3名=阿米娅",
            "q13.亚克力制品（立牌、摇摇乐等）",
            "q14.很想买",
            "q15.会明显增加购买意愿",
            "q16.1～2个月",
            "q17.非常喜欢",
            "q18.角色选择｜材质与工艺",
            "q19.最终价格｜发货时间",
            "q20.更喜欢A款",
            "q21.角色和画面设计=1｜材质与做工=2｜正版授权=3｜实用性=6｜价格=4｜限定或收藏价值=5",
            "q22.吧唧（徽章）=16～25元｜通行证=21～40元｜亚克力制品=31～50元｜毛绒玩偶=81～150元｜手办模玩=501～1000元｜装饰摆件=51～100元｜日用生活=51～100元",
            "q23.120元",
            "q24.希望增加实物图",
            "q25.-",
        ]
    )
    source = tmp_path / "answers.txt"
    source.write_text(
        "问卷答案\n===== 样本001｜玩过《明日方舟》 =====\n" + answers,
        encoding="utf-8",
    )

    imported = parse_questionnaire_text(source, batch_id="TEST-BATCH")
    summaries = build_questionnaire_summaries(imported)

    assert len(imported.responses) == 1
    assert len(imported.operator_rankings) == 3
    assert len(imported.category_prices) == 7
    assert imported.responses.iloc[0]["category"] == "亚克力制品"
    assert imported.responses.iloc[0]["purchase_intent"] == 5
    assert imported.responses.iloc[0]["is_simulated"] == False
    assert summaries["operator"].iloc[0]["operator"] == "能天使"
    assert summaries["profile"].iloc[0]["high_intent_count"] == 1


def test_import_keeps_non_numeric_price_as_missing(tmp_path: Path) -> None:
    answers = "\n".join([f"q{number}.x" for number in range(1, 26)])
    answers = answers.replace("q12.x", "q12.第1名=能天使｜第2名=凯尔希｜第3名=阿米娅")
    answers = answers.replace("q13.x", "q13.日用生活（服饰、杯具、文具等）")
    answers = answers.replace("q14.x", "q14.比较想买")
    answers = answers.replace("q23.x", "q23.只要足够喜欢，价格不是主要因素")
    source = tmp_path / "answers.txt"
    source.write_text(
        "===== 样本001｜玩过《明日方舟》 =====\n" + answers,
        encoding="utf-8",
    )

    imported = parse_questionnaire_text(source)

    assert len(imported.responses) == 1
    assert imported.responses.iloc[0]["category"] == "日用生活"
    assert imported.responses.iloc[0]["acceptable_price"] != imported.responses.iloc[0]["acceptable_price"]
