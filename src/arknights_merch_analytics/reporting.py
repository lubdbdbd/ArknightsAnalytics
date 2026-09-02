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


def save_commerce_figures(
    listings: pd.DataFrame,
    market_signals: pd.DataFrame,
    content_commerce: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    _configure_fonts()

    observed = content_commerce[content_commerce["taobao_observed"]].copy()
    if not observed.empty:
        fig, ax = plt.subplots(figsize=(10, 7))
        sizes = 80 + observed["organic_sku_count"].fillna(0) * 35
        ax.scatter(
            observed["cross_platform_heat"],
            observed["commercial_heat_score"],
            s=sizes,
            c=observed["commercial_validation_priority"],
            cmap="viridis",
            alpha=0.82,
        )
        placed_labels: list[tuple[float, float]] = []
        for _, row in observed.iterrows():
            position = (float(row["cross_platform_heat"]), float(row["commercial_heat_score"]))
            offset_index = sum(
                abs(previous_x - position[0]) < 2 and abs(previous_y - position[1]) < 2
                for previous_x, previous_y in placed_labels
            )
            placed_labels.append(position)
            ax.annotate(
                row["operator"],
                (row["cross_platform_heat"], row["commercial_heat_score"]),
                xytext=(5, 4 + offset_index * 13),
                textcoords="offset points",
            )
        ax.axvline(content_commerce["cross_platform_heat"].median(), color="#777777", linestyle="--")
        ax.axhline(observed["commercial_heat_score"].median(), color="#777777", linestyle="--")
        ax.set_title("内容热度 × 淘宝商业信号（首批公开销量页样本）")
        ax.set_xlabel("Cross-platform content heat")
        ax.set_ylabel("Taobao commercial signal")
        fig.tight_layout()
        fig.savefig(output_dir / "content_commerce_quadrant.png", dpi=180)
        plt.close(fig)

    baseline = listings[
        (listings["query_scope"] == "market_baseline")
        & (listings["ip_scope"] == "arknights")
    ].copy()
    baseline = baseline[baseline["numeric_sales_available"]]
    if not baseline.empty:
        category = baseline.groupby("category", as_index=False).agg(
            organic_sku_count=("item_id", "nunique"),
            sales_proxy_min=("sales_proxy_min", "sum"),
            median_price=("price", "median"),
        )
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(
            category["median_price"],
            category["sales_proxy_min"],
            s=80 + category["organic_sku_count"] * 45,
            color="#dd6b20",
            alpha=0.82,
        )
        for _, row in category.iterrows():
            ax.annotate(
                row["category"],
                (row["median_price"], row["sales_proxy_min"]),
                xytext=(5, 4),
                textcoords="offset points",
            )
        ax.set_title("淘宝周边品类价格带与公开收货人数代理")
        ax.set_xlabel("Median displayed price")
        ax.set_ylabel("Displayed recipient lower-bound proxy")
        fig.tight_layout()
        fig.savefig(output_dir / "taobao_category_demand.png", dpi=180)
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
    taobao_listings: pd.DataFrame | None = None,
    taobao_market_signals: pd.DataFrame | None = None,
    content_commerce: pd.DataFrame | None = None,
    targeted_query_summary: pd.DataFrame | None = None,
    tracking_registry: pd.DataFrame | None = None,
    timeseries_metrics: pd.DataFrame | None = None,
    survey_audit: pd.DataFrame | None = None,
    survey_summary: pd.DataFrame | None = None,
    selection_case_evidence: pd.DataFrame | None = None,
    selection_case_categories: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        operator_heat.to_excel(writer, sheet_name="Character Heat Matrix", index=False)
        if content_scores is not None and not content_scores.empty:
            content_scores.to_excel(writer, sheet_name="Official Content Scores", index=False)
        if xhs_snapshots is not None and not xhs_snapshots.empty:
            xhs_snapshots.to_excel(writer, sheet_name="XHS Ecosystem", index=False)
        if taobao_listings is not None and not taobao_listings.empty:
            taobao_listings.to_excel(writer, sheet_name="Taobao Public Snapshots", index=False)
        if taobao_market_signals is not None and not taobao_market_signals.empty:
            taobao_market_signals.to_excel(writer, sheet_name="Taobao Role Signals", index=False)
        if content_commerce is not None and not content_commerce.empty:
            content_commerce.to_excel(writer, sheet_name="Content Commerce Matrix", index=False)
        if targeted_query_summary is not None and not targeted_query_summary.empty:
            targeted_query_summary.to_excel(writer, sheet_name="Target Query QA", index=False)
        if tracking_registry is not None and not tracking_registry.empty:
            tracking_registry.to_excel(writer, sheet_name="SKU Tracking Registry", index=False)
        if timeseries_metrics is not None and not timeseries_metrics.empty:
            timeseries_metrics.to_excel(writer, sheet_name="SKU Timeseries", index=False)
        if survey_audit is not None:
            survey_audit.to_excel(writer, sheet_name="Survey Audit", index=False)
        if survey_summary is not None:
            survey_summary.to_excel(writer, sheet_name="Survey Summary", index=False)
        if selection_case_evidence is not None and not selection_case_evidence.empty:
            selection_case_evidence.to_excel(writer, sheet_name="Case Evidence", index=False)
        if selection_case_categories is not None and not selection_case_categories.empty:
            selection_case_categories.to_excel(writer, sheet_name="Case Categories", index=False)
        erp.to_excel(writer, sheet_name="ERP Mock", index=False)
        sku.to_excel(writer, sheet_name="SKU Recommendations", index=False)
        notes = pd.DataFrame(
            {
                "item": ["Public content", "Taobao snapshot", "Manual data", "Simulated data"],
                "definition": [
                    "Bilibili and Weibo official-account public aggregate metrics",
                    "Visible listing ID, price, rank and recipient lower-bound proxy; not exact sales",
                    "Category assumptions and survey template",
                    "Orders, sales, inventory and return data; not real sales",
                ],
            }
        )
        notes.to_excel(writer, sheet_name="Data Notes", index=False)


def write_commerce_report(
    listings: pd.DataFrame,
    market_signals: pd.DataFrame,
    content_commerce: pd.DataFrame,
    targeted_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    baseline = listings[
        (listings["query_scope"] == "market_baseline")
        & (listings["ip_scope"] == "arknights")
    ]
    observed = market_signals[market_signals["taobao_observed"]]
    top_signals = observed.head(15)[
        [
            "commerce_rank",
            "operator",
            "organic_sku_count",
            "sales_proxy_min",
            "median_price",
            "commercial_heat_score",
            "commerce_confidence_score",
            "commerce_data_grade",
        ]
    ]
    priority = content_commerce.head(15)[
        [
            "operator",
            "cross_platform_heat",
            "commercial_heat_score",
            "content_commerce_gap",
            "business_quadrant",
            "commercial_validation_priority",
        ]
    ]
    category = baseline.groupby("category", as_index=False).agg(
        organic_sku_count=("item_id", "nunique"),
        sales_proxy_min=("sales_proxy_min", "sum"),
        median_price=("price", "median"),
        official_share=("rights_type", lambda values: (values == "官方/授权").mean()),
        presale_share=("fulfillment_type", lambda values: (values == "预售/补款").mean()),
    )
    lines = [
        "# 淘宝公开商品快照与周边商业化分析",
        "",
        "> 公开展示的“收货人数”仅作为销量下界代理；`100+` 等档位按最低值记录，不能用于声称精确销量或真实 GMV。",
        "",
        "## 样本与质量控制",
        "",
        f"- 公开商品快照：{len(listings)} 条；其中全 IP 自然结果 {len(baseline)} 条。",
        f"- 有全 IP 销量页角色信号：{int(market_signals['taobao_observed'].sum())} / {len(market_signals)} 名角色。",
        "- 广告跳转位不具备稳定商品 ID，未纳入固定 SKU 时间序列。",
        "- 定向搜索结果设置角色相关性门禁，避免把阿米娅、凯尔希等跨角色商品误记为新约能天使供给。",
        "- 每条数据保留查询词、排序方式、快照时间、商品 ID、原始文本与来源文件，支持复核。",
        "",
        "## 全 IP 销量页角色商业信号",
        "",
        top_signals.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 内容热度 × 商业热度验证优先级",
        "",
        priority.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 品类结构",
        "",
        category.sort_values("sales_proxy_min", ascending=False).to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 定向搜索质量",
        "",
        targeted_summary.to_markdown(index=False, floatfmt=".2f")
        if not targeted_summary.empty
        else "暂无定向搜索样本。",
        "",
        "## 周边运营分析维度",
        "",
        "1. 需求代理：公开收货人数下界、销量排名与搜索可见度，不等同于真实成交量。",
        "2. 供给强度：自然 SKU 数、品类宽度、官方/同人结构及预售占比。",
        "3. 价格承载：中位价、四分位价格带及高客单品类占比。",
        "4. 竞争结构：角色商品覆盖、头部结果集中度与广告位干扰。",
        "5. 内容转化缺口：内容热度高但淘宝信号弱的角色优先补采收藏、评价和周期销量快照。",
        "6. 生命周期：后续以相同商品 ID 周期复采，计算价格变动、销量档位跃迁、上新和下架率。",
        "7. 商品策略：低客单验证款、利润承接款、高风险预售款分别设置不同准入门槛。",
        "8. 数据治理：真实公开数据、人工假设和模拟 ERP 分表存储，所有结论携带置信度。",
        "",
        "## 当前限制",
        "",
        "- 当前仅为首批横截面，不能计算真实销售速度；至少需要两期相同 SKU 快照。",
        "- 搜索结果受个性化、广告、地区和活动影响，榜单只能作为公开可见市场信号。",
        "- 未采集买家身份、评论正文、Cookie 或任何个人信息，也未绕过验证码和平台风控。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
