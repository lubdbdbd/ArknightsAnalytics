from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arknights_merch_analytics.channel_strategy import build_channel_strategy,render_channel_strategy

if __name__=='__main__':
    report=build_channel_strategy(ROOT)
    folder=ROOT/'reports/generated/channel_strategy'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (folder/'report.md').write_text(render_channel_strategy(report),encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False))
