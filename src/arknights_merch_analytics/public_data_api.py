"""Read-only access to the latest completed public-data expansion batch."""
from __future__ import annotations
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, Query
from fastapi.responses import Response

from .operations_tasks import excel_text


def register_public_data(app, root: Path):
    def latest():
        candidates=sorted((root/'reports/generated/public_expansion').glob('*/summary.json'),reverse=True)
        candidates=[p for p in candidates if re.fullmatch(r'\d{4}-\d{2}-\d{2}',p.parent.name)
                    and (p.parent/'public_expansion.db').exists()]
        if not candidates:raise HTTPException(503,'尚未生成公开数据扩充批次')
        path=candidates[0]
        return path.parent,json.loads(path.read_text(encoding='utf-8'))

    def read(dataset, q):
        folder,summary=latest()
        if dataset not in summary['tables'] or not re.fullmatch(r'[a-z_]+',dataset):
            raise HTTPException(404,'未知扩充数据表')
        with sqlite3.connect((folder/'public_expansion.db').as_uri()+'?mode=ro',uri=True) as con:
            frame=pd.read_sql_query(f'SELECT * FROM "{dataset}"',con)
        if q:
            frame=frame.loc[frame.astype(str).apply(lambda c:c.str.contains(q,case=False,regex=False)).any(axis=1)]
        return frame,summary

    @app.get('/api/public-expansion')
    def summary():
        _,result=latest()
        return {**result,'scope':'public_observations_and_reference_data',
                'included_in_original_rankings':False,
                'notes':['海外商品按店铺和USD统计，规格与商品分层计数',
                         '角色参考数据不是用户需求，搜索内容不是购买评价',
                         '复采、查询重复命中和派生关联不计入净新增实体']}

    @app.get('/api/public-expansion/data/{dataset}')
    def data(dataset: str,q: str='',limit: int=Query(100,ge=1,le=1000),offset: int=Query(0,ge=0)):
        frame,result=read(dataset,q)
        return {'run_date':result['run_date'],'dataset':dataset,'total':len(frame),
                'items':json.loads(frame.iloc[offset:offset+limit].to_json(orient='records',force_ascii=False))}

    @app.get('/api/public-expansion/export/{dataset}')
    def export(dataset: str,q: str=''):
        frame,result=read(dataset,q)
        for col in frame.select_dtypes(include=['object','string']).columns:
            frame[col]=frame[col].map(excel_text)
        body='\ufeff'+frame.to_csv(index=False)
        return Response(body,media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition':f'attachment; filename="{dataset}_{result["run_date"]}.csv"'})
