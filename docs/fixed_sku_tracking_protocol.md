# 固定 SKU 时间序列追踪方案

## 目标

横截面只能说明某一天公开可见的商品结构，不能证明销售增长。固定 SKU 追踪以稳定商品 ID 为主键，每 7 天复采一次同一商品，将价格、公开收货人数下界、自然排名和在售状态变成纵向证据。

## 准入规则

- 必须具有稳定 `item_id` 和商品 URL。
- 必须属于《明日方舟》本体，排除《明日方舟：终末地》和其他 IP。
- 定向查询结果的 `target_relevance` 不低于 0.50。
- 广告跳转、无商品 ID 和无法复核的聚合卡片不进入注册表。
- 同一商品同一天出现多次，仅保留相关性最高、自然排名最靠前的一条。

## 采样规范

1. 固定查询词、排序方式、地区、账号与设备环境。
2. 每周同一时间窗口采样，活动日额外记录活动标签。
3. 保存商品标题原文，不单独推断未公开的精确销量。
4. `100+`、`1万+` 等展示按最低值记录，并保留截断标记。
5. 商品下架时保留原商品 ID，并记录为状态变化，而不是删除历史。

## 证据等级

| 等级 | 最低要求 | 可支持的结论 |
|---|---|---|
| D | 1 期 | 仅作为基线，不判断趋势 |
| C | 2 期且跨越 7 天 | 可判断方向性变化 |
| B | 3 期且跨越 14 天 | 可进入选品验证证据 |
| A | 4 期且跨越 21 天 | 可用于阶段性商业动量比较 |

公开人数下降、商品换链、跨 IP 命中和排名突变需要人工复核，不能自动解释为销量下降。

## 执行命令

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py
.\.venv\Scripts\python.exe scripts\export_sku_recapture_queue.py --operator 新约能天使 --limit 30
.\.venv\Scripts\python.exe scripts\import_taobao_snapshot.py data\manual\sku_recapture_queue.csv `
  --query "明日方舟 新约能天使 周边" --target-operator "新约能天使"
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

复采前需把 `sku_recapture_queue.csv` 中的 `rank` 和 `title` 更新为当期页面公开值；`title` 应保留价格、收货人数和商品状态原文。
