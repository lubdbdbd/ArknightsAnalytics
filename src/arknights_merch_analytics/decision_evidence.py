from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .operations_analytics import DEMAND_SCENARIOS, _row_weighted_score


SOURCES = ('content', 'survey', 'skland', 'commerce')
METHOD_VERSION = 'decision-evidence-v1'


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def rank_robustness(demand: pd.DataFrame, seed: int = 20260907,
                    runs: int = 200, top_k: int = 10) -> dict:
    if runs < 1 or top_k < 1:
        raise ValueError('runs and top_k must be positive')
    if demand['operator'].isna().any() or demand['operator'].duplicated().any():
        raise ValueError('operator must be present and unique')
    frame = demand[['operator', *[f'{source}_signal' for source in SOURCES]]].copy()
    for source in SOURCES:
        frame[f'{source}_signal'] = pd.to_numeric(frame[f'{source}_signal'], errors='raise')
    numeric = frame.drop(columns='operator')
    if ((numeric < 0) | (numeric > 100)).any().any():
        raise ValueError('signals must be in [0, 100] or missing')
    frame = frame[numeric.notna().any(axis=1)].sort_values('operator').reset_index(drop=True)
    if frame.empty:
        raise ValueError('no observed signals')
    effective_k = min(top_k, len(frame))
    baseline = _row_weighted_score(frame, DEMAND_SCENARIOS['balanced'])
    baseline_rank = baseline.rank(method='min', ascending=False)
    baseline_top = set(frame.loc[baseline_rank.le(effective_k), 'operator'])
    scenarios = dict(DEMAND_SCENARIOS)
    for excluded in SOURCES:
        weights = {source: weight if source != excluded else 0.0
                   for source, weight in DEMAND_SCENARIOS['balanced'].items()}
        total = sum(weights.values())
        scenarios[f'without_{excluded}'] = {source: weight / total for source, weight in weights.items()}
    generator = np.random.default_rng(seed)
    base_weights = np.array([DEMAND_SCENARIOS['balanced'][source] for source in SOURCES])
    for index in range(runs):
        weights = base_weights * generator.uniform(0.8, 1.2, len(SOURCES))
        weights /= weights.sum()
        scenarios[f'perturb_{index + 1:03d}'] = dict(zip(SOURCES, weights.tolist()))
    experiments, summaries = [], []
    for name, weights in scenarios.items():
        score = _row_weighted_score(frame, weights)
        rank = score.rank(method='min', ascending=False)
        members = set(frame.loc[rank.le(effective_k), 'operator'])
        experiment = pd.DataFrame({'operator': frame['operator'], 'scenario': name,
                                   'score': score, 'rank': rank, 'in_top_k': rank.le(effective_k)})
        experiments.append(experiment)
        correlation = baseline_rank.corr(rank, method='pearson') if len(frame) > 1 else np.nan
        summaries.append({'scenario': name, 'weights': weights,
                          'rank_correlation': correlation,
                          'top_k_jaccard': len(members & baseline_top) / len(members | baseline_top),
                          'ranked_count': int(rank.notna().sum()), 'top_k_count': len(members)})
    details = pd.concat(experiments, ignore_index=True)
    perturbations = details[details['scenario'].str.startswith('perturb_')]
    stability = details.groupby('operator').agg(best_rank=('rank', 'min'), worst_rank=('rank', 'max'))
    stability['perturb_top_k_share'] = perturbations.groupby('operator')['in_top_k'].mean()
    stability['baseline_rank'] = pd.Series(baseline_rank.to_numpy(), index=frame['operator'])
    stability['evidence_sources'] = pd.Series(frame.drop(columns='operator').notna().sum(axis=1).to_numpy(), index=frame['operator'])
    stability['rank_range'] = stability['worst_rank'] - stability['best_rank']
    stability['next_action'] = np.where(stability['evidence_sources'].lt(3), '补充缺失来源，勿将少量来源当成多源共识',
                                       np.where(stability['perturb_top_k_share'].ge(0.8) & stability['rank_range'].le(8),
                                                '可优先评审；仍需商品意向与供给验证', '对换权重或去源敏感，先比较分源证据'))
    stability = stability.reset_index().sort_values(['baseline_rank', 'operator'])
    return {'seed': seed, 'perturbation_runs': runs, 'scenario_count': len(scenarios),
            'top_k': effective_k, 'operator_count': len(frame), 'excluded_no_signal': len(demand) - len(frame),
            'weight_basis': '均衡权重32/28/25/15是项目先验，不是用真实销售标签训练得到的最优权重。',
            'method': '固定既有四类信号，逐项乘0.8—1.2随机扰动并归一化；另做五种偏好及四种去源实验。缺失来源按有效权重重分配。',
            'boundary': '仅诊断外层权重，不证明内层指标、曝光校正或样本代表性正确。Top-K包含边界同名次；频率不是成功概率。去源后无证据者不排名。',
            'review_rule': '至少3类来源、扰动Top-K占比≥80%、全情景名次跨度≤8才建议优先评审。这是可修改的探索规则，不是统计学显著性或销售门槛。',
            'scenarios': _records(pd.DataFrame(summaries)), 'operators': _records(stability),
            'experiments': _records(details)}


