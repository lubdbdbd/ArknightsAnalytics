"""Reproduce the historical refund defect and validate regenerated data in memory."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from arknights_merch_analytics.erp import simulate_erp_operations
from arknights_merch_analytics.erp_checks import TABLES, build_erp_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source_paths = {key:ROOT/'data/processed'/f'{value[0]}.csv' for key,value in TABLES.items()}
    source = {key:pd.read_csv(path) for key,path in source_paths.items()}
    before = build_erp_checks(source)
    corrected = simulate_erp_operations(pd.read_csv(ROOT/'data/processed/erp_mock.csv'),
        pd.read_csv(ROOT/'data/survey/anonymous_responses_243.csv'),
        pd.read_csv(ROOT/'data/survey/anonymous_operator_rankings_243.csv'),
        days=90, order_count=6000, seed=20260903)
    # Fail rather than silently compare a different population or changed seed.
    for key in ['sku','headers','lines','inventory','purchases']:
        pd.testing.assert_frame_equal(source[key].fillna(''), corrected[TABLES[key][0]].fillna(''), check_dtype=False)
    old, new = source['aftersales'], corrected['erp_after_sales']
    pd.testing.assert_frame_equal(old.drop(columns='refund_amount'), new.drop(columns='refund_amount'), check_dtype=False)
    after = build_erp_checks({key:corrected[meta[0]] for key,meta in TABLES.items()})
    assert after['summary']['error_count'] == 0, after['summary']
    changes = old[['case_id','order_id','sku_id','refund_amount']].rename(columns={'refund_amount':'old_refund'})
    changes = changes.merge(new[['case_id','refund_amount']].rename(columns={'refund_amount':'corrected_refund'}), on='case_id',validate='one_to_one')
    changes['difference'] = (changes['old_refund']-changes['corrected_refund']).round(2)
    changes = changes.loc[changes['difference'].ne(0)]
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'source_kind':'模拟ERP，旧快照不改写；修正生成器使用相同输入与随机种子在内存重建',
              'before':before['summary'],'after':after['summary'],'as_of':before['as_of'],
              'corrected_case_count':len(changes),'refund_difference':round(changes['difference'].sum(),2),
              'case_population_unchanged':True,
              'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths.values()}}
    (args.output/'refund_fix_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    changes.to_csv(args.output/'refund_changes.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(before['issues']).to_csv(args.output/'historical_check_issues.csv',index=False,encoding='utf-8-sig')
    (args.output/'refund_fix_verification.md').write_text(
        '# ERP退款口径修正验证\n\n'
        f"同一组模拟数据输入、90天周期、6000张订单和随机种子20260903。SKU、订单头、明细、库存、采购及售后非金额字段均逐项比对一致。\n\n"
        f"- 历史快照：{before['summary']['error_count']}项数据异常、{before['summary']['warning_count']}项跟进提醒。\n"
        f"- 修正生成结果：{after['summary']['error_count']}项数据异常、{after['summary']['warning_count']}项跟进提醒。\n"
        f"- 按优惠后商品净额分摊退款，{len(changes)}条售后金额发生变化，合计差额{report['refund_difference']:,.2f}元。该差额属于模拟口径修正，不是追回款项或经营收益。\n\n"
        '原逻辑按原价×件数退款，忽略订单优惠。修正为商品明细净收入×退款件数÷购买件数；换货为0，不含运费退款。\n\n'
        '原始历史CSV保持原样，方便复核缺陷。当前看板仍使用该历史快照；本文的修正结果来自独立内存重建，不代表看板金额已刷新。退款变化会影响净销售和毛利，正式替换快照时应同步刷新依赖报表。\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
