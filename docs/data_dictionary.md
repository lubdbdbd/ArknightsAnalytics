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