def content_comparability(content: pd.DataFrame) -> dict:
    frame = content.copy()
    frame['content_id'] = frame['bvid'].where(frame['platform'].eq('bilibili'), frame['post_id'])
    missing = frame['content_id'].isna() | frame['content_id'].astype(str).str.strip().eq('')
    valid = frame[~missing].copy()
    repeated = int(valid.duplicated(['platform', 'content_id', 'operator']).sum())
    valid['_captured'] = pd.to_datetime(valid['collected_at'], utc=True, errors='coerce')
    valid = valid.sort_values('_captured', na_position='first').drop_duplicates(['platform', 'content_id', 'operator'], keep='last')
    counts = valid.groupby(['platform', 'content_id'])['operator'].transform('nunique')
    valid['association_weight'] = 1 / counts
    valid['age_days_audit'] = ((pd.to_datetime(valid['collected_at'], utc=True, errors='coerce')
                               - pd.to_datetime(valid['published_at'], utc=True, errors='coerce')).dt.total_seconds() / 86400)
    valid['age_band'] = pd.cut(valid['age_days_audit'], [-np.inf, 0, 7, 30, 90, 365, np.inf],
                               labels=['时间异常', '0—7天', '7—30天', '30—90天', '90—365天', '365天以上'], right=False).astype('string').fillna('时间缺失')
    rows = []
    for (platform, band), group in valid.groupby(['platform', 'age_band']):
        rows.append({'platform': platform, 'age_band': band, 'unique_content': group['content_id'].nunique(),
                     'role_links': len(group), 'fractional_content': group['association_weight'].sum()})
    return {'association_rows': len(content), 'missing_id_rows': int(missing.sum()),
            'duplicate_role_links': repeated,
            'unique_content': len(valid.drop_duplicates(['platform', 'content_id'])),
            'fractional_content_total': float(valid['association_weight'].sum()),
            'time_invalid_rows': int(valid['age_band'].isin(['时间异常', '时间缺失']).sum()),
            'cohorts': _records(pd.DataFrame(rows)),
            'method': '审计按平台+内容ID去重，角色多对多关联按1/关联角色数分摊；以采集时点计算内容年龄，展示不同年龄段。此审计不悄悄替换旧榜。',
            'scoring_scope': '本页审计official_content_scores中实际参与旧评分的角色直接内容，不是549条B站官号历史内容全量；全量归档、Campaign背景与直接评分样本必须分开计数。',
            'limitations': [
                'B站播放、微博互动、森空岛攻略浏览不是同一种曝光，不能直接相加成跨平台触达人数。',
                '旧内容热度层使用站内百分位及累计量/发布天数；后者是历史日均代理，不是最近日增长。微博无曝光分母，不把互动量称为真实互动率。',
                '旧内容层曾以50分填补缺失微博；外层需求分虽按可用来源重分配，仍继承该先验，本轮敏感性不能消除它。',
                '小红书只有IP生态快照，不进入角色排名；森空岛攻略样本可能更偏强度需求，不等同周边偏好。',
                'B站Campaign窗口关联是共享宣传背景，不当作角色独占曝光；跨平台重复用户目前无法识别。',
                '可靠时间比较仍需同类型内容、固定发布后7/30天窗口与多次快照；现有横截面只能探索，不能证明热度增长或商业因果。']}


