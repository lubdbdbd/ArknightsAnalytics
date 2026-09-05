from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.pilot_portal import export_portal_capture


def main() -> None:
    manual_dir = ROOT / "data" / "manual" / "commercial_pilot"
    counts = export_portal_capture(manual_dir / "pilot_capture.db", manual_dir)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_commercial_pilot.py")],
        check=True,
    )
    print(
        "Pilot capture exported: "
        f"{counts['campaigns']} campaigns, "
        f"{counts['intent_leads']} intent leads, "
        f"{counts['supplier_quotes']} supplier quotes"
    )


if __name__ == "__main__":
    main()
