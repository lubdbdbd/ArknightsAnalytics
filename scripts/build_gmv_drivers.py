from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arknights_merch_analytics.gmv import build_gmv_report, render_gmv_report

if __name__=='__main__':
    report=build_gmv_report(ROOT)
    folder=ROOT/'reports/generated/gmv'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (folder/'report.md').write_text(render_gmv_report(report),encoding='utf-8')
    print(json.dumps({'orders':report['observed']['summary'],'refund_audit':report['observed']['refund_audit'],
                      'strategies':len(report['strategies']),'sensitivity_cases':len(report['sensitivity'])},ensure_ascii=False))
