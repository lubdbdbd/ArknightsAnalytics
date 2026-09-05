from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


CHANNEL_ALIASES = {
    "淘宝/天猫": "淘宝/天猫",
    "官方商城": "官方商城",
    "B站会员购": "B站会员购",
    "直播间": "直播间",
    "品牌直播间": "直播间",
    "线下展会或快闪店": "线下展会或快闪店",
    "二手平台": "二手平台",
    "其他": "其他",
}
LEAD_TIME_DAYS = {
    "吧唧（徽章）": 12,
    "通行证": 14,
    "亚克力制品": 18,
    "装饰摆件": 25,
    "日用生活": 30,
    "毛绒玩偶": 40,
    "手办模玩": 90,
}
SUPPLIERS = {
    "吧唧（徽章）": "SUP-METAL-01",
    "通行证": "SUP-PRINT-01",
    "亚克力制品": "SUP-ACRYLIC-01",
    "装饰摆件": "SUP-DECOR-01",
    "日用生活": "SUP-LIFESTYLE-01",
    "毛绒玩偶": "SUP-PLUSH-01",
    "手办模玩": "SUP-FIGURE-01",
}
RETURN_REASONS = {
    "亚克力制品": ["表面划痕", "印刷偏色", "尺寸与预期不符"],
    "通行证": ["印刷瑕疵", "运输折损", "重复购买"],
    "吧唧（徽章）": ["表面划痕", "别针松动", "重复购买"],
    "毛绒玩偶": ["车线瑕疵", "填充不均", "尺寸与预期不符"],
    "手办模玩": ["涂装瑕疵", "零件损坏", "到货与宣传差异"],
    "装饰摆件": ["运输破损", "安装困难", "尺寸与预期不符"],
    "日用生活": ["尺码不合适", "材质与预期不符", "功能异常"],
}
EXCLUDED_OPERATOR_ENTITIES = {"丰川祥子"}


def _normalized_weights(values: pd.Series, floor: float = 0.02) -> np.ndarray:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0.0).to_numpy(float)
    numeric = numeric + floor
    return numeric / numeric.sum()