def catalog_identity_audit(listings: pd.DataFrame) -> dict:
    valid = listings.copy()
    missing = valid['item_id'].isna() | valid['item_id'].astype(str).str.strip().isin(['', 'nan', 'None'])
    valid = valid[~missing].copy()
    valid['item_id'] = valid['item_id'].astype(str)
    conflicts = []
    for item_id, group in valid.groupby('item_id'):
        reasons = []
        for field in ['category', 'target_operator', 'fulfillment_type']:
            if group[field].dropna().nunique() > 1:
                reasons.append(f'{field}存在多个值')
        for _, captured in group.groupby('snapshot_at'):
            if captured['price'].dropna().nunique() > 1:
                reasons.append('同采集时点价格冲突')
        if group['operator_mentions'].fillna('').str.contains('|', regex=False).any():
            reasons.append('多角色商品，不可将整条链接销量归给单一角色')
        if reasons:
            conflicts.append({'item_id': item_id, 'snapshot_count': len(group), 'reason': '；'.join(sorted(set(reasons)))})
    return {'snapshot_rows': len(listings), 'unique_item_links': valid['item_id'].nunique(),
            'missing_id_rows': int(missing.sum()), 'repeated_observations': len(valid) - valid['item_id'].nunique(),
            'review_count': len(conflicts), 'conflicts': conflicts,
            'grain': '淘宝item_id是商品链接层，不是可购买规格SKU。83个链接档案不能写成83个精确规格SKU。',
            'policy': '同链接保留历史快照，主档选最新观测；同名不自动合并、跨店/材质/尺寸/套装/预售补款不自动合并。冲突清单必须人工核验，本页不合并或删除记录。'}


def sql_order_case(headers: pd.DataFrame, lines: pd.DataFrame,
                   refunds: pd.DataFrame, query: str) -> dict:
    for frame, identifier in [(headers, 'order_id'), (lines, 'order_line_id'), (refunds, 'case_id')]:
        if frame[identifier].isna().any() or frame[identifier].duplicated().any():
            raise ValueError(f'{identifier} must be present and unique')
    if not set(lines['order_id']).issubset(set(headers['order_id'])) or not set(refunds['order_id']).issubset(set(headers['order_id'])):
        raise ValueError('orphan order reference')
    with sqlite3.connect(':memory:') as connection:
        headers.to_sql('erp_order_headers', connection, index=False)
        lines.to_sql('erp_order_lines', connection, index=False)
        refunds.to_sql('erp_after_sales', connection, index=False)
        output = pd.read_sql_query(query, connection)
        naive = connection.execute('''SELECT SUM(orders.paid_amount) FROM erp_order_headers orders
            JOIN erp_order_lines lines ON orders.order_id=lines.order_id
            WHERE orders.payment_status='paid' ''').fetchone()[0]
    paid = headers[headers['payment_status'].eq('paid')]
    expected = round(paid['paid_amount'].sum(), 2)
    actual = round(output['paid_amount'].sum(), 2)
    return {'header_rows': len(headers), 'line_rows': len(lines), 'refund_rows': len(refunds),
            'paid_order_count': len(paid), 'expected_paid_amount': expected, 'sql_paid_amount': actual,
            'reconciliation_passed': bool(abs(expected - actual) < 0.01),
            'naive_join_paid_amount_incorrect': round(float(naive or 0), 2),
            'duplicate_amplification': round(float(naive or 0) - expected, 2),
            'channels': _records(output), 'query': query,
            'method': '订单头一单一行；明细和已关闭售后分别按订单聚合后再LEFT JOIN，避免两个一对多关系放大金额。分币求和，汇总后还原元。',
            'boundary': '模拟ERP全量订单批次，退款按该批次截至快照的closed记录计入；已关闭退款不含待处理售后。支付含运费，扣已关闭退款后金额不是会计净收入或利润。'}


