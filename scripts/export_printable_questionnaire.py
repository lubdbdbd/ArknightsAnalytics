from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "明日方舟周边用户需求调研问卷-打印版.pdf"
FONT_PATH = Path("C:/Windows/Fonts/simhei.ttf")


SECTIONS = [
    (
        "第一部分：先简单认识一下你",
        [
            ("Q1  你的年龄是？", ["18～22岁", "23～26岁", "27～30岁", "31～35岁", "36岁及以上", "不方便透露"]),
            ("Q2  你接触《明日方舟》多久了？", ["不到3个月", "3个月～1年", "1～3年", "3～5年", "开服至今", "平时不玩游戏，但会关注角色或周边"]),
            ("Q3  最近一个月，你大概多久会玩一次游戏或看看相关内容？", ["几乎每天", "每周3～5天", "每周1～2天", "偶尔上线或看看内容", "最近基本没关注"]),
        ],
    ),
    (
        "第二部分：聊聊你平时怎么买周边",
        [
            ("Q4  你以前买过《明日方舟》或其他ACG官方/正版授权周边吗？", ["买过《明日方舟》官方或正版授权周边", "没买过方舟正版周边，但买过其他ACG正版周边", "还没有买过正版周边"]),
            ("Q5  过去一年，你大概买过多少次ACG周边？", ["没买过", "1～2次", "3～5次", "6～10次", "10次以上"]),
            ("Q6  过去一年，你购买ACG周边大概花了多少钱？", ["0元", "1～200元", "201～500元", "501～1000元", "1001～3000元", "3000元以上", "记不清了"]),
            ("Q7  如果下个月遇到喜欢的周边，你大概愿意留出多少预算？", ["暂时没有预算", "100元以内", "101～300元", "301～500元", "501～1000元", "1000元以上", "看商品再决定"]),
            ("Q8  你平时最愿意从哪里买周边？", ["官方商城", "淘宝/天猫", "B站会员购", "品牌直播间", "线下展会或快闪店", "二手平台", "其他：__________"]),
            ("Q9  什么最容易让你决定买下一款周边？（最多选3项）", ["很喜欢这个角色", "画面或造型设计很好看", "材质和做工让人放心", "有收藏或凑套装的价值", "平时真的能用到", "是限定、联名或活动纪念款", "价格合适", "想支持作品或官方", "朋友推荐或社区评价很好", "其他：__________"]),
            ("Q10  什么情况最容易让你放弃购买？（最多选3项）", ["价格比预期高", "设计不太喜欢", "材质、尺寸或实物效果说不清楚", "预售时间太长", "发货进度不透明", "运费太高", "售后或退换不方便", "担心不是正版", "已经有很多同类周边", "不确定买回来怎么摆或怎么用", "其他：__________"]),
            ("Q11  哪种优惠对你更有吸引力？", ["直接降价", "包邮", "满额赠品", "角色套装更优惠", "预售特典", "积分或会员权益", "不太在意促销，更看重商品本身"]),
        ],
    ),
    (
        "第三部分：如果要出新周边，你更想看到什么",
        [
            ("Q12  如果角色推出新周边，你最想买谁的？请最多填写3名并排序。", ["第1名：________________", "第2名：________________", "第3名：________________"]),
            ("Q13  对你排在第一位的角色，你最希望看到哪类正版周边？", ["亚克力制品（立牌、摇摇乐等）", "通行证/通行认证卡", "吧唧（徽章）", "毛绒玩偶（如山山兔、龙泡泡）", "手办模玩", "装饰摆件（挂件、色纸、灯具等）", "日用生活（服饰、杯具、文具等）", "其他：__________"]),
            ("Q14  如果真的推出这款周边，你现在的想法更接近哪一种？", ["很想买", "比较想买", "要看价格和成品效果", "大概不会买", "完全不会买"]),
            ("Q15  “限定、联名或活动纪念款”会影响你的购买决定吗？", ["会明显增加购买意愿", "会有一点吸引力", "影响不大", "反而会因为难买而放弃"]),
            ("Q16  如果商品需要预售，你最多愿意等多久？", ["只考虑现货", "1个月以内", "1～2个月", "2～3个月", "3～6个月", "只要足够喜欢，等待时间不是主要问题"]),
        ],
    ),
]


