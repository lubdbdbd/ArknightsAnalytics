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

## bilibili_official_archive.csv

- `content_type`：`operator_pv`、`music_ep`、`event_pv`、`gameplay_system`、`offline_event`、`animation_brand`、`other_pv` 或 `other_official`。
- `explicit_operator`：仅在标题包含明确干员结构时写入，不使用普通单字包含匹配。
- `views_per_day`：截至统一分析日期的播放速度。
- `weighted_engagement_rate`：点赞、投币、收藏、分享、评论和弹幕的加权互动率。
- `intent_rate`：收藏、投币和分享形成的深层互动代理。
- `archive_content_score`：全官号样本内的触达、速度和互动复合分。

## bilibili_operator_campaign_content.csv

- `association_type=direct_operator`：标题明确指向角色。
- `association_type=campaign_window`：位于最近角色PV前后14天的共享上线宣传内容。
- `association_weight`：按距离锚点天数衰减，直接角色内容固定为1。
- `days_from_anchor`：内容相对角色PV锚点的发布时间差。

## bilibili_operator_campaign_summary.csv

- `bilibili_campaign_content_count`：角色上线Campaign内的去重内容量。
- `bilibili_direct_content_count` / `window_content_count`：直接与共享内容分层计数。
- `bilibili_weighted_campaign_views`：按归因权重折算的Campaign公开播放量。
- `bilibili_campaign_exposure_score`：加权播放量的样本内百分位。
- `bilibili_campaign_depth_score`：内容数量与类型宽度形成的传播深度分。

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
- `category`：规则归类后的正版周边品类，统一为亚克力制品、通行证、吧唧（徽章）、毛绒玩偶、手办模玩、装饰摆件和日用生活；无法归类时标记为其他正版周边。
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

## sku_tracking_registry.csv

- `item_id`：固定追踪的商品主键。
- `first_seen_at` / `snapshot_at`：第一次与最近一次公开观察时间。
- `observation_count`：去除同日重复后的有效采样期数。
- `next_capture_due`：按 7 天周期计算的下次复采日期。
- `tracking_status`：`baseline_pending_recapture` 或 `tracking_active`。
- `sales_metric_note`：区分公开代理与档位截断下界。

## sku_timeseries_metrics.csv

- `price_delta` / `price_change_rate`：首末期价格变化。
- `sales_proxy_delta`：公开收货人数下界的首末期差值。
- `sales_proxy_delta_per_day`：跨期下界增量除以观察天数，仅作增长代理。
- `rank_improvement`：首期排名减末期排名，正值表示公开搜索位置改善。
- `lifecycle_signal`：基线待复采、增长、稳定、数据异常或信号不足。
- `timeseries_evidence_grade`：D/C/B/A 对应 1 期、2 期 7 天、3 期 14 天和 4 期 21 天。

## survey_response_audit.csv

- `valid`：是否通过知情同意、完成时间、重复、字段范围和前后逻辑校验。
- `exclusion_reason`：无同意、过快、重复、非法字段或价格逻辑冲突等排除原因。

## survey_operator_category_summary.csv

- `respondent_count`：角色 × 品类细分的有效匿名受访者数。
- `purchase_intent_mean` / `high_intent_share`：平均购买意愿及 4～5 分占比。
- `acceptable_price_median` / `p25` / `p75`：价格接受度分布。
- `prior_buyer_share`：既往周边购买者占比。
- `survey_evidence_grade`：样本量证据等级；少于 30 人不能用于方向决策。

## survey_segment_summary.csv

- `user_segment`：核心购买者、偶发购买者、潜在购买者或观察者。
- `respondent_share`：该分群占有效匿名受访者的比例，不代表全体玩家人口比例。
- `annual_merch_spend_median` / `monthly_budget_median`：历史年消费与未来月度预算中位数。
- `preorder_tolerance_days_median`：可接受预售等待时间中位数。

## survey_barrier_summary.csv

- `purchase_barrier`：价格、设计、品质、预售、运费、售后等购买阻力。
- `respondent_count` / `respondent_share`：提及该阻力的去重人数及在有效受访者中的占比。

## survey_price_summary.csv

- `acceptable_price_p25/p50/p75`：最高可接受价格的四分位分布。
- `good_value_price_median` / `expensive_price_median`：合适价格及可选的偏贵价格中位数；新版问卷以前者和最高可接受价格为主。
- `directional_price_floor/ceiling`：用于小批量概念验证的方向性区间，不等于正式成交定价。

## 匿名问卷批次表