def build_decision_evidence(root: Path) -> dict:
    manifest = []

    def read(relative: str) -> pd.DataFrame:
        path = root / relative
        raw = path.read_bytes()
        frame = pd.read_csv(path)
        manifest.append({'file': relative, 'rows': len(frame), 'sha256': hashlib.sha256(raw).hexdigest()})
        return frame

    def processed(name: str) -> pd.DataFrame:
        return read(f'data/processed/{name}.csv')

    demand = processed('operator_demand_fusion')
    content = processed('official_content_scores')
    listings = processed('taobao_public_snapshots')
    categories = processed('survey_243_category_summary')
    profile = processed('survey_243_profile_summary').iloc[0]
    barriers = processed('survey_243_barrier_summary')
    evidence = processed('evidence_inventory')
    readiness = processed('pilot_readiness')
    approvals = processed('pilot_candidate_decisions')
    query_path = root / 'sql' / 'decision_order_case.sql'
    query = query_path.read_text(encoding='utf-8')
    manifest.append({'file': 'sql/decision_order_case.sql', 'rows': None,
                     'sha256': hashlib.sha256(query_path.read_bytes()).hexdigest()})
    sql_case = sql_order_case(processed('erp_order_headers'), processed('erp_order_lines'), processed('erp_after_sales'), query)
    categories = categories.copy()
    categories['next_action'] = np.where(categories['respondent_count'].lt(30), '样本不足30，先补采', '进入具体规格概念比较，不直接备货')
    categories['evidence_type'] = '样本内描述性发现'
    categories = categories.sort_values(['high_intent_share', 'respondent_count'], ascending=False)
    actions = [
        {'decision': '选哪个角色', 'basis': '多源需求矩阵 + 权重敏感性 + 角色问卷', 'next': '检查缺失来源与排名波动，再批准候选', 'not_proven': '全体玩家偏好、真实销量'},
        {'decision': '做什么品类、什么价格', 'basis': '样本内品类意愿 + 价格带 + 商品规格', 'next': '形成具体角色/材质/尺寸/交期概念，重新测意向', 'not_proven': '精确定价、备货量、已支付转化'},
        {'decision': '如何维护与补货', 'basis': '商品身份审计 + 模拟订单/库存/售后', 'next': '人工核验冲突与采购条件，保留处理证据', 'not_proven': '真实库存改善、采购节省、经营增长'}]
    return {'version': METHOD_VERSION, 'title': '决策证据工作台', 'business_questions': actions,
            'sources': _records(evidence), 'manifest': manifest,
            'robustness': rank_robustness(demand), 'content': content_comparability(content),
            'catalog': catalog_identity_audit(listings), 'sql_case': sql_case,
            'survey': {'response_count': int(profile['response_count']), 'high_intent_count': int(profile['high_intent_count']),
                       'categories': _records(categories), 'barriers': _records(barriers.head(3)),
                       'boundary': '243份为项目所有者确认真实的匿名便利样本。品类分组不是随机实验；不同品类的受访者不同，不能声称差异显著或偏好导致购买。价格区间/代表值不是精确定价。30份是探索门槛，不是统计显著性门槛。'},
            'execution': {'approvals': _records(approvals), 'stages': _records(readiness),
                          'boundary': '执行状态读取项目试点记录，不由推荐分或问卷意愿推断。候选批准不等于供应商签约或实际采购；0表示当前记录为0，不代表证明外部从未发生。'},
            'claim_boundary': '新增的是可复现分析与证据展示，不是新增真实订单。建议、审批、实际执行、效果验证分开呈现。'}


