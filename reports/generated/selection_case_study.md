# 新约能天使 周边选品验证案例

> 当前案例状态：`conditional_pilot`。只有内容、淘宝横截面、固定 SKU 时间序列和真实用户调研全部过门禁后，才升级为已验证选品。

## 决策假设

新约能天使具备较强内容关注和深层互动信号，但公开淘宝样本仍受搜索个性化、销量档位截断和非官方供给影响。当前建议不是大规模备货，而是先用低生产风险商品完成小批量验证，同时补齐固定 SKU 周期复采与真实用户调研。

## 证据门禁

| evidence_layer       | metric                     |   value |   threshold | gate_passed   | data_type                | interpretation    | case_status       |
|:---------------------|:---------------------------|--------:|------------:|:--------------|:-------------------------|:------------------|:------------------|
| content_heat         | cross_platform_heat        |   71.00 |       60.00 | True          | real_public_aggregate    | 角色公开内容关注度         | conditional_pilot |
| content_intent       | intent_score               |   82.74 |       70.00 | True          | real_public_aggregate    | 收藏、转发等深层互动意向      | conditional_pilot |
| taobao_query_quality | search_precision           |    0.70 |        0.60 | True          | real_public_snapshot     | 定向搜索样本相关率         | conditional_pilot |
| taobao_demand_proxy  | sales_proxy_lower_bound    |  249.00 |      100.00 | True          | real_public_lower_bound  | 公开收货人数下界代理，不是精确销量 | conditional_pilot |
| fixed_sku_timeseries | grade_c_or_above_available |    0.00 |        1.00 | False         | real_public_longitudinal | 至少两期且跨越7天的固定商品复采  | conditional_pilot |
| user_research        | n_30_segment_available     |    0.00 |        1.00 | False         | real_anonymous_survey    | 至少30名有效受访者的角色品类分层 | conditional_pilot |

## 淘宝品类证据

| category   |   public_sku_count |   sales_proxy_lower_bound |   median_price |   official_share |   fanmade_share | evidence_layer   | data_type            |
|:-----------|-------------------:|--------------------------:|---------------:|-----------------:|----------------:|:-----------------|:---------------------|
| 亚克力立牌      |                 10 |                     47.00 |          16.95 |             0.00 |            0.10 | taobao_category  | real_public_snapshot |
| 其他周边       |                  1 |                      1.00 |           9.00 |             0.00 |            1.00 | taobao_category  | real_public_snapshot |
| 徽章吧唧       |                  5 |                     17.00 |           5.34 |             0.00 |            0.60 | taobao_category  | real_public_snapshot |
| 服装COS      |                  2 |                      5.00 |          68.00 |             0.00 |            0.50 | taobao_category  | real_public_snapshot |
| 毛绒抱枕       |                 10 |                    136.00 |          56.56 |             0.10 |            0.40 | taobao_category  | real_public_snapshot |
| 生活数码       |                  7 |                     43.00 |          16.80 |             0.00 |            0.57 | taobao_category  | real_public_snapshot |

## 模拟 ERP 方案（仅用于方法演示）

| category   |   price |   selection_score | recommendation   |   production_risk |   inventory_risk | is_simulated   |
|:-----------|--------:|------------------:|:-----------------|------------------:|-----------------:|:---------------|
| 徽章         |   18.00 |             72.11 | 重点推荐             |              0.15 |            21.12 | True           |
| 色纸         |   30.00 |             71.27 | 重点推荐             |              0.15 |            13.99 | True           |
| 亚克力立牌      |   48.00 |             64.70 | 常规上架             |              0.25 |            35.98 | True           |
| 毛绒         |  128.00 |             50.33 | 常规上架             |              0.45 |            62.30 | True           |
| 服饰         |  229.00 |             32.62 | 谨慎测试             |              0.65 |            74.95 | True           |
| 手办         |  699.00 |             30.90 | 谨慎测试             |              0.80 |            95.56 | True           |

## 可执行选品建议

1. 低风险首发：徽章、纸品或亚克力小批量组合，用预售收藏、加购和付款转化验证真实需求。
2. 中风险承接：若连续两周固定 SKU 需求代理增长且用户调研价格接受度匹配，再增加毛绒或组合套装。
3. 高风险限制：服饰和手办在缺少真实订单、退款和履约数据时不做现货重仓。
4. 验收指标：预售转化、售罄率、退款率、客诉率、库存周转和复购意愿；公开内容热度不作为最终验收指标。

## 当前缺口

- 真实用户调研尚未达到每个角色×品类30份有效样本。
- 固定商品尚未达到至少两期、跨越7天的C级时间序列证据。
- 缺少授权订单、收藏加购、退款、库存和履约数据，因此不能声称真实商业转化。