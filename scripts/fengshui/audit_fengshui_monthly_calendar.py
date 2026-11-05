"""Compare the active calendar configuration with the frozen twelve-jie oracle."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from fatebridge.validation.fengshui_monthly_calendar import (
    audit_monthly_calendar_reference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.reference.read_bytes()
    if args.reference.suffix == ".gz":
        raw = gzip.decompress(raw)
    fixture = Path(__file__).resolve().parents[2] / "tests/data/fengshui_monthly_v1"
    manifest = json.loads((fixture / "calendar-reference.json").read_text())
    if hashlib.sha256(raw).hexdigest() != manifest["raw_sha256"]:
        raise ValueError("The independently collected frozen oracle cannot be replaced")
    reference = json.loads(raw)
    result = audit_monthly_calendar_reference(reference)
    result["reference_sha256"] = hashlib.sha256(raw).hexdigest()
    result["frozen_reference_identity_verified"] = True
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "comparisons"}, ensure_ascii=False
        )
    )
    return 0 if result["all_scoped_tt_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