- `anonymous_responses_243.csv`：243条受访者主记录；`validation_profile=anonymous_batch_without_timing`表示原始导出未包含提交时间和填写时长。
- `anonymous_operator_rankings_243.csv`：每份答卷最多3条角色偏好，`preference_weight`按第一至第三名分别记3/2/1分。
- `anonymous_category_prices_243.csv`：每份答卷对7类正版周边的价格带选择，保存上下界与仅用于聚合的中点代理。
- `data_type=real_anonymous_survey_user_attested`：批次所有者确认属于真实回收；问卷结论仍受便利抽样限制。

## selection_case_evidence.csv

- `evidence_layer`：内容热度、深层意向、搜索质量、需求代理、固定 SKU 和用户调研。
- `threshold` / `gate_passed`：预先定义的门槛及通过状态。
- `data_type`：真实公开聚合、公开下界、真实纵向数据或真实匿名问卷。
- `case_status`：`conditional_pilot` 或 `validated_candidate`。

## SQL 业务视图

- `vw_role_commercial_dashboard`：角色内容热度、商业信号、数据置信度、验证队列及运营动作。
- `vw_sku_portfolio_rank`：SKU 的角色内排名、品类内排名、品类百分位、风险等级和组合定位。
- `vw_category_operations`：按品类聚合的加权转化率、售罄率、退货率、模拟毛利及库存风险。
- `vw_taobao_listing_quality`：淘宝商品的跨 IP、相关性、销量可用性、截断状态与时间序列准入标签。
- `vw_taobao_category_market`：淘宝品类价格、销量代理、正版/同人、预售与履约服务结构。
- `vw_bilibili_campaign_performance`：角色Campaign内容量、加权曝光、内容深度及排名。
- `vw_erp_executive_dashboard`：净销售、毛利、退货、库存天数、缺货与异常SKU总览。
- `vw_erp_channel_performance`：各渠道订单、实付、客单价、退款金额与退款金额率。
- `vw_erp_inventory_health`：SKU库存周转、库存天数、售罄、缺货和建议动作。
- `vw_erp_replenishment_queue`：根据缺货、再订货点、采购提前期生成补货优先级。
- `vw_erp_after_sales_quality`：SKU售后件数、影响数量、退款金额和平均关闭时长。
- `vw_erp_daily_operations`：按日汇总销量、入库、退货、期末库存和缺货率。

## ERP 业务表

- `erp_sku_master`：210个SKU的角色、品类、售价、成本、供应商、采购提前期、安全库存和再订货点。
- `erp_order_headers`：订单日期、渠道、客群、支付/履约状态、商品额、优惠、运费和实付金额。
- `erp_order_lines`：SKU数量、单价、优惠分摊、净收入、单位成本和明细成本。
- `erp_inventory_daily`：期初、入库、请求销量、实际销量、缺货、退货、残损、期末、锁定和可售库存。
- `erp_purchase_orders`：供应商、下单/预计/实际到货日期、订购/实收数量、采购金额与状态。
- `erp_after_sales`：退款、退货、换货、原因、数量、退款金额和处理时长。
- `erp_financial_summary`：SKU级净销售、COGS、毛利率、退货率、售罄率、库存周转和库存天数。
- 所有ERP业务表的`is_simulated`固定为`true`，不得描述为企业真实经营数据。

## 三条主分析链路

- `skland_operator_summary`：森空岛攻略站公开搜索Top 20的角色级内容数、浏览量、互动量、互动率与最高浏览内容；不等于全站总量。
- `operator_demand_fusion`：融合`content_signal`、`survey_signal`、`skland_signal`与`commerce_signal`；只对当前可用来源重新归一权重，避免把缺失当作低需求。
- `operator_rank_sensitivity`：平衡、内容优先、问卷优先、社区优先、商业优先五套权重的排名、均值、标准差和区间。
- `category_price_architecture`：七品类真实问卷P25/P50/P75价格梯度、淘宝明确官方/授权样本中位价、市场证据等级和定价动作；模拟成本字段单独标记。
- `operator_category_portfolio`：角色需求分、角色×品类购买意愿、样本量折扣、组合得分和验证动作。
- `erp_sku_diagnostics`：SKU净销售、毛利、退货、缺货、库存天数、GMROI、ABC收入等级、XYZ需求波动等级和经营动作。
- `erp_replenishment_plan`：最近28日需求均值/标准差、95%服务水平安全库存、交期需求、库存位置、建议采购量和预算。
- `erp_after_sales_pareto`：品类×售后原因的案例数、影响件数、退款金额、处理时长和累计占比。
- `erp_channel_profitability`：渠道订单、支付率、客单价、退款金额率与不含真实履约成本的毛利代理。
- `erp_category_diagnostics`：品类级收入、毛利、退货率、缺货率、库存天数与建议动作。
- `erp_daily_kpis`：90天订单、收入、销量、满足率、售后金额及7日滚动指标。
- 以上所有`erp_*`新增分析表继续保持`is_simulated=true`；真实问卷与公开平台数据不得与模拟经营指标合并描述为真实营收。

