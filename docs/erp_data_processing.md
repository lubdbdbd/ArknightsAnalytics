# ERP 数据处理方案

## 岗位能力对应

项目把“参与ERP数据处理”拆解为可验证的六步：业务建模、数据录入与导入、清洗校验、经营计算、异常识别、运营动作输出。重点不是开发ERP系统，而是理解订单、商品、库存、采购、售后和财务数据之间的关系，并能使用Excel、Python和SQL完成核对与分析。

## 七张核心业务表

| 表 | 业务用途 | 关键校验 |
|---|---|---|
| SKU Master | 维护角色、品类、售价、成本、供应商和补货参数 | SKU唯一、售价高于0、成本不高于售价 |
| Order Header | 维护订单、渠道、支付、履约、优惠和实付 | 订单唯一、取消订单实付为0 |
| Order Line | 维护SKU、数量、单价、优惠分摊和成本 | 明细净收入=单价×数量-优惠 |
| Inventory Daily | 维护每日入库、销售、退货、残损和期末库存 | 期末=期初+入库-销售+可二次销售退货 |
| Purchase Order | 维护供应商、采购量、预计/实际到货和在途状态 | 实收不超过订购、延期可追溯 |
| After-sales | 维护退款、退货、换货、原因和关闭时长 | 售后订单与SKU必须存在 |
| Financial Summary | 汇总收入、成本、毛利、退货和库存周转 | 订单、库存、售后三层交叉核对 |

## 经营指标

- `Net Sales After Refund = Order Line Net Revenue - Refund Amount`
- `Gross Profit = Net Sales After Refund - COGS`
- `Gross Margin Rate = Gross Profit / Net Sales After Refund`
- `Return Rate = After-sales Units / Sold Units`
- `Sell-through Rate = Sold Units / (Initial Stock + Inbound Units)`
- `Inventory Turnover = COGS / Average Inventory Cost`
- `Days of Inventory = Ending Inventory / Average Daily Sales`
- `Stockout Rate = Stockout Units / Requested Sales Units`
- `Reorder Point = Lead-time Demand + Safety Stock`

## 当前数据产出

- 30名角色×7类正版周边，形成210个SKU主数据。
- 模拟90天经营周期，生成6,000张订单、7,652条订单明细和18,900条库存日快照。
- 根据再订货点生成355张采购单，其中260张已到货、95张期末仍在途；实收6,295件。
- 生成392条退款、退货或换货记录，用于售后原因和处理时长分析。
- 订单头与订单明细按0.01元容差对账，差异订单为0。
- 建立6个ERP业务视图、10组ERP专项SQL和8个ERP复合索引。

## 运营动作

1. 库存低于再订货点或库存天数不足采购提前期时，进入补货队列。
2. 缺货率超过2%时，提高安全库存并检查供应商交付周期。
3. 退货率超过8%时，暂停扩量，复盘材质、包装、详情页和质量问题。
4. 库存周转天数超过180天时，减少采购，并测试组合销售、折扣或渠道迁移。
5. 渠道分析同时观察净销售、客单价和退款金额率，避免只按GMV判断渠道质量。

## 面试回答

我没有把ERP理解成单纯录Excel，而是先建立SKU、订单、库存、采购、售后和财务之间的主外键关系，再用Python生成可复现的模拟业务数据，用SQL完成金额对账、库存流水平衡、渠道分析、售后Pareto和补货判断。用户问卷只用于角色、品类和渠道的需求权重，所有订单和经营结果都保留`is_simulated=true`，所以既能展示完整数据处理能力，也不会把模拟GMV包装成真实业绩。
