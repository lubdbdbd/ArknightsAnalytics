"""Evidence-bounded character lifecycle analysis. Never treat missing coverage as demand zero."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

CN = ZoneInfo('Asia/Shanghai')
ALLOWED_EVENTS = {'release', 'story', 'collaboration', 'anniversary', 'promotion'}


def timestamp(value):
    if value is None or value == '' or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors='coerce', utc=True)
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def day(value):
    parsed = timestamp(value)
    return parsed.astimezone(CN).date() if parsed else None


def clean_rows(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def snapshot_deltas(observations):
    """Deduplicate replicated captures; negative counter changes remain flagged, never clamped."""
    unique = {}
    for row in observations:
        captured, published = timestamp(row.get('collected_at')), timestamp(row.get('published_at'))
        if not captured or not published or captured < published:
            continue
        key = (row['platform'], row['content_id'], captured)
        if key in unique:
            if unique[key].get('view') != row.get('view'):
                raise ValueError(f'同一内容同一时点指标冲突: {key[:2]}')
            continue
        unique[key] = row
    groups = {}
    for (platform, content_id, captured), row in unique.items():
        groups.setdefault((platform, content_id), []).append((captured, row))
    output = []
    for (platform, content_id), captures in sorted(groups.items()):
        captures.sort(key=lambda item: item[0])
        for (start, previous), (end, current) in zip(captures, captures[1:]):
            days = (end-start).total_seconds()/86400
            before, after = previous.get('view'), current.get('view')
            delta = None if before is None or after is None else after-before
            status = 'missing_metric' if delta is None else ('counter_decreased' if delta < 0 else 'observed')
            output.append({'platform': platform, 'content_id': content_id,
                           'start': start.isoformat(), 'end': end.isoformat(),
                           'interval_days': round(days, 6), 'view_delta': delta,
                           'views_per_day': round(delta/days, 3) if status == 'observed' else None,
                           'status': status, 'source_url': current.get('source_url'),
                           'metric_scope': '同一内容两次累计计数之差，不代表角色新增用户或商品销量'})
    return output


def trend_signal(deltas, keys, policy):
    """Require the same content cohort and three contiguous equal observation windows."""
    scoped = [r for r in deltas if (r['platform'], r['content_id']) in keys]
    if not scoped:
        return {'label': '待验证', 'reason': '缺少同一内容的复采记录', 'change': None}
    latest_end = max(day(r['end']) for r in scoped)
    width = policy['trend_window_days']
    groups = []
    for index in range(policy['trend_min_intervals']):
        end = latest_end-timedelta(days=width*index)
        start = end-timedelta(days=width)
        bucket = {r['content_id']: r for r in scoped
                  if r['platform'] == 'bilibili' and day(r['start']) == start and day(r['end']) == end
                  and abs(r['interval_days']-width) <= .05 and r['status'] == 'observed'}
        groups.append(bucket)
    common = set.intersection(*(set(g) for g in groups))
    if len(common) < policy['trend_min_content']:
        return {'label': '待验证', 'reason': f"不足{policy['trend_min_intervals']}个连续{width}日窗口或缺少至少{policy['trend_min_content']}条相同内容样本", 'change': None}
    rates = [sum(g[k]['views_per_day'] for k in common) for g in reversed(groups)]
    if any(value <= 0 for value in rates):
        return {'label': '待验证', 'reason': '窗口增量为零，不能计算稳定的变化比例', 'change': None}
    changes = [rates[i+1]/rates[i]-1 for i in range(len(rates)-1)]
    threshold = policy['trend_change_threshold']
    if all(c >= threshold for c in changes):
        label = '内容增速上升'
    elif all(c <= -threshold for c in changes):
        label = '内容增速回落'
    elif all(abs(c) < threshold for c in changes):
        label = '内容增速相对平稳'
    else:
        label = '内容增速波动'
    return {'label': label, 'reason': '同一内容队列连续等长窗口；仍受内容年龄与推荐分发影响',
            'change': round(rates[-1]/rates[0]-1, 4), 'sample_count': len(common), 'window_rates': rates}


def classify_stage(events, as_of, policy):
    eligible = [r for r in events if r.get('verified') and 0 <= (as_of-day(r['event_at'])).days < policy['observation_window_days']]
    releases = [r for r in eligible if r['event_type'] == 'release']
    if releases:
        return '导入观察期', '有已核验的上线事件；仅确定事件阶段，未证明需求增长'
    if eligible:
        return '事件观察期', '近期存在直接宣传或已核验活动事件，需继续验证需求'
    if events:
        return '阶段待验证', '只有历史事件记录；旧内容不等于衰退或稳定需求'
    return '观察不足', '缺少直接关联的事件与时间证据'


def event_windows(events, contents, as_of, width):
    result = []
    for event in events:
        event_day = day(event['event_at'])
        start, end = event_day-timedelta(days=width), event_day+timedelta(days=width)
        related = [r for r in contents if event['operator'] in r['operators']
                   and r['key'] != event.get('content_key')]
        pre = sum(start <= day(r['published_at']) < event_day for r in related)
        post = sum(event_day <= day(r['published_at']) < end for r in related)
        elapsed = as_of >= end
        result.append({'event_id': event['event_id'], 'operator': event['operator'],
                       'event_type': event['event_type'], 'event_date': str(event_day),
                       'pre_start': str(start), 'post_end_exclusive': str(end),
                       'pre_other_content_in_sample': pre, 'post_other_content_in_sample': post,
                       'window_elapsed': elapsed,
                       'comparison_status': '样本描述，非全量或因果验证' if elapsed else '后窗口未结束',
                       'demand_uplift': None, 'source_url': event['source_url']})
    return result


def build_lifecycle(root: Path, as_of: date | None = None):
    root = Path(root)
    files = [root/'config/lifecycle_policy.json', root/'data/manual/lifecycle_events.json',
             root/'data/processed/operator_demand_fusion.csv',
             root/'data/processed/bilibili_official_archive.csv',
             root/'data/processed/official_content_scores.csv']
    policy = json.loads(files[0].read_text(encoding='utf-8'))
    if policy['trend_min_intervals'] < 3 or policy['trend_min_content'] < 2:
        raise ValueError('趋势观察至少需要3个窗口、2条内容')
    if min(policy['weekly_history'], policy['observation_window_days'], policy['trend_window_days']) <= 0:
        raise ValueError('观察周期必须为正数')
    if not 0 < policy['trend_change_threshold'] < 1:
        raise ValueError('变化阈值必须介于0与1之间')
    roster = clean_rows(pd.read_csv(files[2]))
    names = {r['operator'] for r in roster}
    if len(names) != len(roster):
        raise ValueError('角色名单重复')
    archive, official = clean_rows(pd.read_csv(files[3])), clean_rows(pd.read_csv(files[4]))
    observations, association = [], {}
    def add(raw, platform, content_id, operator=None):
        if not content_id:
            return
        key = f'{platform}:{content_id}'
        if operator in names:
            association.setdefault(key, set()).add(operator)
        observations.append({**raw, 'platform': platform, 'content_id': str(content_id), 'key': key})
    for row in archive:
        add(row, 'bilibili', row['bvid'], row.get('explicit_operator'))
    for row in official:
        add(row, row['platform'], row.get('bvid') or row.get('post_id'), row['operator'])
    for path in sorted((root/'data/public/expansion').glob('*/bilibili_observations.json')):
        files.append(path)
        for row in json.loads(path.read_text(encoding='utf-8')):
            if row.get('is_simulated') is True:
                continue
            add(row, 'bilibili', row['bvid'])
    valid_dates = [day(r.get('collected_at')) for r in observations if timestamp(r.get('collected_at'))]
    cutoff = as_of or max(valid_dates)
    # Date cutoffs are local China dates; a historical run must not use future captures or events.
    usable, invalid_times = [], 0
    for row in observations:
        published, captured = timestamp(row.get('published_at')), timestamp(row.get('collected_at'))
        if not published or not captured or published > captured:
            invalid_times += 1
            continue
        if day(row['collected_at']) <= cutoff and day(row['published_at']) <= cutoff:
            usable.append(row)
    if not usable:
        raise ValueError('分析日期之前没有有效采集记录')
    contents = {}
    for row in sorted(usable, key=lambda r: timestamp(r['collected_at'])):
        contents[row['key']] = {**row, 'operators': sorted(association.get(row['key'], []))}
    direct = [r for r in contents.values() if r['operators']]
    deltas = snapshot_deltas(usable)
    events = []
    for content in direct:
        for operator in content['operators']:
            events.append({'event_id': f"{operator}:{content['key']}", 'operator': operator,
                           'event_type': 'promotion', 'event_at': content['published_at'],
                           'title': content.get('title') or str(content.get('text', ''))[:100],
                           'verified': True, 'source_url': content['source_url'],
                           'content_key': content['key'], 'basis': '已有直接角色关联；宣传发布不等于角色上线'})
    for row in json.loads(files[1].read_text(encoding='utf-8')):
        if (row.get('operator') not in names or row.get('event_type') not in ALLOWED_EVENTS
                or not timestamp(row.get('event_at')) or not row.get('event_id')):
            raise ValueError('人工事件缺少合法角色、类型、时间或ID')
        if row.get('verified') is not True:
            raise ValueError('人工事件必须核验后再导入')
        if not str(row.get('source_url', '')).startswith(('https://', 'http://')) or not row.get('evidence_note'):
            raise ValueError('人工事件必须记录来源链接与核验依据')
        if day(row['event_at']) <= cutoff:
            events.append(row)
    if len({e['event_id'] for e in events}) != len(events):
        raise ValueError('事件ID重复')
    week_end = cutoff-timedelta(days=cutoff.weekday())
    weekly, operators, plans = [], [], []
    next_check = cutoff+timedelta(days=7)
    for role in roster:
        name = role['operator']
        role_contents = [r for r in direct if name in r['operators']]
        role_events = [e for e in events if e['operator'] == name]
        keys = {(r['platform'], r['content_id']) for r in role_contents}
        role_deltas = [r for r in deltas if (r['platform'], r['content_id']) in keys]
        signal = trend_signal(deltas, keys, policy)
        stage, reason = classify_stage(role_events, cutoff, policy)
        latest = max((day(r['published_at']) for r in role_contents), default=None)
        observed_end = max((day(r['collected_at']) for r in role_contents), default=None)
        age = (cutoff-latest).days if latest else None
        stale = observed_end is None or (cutoff-observed_end).days > policy['trend_window_days']
        if stale and signal['label'] != '待验证':
            signal = {'label': '待验证', 'reason': '最新复采已过观察时效，不将历史趋势当作当前趋势', 'change': None}
        gaps = ['补充角色上线/剧情/活动日期的官方依据', '缺少带时间的周边意向及商品连续观测']
        if signal['label'] == '待验证':
            gaps.append(signal['reason'])
        if stale:
            gaps.append(f"角色内容指标超过{policy['trend_window_days']}日未复采或缺失")
        action = ('核对事件日期并开展小样本品类意向调研；复采同一内容' if stage in {'导入观察期', '事件观察期'}
                  else '优先补采直接角色内容与事件依据；不据此判断补货或清仓')
        operators.append({'operator': name, 'stage': stage, 'stage_reason': reason,
                          'content_signal': signal['label'], 'signal_reason': signal['reason'],
                          'signal_change': signal['change'], 'last_direct_publication': str(latest) if latest else None,
                          'last_capture': str(observed_end) if observed_end else None,
                          'days_since_direct_publication': age, 'stale_observation': stale,
                          'direct_content_count': len(role_contents), 'snapshot_interval_count': len(role_deltas),
                          'survey_mentions': role.get('preference_mentions'),
                          'survey_scope': '无答卷日期，仅横截面背景，不参与阶段判定',
                          'demand_stage': '待验证', 'evidence_gaps': '；'.join(gaps), 'next_action': action})
        for index in range(policy['weekly_history']):
            start = week_end-timedelta(weeks=policy['weekly_history']-1-index)
            stop = start+timedelta(days=7)
            sample = [r for r in role_contents if start <= day(r['published_at']) < stop]
            weekly.append({'operator': name, 'week_start': str(start),
                           'bilibili_content_in_sample': sum(r['platform']=='bilibili' for r in sample),
                           'weibo_content_in_sample': sum(r['platform']=='weibo' for r in sample),
                           'fractional_content_in_sample': sum(1/len(r['operators']) for r in sample),
                           'complete_calendar_week': stop <= cutoff,
                           'coverage': '非全量样本；0仅表示未收录，不能解释为没有关注'})
        plans.append({'operator': name, 'priority': 'P1' if stage in {'导入观察期', '事件观察期'} else 'P2',
                      'suggested_next_capture': str(next_check), 'action': action,
                      'fixed_content_ids': [r['key'] for r in role_contents],
                      'event_review_required': True, 'status': '建议，未执行'})
    for row in deltas:
        row['operators'] = sorted(association.get(f"{row['platform']}:{row['content_id']}", []))
    manifest = [{'file': str(p.relative_to(root)).replace('\\', '/'),
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    report = {'version': policy['version'], 'as_of': str(cutoff),
              'data_latest_capture': str(max(day(r['collected_at']) for r in usable)),
              'policy': policy, 'summary': {'operator_count': len(operators),
                 'operators_with_direct_content': sum(r['direct_content_count'] > 0 for r in operators),
                 'direct_unique_content': len(direct), 'events': len(events), 'weekly_rows': len(weekly),
                 'all_content_intervals': len(deltas),
                 'direct_content_intervals': sum(bool(r['operators']) for r in deltas),
                 'counter_decreased_intervals': sum(r['status']=='counter_decreased' for r in deltas),
                 'invalid_time_rows': invalid_times,
                 'trend_ready_operators': sum(r['content_signal']!='待验证' for r in operators),
                 'stage_counts': dict(Counter(r['stage'] for r in operators))},
              'operators': operators, 'events': events, 'weekly': weekly, 'snapshot_deltas': deltas,
              'event_windows': event_windows(events, direct, cutoff, policy['observation_window_days']),
              'observation_plan': plans, 'manifest': manifest,
              'limitations': ['阶段标签是基于已收录事件的观察状态，不是完整IP生命周期或销量判断。',
                 '官号档案不是全量内容普查；时间窗口关联的共享Campaign不归为角色直接曝光。',
                 '累计播放量差只表明两次采集间增长；不同内容年龄、平台与推荐分发不可直接比较。',
                 '209组权重实验衡量排序稳健性，不属于生命周期时间序列。',
                 '243份问卷没有填写日期，淘宝首批为单次快照，均不用于证明需求趋势。',
                 '事件前后窗口仅描述收录内容；无完整覆盖、对照或曝光校正，不作因果解释。']}
    return report


def render_lifecycle(report):
    summary = report['summary']
    lines = ['# 角色生命周期观察报告', '', f"数据截至：{report['as_of']}（北京时间；默认使用最近采集日）", '',
             f"覆盖 {summary['operator_count']} 名角色，{summary['operators_with_direct_content']} 名有直接内容，"
             f"{summary['direct_unique_content']} 条独立直接内容，{summary['weekly_rows']} 条角色周记录。",
             f"同一内容复采区间 {summary['all_content_intervals']} 条，其中直接角色内容区间 {summary['direct_content_intervals']} 条。",
             f"满足连续趋势判断条件的角色：{summary['trend_ready_operators']}。", '',
             '## 阶段分布', '', *[f'- {k}：{v}' for k,v in summary['stage_counts'].items()], '',
             '## 方法与边界', '', *[f'- {s}' for s in report['limitations']], '',
             '## 逐角色结论', '', '|角色|事件阶段|内容信号|最近直接内容|独立内容|复采区间|', '|---|---|---|---|---:|---:|']
    for r in report['operators']:
        lines.append(f"|{r['operator']}|{r['stage']}|{r['content_signal']}|{r['last_direct_publication'] or '缺失'}|{r['direct_content_count']}|{r['snapshot_interval_count']}|")
    lines += ['', '## 可写入简历的补充', '',
              f"建立覆盖{summary['operator_count']}名角色的生命周期观察框架，区分内容发布时间、指标采集时间与角色事件；"
              f"生成{summary['weekly_rows']}条角色周记录，关联{summary['events']}条直接宣传事件，"
              '对同一内容复采计算增量，并设置连续观察门槛与证据缺口清单，为分阶段选品验证提供依据。', '',
              '周记录为派生分析行，不是新增采集数据；未形成已验证的需求增长或衰退结论。', '']
    return '\n'.join(lines)
