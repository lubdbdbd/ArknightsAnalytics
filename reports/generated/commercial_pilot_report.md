# Arknights Analytics 商业试点准备度报告

> 本报告只使用公开聚合数据与真实匿名问卷生成候选方向。供应商、曝光、意向、订单、履约、售后和评价必须由实际执行记录导入，系统不会生成模拟试点成果。

## 项目定位

《明日方舟》IP周边选品与商品运营分析平台，以用户洞察和内容热度形成候选池，再通过正版商品供应验证、内容预热、意向登记、小批量订单、履约和售后复盘建立可审计的0到1验证链路。

## 当前阶段门禁

| stage                 |   current_value | gate                                   | status   | next_action                  |
|:----------------------|----------------:|:---------------------------------------|:---------|:-----------------------------|
| candidate_approval    |               2 | 2 approved candidates / 1 operator     | complete | 围绕已批候选开展A/B内容预热              |
| content_preheat       |               0 | >0 tracked impressions                 | blocked  | 发布A/B概念内容并记录曝光、点击和落地页UV      |
| qualified_intent_pool |               0 | >=30 per approved candidate            | blocked  | 获取至少30条知情同意的匿名有效意向           |
| supplier_validation   |               0 | >=3 suppliers per approved candidate   | blocked  | 完成授权证据、MOQ、成本、样品和交期比价        |
| paid_order_pilot      |               0 | >=10 per approved candidate            | blocked  | 仅在候选与供应商通过门禁后，每个方案开展10至20单试点 |
| fulfillment           |               0 | >=90% delivered per approved candidate | blocked  | 记录打包、发货、签收、取消和退货事件           |
| post_purchase_review  |               0 | >=5 per approved candidate             | blocked  | 回收满意度、质量、交付和复购意愿             |

## 已审批验证方案

| candidate_id   | operator   | category   |   pilot_score |   targeted_respondent_count | evidence_status         | rationale                                                  | decided_at   |
|:---------------|:-----------|:-----------|--------------:|----------------------------:|:------------------------|:-----------------------------------------------------------|:-------------|
| CAND-002       | 新约能天使      | 亚克力制品      |         68.76 |                           2 | needs_targeted_research | 批准新约能天使亚克力制品进入专项意向与供应商核验；作为主力展示款验证角色视觉吸引力和中等价格带，不代表已经采购或备货 | 2026-09-05   |
| CAND-006       | 新约能天使      | 吧唧（徽章）     |         66.66 |                           2 | needs_targeted_research | 批准新约能天使吧唧（徽章）进入专项意向与供应商核验；作为低客单验证款观察转化门槛和组合购买意愿，不代表已经采购或备货 | 2026-09-05   |

## 数据驱动候选方向

| candidate_id   | operator   | base_operator   | category   |   pilot_score |   median_acceptable_price | evidence_status         | decision_note   |
|:---------------|:-----------|:----------------|:-----------|--------------:|--------------------------:|:------------------------|:----------------|
| CAND-001       | 新约能天使      | 能天使             | 毛绒玩偶       |         69.02 |                       200 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-002       | 新约能天使      | 能天使             | 亚克力制品      |         68.76 |                       100 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-008       | 缄默德克萨斯     | 德克萨斯            | 毛绒玩偶       |         59.48 |                       200 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-009       | 缄默德克萨斯     | 德克萨斯            | 亚克力制品      |         59.22 |                       100 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-013       | 归溟幽灵鲨      | 幽灵鲨             | 毛绒玩偶       |         57.69 |                       200 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-014       | 归溟幽灵鲨      | 幽灵鲨             | 亚克力制品      |         57.43 |                       100 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-015       | 凯尔希·思衡托    | 凯尔希             | 毛绒玩偶       |         57.21 |                       200 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-017       | 凯尔希·思衡托    | 凯尔希             | 亚克力制品      |         56.95 |                       100 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-023       | 荒芜拉普兰德     | 拉普兰德            | 毛绒玩偶       |         56.01 |                       200 | needs_targeted_research | 需先补充角色×品类专项样本   |
| CAND-025       | 荒芜拉普兰德     | 拉普兰德            | 亚克力制品      |         55.76 |                       100 | needs_targeted_research | 需先补充角色×品类专项样本   |

## 使用规则

1. 候选评分只用于确定概念测试顺序，不等同于销量预测。
2. 只有通过授权证据校验的现有正版或授权商品才能进入付费试点。
3. 未达到30条专项有效意向前，不进入订单测试。
4. 所有订单必须通过金额对账、状态流转、库存和退款校验。
5. 达成门禁后再报告实际CTR、意向转化率、成交转化率、取消率、履约及时率、退货率、毛利率和满意度。