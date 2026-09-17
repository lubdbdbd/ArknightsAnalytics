from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arknights_merch_analytics.business_decisions import build_business_decisions,render_business_decisions
if __name__=='__main__':
    report=build_business_decisions(ROOT)
    folder=ROOT/'reports/generated/business_decisions'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    (folder/'report.md').write_text(render_business_decisions(report),encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False))
