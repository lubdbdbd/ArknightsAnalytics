from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from arknights_merch_analytics.lifecycle import build_lifecycle, render_lifecycle


def main():
    parser = argparse.ArgumentParser(description='Build evidence-bounded character lifecycle analysis')
    parser.add_argument('--as-of', type=date.fromisoformat)
    args = parser.parse_args()
    report = build_lifecycle(ROOT, args.as_of)
    target = ROOT/'reports/generated/lifecycle'
    target.mkdir(parents=True, exist_ok=True)
    (target/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (target/'report.md').write_text(render_lifecycle(report), encoding='utf-8')
    print(json.dumps({'as_of': report['as_of'], **report['summary']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