## SQL 自动导出结果

- `sql_role_decision_board.csv`：商业验证优先级最高的角色及建议动作。
- `sql_category_operations.csv`：品类经营漏斗与模拟利润表现。
- `sql_top_sku_portfolio.csv`：每名角色的 Top SKU 组合。
- `sql_taobao_quality_audit.csv`：公开商品快照的数据质量审计。
- `sql_taobao_category_market.csv`：淘宝品类市场结构。
- `sql_price_band_structure.csv`：入门、主力、中高客单和高客单价格带。
- `sql_inventory_risk_queue.csv`：每个品类的库存风险优先处理队列。
- `sql_index_plan_audit.csv`：使用 `EXPLAIN QUERY PLAN` 验证复合索引命中的执行计划。
- `sql_bilibili_content_types.csv`：8类B站官号内容的数量、触达和互动表现。
- `sql_bilibili_yearly_trend.csv`：2019—2026年内容供给及类型变化。
- `sql_bilibili_operator_campaigns.csv`：角色上线Campaign曝光和内容深度排名。

## 商业试点候选与阶段表

- `pilot_candidate_shortlist.csv`：由公开内容、淘宝快照和真实匿名问卷生成的角色×品类候选池；`pilot_score`只决定验证顺序，不代表销量预测。
- `survey_role_category_n`：指定角色×品类组合的专项有效样本量；少于30份时`evidence_status=needs_targeted_research`，不得进入订单试点。
- `pilot_readiness.csv`：候选、内容预热、有效意向、供应商、订单、履约和复购评价七阶段的当前值、门槛、状态与下一步动作。
- `pilot_candidate_decisions.csv`：人工审批候选方向，记录是否通过、决策人角色、时间和原因。
- `pilot_supplier_public_leads.csv`：由公开商品快照形成的零售线索，保留商品证据、关联范围和待联系状态；不得当作报价或授权证明。
- `pilot_supplier_sourcing_gap.csv`：按已批准方案统计直接线索、邻近品类证据、授权供应商数量和距3家报价门槛的缺口。

## 商业试点真实记录表

- `pilot_campaigns.csv`：A/B内容预热活动，记录曝光、点击、落地页UV和发布时间，用于计算CTR与访问转化。
- `pilot_intent_leads.csv`：匿名购买意向登记，仅保留意向等级、目标价格、品类和知情同意，不保存姓名、电话、邮箱或地址。
- `pilot_supplier_quotes.csv`：供应商授权核验、MOQ、样品成本、量产成本、交期和报价接受状态。
- `pilot_orders.csv`：小批量试点订单的匿名经营记录，包含数量、商品额、折扣、运费、实付、成本和订单状态。
- `pilot_fulfillment_events.csv`：订单打包、发货、签收、取消和退货事件；不保存收件地址与物流单号。
- `pilot_after_sales.csv`：退款、退货、换货原因、影响数量、退款金额、状态和关闭时间。
- `pilot_reviews.csv`：匿名满意度、质量、交付、复购意愿和问题标签，不保存原始自由文本评论。
- 上述真实试点表的`is_simulated`必须固定为`false`；系统只创建空模板，不生成曝光、意向、供应商、订单、履约、售后或评价成果。

## 商业试点 SQL 视图

- `vw_pilot_content_funnel`：按候选方向汇总曝光、点击、UV、意向和CTR。
- `vw_pilot_supplier_scorecard`：比较授权状态、MOQ、单位成本、样品成本和交期。
- `vw_pilot_order_kpis`：计算订单数、销量、成交额、成本、毛利与取消情况。
- `vw_pilot_fulfillment_kpis`：汇总订单状态及按时发货、签收表现。
- `vw_pilot_after_sales_kpis`：汇总售后件数、退款金额、退货率和关闭情况。
- `vw_pilot_candidate_decision`：联结候选评分、人工审批和各阶段证据，形成最终准入看板。
