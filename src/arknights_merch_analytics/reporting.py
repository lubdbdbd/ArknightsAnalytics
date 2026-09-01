from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _configure_fonts() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def save_figures(
    operator_heat: pd.DataFrame,
    sku: pd.DataFrame,
    output_dir: Path,
    xhs_snapshots: pd.DataFrame | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    _configure_fonts()

    top_heat = operator_heat.head(15).sort_values("heat_score")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_heat["operator"], top_heat["heat_score"], color="#2c7fb8")
    ax.set_title("角色跨平台公开内容热度 Top 15")
    ax.set_xlabel("Cross-platform heat score")
    fig.tight_layout()
    fig.savefig(output_dir / "operator_heat.png", dpi=180)
    plt.close(fig)

    category = sku.groupby("category", as_index=False).agg(
        selection_score=("selection_score", "mean"),
        gmv=("gmv", "sum"),
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(category["selection_score"], category["gmv"], s=100, color="#31a354")
    for _, row in category.iterrows():
        ax.annotate(row["category"], (row["selection_score"], row["gmv"]), xytext=(5, 4), textcoords="offset points")
    ax.set_title("Category Selection Score vs Simulated GMV")
    ax.set_xlabel("Average selection score")
    ax.set_ylabel("Simulated GMV")
    fig.tight_layout()
    fig.savefig(output_dir / "category_portfolio.png", dpi=180)
    plt.close(fig)

    platform_columns = [column for column in ["bilibili_heat", "weibo_heat"] if column in operator_heat]
    if platform_columns:
        heatmap = operator_heat.head(20).set_index("operator")[platform_columns].T
        fig, ax = plt.subplots(figsize=(14, 4.5))
        image = ax.imshow(heatmap.fillna(0), cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)
        ax.set_xticks(range(len(heatmap.columns)), labels=heatmap.columns, rotation=55, ha="right")
        ax.set_yticks(range(len(heatmap.index)), labels=["Bilibili", "Weibo"][: len(heatmap.index)])
        ax.set_title("角色官方内容跨平台热度矩阵（缺失值显示为 0，不参与真实评分）")
        fig.colorbar(image, ax=ax, label="Platform heat score")
        fig.tight_layout()
        fig.savefig(output_dir / "platform_heat_matrix.png", dpi=180)
        plt.close(fig)

    if xhs_snapshots is not None and not xhs_snapshots.empty:
        ordered = xhs_snapshots.sort_values("snapshot_date")
        fig, ax = plt.subplots(figsize=(9, 5))
        labels = ordered["snapshot_date"].astype(str) + "\n" + ordered["window"].astype(str)
        ax.bar(labels, ordered["interaction_per_note"], color="#c51b8a")
        ax.set_title("小红书品牌生态快照（窗口不同，仅作独立观察）")
        ax.set_xlabel("Snapshot / window")
        ax.set_ylabel("Interactions per note")
        fig.tight_layout()
        fig.savefig(output_dir / "xiaohongshu_ecosystem.png", dpi=180)
        plt.close(fig)


def write_report(
    operator_heat: pd.DataFrame,
    sku: pd.DataFrame,
    output_path: Path,
    xhs_snapshots: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_columns = [
        "heat_rank",
        "operator",
        "cross_platform_heat",
        "bilibili_heat",
        "weibo_heat",
        "intent_score",
        "viral_potential_score",
        "merch_opportunity_score",
        "confidence_score",
        "data_quality_grade",
    ]
    top_operators = operator_heat.head(15)[[column for column in top_columns if column in operator_heat]]
    top_skus = sku.head(10)[
        ["sku_id", "selection_score", "recommendation", "sell_through_rate", "gross_margin_rate"]
    ]
    lines = [
        "# 《明日方舟》IP角色热度驱动的周边选品分析",
        "",
        "> 本报告将公开内容互动指标作为角色关注度代理变量；ERP、订单和库存均为模拟数据，不代表真实商业表现。",
        "",
        "## 数据概览",
        "",
        f"- 角色榜单规模：{len(operator_heat)}",
        f"- 有微博角色级交叉验证：{int(operator_heat.get('weibo_role_data_available', pd.Series(dtype=bool)).sum())}",
        "- 小红书：公开品牌生态快照，不冒充角色级官方笔记数据",
        f"- 模拟 SKU 数：{len(sku)}",
        f"- 模拟 GMV：¥{sku['gmv'].sum():,.2f}",
        f"- 平均模拟售罄率：{sku['sell_through_rate'].mean():.2%}",
        "",
        "## 角色综合热度 Top 15",
        "",
        top_operators.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 多维指标解释",
        "",
        "- Reach：累计触达规模；Momentum：按发布时间校正后的传播速度。",
        "- Engagement：综合互动质量；Intent：收藏、投币或转发等深层动作。",
        "- Discussion：评论与弹幕讨论；Consistency：B站与微博热度的一致程度。",
        "- Confidence：平台覆盖、内容样本量与数据粒度共同形成的数据可信度。",
        "- Evergreen：长期触达与互动沉淀；Viral Potential：近期传播速度与讨论爆发力。",
        "- Merch Opportunity：内容热度、收藏/转发意向、一致性与可信度的候选选品分。",
        "",
        "## SKU 推荐 Top 10",
        "",
        top_skus.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 运营建议",
        "",
        "1. 高热度角色优先采用徽章、色纸和立牌完成低风险需求验证，再根据售罄率追加毛绒或手办预售。",
        "2. 高生产风险品类使用预售和分批补货，避免把内容热度直接等同于购买需求。",
        "3. 直播间以低客单引流款开场，以立牌和组合套装承接转化，高客单手办放在核心内容讲解后。",
        "4. 正式商业决策前必须补充真实用户调研、商品收藏加购和历史订单数据。",
        "",
        "## 方法限制",
        "",
        "- 不同视频发布时间、内容类型和平台推荐流量会影响互动指标。",
        "- 微博镜像仅覆盖近期官号内容；未出现不代表角色没有市场热度。",
        "- 小红书公开开放接口暂不提供角色级官方笔记读取，因此仅用于生态校准。",
        "- 小红书快照包含日、周、月不同统计窗口，只能独立观察，不能直接连成时间趋势。",
        "- 公开内容热度无法替代真实购买意愿和销量数据。",
        "- 模拟 ERP 仅用于验证指标、代码和看板结构。",
    ]
    if xhs_snapshots is not None and not xhs_snapshots.empty:
        xhs_table = xhs_snapshots[
            ["snapshot_date", "window", "rank", "note_count", "interaction_total", "interaction_per_note"]
        ]
        lines.extend(["", "## 小红书品牌生态快照", "", xhs_table.to_markdown(index=False, floatfmt=".2f")])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_workbook(
    operator_heat: pd.DataFrame,
    erp: pd.DataFrame,
    sku: pd.DataFrame,
    output_path: Path,
    content_scores: pd.DataFrame | None = None,
    xhs_snapshots: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        operator_heat.to_excel(writer, sheet_name="Character Heat Matrix", index=False)
        if content_scores is not None and not content_scores.empty:
            content_scores.to_excel(writer, sheet_name="Official Content Scores", index=False)
        if xhs_snapshots is not None and not xhs_snapshots.empty:
            xhs_snapshots.to_excel(writer, sheet_name="XHS Ecosystem", index=False)
        erp.to_excel(writer, sheet_name="ERP Mock", index=False)
        sku.to_excel(writer, sheet_name="SKU Recommendations", index=False)
        notes = pd.DataFrame(
            {
                "item": ["Public data", "Manual data", "Simulated data"],
                "definition": [
                    "Bilibili and Weibo official-account public aggregate metrics",
                    "Category assumptions and survey template",
                    "Orders, sales, inventory and return data; not real sales",
                ],
            }
        )
        notes.to_excel(writer, sheet_name="Data Notes", index=False)
