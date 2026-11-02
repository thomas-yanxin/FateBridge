"""Audit frozen general Mei Hua counting-candidate readings."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_general_variants import audit_general_casting_readings

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
report = audit_general_casting_readings(
    root / "tests/fixtures/meihua_general_variants_v2"
)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {
            "output": str(args.output),
            "selected_checks_passed": report["selected_checks_passed"],
        }
    )
)
raise SystemExit(0 if report["selected_checks_passed"] else 1)
