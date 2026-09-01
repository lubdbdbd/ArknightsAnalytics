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


def save_figures(operator_heat: pd.DataFrame, sku: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    _configure_fonts()

    top_heat = operator_heat.head(12).sort_values("heat_score")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_heat["operator"], top_heat["heat_score"], color="#2c7fb8")
    ax.set_title("Operator Public-Content Heat Score")
    ax.set_xlabel("Heat score (0-100 percentile composite)")
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


def write_report(operator_heat: pd.DataFrame, sku: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_operators = operator_heat.head(5)[["heat_rank", "operator", "heat_score", "total_views"]]
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
        f"- 识别角色数：{len(operator_heat)}",
        f"- 模拟 SKU 数：{len(sku)}",
        f"- 模拟 GMV：¥{sku['gmv'].sum():,.2f}",
        f"- 平均模拟售罄率：{sku['sell_through_rate'].mean():.2%}",
        "",
        "## 角色热度 Top 5",
        "",
        top_operators.to_markdown(index=False, floatfmt=".2f"),
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
        "- 公开内容热度无法替代真实购买意愿和销量数据。",
        "- 模拟 ERP 仅用于验证指标、代码和看板结构。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_workbook(operator_heat: pd.DataFrame, erp: pd.DataFrame, sku: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        operator_heat.to_excel(writer, sheet_name="Operator Heat", index=False)
        erp.to_excel(writer, sheet_name="ERP Mock", index=False)
        sku.to_excel(writer, sheet_name="SKU Recommendations", index=False)
        notes = pd.DataFrame(
            {
                "item": ["Public data", "Manual data", "Simulated data"],
                "definition": [
                    "Official public-content aggregate metrics",
                    "Category assumptions and survey template",
                    "Orders, sales, inventory and return data; not real sales",
                ],
            }
        )
        notes.to_excel(writer, sheet_name="Data Notes", index=False)
