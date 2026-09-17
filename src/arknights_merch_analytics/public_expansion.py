"""Public market observations; distinct products, variants and content stay separate."""
from __future__ import annotations

import html
import json
import re
import time
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .bilibili_archive import classify_bilibili_content
from .metrics import EXCLUDED_OPERATOR_ENTITIES
from .skland import is_operator_title_match

STORES = {
    'yostar_us': ('https://us.yostar.store', 'US', 'USD'),
    'gryphline_global': ('https://store.gryphline.com', 'Global', 'USD'),
}
MERCH_QUERIES = ['周边', '谷子', '吧唧', '徽章', '毛绒', '手办', '亚克力', '挂件', '抱枕',
                 '痛包', '开箱', '晒谷', '品控', '售后', '预售', '补款', '物流', '联名',
                 '音律联觉', '嘉年华', '设定集', '美术集', '摆件', '色纸']


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class PublicClient:
    """Low-frequency unauthenticated access; stop on denial instead of retrying it."""
    def __init__(self, source: str, interval: float = 1.2):
        self.source, self.interval = source, interval
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'ArknightsAnalytics/0.3 (public research snapshot)'
        self.requests: list[dict] = []
        self.last = 0.0

    def get(self, url: str, params=None):
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        response = self.session.get(url, params=params, timeout=25)
        self.requests.append({'source': self.source, 'url': response.url, 'observed_at': now(),
                              'http_status': response.status_code,
                              'response_sha256': hashlib.sha256(response.content).hexdigest()})
        response.raise_for_status()
        return response


def money(value):
    if value is None or value == '':
        return None
    try:
        amount = Decimal(str(value))
        return float(amount) if amount.is_finite() and amount >= 0 else None
    except InvalidOperation:
        return None


def classify_product(title: str, product_type: str) -> str:
    text = (title + ' ' + product_type).lower().replace('非亚克力', '')
    def matches(term):
        # English substrings such as 'pin' in 'camping' are not product categories.
        if term.isascii():
            return re.search(r'(?<![a-z])' + re.escape(term) + r'(?:s|es)?(?![a-z])', text) is not None
        return term in text
    for terms, category in [
        (('blind box',), '盲盒'),
        (('plush', 'plushie', 'ぬい', '毛绒'), '毛绒玩偶'),
        (('acrylic', 'アクリル', '亚克力'), '亚克力制品'),
        (('pin', 'badge', '徽章'), '徽章'),
        (('figure', 'statue', 'complete model', '手办'), '手办模玩'),
        (('artbook', 'art book', 'artworks', 'compendium', 'comic', 'illustration'), '出版物'),
        (('t-shirt', 'apparel', 'hoodie', 'hat', 'shirt', 'cap'), '服饰'),
        (('lucky bag',), '福袋'),
        (('bag', 'backpack', 'pouch', 'purse', 'card holder'), '箱包'),
        (('charm', 'keychain', 'key tag'), '挂件'),
        (('necklace', 'bracelet', 'brooch'), '饰品'),
        (('glass', 'cup', 'mug', 'drinkware', 'teacup', 'bottle'), '杯具'),
        (('sticker', 'tape', 'sticky note', 'postcard', 'post card', 'laser ticket'), '文具与纸品'),
        (('painting', 'print', 'poster', 'scroll'), '装饰画与挂画'),
        (('calendar', 'mouse', 'desk', 'light', 'lighting', 'decor', 'tableware', 'table mat', 'tablemat',
          'coaster', 'magnet', 'blanket', 'pillow', 'cushion', 'sofa'), '桌面与生活用品'),
        (('board game',), '桌游'),
        (('commemoration', 'collector', 'gift box', 'anniversary box', 'kit'), '纪念礼盒'),
    ]:
        if any(matches(term) for term in terms):
            return category
    return '其他待复核'