def _styles():
    pdfmetrics.registerFont(TTFont("Chinese", str(FONT_PATH)))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCN", parent=base["Title"], fontName="Chinese", fontSize=20,
            leading=29, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"), spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCN", parent=base["Normal"], fontName="Chinese", fontSize=10,
            leading=17, alignment=TA_CENTER, textColor=colors.HexColor("#53677A"), spaceAfter=6 * mm,
        ),
        "intro": ParagraphStyle(
            "IntroCN", parent=base["Normal"], fontName="Chinese", fontSize=10.5,
            leading=18, alignment=TA_LEFT, textColor=colors.HexColor("#222222"), spaceAfter=3 * mm,
        ),
        "section": ParagraphStyle(
            "SectionCN", parent=base["Heading2"], fontName="Chinese", fontSize=14,
            leading=20, textColor=colors.white, backColor=colors.HexColor("#1F4E78"),
            borderPadding=(5, 7, 5, 7), spaceBefore=4 * mm, spaceAfter=4 * mm,
        ),
        "question": ParagraphStyle(
            "QuestionCN", parent=base["Normal"], fontName="Chinese", fontSize=11,
            leading=17, textColor=colors.HexColor("#111111"), spaceBefore=2 * mm, spaceAfter=1.5 * mm,
        ),
        "option": ParagraphStyle(
            "OptionCN", parent=base["Normal"], fontName="Chinese", fontSize=9.5,
            leading=16, textColor=colors.HexColor("#333333"), leftIndent=2 * mm,
        ),
        "note": ParagraphStyle(
            "NoteCN", parent=base["Normal"], fontName="Chinese", fontSize=9,
            leading=15, textColor=colors.HexColor("#666666"), spaceAfter=2 * mm,
        ),
    }


def _header_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Chinese", 8.5)
    canvas.setFillColor(colors.HexColor("#667788"))
    canvas.drawString(18 * mm, 12 * mm, "《明日方舟》周边用户需求调研问卷｜匿名学习项目")
    canvas.drawRightString(192 * mm, 12 * mm, f"第 {document.page} 页")
    canvas.setStrokeColor(colors.HexColor("#D9E2F3"))
    canvas.line(18 * mm, 16 * mm, 192 * mm, 16 * mm)
    canvas.restoreState()


def _options_table(options: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    cells = [[Paragraph(f"□ {option}", styles["option"]) for option in options[index:index + 2]] for index in range(0, len(options), 2)]
    if cells and len(cells[-1]) == 1:
        cells[-1].append("")
    table = Table(cells, colWidths=[84 * mm, 84 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6 * mm),
    ]))
    return table


def _question_block(question: str, options: list[str], styles: dict[str, ParagraphStyle]):
    return KeepTogether([
        Paragraph(question, styles["question"]),
        _options_table(options, styles),
        Spacer(1, 2 * mm),
    ])


def _concept_section(styles: dict[str, ParagraphStyle]):
    image_box = Table(
        [[Paragraph("A款概念图粘贴区", styles["subtitle"]), Paragraph("B款概念图粘贴区", styles["subtitle"])]],
        colWidths=[84 * mm, 84 * mm], rowHeights=[52 * mm],
    )
    image_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#9EADBA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D3DD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F9FB")),
    ]))
    blocks = [
        Paragraph("第四部分：看看这款商品设想", styles["section"]),
        Paragraph("请在发放前粘贴A/B两款概念图，并在图片旁写清角色、尺寸、材质、配件和预计发货时间，暂不展示价格。", styles["note"]),
        image_box,
        Spacer(1, 4 * mm),
        _question_block("Q17  看到这款商品时，你的第一感觉是？", ["非常喜欢", "比较喜欢", "感觉一般", "不太喜欢", "完全不喜欢"], styles),
        _question_block("Q18  这款商品最吸引你的地方是什么？（最多选3项）", ["角色选择", "画面或造型", "配色", "材质与工艺", "尺寸", "配件或玩法", "实用性", "收藏价值", "暂时没有特别吸引我的地方", "其他：__________"], styles),
        _question_block("Q19  你购买前最想进一步确认什么？（最多选3项）", ["实物图和细节", "具体尺寸", "材质和工艺", "是否为正版授权", "最终价格", "发货时间", "售后规则", "是否容易缺货或限量", "其他：__________"], styles),
        _question_block("Q20  如果同时有A、B两种设计，你更喜欢哪一种？", ["更喜欢A款", "更喜欢B款", "两款都可以", "两款都不太喜欢"], styles),
    ]
    ranking = [["因素", "排序"], ["角色和画面设计", "____"], ["材质与做工", "____"], ["正版授权", "____"], ["实用性", "____"], ["价格", "____"], ["限定或收藏价值", "____"]]
    ranking_table = Table(ranking, colWidths=[130 * mm, 38 * mm])
    ranking_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Chinese"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#8FA6B8")),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    blocks.append(KeepTogether([
        Paragraph("Q21  购买周边时，请将下列因素按重要程度排序（1最重要，6最不重要）。", styles["question"]),
        ranking_table,
        Spacer(1, 3 * mm),
    ]))
    return blocks


