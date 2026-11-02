"""Versioned supplement around the byte-preserved original professional audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts import audit_human_design as original
from scripts.check_human_design_calendar_horizons import (
    BINDINGS,
    capture,
    compare,
    references,
)

ORIGINAL_AUDIT_SHA256 = (
    "e57e8a0dc42fd26e9148237b11311e8e6705017596885c93dc2ec87fc5216fe2"
)


def build_report() -> dict:
    raw = Path(original.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_AUDIT_SHA256:
        raise ValueError(
            "Original audit changed; preserve it before adding a supplement"
        )
    base = original.build_report()
    sources = references()
    observed = capture()
    diagnostic = compare(observed, sources)
    diagnostic["reference_bindings"] = BINDINGS
    diagnostic["production_source_summary"] = observed["ephemeris_source_summary"]
    return {
        "method_id": "human_design_original_audit_with_conjunction_supplement_v1",
        "original_audit_sha256": ORIGINAL_AUDIT_SHA256,
        "original_report": base,
        "near_solar_conjunction_attribution": diagnostic,
        "scope": "Entire original report and criteria retained as a separate object. The added34 investigative positions and counterfactual conventions never regrade the original full calendar cohort or source/doctrine requirements.",
    }


def exit_code(value: dict, *, professional: bool = False, full: bool = False) -> int:
    base = value["original_report"]
    return int(
        base["calendar"]["status"] == "failed"
        or base["additional_calendar_span_external_reference"]["status"] == "failed"
        or base["primary_2024_written_fixing_examples"]["status"] == "failed"
        or professional
        and not base["professional_acceptance"]["all_three_axes_full_marks"]
        or full
        and not base["all_four_axes_full_marks"]
        or value["near_solar_conjunction_attribution"]["status"]
        == "disagreements_remain"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-professional-acceptance", action="store_true")
    parser.add_argument("--require-full-acceptance", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Never overwrite a completed audit")
    result = build_report()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    status = exit_code(
        result,
        professional=args.require_professional_acceptance,
        full=args.require_full_acceptance,
    )
    print(
        json.dumps(
            {
                "exit_code": status,
                "professional_status": result["original_report"][
                    "professional_acceptance"
                ]["status"],
                "conjunction_status": result["near_solar_conjunction_attribution"][
                    "status"
                ],
            }
        )
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
