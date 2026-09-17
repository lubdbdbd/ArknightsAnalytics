"""Inventory-led commercial decisions; never infer real LTV or ROI from synthetic orders."""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import pandas as pd
from .channel_strategy import observed_channel_matrix, records
from .gmv import calculate_scenario

SOURCES=[
 {'title':'Shopify 产品分析指标定义','url':'https://help.shopify.com/en/manual/products/analytics'},
 {'title':'Shopify 库存周转口径','url':'https://www.shopify.com/blog/inventory-formulas'},
 {'title':'Shopify 客户获取成本与价值口径','url':'https://www.shopify.com/blog/customer-acquisition-cost'}
]

def finite_nonnegative(frame, fields):
    for field in fields:
        values=pd.to_numeric(frame[field],errors='coerce')
        if not values.map(lambda v:pd.notna(v) and math.isfinite(v) and v>=0).all():
            raise ValueError(f'{field}存在缺失、非有限值或负值')
        frame[field]=values

def validate_inventory(inventory, skus, headers, lines, purchases):
    inv=inventory.copy()
    if inv.empty or inv.duplicated(['sku_id','snapshot_date']).any():
        raise ValueError('库存快照为空或SKU日期重复')
    for frame in (inv,purchases):
        if 'is_simulated' not in frame or not frame.is_simulated.astype(str).str.lower().eq('true').all():
            raise ValueError('仅接受明确标记的模拟输入')
    if set(inv.sku_id)!=set(skus.sku_id):
        raise ValueError('库存SKU覆盖与主档不一致')
    inv['snapshot_date']=pd.to_datetime(inv.snapshot_date,errors='raise').dt.normalize()
    dates=pd.date_range(inv.snapshot_date.min(),inv.snapshot_date.max())
    if not inv.groupby('sku_id').size().eq(len(dates)).all():
        raise ValueError('库存日快照不连续或缺失')
    fields=['opening_stock','inbound_units','requested_sales_units','sold_units','stockout_units',
            'returned_units','restockable_return_units','damaged_units','closing_stock','locked_stock','available_stock']
    finite_nonnegative(inv,fields)
    if not inv[fields].apply(lambda c:c.eq(c.round())).all().all():
        raise ValueError('库存件数必须是整数')
    inv=inv.sort_values(['sku_id','snapshot_date']).reset_index(drop=True)
    checks=[
        inv.opening_stock+inv.inbound_units+inv.restockable_return_units-inv.sold_units-inv.closing_stock,
        inv.requested_sales_units-inv.sold_units-inv.stockout_units,
        inv.returned_units-inv.restockable_return_units-inv.damaged_units,
        inv.closing_stock-inv.locked_stock-inv.available_stock]
    if any(s.abs().gt(.001).any() for s in checks):
        raise ValueError('库存流量恒等式或锁定库存核对失败')
    previous=inv.groupby('sku_id').closing_stock.shift()
    if (inv.loc[previous.notna(),'opening_stock']-previous.dropna()).abs().gt(.001).any():
        raise ValueError('库存跨日衔接失败')
    first=inv.groupby('sku_id').opening_stock.first()
    if not first.eq(skus.set_index('sku_id').initial_stock.reindex(first.index)).all():
        raise ValueError('库存期初与SKU初始数量不一致')
    eligible=lines.loc[lines.payment_status.eq('paid') & lines.fulfillment_status.isin(['shipped','delivered'])].copy()
    eligible['snapshot_date']=pd.to_datetime(eligible.order_date)
    demand=eligible.groupby(['sku_id','snapshot_date']).quantity.sum().reindex(
        pd.MultiIndex.from_frame(inv[['sku_id','snapshot_date']]),fill_value=0)
    if not (inv.requested_sales_units.to_numpy()==demand.to_numpy()).all():
        raise ValueError('库存请求量与模拟已发货/已签收订单数量不一致')
    po=purchases.copy()
    if po.po_id.duplicated().any() or not po.sku_id.isin(skus.sku_id).all():
        raise ValueError('采购单重复或SKU不存在')
    finite_nonnegative(po,['quantity_received','quantity_ordered'])
    if (po.quantity_received>po.quantity_ordered).any() or not po.purchase_status.isin(['open','received']).all():
        raise ValueError('采购数量或状态不合法')
    arrived=po.loc[po.quantity_received.gt(0)].copy()
    if not arrived.purchase_status.eq('received').all():
        raise ValueError('采购收货状态不一致')
    arrived['snapshot_date']=pd.to_datetime(arrived.received_date,errors='raise')
    if arrived.snapshot_date.isna().any() or not arrived.snapshot_date.between(dates.min(),dates.max()).all():
        raise ValueError('采购收货日期缺失或超出库存窗口')
    receipts=arrived.groupby(['sku_id','snapshot_date']).quantity_received.sum().reindex(
        pd.MultiIndex.from_frame(inv[['sku_id','snapshot_date']]),fill_value=0)
    if not (receipts.to_numpy()==inv.inbound_units.to_numpy()).all():
        raise ValueError('采购收货与库存入库不一致')
    return inv

