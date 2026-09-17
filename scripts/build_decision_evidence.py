from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from arknights_merch_analytics.decision_evidence import build_decision_evidence, render_decision_evidence


def main() -> None:
    report = build_decision_evidence(ROOT)
    target = ROOT / 'reports' / 'generated' / 'decision_evidence'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'report.md').write_text(render_decision_evidence(report), encoding='utf-8')
    for name, rows in [('rank_experiments', report['robustness']['experiments']),
                       ('rank_stability', report['robustness']['operators']),
                       ('sql_channel_case', report['sql_case']['channels']),
                       ('input_manifest', report['manifest'])]:
        pd.DataFrame(rows).to_csv(target / f'{name}.csv', index=False, encoding='utf-8-sig')
    print(json.dumps({'scenario_count': report['robustness']['scenario_count'],
                      'ranked_operators': report['robustness']['operator_count'],
                      'catalog_conflicts': report['catalog']['review_count'],
                      'sql_reconciled': report['sql_case']['reconciliation_passed'],
                      'naive_join_overcount': report['sql_case']['duplicate_amplification']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
