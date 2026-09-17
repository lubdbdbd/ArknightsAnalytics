from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


CATEGORY_CODES = {
    "亚克力制品": "ACR",
    "通行证": "PASS",
    "吧唧（徽章）": "BAG",
    "毛绒玩偶": "PLU",
    "手办模玩": "FIG",
    "装饰摆件": "DEC",
    "日用生活": "LIF",
}

INTERNAL_REQUIRED_FIELDS = (
    "sku_code",
    "sku_id",
    "operator",
    "category",
    "product_name",
    "supplier_id",
    "price",
    "unit_cost",
    "purchase_lead_time_days",
    "sku_status",
)

PRODUCT_FIELD_DICTIONARY = (
    ("spu_code", "SPU编码", "同一角色商品集合的稳定编码", "非空且唯一对应一个角色"),
    ("sku_code", "SKU编码", "可独立库存与销售的商品编码", "非空、全表唯一"),
    ("product_name", "商品名称", "角色名与标准品类组成的规范名称", "非空"),
    ("operator", "角色", "周边对应的《明日方舟》角色", "必须来自角色主数据"),
    ("category", "标准品类", "统一后的七类正版周边", "必须命中品类字典"),
    ("rights_type", "授权属性", "官方、授权、同人或未核验", "公开商品未核验时进入维护队列"),
    ("supplier_id", "供应商编码", "内部采购供应商标识", "内部SKU非空"),
    ("list_price", "标准售价", "商品对外标价", "大于0"),
    ("unit_cost", "单位成本", "模拟ERP采购成本", "大于等于0且小于售价"),
    ("gross_margin_rate", "毛利率", "(售价-成本)/售价", "0至1"),
    ("fulfillment_type", "履约类型", "现货、预售或补款", "公开商品建议明确"),
    ("lifecycle_stage", "生命周期", "规划、在售、停售或归档", "与销售状态一致"),
    ("safety_stock", "安全库存", "应对需求波动的缓冲库存", "大于等于0"),
    ("reorder_point", "再订货点", "触发补货的库存位置", "不低于安全库存"),
    ("source_url", "来源链接", "公开商品的可追溯页面", "公开商品非空"),
    ("snapshot_at", "快照时间", "公开页面采集时间", "公开商品非空"),
    ("data_quality_score", "数据质量分", "字段完整性与业务规则综合评分", "0至100"),
    ("maintenance_action", "维护动作", "下一步需要补充或校正的信息", "异常记录非空"),
    ("is_simulated", "模拟标记", "区分模拟ERP与公开真实快照", "必须明确"),
)