def ratio(a,b):
    return float(a/b) if b>0 else None

def inventory_decisions(inventory,skus,policy):
    days=int((inventory.snapshot_date.max()-inventory.snapshot_date.min()).days)+1
    window=min(int(policy['recent_days']),days)
    cutoff=inventory.snapshot_date.max()-pd.Timedelta(days=window-1)
    rows=[]
    for sku in skus.to_dict('records'):
        data=inventory.loc[inventory.sku_id.eq(sku['sku_id'])]
        recent=data.loc[data.snapshot_date.ge(cutoff)]
        sold=int(data.sold_units.sum());ending=int(data.iloc[-1].closing_stock)
        available=int(data.iloc[-1].available_stock)
        avg=float(data.closing_stock.mean());unit=float(sku['unit_cost'])
        recent_sold=int(recent.sold_units.sum());rate=recent_sold/window
        cover=ratio(available,rate);turnover_days=ratio(avg*days,sold)
        sell_through=ratio(sold,sold+ending)
        shortage_rate=ratio(data.stockout_units.sum(),data.requested_sales_units.sum())
        flags=[];actions=[];changes=[]
        if data.stockout_units.sum()>0 and (shortage_rate or 0)>=policy['shortage_rate']:
            flags.append('供给受限');actions.append('复核缺货日期、现货及采购到货，先验证供给再决定加量')
            changes.append('验证小批次滚动补货和交期方案，避免把缺货期销量当作真实需求上限')
        if available>0 and recent_sold==0:
            flags.append('近期无出库');actions.append('暂停自动补货，核对上架状态、曝光和商品信息')
            changes.append('复核品类、规格与价格接受度；以小批量或意向验证下一批')
        elif available>0 and cover is not None and cover>policy['slow_cover_days'] and sell_through is not None and sell_through<policy['low_sell_through']:
            flags.append('去化缓慢');actions.append('复核在途采购与促销成本，评估组合销售或缩减下一批')
            changes.append('减少大批量首发，比较低价格带或组合规格；不能直接断言价格过高')
        if rate>0 and cover is not None and cover<sku['purchase_lead_time_days']+policy['service_buffer_days']:
            flags.append('覆盖不足');actions.append('核对在途、锁定库存及交期后再确定补货')
            changes.append('调整首批数量或补货节奏，保留授权和质量约束')
        if not flags:
            flags=['常规观察'];actions=['继续观察库存、咨询与履约变化'];changes=['保留现有定义，积累同周期和同渠道的对比依据']
        slow=any(f in flags for f in ['近期无出库','去化缓慢'])
        rows.append({'sku_id':sku['sku_id'],'operator':sku['operator'],'category':sku['category'],
            'catalog_price':sku['price'],'unit_cost':unit,'lead_days':sku['purchase_lead_time_days'],
            'opening_units':int(data.iloc[0].opening_stock),'inbound_units':int(data.inbound_units.sum()),
            'restockable_return_units':int(data.restockable_return_units.sum()),
            'outbound_units':sold,'ending_units':ending,'available_units':available,
            'average_daily_closing_units':round(avg,4),'ending_inventory_cost':round(ending*unit,2),
            'average_inventory_cost':round(avg*unit,2),'outbound_cost':round(sold*unit,2),
            'period_sell_through':sell_through,'inventory_turnover_days':turnover_days,
            'recent_outbound_units':recent_sold,'recent_daily_outbound':rate,'available_cover_days':cover,
            'unmet_units':int(data.stockout_units.sum()),'unmet_rate':shortage_rate,
            'flags':flags,'risk': ' / '.join(flags),'slow_stock_cost':round(ending*unit,2) if slow else 0,
            'suggested_action':'；'.join(actions),'next_product_hypothesis':'；'.join(changes),
            'verification':'核对异常依据 → 选择同角色/同品类对比 → 小批量验证 → 复盘售出、缺货、贡献与退款',
            'evidence_scope':'模拟SKU日库存；订单日期代替出库请求日期，缺少批次库龄和真实发货时间，不是已实现节省'})
    summary={'skus':len(rows),'days':days,'recent_days':window,'inventory_snapshots':len(inventory),
             'outbound_units':sum(r['outbound_units'] for r in rows),'ending_units':sum(r['ending_units'] for r in rows),
             'ending_inventory_cost':round(sum(r['ending_inventory_cost'] for r in rows),2),
             'slow_stock_cost':round(sum(r['slow_stock_cost'] for r in rows),2),
             'unmet_units':sum(r['unmet_units'] for r in rows),'slow_skus':sum(r['slow_stock_cost']>0 for r in rows),
             'flag_counts':dict(Counter(f for r in rows for f in r['flags']))}
    summary['period_sell_through']=ratio(summary['outbound_units'],summary['outbound_units']+summary['ending_units'])
    summary['inventory_turnover_days']=ratio(sum(r['average_inventory_cost'] for r in rows)*days,sum(r['outbound_cost'] for r in rows))
    return rows,summary