def render_decision_evidence(report: dict) -> str:
    def table(rows: list[dict]) -> str:
        return pd.DataFrame(rows).to_markdown(index=False, floatfmt='.4f') if rows else '暂无记录。'

    rank, content, case = report['robustness'], report['content'], report['sql_case']
    sections = [f"# {report['title']}", report['version'], report['claim_boundary'],
                '## 1. 为什么做：替运营解决什么决策', table(report['business_questions']),
                '## 2. 来源和粒度', table(report['sources']),
                '公开快照用于供给与兴趣代理；真实问卷用于样本内偏好；模拟ERP用于规则、关联和对账验证。三类数据不能混成真实经营业绩。',
                '## 3. 跨平台可比性', content['method'], content['scoring_scope'],
                f"角色关联{content['association_rows']}条，独立内容{content['unique_content']}条，重复关联{content['duplicate_role_links']}条；分摊内容当量{content['fractional_content_total']:.2f}。",
                table(content['cohorts']), '\n'.join(f'- {note}' for note in content['limitations']),
                '## 4. 权重实验与稳定性', rank['weight_basis'], rank['method'], rank['boundary'], rank['review_rule'],
                f"固定种子{rank['seed']}，{rank['operator_count']}名角色，{rank['scenario_count']}组实验，其中随机扰动{rank['perturbation_runs']}组；无信号排除{rank['excluded_no_signal']}名。",
                table([{**row, 'weights': json.dumps(row['weights'])} for row in rank['scenarios'] if not row['scenario'].startswith('perturb_')]),
                '### 均衡分前15名的敏感性', table(rank['operators'][:15]),
                '## 5. 问卷产生什么决策', report['survey']['boundary'], table(report['survey']['categories']),
                '### 优先回应的购买阻力', table(report['survey']['barriers']),
                '上述内容是描述性发现及下一步研究建议，不是证明已提高购买转化；不能把品类意愿直接套到某角色新规格。',
                '## 6. 商品身份与维护', report['catalog']['grain'], report['catalog']['policy'],
                f"{report['catalog']['snapshot_rows']}条快照、{report['catalog']['unique_item_links']}个链接，{report['catalog']['review_count']}个链接需人工复核；缺少ID{report['catalog']['missing_id_rows']}条。",
                table(report['catalog']['conflicts']),
                '## 7. 模拟ERP的价值与限制', case['boundary'],
                '验证数据粒度、规则、重复关联和业务对账；不证明真实销量增长、补货节省或退货改善。',
                '## 8. SQL订单案例：两类一对多关系防重复', case['method'],
                f"处理{case['header_rows']}张订单头、{case['line_rows']}条明细、{case['refund_rows']}条售后。",
                f"独立订单头实付{case['expected_paid_amount']:,.2f}元；SQL实付{case['sql_paid_amount']:,.2f}元；对账通过：{case['reconciliation_passed']}。",
                f"错误示范直接JOIN后实付为{case['naive_join_paid_amount_incorrect']:,.2f}元，多算{case['duplicate_amplification']:,.2f}元。这是故意构造的错误查询对照，不是发现了同金额的真实资金损失。",
                '```sql\n' + case['query'] + '\n```', table(case['channels']),
                'Excel也可以通过Power Query、透视表完成；SQL的价值是明确粒度、可重复查询及自动校验，不是Excel无法做。',
                '## 9. 哪些执行了，哪些没验证', report['execution']['boundary'],
                table(report['execution']['approvals']), table(report['execution']['stages']),
                '## 复现与输入指纹', '运行：`.venv/Scripts/python.exe scripts/build_decision_evidence.py`。指纹定位数据版本，不证明采集真实性。',
                table(report['manifest'])]
    return '\n\n'.join(sections) + '\n'
