"""Order-grain reconciliation, including invalid/missing numeric inputs."""
import numpy as np
import pandas as pd


def reconcile_orders(headers: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    headers, lines = headers.copy(), lines.copy()
    header_fields = ['order_amount', 'discount_amount', 'shipping_fee', 'paid_amount']
    line_fields = ['quantity', 'unit_price', 'discount_amount']
    for frame, fields in [(headers, header_fields), (lines, line_fields)]:
        frame[fields] = frame[fields].apply(pd.to_numeric, errors='coerce')
    headers['invalid_header_values'] = (~np.isfinite(headers[header_fields]) | headers[header_fields].lt(0)).any(axis=1)
    headers['invalid_header_values'] |= headers['discount_amount'].gt(headers['order_amount'])
    headers['invalid_order_id'] = headers['order_id'].isna() | headers['order_id'].astype(str).str.strip().eq('')
    lines['line_amount'] = lines['quantity'] * lines['unit_price']
    lines['invalid_line_values'] = (~np.isfinite(lines[line_fields]) | lines[line_fields].lt(0)).any(axis=1)
    lines['invalid_line_values'] |= (lines['quantity'].le(0) | lines['quantity'].mod(1).ne(0)
                                     | lines['discount_amount'].gt(lines['line_amount'])
                                     | lines['order_line_id'].isna()
                                     | lines['order_line_id'].astype(str).str.strip().eq(''))
    grouped = lines.groupby('order_id').agg(line_amount=('line_amount', 'sum'),
        line_discount=('discount_amount', 'sum'), line_count=('order_id', 'size'),
        invalid_line_values=('invalid_line_values', 'any'))
    checked = headers.merge(grouped, how='left', on='order_id')
    checked['expected_paid'] = (checked['order_amount'] - checked['discount_amount'] + checked['shipping_fee']).where(checked['payment_status'].eq('paid'), 0)
    checked['gross_difference'] = (checked['order_amount'] - checked['line_amount']).round(2)
    checked['discount_difference'] = (checked['discount_amount'] - checked['line_discount']).round(2)
    checked['paid_difference'] = (checked['paid_amount'] - checked['expected_paid']).round(2)
    checked['missing_lines'] = checked['line_count'].isna()
    checked['duplicate_header'] = checked['order_id'].duplicated(keep=False)
    checked['duplicate_lines'] = checked['order_id'].isin(lines.loc[lines['order_line_id'].duplicated(keep=False), 'order_id'])
    checked['invalid_payment_status'] = ~checked['payment_status'].isin(['paid', 'cancelled'])
    differences = checked[['gross_difference', 'discount_difference', 'paid_difference']]
    flags = checked[['missing_lines', 'duplicate_header', 'duplicate_lines', 'invalid_payment_status',
                     'invalid_header_values', 'invalid_order_id', 'invalid_line_values']].eq(True)
    checked['passed'] = ~(differences.abs().gt(0.01).any(axis=1) | flags.any(axis=1))
    return checked
