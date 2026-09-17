from __future__ import annotations

import pandas as pd


def build_operations_brief(public: pd.DataFrame, channels: pd.DataFrame,
                           categories: pd.DataFrame, barriers: pd.DataFrame,
                           replenishment: pd.DataFrame) -> dict:
    pending = int(public['verification_status'].eq('pending').sum())
    maintenance = int(public['maintenance_priority'].ne('P2-可入库').sum())
    urgent = replenishment[replenishment['replenishment_priority'].str.startswith('P0', na=False)]
    candidates = categories[categories['respondent_count'].ge(30)].sort_values(
        ['high_intent_share', 'respondent_count', 'category'], ascending=[False, False, True])
    barrier_rows = barriers.sort_values('respondent_count', ascending=False).head(3)
    barrier_text = '、'.join(f"{row.purchase_barrier}（{int(row.respondent_count)}人）" for row in barrier_rows.itertuples())
    if candidates.empty:
        research_finding = '目前没有单品类样本达到30份的候选，先补充调研。'
        research_action = '先补充样本与具体商品概念，再评估价格接受度；暂不形成品类优先级。'
    else:
        candidate = candidates.iloc[0]
        research_finding = (f"在样本不少于30份的品类中，{candidate['category']}高意愿占比最高："
                            f"{candidate['high_intent_share']:.1%}，样本{int(candidate['respondent_count'])}份。")
        research_action = (f"优先做该品类的实物/设计概念测试；重点回应{barrier_text or '尚未记录的购买阻力'}。"
                           '该排序是预设探索规则，不代表显著优于其他品类。')
    task_rows = [
        {'id': 'catalog', 'title': '商品信息维护', 'nature': '公开商品快照 + 人工维护状态',
         'finding': f'{len(public)}个商品档案中，{pending}个尚未人工核验授权；{maintenance}个存在快照规则维护提示。',
         'action': '核对角色、品类、规格与履约方式，补充授权证据；未经核验不进入对外上架名单。',
         'acceptance': '完成字段修订并保留证据URL、修改原因及版本；待处理数量不等同于已闭环数量。',
         'source': '公开商品有效主档 / 原始快照规则', 'target': 'products'},
        {'id': 'erp', 'title': 'ERP经营异常跟进', 'nature': '模拟ERP分析快照',
         'finding': f"{len(urgent)}个SKU被现有模型标记P0补货，建议采购预算合计¥{urgent['suggested_purchase_amount'].sum():,.2f}。",
         'action': '先核对可售、锁定、在途库存及交期，再确认采购建议；结合退款原因检查商品说明与履约。',
         'acceptance': '订单头明细对账、库存与采购依据可以导出复核；不会自动创建真实采购单。',
         'source': 'erp_replenishment_plan / 模拟数据', 'target': 'erp'},
        {'id': 'research', 'title': '衍生品用户调研', 'nature': '真实匿名便利样本',
         'finding': research_finding, 'action': research_action,
         'acceptance': '补充具体角色、规格、图片与报价后复测；购买意愿不当作实际成交转化。',
         'source': 'survey_243_category_summary / survey_243_barrier_summary', 'target': 'research'},
    ]
    live_rows = channels[channels['channel'].eq('直播间')]
    live = None
    if not live_rows.empty:
        row = live_rows.iloc[0]
        live = {'order_count': int(row['order_count']), 'paid_order_count': int(row['paid_order_count']),
                'payment_rate': float(row['payment_rate']), 'paid_amount': float(row['paid_amount'])}
    return {'title': '商品运营简报', 'method': '基于当前快照的确定性规则汇总，不是LLM生成或实时经营日报',
            'tasks': task_rows, 'live_channel': live,
            'live_boundary': '直播间仅为模拟ERP渠道标签，不能认定为抖音。未接入曝光、进房、商品点击、投流费用及平台后台。',
            'live_checklist': ['开播前：核对货品规格、价格、授权、库存、预售交期与FAQ',
                               '直播中：记录观众高频问题、缺货与优惠异常，避免超出证据的承诺',
                               '直播后：在获得真实后台数据后复盘点击、支付、退款及履约，不推算缺失转化率'],
            'scope_note': '所有建议待人工确认；不自动发布内容、不自动上架、不发送采购或营销指令。'}


def render_operations_brief(brief: dict) -> str:
    output = [f"# {brief['title']}", '', brief['method'], '', brief['scope_note']]
    for task in brief['tasks']:
        output.extend(['', f"## {task['title']}", f"数据性质：{task['nature']}", '',
                       f"发现：{task['finding']}", f"建议动作：{task['action']}",
                       f"核对标准：{task['acceptance']}", f"依据：{task['source']}"])
    output.extend(['', '## 直播协作准备', brief['live_boundary'], ''])
    output.extend(f'- {item}' for item in brief['live_checklist'])
    return '\n'.join(output) + '\n'