def normalize_products(payload: dict, store: str, observed_at: str) -> tuple[list, list]:
    base, market, currency = STORES[store]
    products, variants = {}, {}
    for item in payload.get('products', []):
        title = html.unescape(str(item.get('title') or ''))
        tags = item.get('tags') or []
        if isinstance(tags, str):
            tags = tags.split(',')
        # Collection membership plus explicit title/tag check prevents Endfield leakage.
        scope = ' '.join([title, *map(str, tags)]).lower()
        if 'arknights' not in scope or 'endfield' in scope:
            continue
        pid = str(item['id'])
        pkey = store + ':' + pid
        rows = []
        for variant in item.get('variants', []):
            vid = str(variant['id'])
            row = {'variant_key': store + ':' + vid, 'product_key': pkey,
                   'source': store, 'market': market, 'currency': currency,
                   'product_id': pid, 'variant_id': vid,
                   'variant_title': variant.get('title'), 'public_sku': variant.get('sku'),
                   'option1': variant.get('option1'), 'option2': variant.get('option2'),
                   'option3': variant.get('option3'), 'price': money(variant.get('price')),
                   'compare_at_price': money(variant.get('compare_at_price')),
                   'available': variant.get('available') if isinstance(variant.get('available'), bool) else None,
                   'requires_shipping': variant.get('requires_shipping'),
                   'listed_weight_grams': variant.get('grams'),
                   'observed_at': observed_at, 'is_simulated': False,
                   'source_url': f"{base}/products/{item['handle']}?variant={vid}"}
            variants[row['variant_key']] = row
            rows.append(row)
        rows = list({r['variant_key']: r for r in rows}.values())
        prices = [r['price'] for r in rows if r['price'] is not None]
        products[pkey] = {'product_key': pkey, 'source': store, 'market': market,
                         'currency': currency, 'product_id': pid, 'title': title,
                         'source_product_type': item.get('product_type'),
                         'category': classify_product(title, str(item.get('product_type') or '')),
                         'category_method': 'title_and_store_type_rule_requires_review',
                         'vendor': item.get('vendor'), 'tags': json.dumps(tags, ensure_ascii=False),
                         'option_names': json.dumps([o.get('name') for o in item.get('options', [])], ensure_ascii=False),
                         'variant_count': len({r['variant_key'] for r in rows}),
                         'price_min': min(prices) if prices else None,
                         'price_max': max(prices) if prices else None,
                         'available_variant_count': sum(r['available'] is True for r in rows),
                         'unknown_availability_count': sum(r['available'] is None for r in rows),
                         'published_at': item.get('published_at'), 'source_updated_at': item.get('updated_at'),
                         'observed_at': observed_at, 'is_simulated': False,
                         'rights_basis': 'publisher_official_store',
                         'source_url': f"{base}/products/{item['handle']}"}
    return list(products.values()), list(variants.values())


def operator_metadata(table: dict, source_url: str, commit: str, observed_at: str) -> list[dict]:
    rows = []
    for oid, item in table.items():
        if not oid.startswith('char_') or item.get('isNotObtainable') is not False:
            continue
        rows.append({'operator_id': oid, 'operator': item.get('name'), 'english_name': item.get('appellation'),
                     'profession': item.get('profession'), 'subprofession': item.get('subProfessionId'),
                     'rarity': item.get('rarity'), 'nation_id': item.get('nationId'),
                     'group_id': item.get('groupId'), 'team_id': item.get('teamId'),
                     'source_kind': 'community_maintained_game_metadata', 'source_url': source_url,
                     'source_commit': commit, 'observed_at': observed_at, 'is_simulated': False})
    return rows


