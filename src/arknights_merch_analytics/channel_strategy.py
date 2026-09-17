"""SKU-channel planning, separate from simulated observations and actual distribution."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from .erp_reconciliation import reconcile_orders


def records(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def validate_policy(policy, categories):
    weights=policy['weights']
    if set(weights)!={'category','price','replenishment','production'} or not math.isclose(sum(weights.values()),1):
        raise ValueError('渠道适配权重必须包含四个维度且合计1')
    if not all(math.isfinite(v) and 0<=v<=1 for v in weights.values()):
        raise ValueError('渠道权重必须是有限非负比例')
    if not 0 <= policy['conditional_score'] < policy['priority_score'] <= 100:
        raise ValueError('适配评分阈值顺序错误')
    if not 0 < policy['price_gap_review_threshold'] <= 1 or not 0 <= policy['minimum_unit_margin'] < 1:
        raise ValueError('价差或贡献门槛范围错误')
    profiles=policy['profiles']
    if len({p['id'] for p in profiles})!=len(profiles) or len({p['channel'] for p in profiles})!=len(profiles):
        raise ValueError('渠道ID或名称重复')
    for p in profiles:
        if p['channel'] in policy['observation_only_channels']:
            raise ValueError('观察渠道不能同时纳入可配置渠道')
        if p['price_basis'] not in {'retail','wholesale'} or p['status'] not in {'模拟渠道','规划待验证'}:
            raise ValueError('渠道状态或价格口径未知')
        if not all(math.isfinite(p[k]) for k in ['price_min','price_max','preferred_replenishment_days']) or not 0<p['price_min']<=p['price_max'] or p['preferred_replenishment_days']<=0:
            raise ValueError('价格带或补货天数不合法')
        if not categories.issubset(p['category_scores']):
            raise ValueError('品类适配分缺失，不以0替代未知')
        if not all(math.isfinite(v) and 0<=v<=100 for v in p['category_scores'].values()):
            raise ValueError('品类评分须在0到100之间')
        for key in ['discount_rate','channel_fee_rate','refund_rate']:
            if not 0 <= p[key] < 1:
                raise ValueError('费率/折扣超出范围')
        if not math.isfinite(p['variable_cost_per_unit']) or p['variable_cost_per_unit']<0:
            raise ValueError('单位变动费用不合法')


def sku_fit(sku, profile, policy):
    price=float(sku['price']);lead=float(sku['purchase_lead_time_days'])
    low,high=profile['price_min'],profile['price_max']
    price_fit=100 if low<=price<=high else 100*(price/low if price<low else high/price)
    lead_fit=min(100,100*profile['preferred_replenishment_days']/lead)
    scores={'category':float(profile['category_scores'][sku['category']]),'price':price_fit,
            'replenishment':lead_fit,'production':100*(1-float(sku['production_risk']))}
    fit=sum(scores[k]*weight for k,weight in policy['weights'].items())
    proposed_price=round(price*(1-profile['discount_rate']),2)
    contribution=proposed_price*(1-profile['channel_fee_rate']-profile['refund_rate'])-float(sku['unit_cost'])-profile['variable_cost_per_unit']
    margin=contribution/proposed_price if proposed_price>0 else None
    if sku['sku_status']!='active':
        decision='状态待核验'
    elif margin is None or margin<policy['minimum_unit_margin']:
        decision='成本待复核'
    elif fit>=policy['priority_score']:
        decision='优先评审'
    elif fit>=policy['conditional_score']:
        decision='条件配置'
    else:
        decision='暂缓配置'
    reasons=[f"品类适配{scores['category']:.0f}分（人工规划规则）",
             '目录价位于规划价格带' if low<=price<=high else '目录价偏离规划价格带',
             '补货周期符合规划偏好' if lead<=profile['preferred_replenishment_days'] else '补货周期超出规划偏好，核对现货与排期',
             f"生产风险代理值{sku['production_risk']}，不是实际不良率"]
    return {'sku_code':sku['sku_code'],'sku_id':sku['sku_id'],'operator':sku['operator'],
            'category':sku['category'],'channel_id':profile['id'],'channel':profile['channel'],
            'channel_status':profile['status'],'price_basis':profile['price_basis'],
            'price_basis_label':'假设批发出货价' if profile['price_basis']=='wholesale' else '假设商品零售价',
            'catalog_price':price,'unit_cost':float(sku['unit_cost']),
            'replenishment_days':lead,'fit_score':round(fit,2),
            **{f'{k}_score':round(v,2) for k,v in scores.items()},
            'proposed_price':proposed_price,'unit_contribution':round(contribution,2),
            'unit_margin':round(margin,6) if margin is not None else None,
            'decision':decision,'reason':'；'.join(reasons),
            'requirements':'；'.join(profile['requirements']), 'offer_plan':profile['offer_plan'],
            'is_hypothetical':True,
            'cost_scope':'贡献测算扣商品、假设渠道费、退款及单位变动费；未扣营销、固定成本与税费，不是实际利润'}


def observed_channel_matrix(headers, lines, skus):
    if headers.empty or lines.empty or skus.empty:
        raise ValueError('分析输入不能为空')
    if headers[['channel','order_date']].isna().any().any() or headers.channel.astype(str).str.strip().eq('').any():
        raise ValueError('订单渠道或日期缺失')
    for frame in (headers,lines,skus):
        if 'is_simulated' not in frame or not frame.is_simulated.astype(str).str.lower().eq('true').all():
            raise ValueError('当前渠道模块只接受明确标记的模拟ERP')
    if skus.sku_id.duplicated().any() or skus.sku_code.duplicated().any():
        raise ValueError('SKU主档编码重复')
    if skus[['sku_id','sku_code','category','operator']].isna().any().any():
        raise ValueError('SKU主档关键字段缺失')
    numeric=['price','unit_cost','purchase_lead_time_days','production_risk']
    for key in numeric:
        values=pd.to_numeric(skus[key],errors='coerce')
        if not values.map(lambda v:pd.notna(v) and math.isfinite(v)).all():
            raise ValueError('SKU参数缺失或不合法')
    if (skus.price.le(0)|skus.unit_cost.lt(0)|skus.purchase_lead_time_days.le(0)|~skus.production_risk.between(0,1)).any():
        raise ValueError('SKU参数超出范围')
    if not reconcile_orders(headers,lines)['passed'].all():
        raise ValueError('订单头明细核对不通过')
    if not lines.sku_id.isin(skus.sku_id).all() or not lines.order_id.isin(headers.order_id).all():
        raise ValueError('订单明细存在未知SKU或订单')
    amounts=pd.to_numeric(lines.net_revenue,errors='coerce')
    expected=lines.quantity*lines.unit_price-lines.discount_amount
    if amounts.isna().any() or (~amounts.map(math.isfinite)).any() or amounts.lt(0).any() or (amounts-expected).abs().gt(.011).any():
        raise ValueError('明细净额与数量价格优惠不一致')
    paid=headers.loc[headers.payment_status.eq('paid'),['order_id','channel','order_date']]
    detail=lines.drop(columns=['order_date','payment_status'],errors='ignore').merge(paid,on='order_id',validate='many_to_one')
    detail=detail.merge(skus[['sku_id','sku_code','category','operator']],on='sku_id',validate='many_to_one')
    channels=sorted(headers.channel.dropna().unique().tolist())
    matrix=detail.groupby(['sku_id','channel']).agg(paid_orders=('order_id','nunique'),sold_units=('quantity','sum'),
        merchandise_gmv=('net_revenue','sum'),discount_amount=('discount_amount','sum')).reset_index()
    dense=pd.MultiIndex.from_product([skus.sku_id,channels],names=['sku_id','channel']).to_frame(index=False)
    dense=dense.merge(matrix,on=['sku_id','channel'],how='left',validate='one_to_one')
    count_fields=['paid_orders','sold_units','merchandise_gmv','discount_amount']
    dense[count_fields]=dense[count_fields].fillna(0)
    dense['average_paid_unit_price']=dense.merchandise_gmv.div(dense.sold_units.where(dense.sold_units.gt(0)))
    dense['observation_status']=dense.paid_orders.map(lambda n:'模拟窗口有支付订单' if n else '模拟窗口无支付订单，不代表没有需求')
    category=detail.groupby(['channel','category']).agg(paid_orders=('order_id','nunique'),sold_units=('quantity','sum'),
        merchandise_gmv=('net_revenue','sum'),discount_amount=('discount_amount','sum')).reset_index()
    category['channel_sales_share']=category.merchandise_gmv/category.groupby('channel').merchandise_gmv.transform('sum')
    category['average_paid_unit_price']=category.merchandise_gmv/category.sold_units
    summaries=[]
    for channel in channels:
        rows=detail.loc[detail.channel.eq(channel)]
        count=int(rows.order_id.nunique());amount=float(rows.net_revenue.sum())
        summaries.append({'channel':channel,'paid_orders':count,'merchandise_gmv':round(amount,2),
                          'paid_aov':round(amount/count,2) if count else None,
                          'sold_units':int(rows.quantity.sum()),'observed_sku_count':int(rows.sku_id.nunique())})
    expected_gmv=float((headers.loc[headers.payment_status.eq('paid'),'order_amount']-
                        headers.loc[headers.payment_status.eq('paid'),'discount_amount']).sum())
    if abs(sum(r['merchandise_gmv'] for r in summaries)-expected_gmv)>.011:
        raise ValueError('渠道商品GMV与独立订单头汇总不一致')
    return {'summary':summaries,'sku_channel':records(dense),'category_channel':records(category),
            'source_orders':len(headers),'source_lines':len(lines),'paid_orders':int(paid.order_id.nunique()),
            'paid_merchandise_gmv':round(expected_gmv,2),'period_start':str(headers.order_date.min()),
            'period_end':str(headers.order_date.max()),'reconciled':True,'is_simulated':True}


def review_price_gaps(matrix, threshold):
    """Compare same-SKU retail proposals only. Wholesale price and duplicate distribution are not conflicts."""
    eligible={}
    for row in matrix:
        if row['price_basis']=='retail' and row['decision'] in {'优先评审','条件配置'}:
            eligible.setdefault(row['sku_id'],[]).append(row)
    reviews=[]
    for sku_id, rows in eligible.items():
        for left,right in itertools.combinations(sorted(rows,key=lambda r:r['channel']),2):
            maximum=max(left['proposed_price'],right['proposed_price'])
            gap=abs(left['proposed_price']-right['proposed_price'])/maximum if maximum else 0
            if gap+1e-10 < threshold:
                continue
            reviews.append({'sku_id':sku_id,'operator':left['operator'],'category':left['category'],
                            'channel_a':left['channel'],'channel_b':right['channel'],
                            'price_a':left['proposed_price'],'price_b':right['proposed_price'],'relative_gap':round(gap,6),
                            'status':'规划价差待复核','next_action':'核对同规格、活动时段、运费、赠品与服务后再判断；不自动认定冲突或改价'})
    return reviews


def build_channel_strategy(root: Path):
    root=Path(root)
    paths=[root/'config/channel_strategy.json',root/'data/processed/erp_sku_master.csv',
           root/'data/processed/erp_order_headers.csv',root/'data/processed/erp_order_lines.csv']
    policy=json.loads(paths[0].read_text(encoding='utf-8'))
    skus,headers,lines=(pd.read_csv(p) for p in paths[1:])
    validate_policy(policy,set(skus.category.dropna()))
    observed=observed_channel_matrix(headers,lines,skus)
    actual_channels={r['channel'] for r in observed['summary']}
    known={p['channel'] for p in policy['profiles']}|set(policy['observation_only_channels'])
    if not actual_channels.issubset(known):
        raise ValueError('出现未定义渠道，请先补充定位或明确为观察渠道')
    lookups={(r['sku_id'],r['channel']):r for r in observed['sku_channel']}
    matrix=[]
    for sku in records(skus):
        for profile in policy['profiles']:
            row=sku_fit(sku,profile,policy)
            record=lookups.get((sku['sku_id'],profile['channel']))
            row.update(observed_paid_orders=record['paid_orders'] if record else None,
                       observed_gmv=record['merchandise_gmv'] if record else None,
                       observed_price=record['average_paid_unit_price'] if record else None,
                       observation_scope=record['observation_status'] if record else '未接入订单数据，不是零需求')
            matrix.append(row)
    profiles=[];category_matrix=[]
    for profile in policy['profiles']:
        rows=[r for r in matrix if r['channel_id']==profile['id']]
        counts=Counter(r['decision'] for r in rows)
        profiles.append({**profile,'evaluated_skus':len(rows),'priority_count':counts['优先评审'],
                         'conditional_count':counts['条件配置'],'cost_review_count':counts['成本待复核'],
                         'deferred_count':counts['暂缓配置']+counts['状态待核验'],
                         'source_note':'有模拟订单，仅用于方法演练' if profile['channel'] in actual_channels else '仅规划，无订单接入'})
        for category in sorted(skus.category.unique()):
            subset=[r for r in rows if r['category']==category]
            decisions=Counter(r['decision'] for r in subset)
            category_matrix.append({'channel':profile['channel'],'category':category,
                                    'average_fit_score':round(sum(r['fit_score'] for r in subset)/len(subset),2),
                                    'priority_count':decisions['优先评审'],'conditional_count':decisions['条件配置'],
                                    'cost_review_count':decisions['成本待复核'],
                                    'dominant_decision':decisions.most_common(1)[0][0],
                                    'price_basis':profile['price_basis']})
    reviews=review_price_gaps(matrix,policy['price_gap_review_threshold'])
    return {'version':policy['version'],'policy':policy,'profiles':profiles,'observed':observed,
            'matrix':matrix,'category_matrix':category_matrix,'price_reviews':reviews,
            'summary':{'sku_count':len(skus),'observed_channels':len(actual_channels),
                       'planning_channels':len(profiles),'prospective_channels':sum(p['status']=='规划待验证' for p in profiles),
                       'observation_only_channels':len(actual_channels&set(policy['observation_only_channels'])),
                       'sku_channel_evaluations':len(matrix),'category_channel_evaluations':len(category_matrix),
                       'price_review_pairs':len(reviews),'decision_counts':dict(Counter(r['decision'] for r in matrix))},
            'limitations':['原始订单及商品成本是模拟数据，规划矩阵不是实际销售网络或已执行铺货。',
                           '品类分、费率与价格带来自可修改的演练假设；分数不是转化率、销量概率或真实渠道优劣。',
                           '相同SKU跨渠道出售本身不是问题；价差需结合时间、权益及履约条件复核。',
                           '零售代理的批发出货价不与消费者零售价直接比较；众筹/代理无数据时保留空值。',
                           '补货周期不是发货时效，生产风险不是实际不良率；渠道准入、授权、账期和实际库存仍需确认。',
                           '按品类计算的订单数可能跨品类重复，不可相加作为渠道订单总数。',
                           '当前评分基于产品属性，未验证角色偏好与渠道的交互，不证明某角色在某渠道更畅销。'],
            'manifest':[{'file':str(p.relative_to(root)).replace('\\','/'),
                         'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}


def render_channel_strategy(report):
    summary=report['summary'];observed=report['observed']
    policy=report['policy'];weights=policy['weights']
    text=['# 渠道策略与SKU配置分析','',
          f"分析窗口：{observed['period_start']}—{observed['period_end']}；{observed['source_orders']:,}张模拟订单。",'',
          f"{summary['sku_count']}个SKU × {summary['planning_channels']}类规划渠道 = {summary['sku_channel_evaluations']:,}条适配评估。",
          f"规划渠道含{summary['prospective_channels']}类尚未接入数据的渠道；原始订单的{summary['observed_channels']}类渠道中，{summary['observation_only_channels']}类仅作观察。",'',
          report['policy']['assumption_notice'],'','## 渠道定位与配置候选','',
          '|渠道|状态|优先评审|条件配置|成本待复核|定位|','|---|---|---:|---:|---:|---|']
    for r in report['profiles']:
        text.append(f"|{r['channel']}|{r['status']}|{r['priority_count']}|{r['conditional_count']}|{r['cost_review_count']}|{r['positioning']}|")
    text+=['','## 方法','',
           f"品类适配{weights['category']:.0%}、目录价格带{weights['price']:.0%}、补货周期{weights['replenishment']:.0%}、生产风险代理{weights['production']:.0%}；权重是人工规划假设。",
           f"单件贡献率低于{policy['minimum_unit_margin']:.0%}的方案先进入成本复核；适配{policy['priority_score']}分及以上进入优先评审，{policy['conditional_score']}分及以上为条件配置，其余暂缓。优先评审不代表获批上架。",
           f"同SKU同零售价口径的候选中，价差达到{policy['price_gap_review_threshold']:.0%}的共有{summary['price_review_pairs']}组渠道对，均为规划复核项，不是已发生的价格冲突。",'',
           '## 证据与执行边界','',*[f'- {s}' for s in report['limitations']], '',
           '## 简历补充','',
           f"基于7类模拟订单渠道开展商品结构与价格分析，结合品类、价格带、补货周期及生产风险建立{summary['sku_count']}个SKU×{summary['planning_channels']}类规划渠道的适配矩阵，形成{summary['sku_channel_evaluations']:,}条评估；区分零售与批发价格口径，设置单位贡献及跨渠道价差复核规则，输出差异化商品配置候选与渠道准入清单。众筹及零售代理为待验证规划。",'']
    return '\n'.join(text)