def scenario_economics(parameters):
    result=calculate_scenario(parameters)
    spend=result['total_variable_cost']+result['platform_fees']+parameters['marketing_spend']
    return {**result,'modeled_total_cost':round(spend,2),
            'modeled_roi':ratio(result['contribution_profit'],spend),
            'scenario_revenue_to_ad_spend':ratio(result['paid_merchandise_gmv'],parameters['marketing_spend']),
            'roi_scope':'ROI=(扣退款后的收入−商品/履约/赠品/平台/推广成本)/这些成本。无固定成本与税费；非实际ROI。',
            'ad_scope':'销售额/推广费为假设全部归因的情景倍数，不是观测ROAS或增量投放收益'}

def build_business_decisions(root):
    root=Path(root)
    paths=[root/'config/business_decisions.json',root/'config/gmv_scenarios.json']
    paths += [root/f'data/processed/{name}.csv' for name in [
        'erp_sku_master','erp_order_headers','erp_order_lines','erp_inventory_daily','erp_purchase_orders']]
    policy=json.loads(paths[0].read_text(encoding='utf-8'))
    if (not 1<=policy['recent_days']<=365 or not 0<policy['slow_cover_days']<=3650 or
        not 0<policy['low_sell_through']<1 or not 0<policy['shortage_rate']<1 or not 0<=policy['service_buffer_days']<=365):
        raise ValueError('决策规则范围不合法')
    skus,headers,lines,inv,po=(pd.read_csv(p) for p in paths[2:])
    observed=observed_channel_matrix(headers,lines,skus)
    inv=validate_inventory(inv,skus,headers,lines,po)
    rows,summary=inventory_decisions(inv,skus,policy)
    gmv=json.loads(paths[1].read_text(encoding='utf-8'))
    scenarios=[{'name':'基准假设',**scenario_economics(gmv['baseline'])}]
    for s in gmv['strategies']:
        scenarios.append({'name':s['name'],**scenario_economics({**gmv['baseline'],**s['overrides']})})
    categories=[]
    for name in sorted(skus.category.unique()):
        rs=[r for r in rows if r['category']==name]
        sold=sum(r['outbound_units'] for r in rs);stock=sum(r['ending_units'] for r in rs)
        categories.append({'category':name,'skus':len(rs),'outbound_units':sold,'ending_units':stock,
           'sell_through':ratio(sold,sold+stock),
           'turnover_days':ratio(sum(r['average_inventory_cost'] for r in rs)*summary['days'],sum(r['outbound_cost'] for r in rs)),
           'ending_cost':round(sum(r['ending_inventory_cost'] for r in rs),2),
           'slow_cost':round(sum(r['slow_stock_cost'] for r in rs),2)})
    return {'policy':policy,'summary':summary,'inventory':rows,'categories':categories,'scenarios':scenarios,
            'period_start':str(inv.snapshot_date.min().date()),'period_end':str(inv.snapshot_date.max().date()),
            'quality':{'inventory_equations_passed':True,'purchase_receipts_reconciled':True,
                       'fulfilled_order_requests_reconciled':True,'paid_order_units':int(lines.loc[lines.payment_status.eq('paid'),'quantity'].sum()),
                       'source_orders':observed['source_orders'],
                       'note':'支付订单量、履约请求量、库存实际出库量分开统计；不得以支付数量替代实际出库。'},
            'ltv':{'value':None,'status':'暂不可计算','reason':'订单没有稳定的脱敏用户ID，缺少按用户连接的购买历史、获客成本及观察窗口。',
                   'required':['稳定脱敏用户ID与首次购买时间','同一用户的支付、退款和订单贡献记录','明确的观察窗口及获客渠道成本','足够成熟的用户分组与留存记录'],
                   'next_step':'先按首次购买月份建立分组，计算固定90/180/365天的人均净收入和人均贡献；未来LTV预测需另行验证，不能把短期金额直接叫生命周期价值。'},
            'limitations':['售出占比=窗口出库/(窗口出库+期末库存)，用于连续补货场景；不是某一生产批次售罄率。',
               '库存周转天数=平均日末库存成本/窗口出库成本×窗口天数；当前为固定单位成本、毛出库演练口径，未做财务退货成本冲回。',
               '可售天数=期末可用库存/近28天日均出库；分母为零时留空并单列近期无出库，不显示0天。',
               '缺少批次入库年龄，去化缓慢只能作为风险标签，不能确定货物已积压多久。',
               '退款旧快照存在超支付异常，本模块不引用其净利润；ROI仅复用GMV模块的独立成本假设。',
               '用户调研参与生成了模拟需求分布，模拟销量不能反过来独立证明真实用户偏好或策略有效。',
               '建议为待执行假设，不证明定价因果、库存减少或利润提升。'],
            'sources':SOURCES,'manifest':[{'file':str(p.relative_to(root)).replace('\\','/'),
                'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}

def render_business_decisions(report):
    s=report['summary']
    text=['# 商业数据决策分析','',report['policy']['assumption_notice'],'',
          f"窗口：{report['period_start']}—{report['period_end']}；{s['skus']}个模拟SKU，{s['inventory_snapshots']:,}条日库存快照。",
          f"库存出库{s['outbound_units']:,}件，期末库存{s['ending_units']:,}件；期末库存成本{s['ending_inventory_cost']:,.2f}元。",
          f"去化风险覆盖{s['slow_skus']}个SKU，相关库存成本{s['slow_stock_cost']:,.2f}元（不是节省金额）。",'',
          '## 指标与边界','',*[f'- {v}' for v in report['limitations']],'',
          '## 品类比较','|品类|出库件数|期末库存|售出占比|周转天数|','|---|---:|---:|---:|---:|']
    for r in report['categories']:
        sell='不可计算' if r['sell_through'] is None else f"{r['sell_through']:.1%}"
        days='不可计算' if r['turnover_days'] is None else f"{r['turnover_days']:.1f}"
        text.append(f"|{r['category']}|{r['outbound_units']}|{r['ending_units']}|{sell}|{days}|")
    text += ['','## 用户价值','',report['ltv']['reason'],report['ltv']['next_step'],'',
             '## 参考口径','',*[f"- [{s['title']}]({s['url']})" for s in report['sources']],'']
    return '\n'.join(text)
