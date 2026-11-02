"""Audit recorded specialty house roles; never recalculate a chart or score efficacy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fatebridge.validation.house_roles import audit_specialty_house_roles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requested-hsys", type=int)
    parser.add_argument("--declared-base-house-system")
    args = parser.parse_args()
    raw = args.input.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Expected one actual response JSON object")
    report = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "declaration": {
            "requested_hsys": args.requested_hsys,
            "base_house_system": args.declared_base_house_system,
        },
        "audit": audit_specialty_house_roles(
            payload,
            requested_hsys=args.requested_hsys,
            declared_base_house_system=args.declared_base_house_system,
        ),
        "chart_recalculated": False,
        "actual_model_calls": 0,
        "prediction_acceptance": False,
    }
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
    return 0 if report["audit"]["status"] == "consistent_recorded_roles" else 1


if __name__ == "__main__":
    raise SystemExit(main())
