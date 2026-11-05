"""Audit the new predeclared Guolao rate holdout with the configured model.

Moshier's internal rate/position consistency is a separate question from
agreement with NASA. Keep every external residual and the original line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .audit_guolao_motion import evaluate, load_reference
else:
    from audit_guolao_motion import evaluate, load_reference

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SHA256 = "3a80c3399083fcbbcae582fc71b570a8ed1d82b1f10af589af74de75cde3bb2b"
REFERENCE_SHA256 = "27622cc6d3baef2e984b2350aa502a448f14efec8e159acb3be2ecd9aa7b8a4d"


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "tests/data/astro/guolao_moshier_motion/protocol.json",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "tests/data/astro/guolao_moshier_motion/reference.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        protocol, reference = load_reference(
            args.protocol,
            args.reference,
            protocol_sha256=PROTOCOL_SHA256,
            reference_sha256=REFERENCE_SHA256,
        )
    except (OSError, ValueError, KeyError) as error:
        result = {
            "reference_validation_error": str(error),
            "numerical_subset_checks_passed": False,
            "all_four_objectives_validated": False,
            "authority_certified": False,
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        return 2
    result = evaluate(protocol, reference)
    result.update(
        audit_version="guolao_moshier_position_rate_holdout_v1",
        protocol_sha256=PROTOCOL_SHA256,
        reference_sha256=REFERENCE_SHA256,
        scope="Actual seven-body Guolao rates at twelve newly predeclared TT epochs. Moshier position-rate consistency does not remove its physical-model error; Swiss/NASA can share DE441. Not whole-domain, whole-original, station-time or outcome certification.",
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
    if result["source_errors"] or result["unresolved_reference"]:
        return 2
    return 0 if result["numerical_subset_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
