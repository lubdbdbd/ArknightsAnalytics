"""Read-only ERP checks with explicit grain, source rows and snapshot date."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .erp_reconciliation import reconcile_orders

TABLES = {
    'sku': ('erp_sku_master', '商品主档', ['sku_id']),
    'headers': ('erp_order_headers', '订单', ['order_id']),
    'lines': ('erp_order_lines', '订单明细', ['order_line_id']),
    'inventory': ('erp_inventory_daily', '库存', ['sku_id', 'snapshot_date']),
    'purchases': ('erp_purchase_orders', '采购', ['po_id']),
    'aftersales': ('erp_after_sales', '售后', ['case_id']),
}
NUMBERS = {
    'headers': ['order_amount', 'discount_amount', 'shipping_fee', 'paid_amount'],
    'lines': ['quantity', 'unit_price', 'discount_amount', 'net_revenue'],
    'inventory': ['opening_stock', 'inbound_units', 'sold_units', 'restockable_return_units',
                  'closing_stock', 'locked_stock', 'available_stock'],
    'purchases': ['quantity_ordered', 'quantity_received', 'unit_purchase_cost', 'purchase_amount'],
    'aftersales': ['units', 'refund_amount'],
}
EXTRA = {'sku': [], 'headers': ['payment_status'], 'lines': ['order_id', 'sku_id'],
         'inventory': [], 'purchases': ['sku_id', 'order_date', 'expected_date', 'received_date', 'purchase_status'],
         'aftersales': ['order_id', 'sku_id', 'case_status']}

FIELD_LABELS = dict(zip(
    ['sku_id','order_id','order_line_id','case_id','po_id','snapshot_date','order_amount','paid_amount',
     'gross_difference','discount_difference','paid_difference','invalid_header_values','invalid_line_values','missing_lines',
     'discount_amount','shipping_fee','quantity','unit_price','net_revenue','opening_stock','inbound_units','sold_units',
     'restockable_return_units','closing_stock','locked_stock','available_stock','_previous_closing',
     'quantity_ordered','quantity_received','unit_purchase_cost','purchase_amount','purchase_status',
     'order_date','expected_date','received_date','units','refund_amount','_closed_refund'],
    ['SKU','订单号','订单明细号','售后单号','采购单号','快照日期','商品金额','实付金额',
     '商品额差值','优惠差值','实付差值','表头数值无效','明细数值无效','缺失明细',
     '优惠金额','运费','购买件数','商品单价','商品净收入','期初库存','入库件数','实际售出',
     '可售退货入库','期末库存','锁定库存','可售库存','上日期末库存',
     '订购件数','实收件数','单位采购成本','采购金额','采购状态',
     '下单日期','预计到货','实际到货','售后件数','退款金额','累计已关闭退款']))


def build_erp_checks(source: dict[str, pd.DataFrame], scenario: str = 'snapshot') -> dict:
    if scenario not in {'snapshot', 'demo'}:
        raise ValueError('未知核对场景')
    tables = {key: source[key].reset_index(drop=True).copy(deep=True) for key in TABLES}
    for key, (_, _, identity) in TABLES.items():
        missing = set(identity + NUMBERS.get(key, []) + EXTRA[key]) - set(tables[key].columns)
        if missing:
            raise ValueError(f'{TABLES[key][0]} 缺少字段：{", ".join(sorted(missing))}')
    injections = []
    if scenario == 'demo':
        for key, field, change in [('headers', 'paid_amount', lambda row: float(row['paid_amount']) + 1),
                                    ('inventory', 'closing_stock', lambda row: float(row['closing_stock']) + 2),
                                    ('purchases', 'quantity_received', lambda row: float(row['quantity_ordered']) + 1),
                                    ('aftersales', 'order_id', lambda row: 'DEMO-MISSING-ORDER')]:
            if not tables[key].empty:
                before = str(tables[key].at[0, field])
                value = change(tables[key].iloc[0])
                tables[key].at[0, field] = value
                injections.append({'table': TABLES[key][0], 'source_row': 2, 'field': field, 'before': before, 'after': str(value)})
    issues, rules = [], []

    def add(code, title, key, frame, bad, expected, action, fields, severity='error'):
        mask = pd.Series(bad, index=frame.index).fillna(False).astype(bool)
        count = int(mask.sum())
        rules.append({'code': code, 'title': title, 'domain': TABLES[key][1], 'checked_count': len(frame),
                      'issue_count': count, 'severity': severity,
                      'state': '无可核对数据' if frame.empty else ('待复核' if count else '通过'),
                      'expected': expected})
        for index, row in frame.loc[mask].iterrows():
            record = ' / '.join(str(row.get(field, '')) for field in TABLES[key][2])
            source_row = int(row.get('_source_row', index + 2))
            raw = f'{code}:{record}:{source_row}'
            issues.append({'issue_id': hashlib.sha256(raw.encode()).hexdigest()[:16], 'rule_code': code,
                'rule': title, 'domain': TABLES[key][1], 'severity': severity,
                'source_table': TABLES[key][0], 'source_row': source_row, 'record_id': record,
                'observed': '；'.join(f'{FIELD_LABELS.get(field, field)}={row.get(field, "")}' for field in fields),
                'expected': expected, 'action': action})

    for key, (_, _, identity) in TABLES.items():
        frame = tables[key]
        missing_id = frame[identity].isna().any(axis=1) | frame[identity].astype(str).apply(lambda s: s.str.strip().eq('')).any(axis=1)
        add(f'{key}_identity', '主键必填与唯一', key, frame, missing_id | frame.duplicated(identity, keep=False),
            '主键非空且唯一；库存按SKU与日期联合唯一', '查验原始记录，确认重复原因后人工修订，不直接删除整行。', identity)
        if key in NUMBERS:
            fields = NUMBERS[key]
            numeric = frame[fields].apply(pd.to_numeric, errors='coerce')
            bad = (~np.isfinite(numeric) | numeric.lt(0)).any(axis=1)
            add(f'{key}_numbers', '必需数值有效且非负', key, frame, bad,
                '必需字段为有限非负数；空白不能作为0通过核对', '回查金额或数量来源，补全后重新核对。', fields)
            frame[fields] = numeric

    sku, headers, lines, inventory, purchases, aftersales = (tables[key] for key in TABLES)
    for key in ['lines', 'inventory', 'purchases', 'aftersales']:
        frame = tables[key]
        add(f'{key}_sku', 'SKU主档关联', key, frame, ~frame['sku_id'].isin(sku['sku_id'].dropna()),
            'SKU必须能关联原始ERP商品主档', '核对SKU编码，确认主档是否漏建或业务记录是否录错。', ['sku_id'])
    for key in ['lines', 'aftersales']:
        frame = tables[key]
        add(f'{key}_order', '订单主档关联', key, frame, ~frame['order_id'].isin(headers['order_id'].dropna()),
            '关联订单必须存在', '查验订单号及导出范围，补齐关联记录后再汇总。', ['order_id'])
    checked = reconcile_orders(headers, lines)
    add('order_reconciliation', '订单头与明细金额核对', 'headers', checked, ~checked['passed'],
        '商品额、优惠、支付金额差异不超过0.01元，且无缺失、重复或非法输入',
        '按订单号检查数量×单价、优惠分摊、运费及支付状态；先预聚合明细再与订单头核对。',
        ['order_amount', 'paid_amount', 'gross_difference', 'discount_difference', 'paid_difference', 'invalid_header_values', 'invalid_line_values', 'missing_lines'])
    line_expected = lines['quantity'] * lines['unit_price'] - lines['discount_amount']
    add('line_net', '明细净收入计算', 'lines', lines,
        (lines['net_revenue']-line_expected).round(2).abs().gt(.01) | lines['quantity'].le(0) | lines['quantity'].mod(1).ne(0),
        '明细净收入=数量×单价−优惠；件数为正整数', '检查单价、件数和优惠分摊，不把运费混入商品净收入。', NUMBERS['lines'])

    expected_stock = inventory['opening_stock'] + inventory['inbound_units'] - inventory['sold_units'] + inventory['restockable_return_units']
    add('inventory_balance', '库存日流水平衡', 'inventory', inventory, inventory['closing_stock'].ne(expected_stock),
        '期末=期初+采购入库−实际售出+可二次销售退货；不可售退货不重复扣减',
        '核对当日入库、实际出库及退货入库；区分需求件数与实际售出件数。',
        ['opening_stock','inbound_units','sold_units','restockable_return_units','closing_stock'])
    add('inventory_available', '可售与锁定库存', 'inventory', inventory,
        inventory['locked_stock'].gt(inventory['closing_stock']) | inventory['available_stock'].ne(inventory['closing_stock']-inventory['locked_stock']),
        '可售库存=期末库存−锁定库存，锁定不能超过期末', '核对订单占用与释放记录，再计算可售库存。', ['closing_stock','locked_stock','available_stock'])
    inventory['_date'] = pd.to_datetime(inventory['snapshot_date'], errors='coerce')
    add('inventory_date', '库存快照日期有效', 'inventory', inventory, inventory['_date'].isna(),
        '每条库存记录应有有效日期', '修正日期格式后再判断连续性和采购逾期。', ['snapshot_date'])
    ordered = inventory.assign(_source_row=inventory.index+2).sort_values(['sku_id','_date'])
    previous = ordered.groupby('sku_id')['closing_stock'].shift()
    previous_date = ordered.groupby('sku_id')['_date'].shift()
    contiguous = ordered['_date'].sub(previous_date).dt.days.eq(1)
    ordered['_previous_closing'] = previous
    add('inventory_continuity', '相邻日期库存结转', 'inventory', ordered.loc[contiguous],
        ordered.loc[contiguous, 'opening_stock'].ne(previous.loc[contiguous]),
        '相邻自然日的期初等于上日期末', '检查跨日调整及补录记录，不用覆盖期末数的方式强行对平。', ['opening_stock','_previous_closing'])
    gaps = previous_date.notna() & ordered['_date'].sub(previous_date).dt.days.gt(1)
    add('inventory_gaps', '库存快照缺日提醒', 'inventory', ordered, gaps,
        '日快照应连续；跨缺失日期不判断结转通过', '补齐缺失日快照，或注明停采原因。', ['snapshot_date'], severity='warning')

    add('purchase_quantity', '采购订购与实收数量', 'purchases', purchases,
        purchases['quantity_received'].gt(purchases['quantity_ordered']) | purchases['quantity_ordered'].le(0)
        | purchases[['quantity_ordered','quantity_received']].mod(1).ne(0).any(axis=1),
        '订购为正整数，实收为非负整数且不超过订购', '按采购单核对分批收货、退供及重复入库记录。', ['quantity_ordered','quantity_received'])
    add('purchase_amount', '采购金额计算', 'purchases', purchases,
        (purchases['purchase_amount']-purchases['quantity_ordered']*purchases['unit_purchase_cost']).round(2).abs().gt(.01),
        '采购金额=订购量×单位采购成本，容差0.01元', '区分订购金额与已收货金额，核对成本及数量口径。', NUMBERS['purchases'])
    dates = {field: pd.to_datetime(purchases[field], errors='coerce') for field in ['order_date','expected_date','received_date']}
    received = purchases['purchase_status'].eq('received')
    add('purchase_dates', '采购状态与日期', 'purchases', purchases,
        dates['order_date'].isna() | dates['expected_date'].isna() | dates['expected_date'].lt(dates['order_date'])
        | (received & (dates['received_date'].isna() | purchases['quantity_received'].le(0)))
        | dates['received_date'].lt(dates['order_date']) | ~purchases['purchase_status'].isin(['open','received']),
        '预计到货不早于下单；已收货需填写有效收货日期及数量', '核对采购状态与收货凭证；部分收货是否结案需要人工确认。', ['purchase_status','order_date','expected_date','received_date'])
    as_of = inventory['_date'].max()
    add('purchase_overdue', '期末采购逾期提醒', 'purchases', purchases if pd.notna(as_of) else purchases.iloc[0:0],
        purchases['purchase_status'].eq('open') & dates['expected_date'].lt(as_of) & purchases['quantity_received'].lt(purchases['quantity_ordered']) if pd.notna(as_of) else pd.Series(False, index=purchases.index),
        '以库存快照末日判断逾期，不使用电脑当前日期；逾期属于跟进提醒', '联系供应商确认剩余数量和预计到货日，再复核补货建议中的在途数量。', ['expected_date','quantity_ordered','quantity_received'], severity='warning')
    pairs = pd.MultiIndex.from_frame(lines[['order_id','sku_id']].drop_duplicates())
    add('aftersales_pair', '售后订单与SKU组合', 'aftersales', aftersales,
        ~pd.MultiIndex.from_frame(aftersales[['order_id','sku_id']]).isin(pairs),
        '订单和SKU必须同时对应同一条销售明细', '核对售后单的订单及SKU，避免仅分别存在却错误关联。', ['order_id','sku_id'])
    refund = aftersales.loc[aftersales['case_status'].eq('closed')].groupby('order_id')['refund_amount'].sum(min_count=1)
    refund_check = headers.assign(_closed_refund=headers['order_id'].map(refund).fillna(0))
    add('refund_cap', '已关闭退款与订单实付', 'headers', refund_check,
        (refund_check['_closed_refund']-refund_check['paid_amount']).round(2).gt(.01),
        '先按订单汇总已关闭售后，再与订单头核对；累计退款不得超过实付',
        '检查重复退款、订单归属和售后关闭状态；待处理售后不作为已完成退款。', ['paid_amount','_closed_refund'])
    result = {'scenario': scenario, 'is_simulated': True,
              'scope': '异常演练：仅修改内存副本' if scenario=='demo' else '原始模拟ERP快照：只读核对',
              'as_of': as_of.date().isoformat() if pd.notna(as_of) else None,
              'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'source_counts': {TABLES[key][0]: len(value) for key,value in source.items()},
              'rules': rules, 'issues': issues, 'injections': injections,
              'summary': {'rule_count': len(rules), 'error_count': sum(i['severity']=='error' for i in issues),
                          'warning_count': sum(i['severity']=='warning' for i in issues),
                          'affected_records': len({(i['source_table'],i['source_row']) for i in issues})},
              'limitations': ['异常数量按规则命中计，同一源记录可命中多项；源行号从CSV表头后的第2行开始。',
                  '采购逾期以库存末日为准；没有有效库存日期时不能判断逾期。',
                  '仅核对列出的内部数据规则，未接入支付账单、仓库实盘或供应商凭证。']}
    return json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
