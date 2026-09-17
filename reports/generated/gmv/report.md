# GMV驱动分析与营销情景测算

模拟订单期间：2026-06-01—2026-08-29

## 订单可计算指标

- 订单总数：6000；支付订单：5793。
- 支付商品GMV：1,268,567.90元（不含运费，未扣退款）。
- 商品客单价：218.98元；订单支付完成率：96.55%。
- 访客转化、购买频次和复购率缺少必要数据，保留为空。

## GMV变化拆解

{
  "status": "available",
  "before_start": "2026-07-05",
  "before_end": "2026-08-01",
  "after_start": "2026-08-02",
  "after_end": "2026-08-29",
  "before": {
    "order_count": 1947,
    "paid_orders": 1876,
    "cancelled_orders": 71,
    "paid_merchandise_gmv": 401186.2,
    "shipping_collected": 5640.0,
    "paid_cash_including_shipping": 406826.2,
    "discount_amount": 16190.8,
    "paid_aov": 213.85,
    "paid_units": 2678,
    "units_per_order": 1.4275,
    "net_unit_price": 149.81,
    "order_payment_completion_rate": 0.963534,
    "visitors": null,
    "paying_buyers": null,
    "visitor_conversion": null,
    "purchase_frequency": null,
    "repeat_purchase_rate": null
  },
  "after": {
    "order_count": 1625,
    "paid_orders": 1569,
    "cancelled_orders": 56,
    "paid_merchandise_gmv": 353611.5,
    "shipping_collected": 4668.0,
    "paid_cash_including_shipping": 358279.5,
    "discount_amount": 15000.5,
    "paid_aov": 225.37,
    "paid_units": 2274,
    "units_per_order": 1.4493,
    "net_unit_price": 155.5,
    "order_payment_completion_rate": 0.965538,
    "visitors": null,
    "paying_buyers": null,
    "visitor_conversion": null,
    "purchase_frequency": null,
    "repeat_purchase_rate": null
  },
  "gmv_change": -47574.7,
  "order_count_contribution": -67421.15,
  "aov_contribution": 19846.45,
  "reconciled": true,
  "method": "对订单数与客单价的两种变化顺序取平均，分摊交互项；属于会计式拆解，不是营销因果归因。"
}

## 营销情景（全部为假设）

以下是演练假设，不是观测流量、实验效果、真实销售或需求预测；所有方案采用相同经营周期。

|方案|预计订单|GMV|贡献利润|GMV较基准变化|贡献利润较基准变化|
|---|---:|---:|---:|---:|---:|
|组合销售|270.0|48,600.00|16,712.00|12,600.00|4,992.00|
|阶梯优惠|330.0|44,550.00|11,936.00|8,550.00|216.00|
|限量溢价|250.0|33,000.00|12,360.00|-3,000.00|640.00|
|大促节点|540.0|58,320.00|11,934.40|22,320.00|214.40|

演练测算；贡献利润已扣假设退款、商品、履约、赠品、平台费及推广费，未含固定成本和税费；退货成本不回冲。

共4类策略、12组转化假设敏感性情景。这些不是A/B实验结果。

## GMV增长但贡献下降的假设案例

- 大促节点，转化假设为预设的80%：GMV较基准增加10,656.00元，贡献利润变化-3,172.48元。需要验证额外订单能否覆盖优惠与推广成本。

## 真实验证方案

- **组合销售**：比较单品页与套装页，同期随机分配合格用户，核对客单价、转化、单订单贡献及退款。
- **阶梯优惠**：固定商品与渠道比较优惠档位，记录各档订单数、优惠金额、凑单件数和贡献利润；优惠规则需先核准。
- **限量溢价**：先验证授权、真实限量与供给，再开展价格接受度及小规模意向验证，关注滞销、取消和履约风险。
- **大促节点**：预先记录活动周期、来源和分组，监测支付、优惠、履约及退款；同期对照，不能把季节性增长都归因于活动。

## 数据缺口与退款边界

- 访客UV及商品曝光/访问事件
- 匿名客户唯一标识及跨期订单关联
- 实际营销支出与投放归因
- 经修正并复核的售后快照
- 旧售后快照有44个订单的已关闭退款超过含运费实付，暂不出具扣退款净销售或实测利润。

## 简历补充

基于6,000张模拟订单，按支付订单数与商品客单价拆解GMV，对连续两个28日窗口进行变化贡献分析；构建组合销售、阶梯优惠、限量溢价及大促4类营销方案，开展12组转化假设敏感性测算，联动折扣、成本、退款及承接容量评估成交与贡献利润，输出实验方案和数据补采要求。
