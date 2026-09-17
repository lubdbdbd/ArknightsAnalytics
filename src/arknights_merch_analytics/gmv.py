"""Order-grain GMV diagnostics and explicitly hypothetical marketing economics."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .erp_reconciliation import reconcile_orders


class Scenario(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    visitors: int = Field(ge=0, le=100_000_000)
    buyer_conversion: float = Field(ge=0, le=1)
    purchase_frequency: float = Field(ge=1, le=100)
    list_basket_value: float = Field(gt=0, le=1_000_000)
    discount_rate: float = Field(ge=0, le=1)
    cogs_per_order: float = Field(ge=0, le=1_000_000)
    fulfillment_per_order: float = Field(ge=0, le=100_000)
    gift_per_order: float = Field(ge=0, le=100_000)
    platform_fee_rate: float = Field(ge=0, le=1)
    refund_amount_rate: float = Field(ge=0, le=1)
    marketing_spend: float = Field(ge=0, le=1_000_000_000)
    order_capacity: int | None = Field(default=None, ge=0, le=100_000_000)


class ScenarioComparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base: Scenario
    candidate: Scenario


def money(value):
    return round(float(value), 2)


def calculate_scenario(parameters: Scenario | dict):
    p = parameters if isinstance(parameters, Scenario) else Scenario.model_validate(parameters)
    potential_buyers = p.visitors*p.buyer_conversion
    potential_orders = potential_buyers*p.purchase_frequency
    orders = potential_orders if p.order_capacity is None else min(potential_orders,p.order_capacity)
    aov = p.list_basket_value*(1-p.discount_rate)
    gmv = orders*aov
    refund = gmv*p.refund_amount_rate
    fees = gmv*p.platform_fee_rate
    variable_cost = p.cogs_per_order+p.fulfillment_per_order+p.gift_per_order
    unit_contribution = aov*(1-p.refund_amount_rate-p.platform_fee_rate)-variable_cost
    contribution = orders*unit_contribution-p.marketing_spend
    breakeven = p.marketing_spend/unit_contribution if unit_contribution > 0 else None
    # Expected counts may be fractional; round up only the actionable break-even order threshold.
    breakeven_orders = math.ceil(breakeven) if breakeven is not None else None
    conversion_needed = breakeven/(p.visitors*p.purchase_frequency) if breakeven is not None and p.visitors>0 else None
    capacity_feasible = (breakeven_orders is not None and p.visitors>0 and
        (p.order_capacity is None or breakeven_orders <= p.order_capacity) and conversion_needed <= 1)
    alerts=[]
    if orders < potential_orders:
        alerts.append('承接上限已限制订单量；提高流量不一定增加可承接成交')
    if unit_contribution <= 0:
        alerts.append('每单贡献不为正，增加订单无法覆盖推广投入')
    if contribution < 0:
        alerts.append('该假设下贡献利润为负')
    if not capacity_feasible:
        alerts.append('当前成本、流量或承接约束下无法达到测算盈亏平衡')
    return {'parameters': p.model_dump(), 'is_hypothetical': True,
            'potential_buyers': round(potential_buyers,4), 'potential_orders': round(potential_orders,4),
            'expected_paid_orders': round(orders,4), 'paid_aov': money(aov),
            'paid_merchandise_gmv': money(gmv), 'discount_amount': money(orders*p.list_basket_value*p.discount_rate),
            'expected_refund': money(refund), 'net_merchandise_amount': money(gmv-refund),
            'platform_fees': money(fees), 'total_variable_cost': money(orders*variable_cost),
            'unit_contribution': money(unit_contribution), 'contribution_profit': money(contribution),
            'breakeven_orders': breakeven_orders,
            'breakeven_buyer_conversion': conversion_needed,
            'breakeven_feasible': capacity_feasible,
            'alerts': alerts,
            'boundary': '演练测算；贡献利润已扣假设退款、商品、履约、赠品、平台费及推广费，未含固定成本和税费；退货成本不回冲。'}


def compare_scenario(base: Scenario | dict, candidate: Scenario | dict):
    b=calculate_scenario(base)
    c=calculate_scenario(candidate)
    p=Scenario.model_validate(candidate)
    aov=p.list_basket_value*(1-p.discount_rate)
    unit=aov*(1-p.refund_amount_rate-p.platform_fee_rate)-(p.cogs_per_order+p.fulfillment_per_order+p.gift_per_order)
    # Recover unrounded baseline profit for break-even comparison.
    bp=Scenario.model_validate(base)
    bo=bp.visitors*bp.buyer_conversion*bp.purchase_frequency
    if bp.order_capacity is not None:
        bo=min(bo,bp.order_capacity)
    base_profit=bo*(bp.list_basket_value*(1-bp.discount_rate)*(1-bp.refund_amount_rate-bp.platform_fee_rate)
                    -bp.cogs_per_order-bp.fulfillment_per_order-bp.gift_per_order)-bp.marketing_spend
    needed= max(0,math.ceil((base_profit+p.marketing_spend)/unit)) if unit>0 else None
    feasible=needed is not None and needed <= p.visitors*p.purchase_frequency and (p.order_capacity is None or needed <= p.order_capacity)
    return {**c,'gmv_change': money(c['paid_merchandise_gmv']-b['paid_merchandise_gmv']),
            'contribution_change': money(c['contribution_profit']-b['contribution_profit']),
            'orders_to_match_base_contribution': needed, 'match_base_feasible': feasible,
            'gmv_up_profit_down': c['paid_merchandise_gmv']>b['paid_merchandise_gmv'] and c['contribution_profit']<b['contribution_profit']}


def _records(frame):
    return json.loads(frame.to_json(orient='records',force_ascii=False))


def order_metrics(orders):
    paid=orders.loc[orders['payment_status'].eq('paid')]
    n=len(paid)
    amount=float(paid['merchandise_paid'].sum())
    units=float(paid['units'].sum())
    return {'order_count':len(orders),'paid_orders':n,
            'cancelled_orders':int(orders['payment_status'].eq('cancelled').sum()),
            'paid_merchandise_gmv':money(amount),'shipping_collected':money(paid['shipping_fee'].sum()),
            'paid_cash_including_shipping':money(paid['paid_amount'].sum()),
            'discount_amount':money(paid['discount_amount'].sum()),
            'paid_aov':money(amount/n) if n else None,
            'paid_units':int(units),'units_per_order':round(units/n,4) if n else None,
            'net_unit_price':money(amount/units) if units else None,
            'order_payment_completion_rate':round(n/len(orders),6) if len(orders) else None,
            'visitors':None,'paying_buyers':None,'visitor_conversion':None,
            'purchase_frequency':None,'repeat_purchase_rate':None}


def decompose_periods(before, after):
    b=order_metrics(before);a=order_metrics(after)
    result={'before':b,'after':a,'gmv_change':money(a['paid_merchandise_gmv']-b['paid_merchandise_gmv']),
            'order_count_contribution':None,'aov_contribution':None,'reconciled':None}
    if b['paid_orders'] and a['paid_orders']:
        n0,n1=b['paid_orders'],a['paid_orders']
        # Unrounded means retain exact additive identity before monetary output rounding.
        p0=float(before.loc[before.payment_status.eq('paid'),'merchandise_paid'].sum())/n0
        p1=float(after.loc[after.payment_status.eq('paid'),'merchandise_paid'].sum())/n1
        count=(n1-n0)*(p0+p1)/2
        price=(p1-p0)*(n0+n1)/2
        result.update(order_count_contribution=money(count),aov_contribution=money(price),
                      reconciled=abs(count+price-result['gmv_change'])<.011)
    result['method']='对订单数与客单价的两种变化顺序取平均，分摊交互项；属于会计式拆解，不是营销因果归因。'
    return result


def observed_order_analysis(headers, lines, aftersales):
    if headers.empty or lines.empty:
        raise ValueError('缺少订单头或订单明细')
    for frame in [headers,lines,aftersales]:
        if 'is_simulated' not in frame or not frame['is_simulated'].astype(str).str.lower().eq('true').all():
            raise ValueError('当前模块只接受明确标记的模拟ERP数据')
    checked=reconcile_orders(headers,lines)
    if not checked['passed'].all():
        raise ValueError('订单核对未通过，先修正订单头与明细，再进行GMV分析')
    if not lines['order_id'].isin(headers['order_id']).all():
        raise ValueError('存在不属于订单头的孤立明细')
    net_values=pd.to_numeric(lines['net_revenue'],errors='coerce')
    if not net_values.map(lambda value: pd.notna(value) and math.isfinite(value) and value>=0).all():
        raise ValueError('明细净额存在缺失或非法数值')
    frame=headers.copy()
    totals=lines.groupby('order_id').agg(units=('quantity','sum'),line_net=('net_revenue','sum'))
    frame=frame.merge(totals,how='left',on='order_id',validate='one_to_one')
    frame['merchandise_paid']=(frame['order_amount']-frame['discount_amount']).where(frame.payment_status.eq('paid'),0)
    if (frame.loc[frame.payment_status.eq('paid'),'line_net']-frame.loc[frame.payment_status.eq('paid'),'merchandise_paid']).abs().gt(.011).any():
        raise ValueError('商品实付与明细净额不一致')
    dates=pd.to_datetime(frame.order_date,errors='raise')
    end=dates.max().date()
    after_start=end-timedelta(days=27)
    before_start=after_start-timedelta(days=28)
    if dates.min().date()>before_start:
        comparison={'status':'insufficient_history','before_start':str(before_start),'after_end':str(end)}
    else:
        before=frame.loc[(dates.dt.date>=before_start)&(dates.dt.date<after_start)]
        after=frame.loc[(dates.dt.date>=after_start)&(dates.dt.date<=end)]
        comparison={'status':'available','before_start':str(before_start),'before_end':str(after_start-timedelta(days=1)),
                    'after_start':str(after_start),'after_end':str(end),**decompose_periods(before,after)}
    channels=[{'channel':key,**order_metrics(group)} for key,group in frame.groupby('channel')]
    segments=[{'customer_segment':key,**order_metrics(group)} for key,group in frame.groupby('customer_segment')]
    # Existing raw refund snapshot contains a known defect. Report it instead of presenting net sales as trusted.
    closed=aftersales.loc[aftersales.case_status.eq('closed')]
    refund=closed.groupby('order_id')['refund_amount'].sum()
    merged=frame.set_index('order_id')
    refund_exceeds_cash=(refund.reindex(merged.index,fill_value=0)-merged['paid_amount']).round(2).gt(.01)
    refund_exceeds_goods=(refund.reindex(merged.index,fill_value=0)-merged['merchandise_paid']).round(2).gt(.01)
    return {'is_simulated':True,'period_start':str(dates.min().date()),'period_end':str(end),
            'summary':order_metrics(frame),'channels':channels,'segments':segments,'comparison':comparison,
            'reconciliation':{'orders_checked':len(checked),'passed':True,
                             'merchandise_plus_shipping_equals_cash':bool(abs(frame.merchandise_paid.sum()+frame.loc[frame.payment_status.eq('paid'),'shipping_fee'].sum()-frame.paid_amount.sum())<.011)},
            'refund_audit':{'closed_cases':len(closed),'orders_exceeding_cash':int(refund_exceeds_cash.sum()),
                            'orders_exceeding_merchandise':int(refund_exceeds_goods.sum()),
                            'net_sales_after_refund':None,
                            'status':'待刷新并复核修正后的售后快照；本模块不展示已扣退款净销售或实测利润'},
            'missing_data':['访客UV及商品曝光/访问事件','匿名客户唯一标识及跨期订单关联','实际营销支出与投放归因','经修正并复核的售后快照'],
            'metric_notes':['GMV采用已支付订单优惠后商品金额，不含运费；取消订单不计入，退款单列。',
                            '订单支付完成率＝已支付订单数÷已创建订单数，不是访问转化率。',
                            'customer_segment是客群标签，不是客户ID；不能用其计算人数或复购。',
                            '订单数×客单价已包含重复购买订单，不再乘购买频次或复购率。']}


def build_gmv_report(root: Path):
    root=Path(root)
    files=[root/'config/gmv_scenarios.json',*[root/'data/processed'/f'erp_{name}.csv' for name in ['order_headers','order_lines','after_sales']]]
    config=json.loads(files[0].read_text(encoding='utf-8'))
    observed=observed_order_analysis(*(pd.read_csv(p) for p in files[1:]))
    base=config['baseline']
    strategies=[];sensitivity=[]
    for case in config['strategies']:
        parameters={**base,**case['overrides']}
        result=compare_scenario(base,parameters)
        strategies.append({**case,**result})
        for multiplier in config['conversion_multipliers']:
            p={**parameters,'buyer_conversion':parameters['buyer_conversion']*multiplier}
            r=compare_scenario(base,p)
            sensitivity.append({'strategy':case['name'],'conversion_multiplier':multiplier,
                                'buyer_conversion':p['buyer_conversion'],**{k:r[k] for k in [
                                    'expected_paid_orders','paid_aov','paid_merchandise_gmv','contribution_profit',
                                    'gmv_change','contribution_change','gmv_up_profit_down']}})
    return {'version':config['version'],'observed':observed,'baseline':calculate_scenario(base),
            'strategies':strategies,'sensitivity':sensitivity,'assumption_notice':config['assumption_notice'],
            'risk_examples':[row for row in sensitivity if row['gmv_up_profit_down']],
            'identities':['已支付订单数 × 优惠后商品客单价 = 支付商品GMV',
                          '同周期访客UV × 购买用户转化率 × 人均支付订单数 × 商品客单价 = 支付商品GMV（需一致用户去重口径，且未受订单容量限制）'],
            'experiment_status':'方案设计与假设测算，未执行真实营销实验',
            'manifest':[{'file':str(p.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}


def render_gmv_report(report):
    o=report['observed'];s=o['summary'];c=o['comparison']
    lines=['# GMV驱动分析与营销情景测算','',f"模拟订单期间：{o['period_start']}—{o['period_end']}",'',
           '## 订单可计算指标','',f"- 订单总数：{s['order_count']}；支付订单：{s['paid_orders']}。",
           f"- 支付商品GMV：{s['paid_merchandise_gmv']:,.2f}元（不含运费，未扣退款）。",
           f"- 商品客单价：{s['paid_aov']:,.2f}元；订单支付完成率：{s['order_payment_completion_rate']:.2%}。",
           '- 访客转化、购买频次和复购率缺少必要数据，保留为空。', '',
           '## GMV变化拆解','',json.dumps(c,ensure_ascii=False,indent=2),'',
           '## 营销情景（全部为假设）','',report['assumption_notice'],'',
           '|方案|预计订单|GMV|贡献利润|GMV较基准变化|贡献利润较基准变化|', '|---|---:|---:|---:|---:|---:|']
    for r in report['strategies']:
        lines.append(f"|{r['name']}|{r['expected_paid_orders']}|{r['paid_merchandise_gmv']:,.2f}|{r['contribution_profit']:,.2f}|{r['gmv_change']:,.2f}|{r['contribution_change']:,.2f}|")
    lines+=['',report['baseline']['boundary'],'',f"共{len(report['strategies'])}类策略、{len(report['sensitivity'])}组转化假设敏感性情景。这些不是A/B实验结果。",'',
            '## GMV增长但贡献下降的假设案例','',
            *[f"- {r['strategy']}，转化假设为预设的{r['conversion_multiplier']:.0%}：GMV较基准增加{r['gmv_change']:,.2f}元，贡献利润变化{r['contribution_change']:,.2f}元。需要验证额外订单能否覆盖优惠与推广成本。" for r in report['risk_examples']], '',
            '## 真实验证方案','',*[f"- **{r['name']}**：{r['experiment']}" for r in report['strategies']], '',
            '## 数据缺口与退款边界','',*[f'- {text}' for text in o['missing_data']],
            f"- 旧售后快照有{o['refund_audit']['orders_exceeding_cash']}个订单的已关闭退款超过含运费实付，暂不出具扣退款净销售或实测利润。",'',
            '## 简历补充','',
            f"基于{s['order_count']:,}张模拟订单，按支付订单数与商品客单价拆解GMV，对连续两个28日窗口进行变化贡献分析；构建组合销售、阶梯优惠、限量溢价及大促4类营销方案，开展12组转化假设敏感性测算，联动折扣、成本、退款及承接容量评估成交与贡献利润，输出实验方案和数据补采要求。",'']
    return '\n'.join(lines)
