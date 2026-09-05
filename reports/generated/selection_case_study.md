# 新约能天使 周边选品验证案例

> 当前案例状态：`conditional_pilot`。只有内容、淘宝横截面、固定 SKU 时间序列和真实用户调研全部过门禁后，才升级为已验证选品。

## 决策假设

新约能天使具备较强内容关注和深层互动信号，但公开淘宝样本仍受搜索个性化、销量档位截断和非官方供给影响。当前建议不是大规模备货，而是先用低生产风险商品完成小批量验证，同时补齐固定 SKU 周期复采与真实用户调研。

## 证据门禁

| evidence_layer       | metric                     |   value |   threshold | gate_passed   | data_type                | interpretation    | case_status       |
|:---------------------|:---------------------------|--------:|------------:|:--------------|:-------------------------|:------------------|:------------------|
| content_heat         | cross_platform_heat        |   71.93 |       60.00 | True          | real_public_aggregate    | 角色公开内容关注度         | conditional_pilot |
| content_intent       | intent_score               |   82.67 |       70.00 | True          | real_public_aggregate    | 收藏、转发等深层互动意向      | conditional_pilot |
| taobao_query_quality | search_precision           |    0.70 |        0.60 | True          | real_public_snapshot     | 定向搜索样本相关率         | conditional_pilot |
| taobao_demand_proxy  | sales_proxy_lower_bound    |  100.00 |      100.00 | True          | real_public_lower_bound  | 公开收货人数下界代理，不是精确销量 | conditional_pilot |
| fixed_sku_timeseries | grade_c_or_above_available |    0.00 |        1.00 | False         | real_public_longitudinal | 至少两期且跨越7天的固定商品复采  | conditional_pilot |
| user_research        | n_30_segment_available     |    0.00 |        1.00 | False         | real_anonymous_survey    | 至少30名有效受访者的角色品类分层 | conditional_pilot |

## 淘宝品类证据

| category   |   public_sku_count |   sales_proxy_lower_bound |   median_price |   official_share |   fanmade_share | evidence_layer   | data_type            |
|:-----------|-------------------:|--------------------------:|---------------:|-----------------:|----------------:|:-----------------|:---------------------|
| 亚克力制品      |                  4 |                      9.00 |          14.40 |             0.00 |            0.25 | taobao_category  | real_public_snapshot |
| 其他正版周边     |                  4 |                     15.00 |          14.12 |             0.00 |            1.00 | taobao_category  | real_public_snapshot |
| 吧唧（徽章）     |                  5 |                     17.00 |           5.34 |             0.00 |            0.60 | taobao_category  | real_public_snapshot |
| 日用生活       |                  6 |                     34.00 |          52.69 |             0.00 |            0.33 | taobao_category  | real_public_snapshot |
| 毛绒玩偶       |                 10 |                    136.00 |          56.56 |             0.10 |            0.40 | taobao_category  | real_public_snapshot |
| 通行证        |                  6 |                     38.00 |          38.03 |             0.00 |            0.00 | taobao_category  | real_public_snapshot |

## 模拟 ERP 方案（仅用于方法演示）

| category   |   price |   selection_score | recommendation   |   production_risk |   inventory_risk | is_simulated   |
|:-----------|--------:|------------------:|:-----------------|------------------:|-----------------:|:---------------|
| 吧唧（徽章）     |   18.00 |             78.08 | 重点推荐             |              0.15 |             4.67 | True           |
| 通行证        |   39.00 |             67.40 | 重点推荐             |              0.20 |            18.52 | True           |
| 亚克力制品      |   48.00 |             67.34 | 重点推荐             |              0.24 |            36.55 | True           |
| 装饰摆件       |   89.00 |             46.17 | 常规上架             |              0.38 |            50.60 | True           |
| 毛绒玩偶       |  128.00 |             45.18 | 常规上架             |              0.46 |            66.52 | True           |
| 日用生活       |   99.00 |             43.02 | 谨慎测试             |              0.52 |            73.76 | True           |

## 可执行选品建议

1. 低风险首发：吧唧（徽章）、通行证或亚克力制品小批量组合，用预售收藏、加购和付款转化验证真实需求。
2. 中风险承接：若连续两周固定 SKU 需求代理增长且用户调研价格接受度匹配，再增加装饰摆件、日用生活或毛绒玩偶。
3. 高风险限制：手办模玩在缺少真实订单、退款和履约数据时不做现货重仓；日用生活需额外验证规格和退换风险。
4. 验收指标：预售转化、售罄率、退款率、客诉率、库存周转和复购意愿；公开内容热度不作为最终验收指标。

## 当前缺口

- 真实用户调研尚未达到每个角色×品类30份有效样本。
- 固定商品尚未达到至少两期、跨越7天的C级时间序列证据。
- 缺少授权订单、收藏加购、退款、库存和履约数据，因此不能声称真实商业转化。