def _price_section(styles: dict[str, ParagraphStyle]):
    price_rows = [
        ["品类", "第一档", "第二档", "第三档", "第四档"],
        ["吧唧（徽章）", "□ 15元内", "□ 16～25元", "□ 26～35元", "□ 36元以上"],
        ["通行证", "□ 20元内", "□ 21～40元", "□ 41～60元", "□ 60元以上"],
        ["亚克力制品", "□ 30元内", "□ 31～50元", "□ 51～80元", "□ 80元以上"],
        ["毛绒玩偶", "□ 80元内", "□ 81～150元", "□ 151～250元", "□ 250元以上"],
        ["手办模玩", "□ 200元内", "□ 201～500元", "□ 501～1000元", "□ 1000元以上"],
        ["装饰摆件", "□ 50元内", "□ 51～100元", "□ 101～200元", "□ 200元以上"],
        ["日用生活", "□ 50元内", "□ 51～100元", "□ 101～200元", "□ 200元以上"],
    ]
    price_table = Table(price_rows, colWidths=[32 * mm, 34 * mm, 34 * mm, 34 * mm, 34 * mm])
    price_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Chinese"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#8FA6B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
    ]))
    return [
        Paragraph("第五部分：最后聊聊价格和建议", styles["section"]),
        Paragraph("Q22  如果商品的设计和质量符合预期，你觉得什么价格比较合适？请在对应品类中勾选。", styles["question"]),
        price_table,
        Spacer(1, 3 * mm),
        Paragraph("Q23  对这类商品来说，价格超过多少时你大概率不会考虑？", styles["question"]),
        Paragraph("人民币：________________ 元    □ 只要足够喜欢，价格不是主要因素", styles["option"]),
        Spacer(1, 4 * mm),
        Paragraph("Q24【选答】如果只能改进这款商品的一点，你最希望改哪里？", styles["question"]),
        Paragraph("________________________________________________________________________________", styles["option"]),
        Paragraph("________________________________________________________________________________", styles["option"]),
        Spacer(1, 4 * mm),
        Paragraph("Q25【选答】关于《明日方舟》周边，你还有什么特别想买、想吐槽或想建议的吗？", styles["question"]),
        Paragraph("________________________________________________________________________________", styles["option"]),
        Paragraph("________________________________________________________________________________", styles["option"]),
        Paragraph("________________________________________________________________________________", styles["option"]),
        Spacer(1, 8 * mm),
        Paragraph("感谢填写！每一条真实反馈都会帮助我们更准确地理解玩家，而不是只靠播放量或搜索热度猜测需求。", styles["intro"]),
    ]


def main() -> None:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Chinese font not found: {FONT_PATH}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm, title="明日方舟周边用户需求调研问卷",
        author="ConstantineChenn",
    )
    story = [
        Paragraph("博士，想听听你对《明日方舟》周边的想法", styles["title"]),
        Paragraph("版本 v2.2｜预计用时 5～8 分钟｜匿名用户需求研究", styles["subtitle"]),
        Paragraph("你好，博士！我们正在了解大家平时会关注、购买什么样的《明日方舟》官方或正版授权周边，也想知道哪些设计、价格或购买体验会影响你的选择。本问卷不讨论盗版、无授权商品或数字权益。问卷没有标准答案，按照真实习惯填写即可。", styles["intro"]),
        Paragraph("本次填写全程匿名，不收集姓名、手机号、游戏账号、IP或住址。结果仅以汇总形式用于个人学习项目分析。填写完全自愿，你可以随时停止。", styles["intro"]),
        Spacer(1, 2 * mm),
        Paragraph("问卷编号：________________    发放渠道：________________    填写日期：____年__月__日", styles["question"]),
        Paragraph("□ 我已阅读以上说明并自愿参与。", styles["question"]),
        Spacer(1, 4 * mm),
    ]
    for section_title, questions in SECTIONS:
        story.append(Paragraph(section_title, styles["section"]))
        for question, options in questions:
            story.append(_question_block(question, options, styles))
    story.append(PageBreak())
    story.extend(_concept_section(styles))
    story.extend(_price_section(styles))
    document.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