def _require_columns(frame: pd.DataFrame, required: set[str], table_name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{table_name} missing columns: {sorted(missing)}")


def build_internal_product_master(sku_master: pd.DataFrame) -> pd.DataFrame:
    _require_columns(sku_master, set(INTERNAL_REQUIRED_FIELDS), "sku_master")
    frame = sku_master.copy()
    operators = sorted(frame["operator"].astype(str).unique())
    spu_codes = {operator: f"SPU-{index:04d}" for index, operator in enumerate(operators, 1)}
    frame.insert(0, "spu_code", frame["operator"].astype(str).map(spu_codes))
    frame["category_code"] = frame["category"].map(CATEGORY_CODES)
    frame["rights_type"] = "模拟正版商品主数据"
    frame["lifecycle_stage"] = frame["sku_status"].map(
        {"active": "在售", "planned": "规划", "inactive": "停售"}
    ).fillna("待确认")
    frame["product_owner"] = "Merch Operations"
    frame["data_source"] = "simulated_erp_sku_master"
    frame["list_price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["unit_cost"] = pd.to_numeric(frame["unit_cost"], errors="coerce")
    frame["gross_margin_rate"] = (
        (frame["list_price"] - frame["unit_cost"]) / frame["list_price"].replace(0, np.nan)
    )

    required_present = pd.DataFrame(
        {
            column: frame[column].notna() & frame[column].astype(str).str.strip().ne("")
            for column in INTERNAL_REQUIRED_FIELDS
        }
    )
    frame["required_field_completeness"] = required_present.mean(axis=1)
    frame["duplicate_sku_code"] = frame["sku_code"].astype(str).duplicated(keep=False)
    frame["invalid_price"] = frame["list_price"].isna() | frame["list_price"].le(0)
    frame["invalid_cost"] = (
        frame["unit_cost"].isna()
        | frame["unit_cost"].lt(0)
        | frame["unit_cost"].ge(frame["list_price"])
    )
    frame["missing_supplier"] = frame["supplier_id"].isna() | frame["supplier_id"].astype(
        str
    ).str.strip().eq("")
    frame["invalid_category"] = frame["category_code"].isna()
    frame["invalid_stock_policy"] = pd.to_numeric(
        frame["reorder_point"], errors="coerce"
    ).lt(pd.to_numeric(frame["safety_stock"], errors="coerce"))

    issue_columns = [
        "duplicate_sku_code",
        "invalid_price",
        "invalid_cost",
        "missing_supplier",
        "invalid_category",
        "invalid_stock_policy",
    ]
    frame["rule_issue_count"] = frame[issue_columns].sum(axis=1)
    frame["data_quality_score"] = (
        frame["required_field_completeness"] * 70 - frame["rule_issue_count"] * 8 + 30
    ).clip(0, 100)
    frame["data_quality_grade"] = pd.cut(
        frame["data_quality_score"],
        bins=[-1, 59.99, 74.99, 89.99, 100],
        labels=["D", "C", "B", "A"],
    ).astype(str)

    def maintenance_action(row: pd.Series) -> str:
        actions: list[str] = []
        if row["duplicate_sku_code"]:
            actions.append("隔离重复SKU编码，核验规格后人工处理")
        if row["invalid_category"]:
            actions.append("补充标准品类映射")
        if row["missing_supplier"]:
            actions.append("补充供应商")
        if row["invalid_price"] or row["invalid_cost"]:
            actions.append("复核售价与成本")
        if row["invalid_stock_policy"]:
            actions.append("复核安全库存与再订货点")
        if row["required_field_completeness"] < 1:
            actions.append("补齐必填字段")
        return "；".join(actions) if actions else "主数据校验通过"

    frame["maintenance_action"] = frame.apply(maintenance_action, axis=1)
    frame["maintenance_status"] = np.where(frame["rule_issue_count"].gt(0), "待处理", "已校验")
    return frame.sort_values(["spu_code", "category_code", "sku_code"]).reset_index(drop=True)


def build_public_listing_master(listings: pd.DataFrame) -> pd.DataFrame:
    required = {
        "item_id",
        "raw_text",
        "url",
        "snapshot_at",
        "query",
        "category",
        "rights_type",
        "fulfillment_type",
        "operator_mentions",
        "target_operator",
        "price",
        "sales_proxy_min",
        "rank",
        "is_simulated",
    }
    _require_columns(listings, required, "taobao_public_snapshots")
    frame = listings.copy()
    missing_id = frame['item_id'].isna() | frame['item_id'].astype(str).str.strip().isin(['', 'nan', 'None'])
    if missing_id.any():
        raise ValueError('商品链接ID缺失，须先隔离并补证，禁止将空ID自动合并为一个商品')
    frame["item_id"] = frame["item_id"].astype(str).str.strip()
    conflicts = set()
    for item_id, observations in frame.groupby('item_id'):
        if observations['category'].dropna().nunique() > 1:
            conflicts.add(item_id)
        if any(group['price'].dropna().nunique() > 1 for _, group in observations.groupby('snapshot_at')):
            conflicts.add(item_id)
    frame['identity_review_required'] = frame['item_id'].isin(conflicts) | frame['operator_mentions'].fillna('').str.contains('|', regex=False)
    frame["snapshot_at"] = pd.to_datetime(frame["snapshot_at"], errors="coerce", utc=True)
    frame["capture_count"] = frame.groupby("item_id")["item_id"].transform("size")
    frame = frame.sort_values(["item_id", "snapshot_at", "rank"]).drop_duplicates(
        "item_id", keep="last"
    )
    frame = frame.reset_index(drop=True)

    def resolved_operator(row: pd.Series) -> str:
        target = str(row.get("target_operator") or "").strip()
        mentions = [value for value in str(row.get("operator_mentions") or "").split("|") if value]
        if target and target.lower() != "nan":
            return target
        return mentions[0] if len(mentions) == 1 else "未归因"

    frame["operator"] = frame.apply(resolved_operator, axis=1)
    frame["external_sku_id"] = "TB-" + frame["item_id"]
    frame["product_title"] = frame["raw_text"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    frame["source_url"] = frame["url"]
    frame["list_price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["sales_proxy_min"] = pd.to_numeric(frame["sales_proxy_min"], errors="coerce")
    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    frame["data_source"] = "taobao_public_search_snapshot"

    frame["missing_identifier"] = frame["item_id"].str.strip().eq("")
    frame["missing_title"] = frame["product_title"].eq("")
    frame["missing_url"] = frame["source_url"].isna() | frame["source_url"].astype(str).str.strip().eq("")
    frame["missing_price"] = frame["list_price"].isna() | frame["list_price"].le(0)
    frame["operator_unassigned"] = frame["operator"].eq("未归因")
    frame["rights_unverified"] = frame["rights_type"].ne("官方/授权")
    frame["fulfillment_unknown"] = frame["fulfillment_type"].eq("未标明")
    frame["duplicate_capture"] = frame["capture_count"].gt(1)

    frame["price_outlier"] = False
    for _, indexes in frame.groupby("category").groups.items():
        prices = frame.loc[indexes, "list_price"].dropna()
        if len(prices) < 4:
            continue
        q1, q3 = prices.quantile([0.25, 0.75])
        iqr = q3 - q1
        lower = max(0, q1 - 1.5 * iqr)
        upper = q3 + 1.5 * iqr
        frame.loc[indexes, "price_outlier"] = frame.loc[indexes, "list_price"].lt(
            lower
        ) | frame.loc[indexes, "list_price"].gt(upper)

    score = pd.Series(100.0, index=frame.index)
    penalties = {
        "missing_identifier": 30,
        "missing_title": 20,
        "missing_url": 15,
        "missing_price": 15,
        "operator_unassigned": 10,
        "rights_unverified": 20,
        "fulfillment_unknown": 8,
        "duplicate_capture": 4,
        "price_outlier": 8,
    }
    for column, penalty in penalties.items():
        score -= frame[column].astype(int) * penalty
    frame["data_quality_score"] = score.clip(0, 100)
    frame["data_quality_grade"] = pd.cut(
        frame["data_quality_score"],
        bins=[-1, 59.99, 74.99, 89.99, 100],
        labels=["D", "C", "B", "A"],
    ).astype(str)

    def maintenance_action(row: pd.Series) -> str:
        actions: list[str] = []
        if row["missing_identifier"] or row["missing_url"]:
            actions.append("补充商品标识与链接")
        if row["missing_title"]:
            actions.append("补充商品标题")
        if row["rights_unverified"]:
            actions.append("核验官方或授权资质")
        if row["operator_unassigned"]:
            actions.append("补充角色归因")
        if row["fulfillment_unknown"]:
            actions.append("补充现货或预售状态")
        if row["missing_price"]:
            actions.append("补充有效价格")
        if row["price_outlier"]:
            actions.append("复核规格、套装与价格单位")
        if row["duplicate_capture"]:
            actions.append("主档归并跨查询重复观测，保留原始快照")
        if row['identity_review_required']:
            actions.append('复核多角色或同链接规格冲突，不能按单一角色归因销量')
        return "；".join(actions) if actions else "公开商品信息可用"

    frame["maintenance_action"] = frame.apply(maintenance_action, axis=1)
    critical = frame[["missing_identifier", "missing_title", "missing_url", "missing_price"]].any(axis=1)
    important = frame[
        [
            "rights_unverified",
            "operator_unassigned",
            "fulfillment_unknown",
            "price_outlier",
            "duplicate_capture",
        ]
    ].any(axis=1)
    important = important | frame['identity_review_required']
    frame["maintenance_priority"] = np.select(
        [critical, important], ["P0-阻断", "P1-待核验"], default="P2-可入库"
    )
    frame["maintenance_status"] = np.where(
        frame["maintenance_priority"].eq("P2-可入库"), "已校验", "待处理"
    )
    columns = [
        "external_sku_id",
        "item_id",
        "product_title",
        "operator",
        "category",
        "rights_type",
        "fulfillment_type",
        "list_price",
        "sales_proxy_min",
        "rank",
        "query",
        "snapshot_at",
        "source_url",
        "capture_count",
        "data_quality_score",
        "data_quality_grade",
        "maintenance_priority",
        "maintenance_status",
        "maintenance_action",
        "identity_review_required",
        *penalties.keys(),
        "data_source",
        "is_simulated",
    ]
    return frame[columns].sort_values(
        ["maintenance_priority", "data_quality_score", "external_sku_id"]
    ).reset_index(drop=True)


def build_product_maintenance_queue(public_master: pd.DataFrame) -> pd.DataFrame:
    queue = public_master[public_master["maintenance_priority"].ne("P2-可入库")].copy()
    return queue[
        [
            "external_sku_id",
            "operator",
            "category",
            "rights_type",
            "fulfillment_type",
            "list_price",
            "data_quality_score",
            "data_quality_grade",
            "maintenance_priority",
            "maintenance_action",
            "source_url",
            "snapshot_at",
        ]
    ].reset_index(drop=True)


def build_product_category_health(
    internal_master: pd.DataFrame, public_master: pd.DataFrame
) -> pd.DataFrame:
    internal = internal_master.groupby("category", as_index=False).agg(
        internal_sku_count=("sku_code", "nunique"),
        internal_spu_count=("spu_code", "nunique"),
        internal_price_median=("list_price", "median"),
        internal_gross_margin_median=("gross_margin_rate", "median"),
        internal_quality_score=("data_quality_score", "mean"),
    )
    public = public_master.groupby("category", as_index=False).agg(
        public_listing_count=("external_sku_id", "nunique"),
        official_listing_count=("rights_type", lambda values: int((values == "官方/授权").sum())),
        public_price_median=("list_price", "median"),
        public_quality_score=("data_quality_score", "mean"),
        maintenance_queue_count=(
            "maintenance_priority", lambda values: int((values != "P2-可入库").sum())
        ),
    )
    output = internal.merge(public, on="category", how="outer")
    output["official_listing_share"] = output["official_listing_count"] / output[
        "public_listing_count"
    ].replace(0, np.nan)
    output["market_price_gap_pct"] = (
        output["public_price_median"] - output["internal_price_median"]
    ) / output["internal_price_median"].replace(0, np.nan)
    output["category_action"] = np.select(
        [
            output["official_listing_count"].fillna(0).lt(3),
            output["maintenance_queue_count"].fillna(0).gt(
                output["public_listing_count"].fillna(0) * 0.5
            ),
            output["market_price_gap_pct"].abs().gt(0.5),
        ],
        ["补采正版商品与供应商报价", "优先清理商品属性与授权状态", "复核规格差异与价格口径"],
        default="维持常规商品信息维护",
    )
    return output.sort_values(
        ["official_listing_count", "public_listing_count"], ascending=[True, False]
    ).reset_index(drop=True)


def build_product_change_log(
    internal_master: pd.DataFrame, public_master: pd.DataFrame, event_at: str
) -> pd.DataFrame:
    internal_events = pd.DataFrame(
        {
            "event_at": event_at,
            "entity_type": "internal_sku",
            "entity_id": internal_master["sku_code"],
            "change_type": "CREATE_BASELINE",
            "field_name": "product_master",
            "old_value": "",
            "new_value": internal_master["product_name"],
            "source": internal_master["data_source"],
            "is_simulated": True,
        }
    )
    public_events = pd.DataFrame(
        {
            "event_at": public_master["snapshot_at"].astype(str),
            "entity_type": "public_listing",
            "entity_id": public_master["external_sku_id"],
            "change_type": "OBSERVE_BASELINE",
            "field_name": "listing_snapshot",
            "old_value": "",
            "new_value": public_master["product_title"],
            "source": public_master["data_source"],
            "is_simulated": False,
        }
    )
    return pd.concat([internal_events, public_events], ignore_index=True)


def build_product_field_dictionary() -> pd.DataFrame:
    return pd.DataFrame(
        PRODUCT_FIELD_DICTIONARY,
        columns=["field_name", "field_name_cn", "business_definition", "validation_rule"],
    )


def export_product_catalog(
    tables: dict[str, pd.DataFrame],
    processed_dir: Path,
    database_path: Path,
    views_path: Path,
) -> None:
    import sqlite3

    processed_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        for name, frame in tables.items():
            frame.to_csv(processed_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
            export_frame = frame.copy()
            for column in export_frame.select_dtypes(include=["bool"]).columns:
                export_frame[column] = export_frame[column].astype(int)
            export_frame.to_sql(name, connection, if_exists="replace", index=False)
        connection.executescript(views_path.read_text(encoding="utf-8"))


def write_product_catalog_report(tables: dict[str, pd.DataFrame], output_path: Path) -> None:
    internal = tables["product_catalog_internal"]
    public = tables["product_catalog_public"]
    queue = tables["product_maintenance_queue"]
    category = tables["product_category_health"]
    priority = (
        public.groupby("maintenance_priority", as_index=False)
        .agg(listing_count=("external_sku_id", "nunique"))
        .sort_values("maintenance_priority")
    )
    top_issues = pd.DataFrame(
        {
            "issue": [
                "授权状态待核验",
                "角色未归因",
                "履约状态不明确",
                "价格异常",
                "跨查询重复快照",
            ],
            "listing_count": [
                int(public["rights_unverified"].sum()),
                int(public["operator_unassigned"].sum()),
                int(public["fulfillment_unknown"].sum()),
                int(public["price_outlier"].sum()),
                int(public["duplicate_capture"].sum()),
            ],
        }
    ).sort_values("listing_count", ascending=False)
    lines = [
        "# Arknights Analytics｜商品信息维护与主数据治理",
        "",
        "> 数据边界：内部商品与经营参数为可复现模拟 ERP 数据；淘宝商品为公开搜索快照。两类数据通过 `is_simulated`、来源字段和独立主表严格隔离。",
        "",
        "## 1. 商品主数据",
        "",
        f"- 建立 {internal['spu_code'].nunique()} 个 SPU、{internal['sku_code'].nunique()} 个 SKU 的标准商品档案，覆盖 {internal['operator'].nunique()} 名角色与 {internal['category'].nunique()} 类周边。",
        f"- 维护商品编码、角色、品类、授权属性、供应商、售价、成本、毛利率、采购提前期、安全库存、再订货点和生命周期等 {len(tables['product_field_dictionary'])} 项字段定义。",
        f"- 内部主数据必填字段平均完整率 {internal['required_field_completeness'].mean():.2%}，规则异常 {int(internal['rule_issue_count'].sum())} 项。",
        "",
        "## 2. 公开商品维护",
        "",
        f"- 将 {int(public['capture_count'].sum())} 条公开快照去重为 {public['external_sku_id'].nunique()} 个外部商品档案，其中明确官方/授权 {int(public['rights_type'].eq('官方/授权').sum())} 个。",
        f"- 自动生成 {len(queue)} 条商品维护任务，覆盖授权核验、角色归因、履约状态、价格异常和重复快照处理。",
        "",
        priority.to_markdown(index=False),
        "",
        "### 主要数据问题",
        "",
        top_issues.to_markdown(index=False),
        "",
        "## 3. 品类维护看板",
        "",
        category.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 4. SQL 运营化",
        "",
        "- 建立 4 个商品维护视图和 11 组专项查询，覆盖主数据健康度、授权补证、角色归因、履约补充、价格异常、重复合并、品类覆盖和变更审计。",
        "- 建立 6 个复合索引，支持按角色×品类、优先级×质量分、授权×品类及实体×时间查询。",
        "",
        "## 5. 维护流程",
        "",
        "1. 新商品进入时先生成 SPU/SKU 编码，并按字段字典补齐角色、品类、授权、规格、供应商与价格信息。",
        "2. 通过必填、唯一性、价格成本、品类映射、库存策略和公开商品来源规则进行自动校验。",
        "3. 异常记录进入 P0/P1 维护队列，由运营补充授权证明、商品归因、规格或履约信息。",
        "4. 校验通过后进入商品池，并通过变更日志保留首次建档与后续字段变更证据。",
        "",
        "## 方法限制",
        "",
        "- 公开商品标题可能包含套装、多角色或补款信息，价格异常只能触发复核，不能直接判定商品信息错误。",
        "- 当前公开快照主要用于展示商品信息治理方法，不代表淘宝完整商品供给。",
        "- 模拟 ERP 商品参数不代表真实企业成本、库存或供应商数据。",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
