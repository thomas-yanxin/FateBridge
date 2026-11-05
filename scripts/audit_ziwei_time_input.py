"""Audit receipt propagation, not independent astronomical or classical truth."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.utils.birth_input import create_person_info

FIXTURES = Path(__file__).resolve().parents[1] / "tests/data/ziwei_independent"


def audit_time_input(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads((fixtures / "time_input_manifest.json").read_text())
    for source in manifest["source_documents"]:
        raw = (fixtures / source["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError("Time input source checksum mismatch: " + source["path"])
    differences, receipts = [], []
    for case in manifest["cases"]:
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            result = calculate_ziwei_birth(
                create_person_info(**manifest["base_input"], **case["input"]),
                rule_profile=profile,
            )
            b = result["ziwei_birth"]["calendar_basis"]
            r = b["time_input"]
            checks = {k: r.get(k) == v for k, v in case["expected_receipt"].items()}
            checks.update(
                context_status=result["analysis_context"]["time_input_status"]
                == r["status"],
                advisory_propagated=all(
                    s in result["snapshot_text"] for s in r["advisories"]
                ),
                not_classically_certified=not b["classical_clock_rule_verified"],
                non_evaluated_components_are_unknown=r["applied"]
                or all(
                    r[k] is None
                    for k in (
                        "longitude_correction_minutes",
                        "equation_of_time_minutes",
                        "daylight_saving_minutes",
                    )
                ),
                no_false_birth_precision=r["seconds_are_derived_not_birth_accuracy"]
                is True,
            )
            if not all(checks.values()):
                differences.append(
                    dict(case=case["id"], profile=profile, checks=checks)
                )
            receipts.append(dict(case=case["id"], profile=profile, checks=checks))
    return {
        "method_id": manifest["schema_version"],
        "conditional_input_cases": len(manifest["cases"]),
        "profile_receipts_checked": len(receipts),
        "receipts": receipts,
        "differences": differences,
        "independent_astronomical_vectors": 0,
        "historical_birth_clock_certified": False,
        "full_calendar_acceptance_passed": False,
        "scope": "Input branch declarations and propagation only; official sources explain the distinction, not these software branch expectations",
    }