def _survey_weights(
    responses: pd.DataFrame,
    rankings: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    if rankings.empty:
        operator_weights: dict[str, float] = {}
    else:
        operator_scores = rankings.groupby("operator")["preference_weight"].sum()
        operator_weights = (operator_scores / operator_scores.sum()).to_dict()
    if responses.empty:
        return operator_weights, {}, {}
    category_counts = responses["category"].value_counts(normalize=True)
    channel_counts = responses["channel"].map(CHANNEL_ALIASES).fillna("其他").value_counts(normalize=True)
    return operator_weights, category_counts.to_dict(), channel_counts.to_dict()


def simulate_erp_operations(
    base_skus: pd.DataFrame,
    responses: pd.DataFrame,
    rankings: pd.DataFrame,
    start_date: str = "2026-06-01",
    days: int = 90,
    order_count: int = 6000,
    seed: int = 20260903,
) -> dict[str, pd.DataFrame]:
    if base_skus.empty:
        raise ValueError("Base SKU table cannot be empty")
    if days <= 0 or order_count <= 0:
        raise ValueError("days and order_count must be positive")
    rng = np.random.default_rng(seed)
    operator_weights, category_weights, channel_weights = _survey_weights(responses, rankings)
    skus = base_skus.loc[
        ~base_skus["operator"].astype(str).isin(EXCLUDED_OPERATOR_ENTITIES)
    ].copy().reset_index(drop=True)
    required = {
        "sku_id",
        "operator",
        "category",
        "price",
        "unit_cost",
        "heat_score",
        "launch_inventory",
        "sold_units",
        "production_risk",
    }
    missing = required.difference(skus.columns)
    if missing:
        raise ValueError(f"Missing base SKU columns: {sorted(missing)}")

    operator_factor = skus["operator"].map(operator_weights).fillna(0.0)
    category_factor = skus["category"].map(category_weights).fillna(0.0)
    heat_factor = pd.to_numeric(skus["heat_score"], errors="coerce").fillna(0.0) / 100
    demand_score = 0.45 * operator_factor + 0.35 * category_factor + 0.20 * heat_factor
    sku_probabilities = _normalized_weights(demand_score)

    sku_master = skus[
        [
            "sku_id",
            "operator",
            "category",
            "price",
            "unit_cost",
            "production_risk",
            "launch_inventory",
            "sold_units",
        ]
    ].copy()
    sku_master.insert(0, "sku_code", [f"AK-{index:04d}" for index in range(1, len(skus) + 1)])
    sku_master["product_name"] = sku_master["operator"] + " " + sku_master["category"]
    sku_master["supplier_id"] = sku_master["category"].map(SUPPLIERS)
    sku_master["purchase_lead_time_days"] = sku_master["category"].map(LEAD_TIME_DAYS).fillna(30)
    expected_total_units = order_count * 1.29 * 1.13 * 0.965 * 0.985
    sku_master["average_daily_demand_plan"] = (
        expected_total_units * sku_probabilities / max(days, 1)
    ).round(2)
    sku_master["safety_stock"] = np.maximum(
        8,
        np.ceil(
            sku_master["average_daily_demand_plan"]
            * np.sqrt(sku_master["purchase_lead_time_days"])
            * (1.3 + sku_master["production_risk"])
        ),
    ).astype(int)
    sku_master["reorder_point"] = np.ceil(
        sku_master["average_daily_demand_plan"] * sku_master["purchase_lead_time_days"]
        + sku_master["safety_stock"]
    ).astype(int)
    opening_cover_days = np.minimum(
        sku_master["purchase_lead_time_days"] * 1.35 + 14,
        days * 0.72,
    )
    sku_master["initial_stock"] = np.maximum(
        np.ceil(sku_master["average_daily_demand_plan"] * opening_cover_days),
        sku_master["reorder_point"] + sku_master["safety_stock"],
    ).astype(int)
    sku_master["sku_status"] = "active"
    sku_master["is_simulated"] = True
    sku_master["simulation_seed"] = seed

    dates = pd.date_range(start=start_date, periods=days, freq="D")
    day_index = np.arange(days)
    campaign_curve = (
        1.0
        + 1.4 * np.exp(-((day_index - int(days * 0.20)) ** 2) / (2 * max(days * 0.035, 1) ** 2))
        + 0.9 * np.exp(-((day_index - int(days * 0.66)) ** 2) / (2 * max(days * 0.05, 1) ** 2))
    )
    weekend_factor = np.array([1.20 if date.dayofweek >= 5 else 1.0 for date in dates])
    date_probabilities = campaign_curve * weekend_factor
    date_probabilities /= date_probabilities.sum()

    if channel_weights:
        channels = np.array(list(channel_weights), dtype=object)
        channel_probabilities = np.array(list(channel_weights.values()), dtype=float)
        channel_probabilities /= channel_probabilities.sum()
    else:
        channels = np.array(["官方商城", "淘宝/天猫", "B站会员购", "直播间"], dtype=object)
        channel_probabilities = np.array([0.30, 0.35, 0.20, 0.15])

    order_rows: list[dict[str, object]] = []
    line_rows: list[dict[str, object]] = []
    for order_number in range(1, order_count + 1):
        order_id = f"ORD-{order_number:07d}"
        order_date = pd.Timestamp(rng.choice(dates, p=date_probabilities))
        channel = str(rng.choice(channels, p=channel_probabilities))
        line_count = int(rng.choice([1, 2, 3], p=[0.76, 0.20, 0.04]))
        line_count = min(line_count, len(sku_master))
        selected_indices = rng.choice(
            len(sku_master), size=line_count, replace=False, p=sku_probabilities
        )
        payment_status = str(rng.choice(["paid", "cancelled"], p=[0.965, 0.035]))
        if payment_status == "cancelled":
            fulfillment_status = "cancelled"
        else:
            fulfillment_status = str(
                rng.choice(["delivered", "shipped", "pending"], p=[0.94, 0.045, 0.015])
            )
        order_amount = 0.0
        discount_amount = 0.0
        for line_number, sku_index in enumerate(selected_indices, start=1):
            sku = sku_master.iloc[int(sku_index)]
            quantity = int(rng.choice([1, 2, 3], p=[0.88, 0.105, 0.015]))
            unit_price = float(sku["price"])
            discount_rate = float(rng.choice([0.0, 0.05, 0.10, 0.15], p=[0.55, 0.20, 0.20, 0.05]))
            gross = unit_price * quantity
            discount = round(gross * discount_rate, 2)
            order_amount += gross
            discount_amount += discount
            line_rows.append(
                {
                    "order_line_id": f"{order_id}-{line_number}",
                    "order_id": order_id,
                    "order_date": order_date.date().isoformat(),
                    "sku_id": sku["sku_id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_rate": discount_rate,
                    "discount_amount": discount,
                    "net_revenue": round(gross - discount, 2),
                    "unit_cost": float(sku["unit_cost"]),
                    "line_cost": round(float(sku["unit_cost"]) * quantity, 2),
                    "payment_status": payment_status,
                    "fulfillment_status": fulfillment_status,
                    "is_simulated": True,
                    "simulation_seed": seed,
                }
            )
        shipping_fee = 0.0 if order_amount - discount_amount >= 99 else float(
            rng.choice([0, 8, 10, 12], p=[0.35, 0.35, 0.20, 0.10])
        )
        paid_amount = 0.0 if payment_status == "cancelled" else round(
            order_amount - discount_amount + shipping_fee, 2
        )
        order_rows.append(
            {
                "order_id": order_id,
                "order_date": order_date.date().isoformat(),
                "channel": channel,
                "customer_segment": str(
                    rng.choice(
                        ["core_buyer", "occasional_buyer", "potential_buyer"],
                        p=[0.42, 0.43, 0.15],
                    )
                ),
                "payment_status": payment_status,
                "fulfillment_status": fulfillment_status,
                "order_amount": round(order_amount, 2),
                "discount_amount": round(discount_amount, 2),
                "shipping_fee": shipping_fee,
                "paid_amount": paid_amount,
                "is_simulated": True,
                "simulation_seed": seed,
            }
        )

    orders = pd.DataFrame(order_rows)
    order_lines = pd.DataFrame(line_rows)
    eligible_lines = order_lines.loc[
        order_lines["payment_status"].eq("paid")
        & order_lines["fulfillment_status"].isin(["delivered", "shipped"])
    ].copy()
    eligible_lines = eligible_lines.merge(
        sku_master[["sku_id", "category", "production_risk"]], on="sku_id", how="left"
    )

    after_sales_rows: list[dict[str, object]] = []
    for row in eligible_lines.itertuples(index=False):
        case_probability = min(0.025 + float(row.production_risk) * 0.075, 0.12)
        if rng.random() >= case_probability:
            continue
        case_type = str(rng.choice(["refund", "return", "exchange"], p=[0.34, 0.46, 0.20]))
        requested_at = pd.Timestamp(row.order_date) + pd.Timedelta(days=int(rng.integers(2, 16)))
        resolution_days = int(rng.integers(1, 8))
        units = min(int(row.quantity), int(rng.choice([1, 2], p=[0.92, 0.08])))
        refund_amount = round(float(row.unit_price) * units, 2) if case_type != "exchange" else 0.0
        after_sales_rows.append(
            {
                "case_id": f"AS-{len(after_sales_rows) + 1:06d}",
                "order_id": row.order_id,
                "sku_id": row.sku_id,
                "case_type": case_type,
                "reason": str(rng.choice(RETURN_REASONS.get(row.category, ["其他"]))),
                "requested_at": requested_at.date().isoformat(),
                "resolved_at": (requested_at + pd.Timedelta(days=resolution_days)).date().isoformat(),
                "units": units,
                "refund_amount": refund_amount,
                "case_status": "closed",
                "is_simulated": True,
                "simulation_seed": seed,
            }
        )
    after_sales = pd.DataFrame(
        after_sales_rows,
        columns=[
            "case_id",
            "order_id",
            "sku_id",
            "case_type",
            "reason",
            "requested_at",
            "resolved_at",
            "units",
            "refund_amount",
            "case_status",
            "is_simulated",
            "simulation_seed",
        ],
    )

    daily_sales = (
        eligible_lines.groupby(["order_date", "sku_id"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"order_date": "snapshot_date", "quantity": "sold_units"})
    )
    if after_sales.empty:
        daily_returns = pd.DataFrame(columns=["snapshot_date", "sku_id", "returned_units"])
    else:
        daily_returns = (
            after_sales.loc[after_sales["case_type"].isin(["return", "exchange"])]
            .groupby(["resolved_at", "sku_id"], as_index=False)["units"]
            .sum()
            .rename(columns={"resolved_at": "snapshot_date", "units": "returned_units"})
        )
    sales_lookup = daily_sales.set_index(["snapshot_date", "sku_id"])["sold_units"].to_dict()
    returns_lookup = daily_returns.set_index(["snapshot_date", "sku_id"])["returned_units"].to_dict()

    inventory_rows: list[dict[str, object]] = []
    purchase_rows: list[dict[str, object]] = []
    for sku in sku_master.itertuples(index=False):
        stock = int(sku.initial_stock)
        scheduled_receipts: dict[str, tuple[str, int]] = {}
        open_purchase = False
        for snapshot_date in dates:
            date_key = snapshot_date.date().isoformat()
            opening_stock = stock
            po_id = ""
            inbound_units = 0
            if date_key in scheduled_receipts:
                po_id, inbound_units = scheduled_receipts[date_key]
                stock += inbound_units
                open_purchase = False
                for purchase in purchase_rows:
                    if purchase["po_id"] == po_id:
                        purchase["received_date"] = date_key
                        purchase["quantity_received"] = inbound_units
                        purchase["purchase_status"] = "received"
                        break
            requested_sales = int(sales_lookup.get((date_key, sku.sku_id), 0))
            sold_units = min(stock, requested_sales)
            stock -= sold_units
            returned_units = int(returns_lookup.get((date_key, sku.sku_id), 0))
            restockable_returns = int(round(returned_units * 0.72))
            damaged_units = returned_units - restockable_returns
            stock += restockable_returns
            stockout_units = max(requested_sales - sold_units, 0)
            if stock <= int(sku.reorder_point) and not open_purchase:
                order_quantity = max(
                    int(sku.reorder_point * 2 - stock),
                    int(np.ceil(sku.average_daily_demand_plan * sku.purchase_lead_time_days)),
                    24,
                )
                expected = snapshot_date + pd.Timedelta(days=int(sku.purchase_lead_time_days))
                delay_probability = min(0.06 + float(sku.production_risk) * 0.22, 0.28)
                delay_days = int(rng.integers(1, 8)) if rng.random() < delay_probability else 0
                actual_receipt = expected + pd.Timedelta(days=delay_days)
                fill_rate = float(
                    rng.uniform(0.88, 0.97) if rng.random() < float(sku.production_risk) * 0.18 else 1.0
                )
                receipt_quantity = max(1, int(round(order_quantity * fill_rate)))
                po_number = len(purchase_rows) + 1
                po_id = f"PO-{po_number:06d}"
                purchase_rows.append(
                    {
                        "po_id": po_id,
                        "supplier_id": sku.supplier_id,
                        "sku_id": sku.sku_id,
                        "order_date": date_key,
                        "expected_date": expected.date().isoformat(),
                        "received_date": "",
                        "quantity_ordered": order_quantity,
                        "quantity_received": 0,
                        "unit_purchase_cost": sku.unit_cost,
                        "purchase_amount": round(order_quantity * sku.unit_cost, 2),
                        "purchase_status": "open",
                        "is_simulated": True,
                        "simulation_seed": seed,
                    }
                )
                if actual_receipt <= dates[-1]:
                    scheduled_receipts[actual_receipt.date().isoformat()] = (
                        po_id,
                        receipt_quantity,
                    )
                open_purchase = True
            locked_stock = min(stock, max(0, int(round(sku.average_daily_demand_plan * 0.5))))
            inventory_rows.append(
                {
                    "snapshot_date": date_key,
                    "sku_id": sku.sku_id,
                    "opening_stock": opening_stock,
                    "inbound_units": inbound_units,
                    "requested_sales_units": requested_sales,
                    "sold_units": sold_units,
                    "stockout_units": stockout_units,
                    "returned_units": returned_units,
                    "restockable_return_units": restockable_returns,
                    "damaged_units": damaged_units,
                    "closing_stock": stock,
                    "locked_stock": locked_stock,
                    "available_stock": max(stock - locked_stock, 0),
                    "is_simulated": True,
                    "simulation_seed": seed,
                }
            )
    inventory = pd.DataFrame(inventory_rows)
    purchases = pd.DataFrame(
        purchase_rows,
        columns=[
            "po_id",
            "supplier_id",
            "sku_id",
            "order_date",
            "expected_date",
            "received_date",
            "quantity_ordered",
            "quantity_received",
            "unit_purchase_cost",
            "purchase_amount",
            "purchase_status",
            "is_simulated",
            "simulation_seed",
        ],
    )

    paid_lines = order_lines.loc[order_lines["payment_status"].eq("paid")].copy()
    finance = paid_lines.groupby("sku_id", as_index=False).agg(
        sold_units=("quantity", "sum"),
        gross_sales=("unit_price", lambda values: 0.0),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_revenue", "sum"),
        cogs=("line_cost", "sum"),
    )
    gross_sales = paid_lines.assign(
        gross_line=lambda frame: frame["unit_price"] * frame["quantity"]
    ).groupby("sku_id")["gross_line"].sum()
    finance["gross_sales"] = finance["sku_id"].map(gross_sales)
    if after_sales.empty:
        return_summary = pd.DataFrame(columns=["sku_id", "return_units", "refund_amount"])
    else:
        return_summary = after_sales.groupby("sku_id", as_index=False).agg(
            return_units=("units", "sum"), refund_amount=("refund_amount", "sum")
        )
    inventory_summary = inventory.groupby("sku_id", as_index=False).agg(
        average_inventory=("closing_stock", "mean"),
        ending_inventory=("closing_stock", "last"),
        inbound_units=("inbound_units", "sum"),
        stockout_units=("stockout_units", "sum"),
    )
    finance = (
        sku_master[
            [
                "sku_id",
                "operator",
                "category",
                "price",
                "unit_cost",
                "initial_stock",
                "reorder_point",
                "purchase_lead_time_days",
            ]
        ]
        .merge(finance, on="sku_id", how="left")
        .merge(return_summary, on="sku_id", how="left")
        .merge(inventory_summary, on="sku_id", how="left")
        .fillna(0)
    )
    finance["net_sales_after_refund"] = finance["net_sales"] - finance["refund_amount"]
    finance["gross_profit"] = finance["net_sales_after_refund"] - finance["cogs"]
    finance["gross_margin_rate"] = finance["gross_profit"] / finance[
        "net_sales_after_refund"
    ].replace(0, np.nan)
    finance["return_rate"] = finance["return_units"] / finance["sold_units"].replace(0, np.nan)
    finance["sell_through_rate"] = finance["sold_units"] / (
        finance["initial_stock"] + finance["inbound_units"]
    ).replace(0, np.nan)
    finance["inventory_turnover"] = finance["cogs"] / (
        finance["average_inventory"] * finance["unit_cost"]
    ).replace(0, np.nan)
    average_daily_sales = finance["sold_units"] / days
    finance["days_of_inventory"] = finance["ending_inventory"] / average_daily_sales.replace(0, np.nan)
    finance["stockout_rate"] = finance["stockout_units"] / (
        finance["sold_units"] + finance["stockout_units"]
    ).replace(0, np.nan)
    finance["inventory_status"] = np.select(
        [
            finance["stockout_rate"].ge(0.02),
            finance["return_rate"].ge(0.08),
            finance["days_of_inventory"].gt(180),
            finance["days_of_inventory"].lt(finance["purchase_lead_time_days"] + 7),
        ],
        ["stockout_risk", "high_return", "slow_moving", "replenish_now"],
        default="healthy",
    )
    finance["recommended_action"] = finance["inventory_status"].map(
        {
            "stockout_risk": "提高安全库存并缩短补货周期",
            "high_return": "暂停扩量并复盘质量与详情页",
            "slow_moving": "减少采购并测试促销清货",
            "replenish_now": "立即补货",
            "healthy": "维持现有补货节奏",
        }
    )
    finance["is_simulated"] = True
    finance["simulation_seed"] = seed

    return {
        "erp_sku_master": sku_master,
        "erp_order_headers": orders,
        "erp_order_lines": order_lines,
        "erp_inventory_daily": inventory,
        "erp_purchase_orders": purchases,
        "erp_after_sales": after_sales,
        "erp_financial_summary": finance,
    }


def export_erp_tables(
    tables: dict[str, pd.DataFrame],
    output_dir: Path,
    database_path: Path,
    views_path: Path | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    with sqlite3.connect(database_path) as connection:
        for name, frame in tables.items():
            frame.to_sql(name, connection, if_exists="replace", index=False)
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_erp_orders_date_channel
                ON erp_order_headers(order_date, channel);
            CREATE INDEX IF NOT EXISTS idx_erp_lines_order_sku
                ON erp_order_lines(order_id, sku_id);
            CREATE INDEX IF NOT EXISTS idx_erp_lines_sku_date
                ON erp_order_lines(sku_id, order_date);
            CREATE INDEX IF NOT EXISTS idx_erp_inventory_sku_date
                ON erp_inventory_daily(sku_id, snapshot_date);
            CREATE INDEX IF NOT EXISTS idx_erp_inventory_date_stockout
                ON erp_inventory_daily(snapshot_date, stockout_units);
            CREATE INDEX IF NOT EXISTS idx_erp_purchase_sku_status
                ON erp_purchase_orders(sku_id, purchase_status, expected_date);
            CREATE INDEX IF NOT EXISTS idx_erp_after_sales_sku_type
                ON erp_after_sales(sku_id, case_type);
            CREATE INDEX IF NOT EXISTS idx_erp_finance_status_margin
                ON erp_financial_summary(inventory_status, gross_margin_rate DESC);
            """
        )
        if views_path is not None and views_path.exists():
            connection.executescript(views_path.read_text(encoding="utf-8"))


def write_erp_report(
    tables: dict[str, pd.DataFrame],
    database_path: Path,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        kpis = pd.read_sql_query("SELECT * FROM vw_erp_executive_dashboard", connection)
        channel = pd.read_sql_query(
            "SELECT * FROM vw_erp_channel_performance ORDER BY net_sales_after_refund DESC",
            connection,
        )
        replenishment = pd.read_sql_query(
            "SELECT * FROM vw_erp_replenishment_queue ORDER BY replenishment_priority LIMIT 20",
            connection,
        )
        slow_moving = pd.read_sql_query(
            "SELECT * FROM vw_erp_inventory_health WHERE inventory_status = 'slow_moving' "
            "ORDER BY days_of_inventory DESC LIMIT 20",
            connection,
        )
        after_sales = pd.read_sql_query(
            "SELECT * FROM vw_erp_after_sales_quality ORDER BY return_rate_pct DESC LIMIT 20",
            connection,
        )
    lines = [
        "# ERP 经营数据处理报告",
        "",
        "> 订单、库存、采购、售后和财务数据均为明确标注的模拟经营数据；243份问卷用于需求权重，不等同于真实成交。",
        "",
        "## 数据资产",
        "",
    ]
    for name, frame in tables.items():
        lines.append(f"- `{name}`：{len(frame):,} 条记录。")
    lines.extend(
        [
            "",
            "## 核心经营指标",
            "",
            kpis.to_markdown(index=False, floatfmt=".2f"),
            "",
            "## 渠道表现",
            "",
            channel.to_markdown(index=False, floatfmt=".2f"),
            "",
            "## 补货优先队列",
            "",
            replenishment.to_markdown(index=False, floatfmt=".2f"),
            "",
            "## 滞销库存",
            "",
            slow_moving.to_markdown(index=False, floatfmt=".2f") if not slow_moving.empty else "无滞销SKU。",
            "",
            "## 售后质量",
            "",
            after_sales.to_markdown(index=False, floatfmt=".2f"),
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")