def collect_bili(root: Path, raw: Path, limit: int = 100) -> dict:
    client = PublicClient('bilibili')
    baseline = json.loads((root/'data/public/bilibili_official_archive.json').read_text(encoding='utf-8'))
    ordered = sorted(baseline, key=lambda x:x.get('published_at',''), reverse=True)
    # Start across publication years rather than visiting only the latest recommendation cluster.
    queue = [r['bvid'] for r in ordered[:20]] + [r['bvid'] for r in ordered[20::max(1,len(ordered)//60)]]
    queue = list(dict.fromkeys(queue)); visited=set(); observed={}; status='request_budget_reached'; error=''
    try:
        for step in range(limit):
            if not queue:status='queue_exhausted';break
            seed=queue.pop(0)
            if seed in visited:continue
            visited.add(seed)
            response=client.get('https://api.bilibili.com/x/web-interface/archive/related', {'bvid':seed})
            payload=response.json()
            if payload.get('code') != 0:raise RuntimeError(f"API code {payload.get('code')}")
            stamp=now()
            for item in payload.get('data') or []:
                if (item.get('owner') or {}).get('mid') != 161775300:continue
                title=str(item.get('title') or '')
                if any(excluded in title for excluded in EXCLUDED_OPERATOR_ENTITIES):continue
                bvid=item.get('bvid')
                if not bvid or not item.get('pubdate'):continue
                stat=item.get('stat') or {}
                observed[bvid]={'bvid':bvid,'title':title,'owner_mid':161775300,
                   'published_at':datetime.fromtimestamp(item['pubdate'],timezone.utc).isoformat(),
                   **{k:stat.get(k) for k in ('view','like','coin','favorite','share','reply','danmaku')},
                   'content_type':classify_bilibili_content(title),'source_url':f'https://www.bilibili.com/video/{bvid}',
                   'collected_at':stamp,'source_type':'official_public_aggregate','is_simulated':False}
                if bvid not in visited and bvid not in queue:queue.append(bvid)
            if step%20==0:
                write_json(raw/'bilibili_observations.json',list(observed.values()))
                print(f'Bilibili requests={step+1} unique_observed={len(observed)}',flush=True)
    except (requests.RequestException,ValueError,RuntimeError) as exc:
        status='stopped_on_source_error';error=str(exc)
    write_json(raw/'bilibili_observations.json',list(observed.values()))
    result={'status':status,'error':error,'requests':client.requests}
    write_json(raw/'bilibili_manifest.json',result)
    return result


def collect_skland(root: Path, raw: Path, operators: list[dict], limit: int = 128) -> dict:
    client=PublicClient('skland',1.0)
    baseline=pd.read_csv(root/'data/public/skland_strategy_operator_search_snapshot.csv')
    existing=set(baseline['query_operator'].dropna().astype(str))
    choices=[r['operator'] for r in sorted(operators,key=lambda r:r['rarity'] or '',reverse=True)
             if r['operator'] not in existing and len(r['operator'])>1][:40]
    queries=[(q,'merch_topic') for q in MERCH_QUERIES]+[(q,'operator') for q in choices]
    pool=[r['operator'] for r in operators]; observations=[]; status='query_budget_complete';error=''
    try:
        for query,kind in queries:
            for sort in ('hot','time'):
                if len(client.requests)>=limit:break
                response=client.get('https://strategy.skland.com/api/resources/items',
                                    {'keyword':query,'current':1,'pageSize':20,'sort':sort})
                payload=response.json()
                if payload.get('code') != 0:raise RuntimeError(f"API code {payload.get('code')}")
                stamp=now()
                for rank,entry in enumerate((payload.get('data') or {}).get('list') or [],1):
                    item=entry.get('item') or {}; stats=entry.get('itemRts') or {}
                    iid=str(item.get('id') or '')
                    if not iid:continue
                    title=str(entry.get('title') or '')
                    matched=(is_operator_title_match(query,title,pool) if kind=='operator' else query.casefold() in title.casefold())
                    observations.append({'item_id':iid,'query':query,'query_kind':kind,'sort':sort,
                        'result_rank':rank,'title':title,'query_title_match':matched,
                        'posted_at':datetime.fromtimestamp(entry['postedAt']/1000,timezone.utc).isoformat() if entry.get('postedAt') else None,
                        **{k:int(stats[k]) if stats.get(k) is not None else None for k in ('viewed','liked','collected','reposted','commented')},
                        'source_url':f'https://www.skland.com/article?id={iid}', 'observed_at':stamp,
                        'scope':'strategy_public_search_top20','is_simulated':False})
                if len(client.requests)%20==0:
                    write_json(raw/'skland_search_observations.json',observations)
                    print(f'Skland requests={len(client.requests)} observations={len(observations)}',flush=True)
    except (requests.RequestException,ValueError,RuntimeError) as exc:
        status='stopped_on_source_error';error=str(exc)
    write_json(raw/'skland_search_observations.json',observations)
    result={'status':status,'error':error,'queries':queries,'requests':client.requests}
    write_json(raw/'skland_manifest.json',result)
    return result


def latest_union(old: list[dict], new: list[dict], key: str) -> list[dict]:
    """Callers supply chronological batches; identity, not row count, defines size."""
    records={str(r[key]):dict(r) for r in old if r.get(key) is not None}
    for row in new:
        if row.get(key) is not None:records[str(row[key])]={**records.get(str(row[key]),{}),**row}
    return list(records.values())


def skland_entities(observations: list[dict]) -> list[dict]:
    accepted=[r for r in observations if r.get('query_title_match') is True]
    grouped={}
    for r in accepted:
        entry=grouped.setdefault(r['item_id'],{'row':{},'queries':set(),'kinds':set()})
        entry['row']={k:v for k,v in r.items() if k not in ('query','query_kind','sort','result_rank','query_title_match')}
        entry['queries'].add(r['query']);entry['kinds'].add(r['query_kind'])
    return [{**e['row'],'matched_queries':json.dumps(sorted(e['queries']),ensure_ascii=False),
             'query_kinds':','.join(sorted(e['kinds']))} for e in grouped.values()]
