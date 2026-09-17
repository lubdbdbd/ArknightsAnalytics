"""Replay collected public observations without network calls or changing old baselines."""
from __future__ import annotations
import argparse,hashlib,html,json,sqlite3,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arknights_merch_analytics.public_expansion import normalize_products,STORES,latest_union,skland_entities
from arknights_merch_analytics.metrics import EXCLUDED_OPERATOR_ENTITIES

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-date',required=True);args=parser.parse_args()
    raw=ROOT/'data/public/expansion'/args.run_date
    out=ROOT/'data/processed/expansion'/args.run_date;out.mkdir(parents=True,exist_ok=True)
    report=ROOT/'reports/generated/public_expansion'/args.run_date;report.mkdir(parents=True,exist_ok=True)
    def load(name):
        path=raw/name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    products=[];variants=[];tables={}
    for source in STORES:
        payload=load(source+'.json')
        if payload:
            p,v=normalize_products(payload,source,payload['observed_at']);products+=p;variants+=v
    tables['official_store_products']=pd.DataFrame(products)
    tables['official_store_variants']=pd.DataFrame(variants)
    tables['operator_reference']=pd.DataFrame(load('operator_metadata.json'))
    news=load('yostar_news.json')
    tables['official_news']=pd.DataFrame([{'post_id':str(p['id']),'title':html.unescape(p['title']['rendered']),
        'published_at':p['date']+'+09:00','source_url':p['link'],'source':'yostar_plus',
        'observed_at':news['observed_at'],'is_simulated':False,
        'relevance':'explicit_title' if 'アークナイツ' in p['title']['rendered'] else 'search_match_requires_review'}
        for p in news.get('posts',[])]) if news else pd.DataFrame()

    bili_old=json.loads((ROOT/'data/public/bilibili_official_archive.json').read_text(encoding='utf-8'))
    bili_old=[r for r in bili_old if not any(x in r['title'] for x in EXCLUDED_OPERATOR_ENTITIES)]
    bili_new=load('bilibili_observations.json')
    tables['bilibili_new_observations']=pd.DataFrame(bili_new)
    tables['bilibili_expanded_archive']=pd.DataFrame(latest_union(bili_old,bili_new,'bvid'))
    weibo_old=json.loads((ROOT/'data/public/weibo_official_recent_posts.json').read_text(encoding='utf-8'))
    weibo_new=load('weibo_observations.json')
    tables['weibo_new_observations']=pd.DataFrame(weibo_new)
    tables['weibo_expanded_archive']=pd.DataFrame(latest_union(weibo_old,weibo_new,'post_id'))

    sk_old=pd.read_csv(ROOT/'data/public/skland_strategy_operator_search_snapshot.csv',dtype={'item_id':str})
    sk_obs=load('skland_search_observations.json')
    sk_new=skland_entities(sk_obs)
    tables['skland_search_observations']=pd.DataFrame(sk_obs)
    tables['skland_new_entities']=pd.DataFrame(sk_new)
    old_fields=['item_id','title','posted_at','viewed','liked','collected','reposted','commented','source_url','is_simulated']
    # The published 582 baseline counts explicit title matches, not all 830 search hits.
    old_sanitized=sk_old.loc[sk_old['direct_name_match'].eq(True),old_fields].drop_duplicates('item_id').to_dict('records')
    tables['skland_expanded_entities']=pd.DataFrame(latest_union(old_sanitized,sk_new,'item_id'))

    # Sales cannot be inferred from available=true; prices summarized per listing, not variant.
    pframe=tables['official_store_products']
    if not pframe.empty:
        tables['official_store_category_summary']=pframe.groupby(['source','market','currency','category'],dropna=False).agg(
            product_listings=('product_key','nunique'),variant_count=('variant_count','sum'),
            min_list_price=('price_min','min'),median_start_price=('price_min','median'),
            max_list_price=('price_max','max'),available_variants=('available_variant_count','sum')).reset_index()
    mapping=[]
    import re
    operators=tables['operator_reference'].to_dict('records')
    titles={p['product_key']:p['title'] for p in products}
    for variant in variants:
        text=titles[variant['product_key']]+' '+str(variant['variant_title'])
        for op in operators:
            en=str(op.get('english_name') or '').strip();cn=str(op.get('operator') or '')
            matched=bool((len(en)>=3 and re.search(r'(?<![A-Za-z])'+re.escape(en)+r'(?![A-Za-z])',text,re.I))
                         or (len(cn)>=2 and any('\u4e00'<=c<='\u9fff' for c in cn) and cn in text))
            if matched:mapping.append({'variant_key':variant['variant_key'],'product_key':variant['product_key'],
                'operator_id':op['operator_id'],'operator':op['operator'],'match_method':'explicit_name_candidate',
                'review_status':'pending','source_url':variant['source_url']})
    tables['variant_operator_candidates']=pd.DataFrame(mapping,columns=['variant_key','product_key','operator_id','operator','match_method','review_status','source_url'])

    def count_new(before,after,key):
        return len({str(r[key]) for r in after}-{str(r[key]) for r in before})
    counts=[
      {'dataset':'B站官号内容','unit':'去重BV号','before':len({r['bvid'] for r in bili_old}),
       'observed_this_run':len(bili_new),'net_new':count_new(bili_old,bili_new,'bvid'),
       'after':len(tables['bilibili_expanded_archive']),'use':'历史内容与传播类型分析'},
      {'dataset':'微博官号内容','unit':'去重帖子ID','before':len({r['post_id'] for r in weibo_old}),
       'observed_this_run':len(weibo_new),'net_new':count_new(weibo_old,weibo_new,'post_id'),
       'after':len(tables['weibo_expanded_archive']),'use':'近期官方发布与内容互证'},
      {'dataset':'森空岛搜索内容','unit':'去重文章ID','before':len(old_sanitized),
       'observed_this_run':len(sk_new),'net_new':count_new(old_sanitized,sk_new,'item_id'),
       'after':len(tables['skland_expanded_entities']),'use':'新增角色与周边主题搜索聚合'},
    ]
    for name,table,unit,use in [('官方海外商品档案','official_store_products','店铺限定商品ID','品类与供给结构'),
          ('官方海外商品规格','official_store_variants','店铺限定规格ID','规格、标价、可售状态'),
          ('官方资讯检索样本','official_news','官方资讯ID','筛选上新及活动线索，区分标题匹配与待复核'),
          ('角色参考主档','operator_reference','可获得干员ID','角色名称、阵营、职业与稀有度治理')]:
        n=len(tables[table]);counts.append({'dataset':name,'unit':unit,'before':0,'observed_this_run':n,'net_new':n,'after':n,'use':use})
    tables['data_expansion_inventory']=pd.DataFrame(counts)

    checks=[]
    def check(name,ok,detail):checks.append({'check':name,'passed':bool(ok),'detail':detail})
    for table,key in [('official_store_products','product_key'),('official_store_variants','variant_key'),
                      ('operator_reference','operator_id'),('official_news','post_id'),
                      ('bilibili_expanded_archive','bvid'),('weibo_expanded_archive','post_id'),('skland_expanded_entities','item_id')]:
        f=tables[table];check(table+'_unique',not f.empty and not f[key].duplicated().any(),str(len(f)))
        check(table+'_source_url',not f.empty and f['source_url'].fillna('').str.startswith('https://').all(),'Every retained row has a source URL')
    vf=tables['official_store_variants']
    check('variant_product_fk',set(vf.product_key)<=set(pframe.product_key),'All variants reference collected listings')
    check('variant_count_reconciles',int(pframe.variant_count.sum())==len(vf),'Listing counts equal distinct variant rows')
    check('valid_price',vf.price.notna().all() and vf.price.ge(0).all(),'Unknown is not zero')
    check('endfield_excluded',not pframe.title.str.contains('endfield',case=False).any(),'Separate game scope')
    check('no_author_identifiers',not any(c.startswith('author_') for c in tables['skland_expanded_entities'].columns),'Only public content metadata and aggregates retained')
    for row in counts:check(row['dataset']+'_growth',row['before']+row['net_new']==row['after'],row['unit'])
    tables['data_quality_checks']=pd.DataFrame(checks)
    if not all(c['passed'] for c in checks):raise RuntimeError('Quality checks failed: '+str([c for c in checks if not c['passed']]))
    schema=[]
    for name,frame in tables.items():
        if not len(frame.columns):continue
        # Excel CSV formula escaping is confined to export; SQL retains source text exactly.
        export=frame.copy()
        for col in export.select_dtypes(include=['object','string']).columns:
            export[col]=export[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
        export.to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
        for col in frame.columns:schema.append({'table':name,'field':col,'dtype':str(frame[col].dtype),
           'non_null':int(frame[col].notna().sum()),'row_count':len(frame)})
    pd.DataFrame(schema).to_csv(out/'field_inventory.csv',index=False,encoding='utf-8-sig')
    db=report/'public_expansion.db'
    with sqlite3.connect(db) as con:
        for name,frame in tables.items():
            if len(frame.columns):frame.to_sql(name,con,index=False,if_exists='replace')
        con.executescript('''CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_product ON official_store_products(product_key);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_variant ON official_store_variants(variant_key);
        CREATE INDEX IF NOT EXISTS idx_exp_variant_product ON official_store_variants(product_key);
        CREATE INDEX IF NOT EXISTS idx_exp_operator ON operator_reference(operator);
        CREATE VIEW IF NOT EXISTS vw_official_product_supply AS SELECT p.source,p.currency,p.category,
            COUNT(DISTINCT p.product_key) AS product_listings,COUNT(v.variant_key) AS variants,
            SUM(CASE WHEN v.available=1 THEN 1 ELSE 0 END) AS available_variants
            FROM official_store_products p LEFT JOIN official_store_variants v USING(product_key)
            GROUP BY p.source,p.currency,p.category;''')
    payload={'run_date':args.run_date,'inventory':counts,'quality_checks':checks,
        'tables':{n:{'rows':len(f),'fields':len(f.columns)} for n,f in tables.items()},
        'skland_query_observations':len(sk_obs),'skland_rejected_nonmatching':sum(not r['query_title_match'] for r in sk_obs),
        'skland_baseline_raw_unique_hits':int(sk_old.item_id.nunique()),
        'merch_topic_unique_content':len({r['item_id'] for r in sk_obs if r['query_kind']=='merch_topic' and r['query_title_match']}),
        'official_news_explicit_title_matches':int(tables['official_news'].relevance.eq('explicit_title').sum()),
        'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.glob('*.json'))}}
    (report/'summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    notes=[f'# 公开数据扩充结果 {args.run_date}', '',
        '本轮新增官方商品供给、商品规格、官方资讯和角色参考主档，并扩展已有内容来源。统计按实体ID去重，商品与规格分层，搜索命中行和重复复采不算新增独立内容。', '',
        tables['data_expansion_inventory'].to_markdown(index=False),'',
        '## 商品供给结构（USD，按店铺分开）','',tables['official_store_category_summary'].to_markdown(index=False),'',
        '## 使用方式与范围','',
        '- 商品数据来自Yostar美区与GRYPHLINE官方商店；价格是采集时公开标价，不是中国市场实付价，不与人民币直接合并。',
        '- 两家店的同一实物商品尚未跨渠道合并。商品档案数表示店铺商品链接数；规格不是独立商品数。可售状态不是销量或库存数量。',
        '- 角色候选关联采用中英文显式名称规则，待人工复核；不用于自动分摊销量。',
        f"- 官方资讯共{len(tables['official_news'])}条关键词检索样本，其中{payload['official_news_explicit_title_matches']}条标题明确含明日方舟日文名称，其余标记待复核，不能全部视作周边上新。",
        '- 森空岛读取攻略站公开搜索Top20，只保留标题和聚合互动，不采集作者资料、不打开文章增加浏览量。周边关键词搜索结果不是已标注的购买评价。',
        '- 森空岛旧快照共有830个搜索命中ID，其中582个通过角色标题匹配；扩充沿用582个有效内容的口径，未把旧的不相关命中算成增长。',
        '- B站样本来自官方账号相关推荐图，存在推荐抽样偏差；合并档案保留各行原采集时间，不把不同时间的指标当同日全量。',
        '- 角色主档来源于社区维护的游戏数据仓库，并固定提交版本；用于名称治理，不代表用户需求或新增问卷。',
        '- 原淘宝84条快照（83个商品）、243份真实问卷和旧ERP均保留，本轮未生成真实订单或追加问卷。',
        '- 原首页与历史排名继续使用既有基线；新数据在扩充数据表及独立SQL库中可查询，尚未混入既有综合评分。', '',
        f'质量检查：{len(checks)}项通过。CSV见 data/processed/expansion/{args.run_date}/；SQL库见本目录 public_expansion.db。', '',
        '## 无网络复现','',f'`python scripts/build_public_expansion.py --run-date {args.run_date}`','',
        '## 下一轮采集','',
        '`python scripts/collect_public_expansion.py` 默认创建当天独立快照；同名日期已存在时停止，防止覆盖历史。',
    ]
    (report/'report.md').write_text('\n'.join(notes),encoding='utf-8')
    print(json.dumps({'inventory':counts,'checks_passed':len(checks),'db':str(db)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
