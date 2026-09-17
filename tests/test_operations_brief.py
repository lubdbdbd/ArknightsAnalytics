import pandas as pd
import pytest

from arknights_merch_analytics.operations_brief import build_operations_brief, render_operations_brief


def inputs():
    return {
        'public': pd.DataFrame({'verification_status': ['pending', 'verified'],
                                'maintenance_priority': ['P1-复核', 'P2-可入库']}),
        'channels': pd.DataFrame({'channel': ['直播间'], 'order_count': [10], 'paid_order_count': [8],
                                 'payment_rate': [.8], 'paid_amount': [800]}),
        'categories': pd.DataFrame({'category': ['毛绒玩偶', '通行证'], 'respondent_count': [34, 20],
                                   'high_intent_share': [.55, .9]}),
        'barriers': pd.DataFrame({'purchase_barrier': ['价格高'], 'respondent_count': [5]}),
        'replenishment': pd.DataFrame({'replenishment_priority': ['P0-立即补货', 'P2-观察'],
                                      'suggested_purchase_amount': [120.5, 300]}),
    }


def test_brief_converts_evidence_to_actions_without_claiming_execution():
    brief = build_operations_brief(**inputs())
    assert len(brief['tasks']) == 3
    assert '1个尚未人工核验' in brief['tasks'][0]['finding']
    assert '120.50' in brief['tasks'][1]['finding']
    assert '毛绒玩偶' in brief['tasks'][2]['finding']
    assert brief['live_channel']['paid_order_count'] == 8
    assert '不能认定为抖音' in brief['live_boundary']
    assert '不自动' in brief['scope_note']


def test_small_sample_does_not_win_research_ranking():
    data = inputs()
    data['categories']['respondent_count'] = [10, 20]
    brief = build_operations_brief(**data)
    assert '先补充调研' in brief['tasks'][2]['finding']
    assert '暂不形成品类优先级' in brief['tasks'][2]['action']


@pytest.mark.parametrize('field', ['channels', 'public', 'replenishment', 'barriers', 'categories'])
def test_empty_evidence_is_safe(field):
    data = inputs()
    data[field] = data[field].iloc[0:0]
    brief = build_operations_brief(**data)
    assert len(brief['tasks']) == 3
    if field == 'channels':
        assert brief['live_channel'] is None


def test_export_preserves_sources_and_boundaries():
    content = render_operations_brief(build_operations_brief(**inputs()))
    assert content.startswith('# 商品运营简报')
    assert '确定性规则' in content
    assert '模拟ERP' in content
    assert 'survey_243_category_summary' in content
    assert '不自动上架' in content
