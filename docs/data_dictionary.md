# 数据字典

## public_videos

| 字段 | 含义 |
|---|---|
| bvid | B站公开视频标识 |
| title | 视频标题 |
| published_at | 发布时间 |
| view / like / coin / favorite / danmaku | 采集时点公开展示指标 |
| source_url | 可核验来源 |
| metric_precision | `display_rounded` 表示页面展示值经过“万”单位换算 |

`share` 与 `reply` 在页面快照未稳定展示时保留为空，不进行反推或编造。

## operator_heat

| 字段 | 含义 |
|---|---|
| views_per_day | 截至分析日期的日均播放速度 |
| engagement_rate | 点赞、投币、收藏、分享、评论和弹幕的加权互动率 |
| heat_score | 样本内0～100分的复合热度指标 |
| heat_rank | 当前样本内排名 |

## erp_mock

全部订单、库存和退货字段均为模拟数据：

| 字段 | 含义 |
|---|---|
| launch_inventory | 模拟首批备货量 |
| sold_units | 模拟销量 |
| return_units | 模拟退货量 |
| is_simulated | 固定为 `true` |
| simulation_seed | 可复现随机种子 |

## sku_recommendations

| 字段 | 含义 |
|---|---|
| gross_margin_rate | 模拟毛利率 |
| sell_through_rate | 模拟售罄率 |
| conversion_rate | 模拟订单转化率 |
| inventory_risk | 根据滞销与退货风险形成的风险分 |
| selection_score | 角色热度、转化、毛利、直播适配和库存风险的综合分 |
# 核心数据字典

## character_heat_matrix.csv

- `cross_platform_heat`：角色综合公开内容热度。
- `bilibili_heat` / `weibo_heat`：平台内百分位复合分。
- `reach_score`：传播规模。
- `momentum_score`：发布时间校正后的传播速度。
- `engagement_score`：综合互动质量。
- `intent_score`：收藏、投币和转发等深层互动。
- `discussion_score`：评论与弹幕讨论强度。
- `cross_platform_consistency`：平台分差转换的一致性。
- `confidence_score`：样本量与平台覆盖形成的可信度。
- `evergreen_score`：长期热度指标。
- `viral_potential_score`：短期爆发潜力。
- `merch_opportunity_score`：接入真实电商数据前的内容侧选品候选分。
- `commerce_validation_status`：后续淘宝数据补充优先级。

## platform_ecosystem.csv

- `scope=brand_ecosystem`：平台整体品牌/话题生态，不代表官方账号单篇数据。
- `note_count`：公开榜单展示的相关笔记量。
- `interaction_total`：点赞、收藏、评论合计。
- `interaction_per_note`：互动总量除以笔记量。
- `favorite_rate` / `comment_rate`：生态互动结构。

## taobao_public_snapshots.csv

- `item_id`：可跨期追踪的淘宝商品 ID。
- `rank`：固定查询词与排序下的自然结果位置。
- `price`：页面公开展示价格，不代表最终实付价。
- `sales_proxy_min`：公开“收货人数”的最低值代理。
- `sales_proxy_censored`：`100+` 等区间展示是否被截断。
- `category`：规则归类后的周边品类。
- `rights_type`：官方/授权、同人原创或未标明。
- `fulfillment_type`：现货、预售/补款或未标明。
- `operator_mentions`：异格名、基础名和昵称治理后的角色归因。
- `target_relevance`：定向查询结果与目标角色的相关度。
- `ip_scope`：`arknights`、`endfield` 或其他，避免两个产品线混算。
- `is_simulated`：固定为 `false`。

## taobao_role_signals.csv

- `organic_sku_count`：全 IP 自然销量页观察到的角色商品数。
- `sales_proxy_min`：多角色商品按角色数等分后的公开收货人数下界。
- `market_visibility`：按搜索排名衰减后的可见度。
- `category_breadth`：角色商品覆盖品类数。
- `commercial_heat_score`：需求、供给、可见度、价格和品类宽度的综合商业信号。
- `commerce_confidence_score` / `commerce_data_grade`：样本量与数值覆盖形成的可信度。

## content_commerce_matrix.csv

- `business_quadrant`：核心商业角色、内容热但供给待验证、内容长尾但商品信号强、低成本观察。
- `content_commerce_gap`：内容热度减商业信号，正值较大表示存在商业验证缺口。
- `commercial_validation_priority`：内容热度、深层互动、商业缺口和低置信度共同形成的补采优先级。

## SQL 业务视图

- `vw_role_commercial_dashboard`：角色内容热度、商业信号、数据置信度、验证队列及运营动作。
- `vw_sku_portfolio_rank`：SKU 的角色内排名、品类内排名、品类百分位、风险等级和组合定位。
- `vw_category_operations`：按品类聚合的加权转化率、售罄率、退货率、模拟毛利及库存风险。
- `vw_taobao_listing_quality`：淘宝商品的跨 IP、相关性、销量可用性、截断状态与时间序列准入标签。
- `vw_taobao_category_market`：淘宝品类价格、销量代理、正版/同人、预售与履约服务结构。

## SQL 自动导出结果

- `sql_role_decision_board.csv`：商业验证优先级最高的角色及建议动作。
- `sql_category_operations.csv`：品类经营漏斗与模拟利润表现。
- `sql_top_sku_portfolio.csv`：每名角色的 Top SKU 组合。
- `sql_taobao_quality_audit.csv`：公开商品快照的数据质量审计。
- `sql_taobao_category_market.csv`：淘宝品类市场结构。
- `sql_price_band_structure.csv`：入门、主力、中高客单和高客单价格带。
- `sql_inventory_risk_queue.csv`：每个品类的库存风险优先处理队列。
- `sql_index_plan_audit.csv`：使用 `EXPLAIN QUERY PLAN` 验证复合索引命中的执行计划。
