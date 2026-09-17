from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arknights_merch_analytics.public_expansion import PublicClient,STORES,now,write_json,operator_metadata,collect_bili,collect_skland

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-date',default=datetime.now().date().isoformat())
    parser.add_argument('--bili-requests',type=int,default=100)
    parser.add_argument('--skland-requests',type=int,default=128)
    args=parser.parse_args()
    datetime.strptime(args.run_date,'%Y-%m-%d')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',args.run_date):parser.error('run-date must use YYYY-MM-DD')
    if args.bili_requests < 0 or args.skland_requests < 0:parser.error('request budgets must be nonnegative')
    raw=ROOT/'data/public/expansion'/args.run_date
    raw.mkdir(parents=True,exist_ok=False)
    client=PublicClient('official_catalogs_and_metadata')
    results={};currency_evidence=[]
    for name,(base,_,expected_currency) in STORES.items():
        products=[];seen=set()
        try:
            homepage=client.get(base)
            currency_match=re.search(r'Shopify\.currency\s*=\s*(\{[^;]+\})',homepage.text)
            currency=json.loads(currency_match.group(1)).get('active') if currency_match else None
            currency_evidence.append({'source_url':homepage.url,'observed_at':now(),
                'http_status':homepage.status_code,'currency':currency,
                'evidence':[currency_match.group(0)] if currency_match else []})
            if currency!=expected_currency:raise ValueError(f'Currency requires review: {currency!r}')
            for page in range(1,6):
                payload=client.get(base+'/collections/arknights/products.json',{'limit':250,'page':page}).json()
                batch=payload.get('products',[])
                unseen=[p for p in batch if str(p['id']) not in seen]
                products.extend(unseen);seen.update(str(p['id']) for p in unseen)
                if len(batch)<250 or not unseen:break
            write_json(raw/(name+'.json'),{'observed_at':now(),'products':products})
            results[name]={'products':len(products),'status':'collected'}
        except Exception as exc:results[name]={'status':'failed','error':str(exc)}
        print(name,results[name],flush=True)
    write_json(raw/'currency_evidence.json',currency_evidence)
    try:
        response=client.get('https://plus.yostar.co.jp/wp-json/wp/v2/posts',
             {'search':'アークナイツ','per_page':100,'_fields':'id,date,link,title,categories'})
        posts=response.json()
        write_json(raw/'yostar_news.json',{'observed_at':now(),'posts':posts,'total_pages':response.headers.get('X-WP-TotalPages')})
        results['yostar_news']={'status':'collected','records':len(posts)}
    except Exception as exc:results['yostar_news']={'status':'failed','error':str(exc)}
    operators=[]
    try:
        commit=client.get('https://api.github.com/repos/Kengxxiao/ArknightsGameData/commits/master').json()
        sha=commit['sha']
        source=f'https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/{sha}/zh_CN/gamedata/excel/character_table.json'
        table=client.get(source).json()
        operators=operator_metadata(table,source,sha,now())
        write_json(raw/'operator_metadata.json',operators)
        write_json(raw/'gamedata_commit.json',{'sha':sha,'commit_date':commit['commit']['committer']['date'],'source_url':source})
        results['operators']={'status':'collected','records':len(operators)}
    except Exception as exc:results['operators']={'status':'failed','error':str(exc)}
    # Preserve the new mirror batch separately from the old observation snapshot.
    try:
        from arknights_merch_analytics.collector import collect_weibo_sina_mirror
        rows=collect_weibo_sina_mirror('6279793937',raw/'weibo_observations.json')
        results['weibo']={'status':'collected','records':len(rows)}
    except Exception as exc:results['weibo']={'status':'failed','error':str(exc)}
    write_json(raw/'source_manifest.json',{'observed_at':now(),'results':results,'requests':client.requests})
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={'bilibili':pool.submit(collect_bili,ROOT,raw,args.bili_requests),
              'skland':pool.submit(collect_skland,ROOT,raw,operators,args.skland_requests)}
        for name,job in jobs.items():
            result=job.result();print(name,result['status'],len(result['requests']),flush=True)
    print('Saved source observations:',raw,flush=True)

if __name__=='__main__':main()
