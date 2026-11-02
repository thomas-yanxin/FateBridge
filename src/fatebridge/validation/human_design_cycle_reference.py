"""Finite independent cycle comparisons; angular and timing claims stay apart."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.human_design_cycle_sources import CycleSourceTrace
from fatebridge.core.human_design_cycles import (
    Row,
    _native_reader,
    derive_body_contacts,
)


@runtime.preserve_ephemeris_path()
def independent_cycle_checks(root: Path) -> dict[str, Any]:
    plan_path = root / "tests/fixtures/human-design-cycles-plan.json"
    reference_path = root / "tests/fixtures/human-design-cycles-reference.json"
    plan = json.loads(plan_path.read_text())
    reference = json.loads(reference_path.read_text())
    if reference["plan_sha256"] != hashlib.sha256(plan_path.read_bytes()).hexdigest():
        raise ValueError("Cycle reference plan changed")
    generator = root / "scripts/gen_human_design_cycles_reference.py"
    if (
        reference["generator_sha256"]
        != hashlib.sha256(generator.read_bytes()).hexdigest()
    ):
        raise ValueError("Cycle reference generator changed")
    rows = []
    sources = CycleSourceTrace()
    for record in reference["records"]:
        body, birth = record["body"], record["birth"]["jd_tt"]
        trace: dict[float, Row] = {}
        failures: dict[float, str] = {}
        reader = _native_reader(
            body, False, trace, failures, source_trace=sources, source_indices={}
        )
        calculated = derive_body_contacts(body, birth, reader)
        epoch_errors = []
        residuals = []
        differences = []
        if calculated["natal_longitude"] is not None:
            epoch_errors.append(
                abs(
                    (calculated["natal_longitude"] - record["natal_longitude"] + 180)
                    % 360
                    - 180
                )
                * 3600
            )
        if calculated["status"] == "sampled_search_completed":
            for event in record["contacts"]:
                position = reader(event["jd_tt"])[1]
                epoch_errors.append(
                    abs((position - event["longitude"] + 180) % 360 - 180) * 3600
                )
                target = (
                    calculated["natal_longitude"] + record["target_arc_degrees"]
                ) % 360
                residuals.append(abs((position - target + 180) % 360 - 180) * 3600)
            if len(calculated["contacts"]) == len(record["contacts"]):
                differences = [
                    (a["jd_tt"] - b["jd_tt"]) * 86400
                    for a, b in zip(calculated["contacts"], record["contacts"])
                ]
        count_match = len(calculated["contacts"]) == len(record["contacts"])
        motion_match = [r["motion"] for r in calculated["contacts"]] == [
            r["motion"] for r in record["contacts"]
        ]
        angular_pass = bool(epoch_errors) and all(
            x <= plan["same_epoch_tolerance_arcseconds"] for x in epoch_errors
        )
        root_pass = bool(residuals) and all(
            x <= plan["root_angular_residual_tolerance_arcseconds"] for x in residuals
        )
        passed = (
            calculated["status"] == "sampled_search_completed"
            and count_match
            and motion_match
            and angular_pass
            and root_pass
        )
        rows.append(
            {
                "birth": record["birth"],
                "body": body,
                "status": calculated["status"],
                "native_return_flag_model": calculated["native_return_flag_model"],
                "failure": calculated["failure"],
                "independent_contacts": len(record["contacts"]),
                "engine_contacts": len(calculated["contacts"]),
                "contact_count_matches": count_match,
                "motion_sequence_matches": motion_match,
                "same_epoch_errors_arcseconds": epoch_errors,
                "root_residuals_arcseconds": residuals,
                "root_time_differences_seconds": differences,
                "angular_checks_passed": angular_pass and root_pass,
                "bounded_case_passed": passed,
            }
        )
    return {
        "method_id": "human_design_independent_cycle_checks_v1",
        "plan_sha256": reference["plan_sha256"],
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "same_epoch_tolerance_arcseconds": plan["same_epoch_tolerance_arcseconds"],
        "root_residual_tolerance_arcseconds": plan[
            "root_angular_residual_tolerance_arcseconds"
        ],
        "timing_accuracy_certified": False,
        "continuous_completeness_certified": False,
        "bounded_acceptance_passed": all(r["bounded_case_passed"] for r in rows),
        "cases_checked": len(rows),
        "cases_passed": sum(r["bounded_case_passed"] for r in rows),
        "rows": rows,
        "source_evidence": sources.finish(),
        "scope": "Independent fixed-TT DE440/Horizons-SPK apparent longitude and independently solved contact roots. One-day reference and two-day engine grids are finite. Contact counts and angular thresholds do not certify subsecond timing, arbitrary dates, source doctrine, astrology, or reality.",
    }
