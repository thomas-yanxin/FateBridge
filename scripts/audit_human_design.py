"""Audit the three professional axes; retain reality prediction separately."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time, tt_from_ut1
from fatebridge.core.human_design import (
    bodygraph,
    chart_at,
    longitude_activation,
    planetary_positions,
)
from fatebridge.core.human_design_bridging import definition_bridging
from fatebridge.core.human_design_cross_coverage import expanded_cross_audit
from fatebridge.core.human_design_cycles import derive_body_contacts
from fatebridge.core.human_design_depth import depth_reference, line_fixings
from fatebridge.core.human_design_evidence import reference_table_audit
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.core.human_design_solar_root import solve_solar_root
from fatebridge.core.human_design_source_variants import source_variant_audit
from fatebridge.core.human_design_time import epoch_context_at_tt, solve_design_epoch
from fatebridge.validation.human_design_arithmetic import check_opposition_arithmetic
from fatebridge.validation.human_design_astronomy import physical_astronomy_checks
from fatebridge.validation.human_design_comparisons import (
    verify_node_comparison_reports,
)
from fatebridge.validation.human_design_cycle_reference import independent_cycle_checks
from fatebridge.validation.human_design_fixing import fixing_marker_checks
from fatebridge.validation.human_design_joint import verify_joint_snapshot
from fatebridge.validation.human_design_leap import confirmed_leap_checks
from fatebridge.validation.human_design_official import (
    combine_official_chart_cohorts,
    official_chart_checks,
)
from fatebridge.validation.human_design_primary_fixing import primary_fixing_checks
from fatebridge.validation.human_design_profile import public_profile_checks
from fatebridge.validation.human_design_publisher import publisher_natal_checks
from fatebridge.validation.human_design_transition import verify_transition_trace

ROOT = Path(__file__).resolve().parents[1]


def human_design_input_paths(root: Path) -> list[str]:
    """Bind new domain modules and their oracles without replacing old inputs."""
    patterns = (
        "src/fatebridge/core/human_design*.py",
        "src/fatebridge/validation/human_design*.py",
        "src/fatebridge/data/human_design/*.json",
        "scripts/*human_design*.py",
        "tests/test_human_design*.py",
        "tests/fixtures/human-design*.json",
        "tests/fixtures/human-design*.json.gz",
        "docs/contracts/human_design.json",
    )
    return sorted(
        {
            str(path.relative_to(root))
            for pattern in patterns
            for path in root.glob(pattern)
            if path.is_file()
        }
    )


def cycle_phase_arithmetic_checks() -> dict:
    path = ROOT / "tests/fixtures/human-design-cycle-phase-plan.json"
    plan = json.loads(path.read_text())
    rows = []
    for birth in plan["birth_tt"]:
        for natal in plan["natal_longitudes"]:
            for item in plan["bodies"]:
                rate = Fraction(item["target_arc"], item["target_offset_days"])
                origin, start = Fraction(natal), Fraction(birth)
                exact_root = start + item["target_offset_days"]
                known = float(exact_root)

                def read(tt):
                    return [
                        tt,
                        float((origin + rate * (Fraction(tt) - start)) % 360),
                        float(rate),
                        258,
                    ]

                result = derive_body_contacts(item["body"], birth, read)
                record = {
                    "birth_tt": birth,
                    "natal_longitude": natal,
                    "body": item["body"],
                    "known_analytic_root_tt": known,
                    "contact_count": len(result["contacts"]),
                    "analytic_root_is_representable": Fraction(known) == exact_root,
                    "passed": False,
                }
                if len(result["contacts"]) == 1:
                    event = result["contacts"][0]
                    difference = (Fraction(event["longitude"]) - origin) % 360
                    expected = (
                        difference - 180
                        if item["target_arc"] == 180
                        else (difference + 180) % 360 - 180
                    )
                    pair = event["exact_residual"]
                    lo, hi = event["bracket_jd_tt"]
                    record.update(
                        {
                            "known_analytic_root_in_bracket": lo <= known <= hi,
                            "reported_residual_matches_direct": event[
                                "residual_degrees"
                            ]
                            == float(expected),
                            "exact_residual_matches_direct": Fraction(
                                int(pair["numerator"]), int(pair["denominator"])
                            )
                            == expected,
                            "contact": event,
                        }
                    )
                    record["passed"] = (
                        result["status"] == "sampled_search_completed"
                        and record["analytic_root_is_representable"]
                        and record["known_analytic_root_in_bracket"]
                        and record["reported_residual_matches_direct"]
                        and record["exact_residual_matches_direct"]
                    )
                rows.append(record)
    return {
        "method_id": "human_design_multidecade_phase_arithmetic_oracle_v1",
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "case_count": len(rows),
        "cases_passed": sum(r["passed"] for r in rows),
        "status": (
            "bounded_analytic_checks_passed"
            if len(rows) == plan["case_count"] and all(r["passed"] for r in rows)
            else "failed"
        ),
        "scope": "Exact analytic linear-orbit roots and direct differences of returned binary longitudes. Rounding can make a returned longitude at the analytic zero differ infinitesimally from zero; do not call every analytic zero an observed native-function zero. Not an independent ephemeris, physical timing certificate, exhaustive search or source convention adjudication.",
        "cases": rows,
    }


def solar_root_resolution_checks() -> dict:
    plan_path = ROOT / "tests/fixtures/human-design-solar-root-plan.json"
    plan = json.loads(plan_path.read_text())
    rows = []
    for birth in plan["birth_tt"]:
        for num, den in plan["linear_rates_rational"]:
            rate = Fraction(num, den)
            p = Fraction(*plan["birth_sun_longitude_rational"])

            def sun(tt):
                return float((p + rate * (Fraction(tt) - Fraction(birth))) % 360)

            true = Fraction(birth) - 88 / rate
            nearest = float(true)
            candidates = {
                nearest,
                math.nextafter(nearest, -math.inf),
                math.nextafter(nearest, math.inf),
            }

            def residual(tt):
                return (Fraction(sun(birth)) - Fraction(sun(tt))) % 360 - 88

            expected = min(candidates, key=lambda tt: (abs(residual(tt)), tt))
            actual = solve_solar_root(birth, sun)
            rows.append(
                {
                    "birth_tt": birth,
                    "rate_rational": [num, den],
                    "expected_best_tt": expected,
                    "actual_tt": actual["design_jd_tt"],
                    "matched": actual["design_jd_tt"] == expected,
                    "exact_residual_matched": actual["residual_degrees"]
                    == float(residual(expected)),
                }
            )
    passed = len(rows) == 10 and all(
        r["matched"] and r["exact_residual_matched"] for r in rows
    )
    return {
        "status": "bounded_adjacent_float_root_passed" if passed else "failed",
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "cases": rows,
        "scope": "Ten exact rational linear-function oracles; endpoint resolution only. Does not establish Swiss positional accuracy, other-body bracket stability or physical timing error bounds.",
    }


def cycle_source_checks() -> dict:
    """One bounded actual cycle source receipt and three rehashed negatives."""
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.replay_metadata import digest
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading

    spec = next(s for s in CATALOG if s.key == "human_design")
    value = execute_tool(
        spec,
        spec.request_model(
            birth_year=1980,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=0,
            birth_timezone="UTC",
            cycle_reference_datetime="2029-07-01T00:00:00Z",
        ),
    )
    control = verify_human_design_reading(value)
    source = value["cycle_context"]["source_evidence"]
    negatives = []
    for mutation in ("detached_index", "atomic_certificate", "source_model"):
        altered = deepcopy(value)
        context = altered["cycle_context"]
        if mutation == "detached_index":
            context["bodies"][0]["evaluation_source_context_indices"].pop()
        elif mutation == "atomic_certificate":
            context["source_evidence"]["atomic_file_read_proven"] = True
        else:
            context["source_evidence"]["contexts"][0][
                "native_return_flag_model"
            ] = "unverified"
        altered["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in altered.items() if k != "run_metadata"}
        )
        negatives.append(
            {
                "mutation": mutation,
                "rejected": verify_human_design_reading(altered)["status"]
                == "rejected",
            }
        )
    complete = source["status"] == "observed_contexts_endpoint_verified" and any(
        f["slot"] == 2 for f in source["files"]
    )
    passed = (
        complete
        and control["status"] == "verified_fixed_template_reading"
        and all(r["rejected"] for r in negatives)
    )
    return {
        "status": "bounded_cycle_sources_verified" if passed else "not_verified",
        "control": control,
        "source_evidence": source,
        "negative_controls": negatives,
        "scope": "One source-bound native cycle run and three rehashed contradictions. File identities do not authenticate all coordinates or certify source doctrine, exact physical timing, continuous search completeness, or real-world predictions.",
    }


def provenance_regression_checks(payload: dict) -> dict:
    """Rehash seven bounded contradictory payloads under the selected model."""
    from fatebridge.services.replay_metadata import digest
    from fatebridge.validation.human_design import verify_human_design_reading

    control = verify_human_design_reading(payload)
    rows = []
    for mutation in (
        "north_native_flag",
        "south_native_flag",
        "earth_speed",
        "south_speed",
        "swiss_policy_type",
        "physical_scope",
        "factor_models",
    ):
        value = deepcopy(payload)
        policy = value["calculation_policy"]
        if mutation == "swiss_policy_type":
            policy["require_swiss_files"] = "false"
        elif mutation == "physical_scope":
            policy["ephemeris_model_scope"] = "all_factor_computation_models"
        elif mutation == "factor_models":
            policy["nonphysical_factor_models"]["personality"][
                "Earth"
            ] = "not_a_backend"
        else:
            body = {
                "north_native_flag": "NorthNode",
                "south_native_flag": "SouthNode",
                "earth_speed": "Earth",
                "south_speed": "SouthNode",
            }[mutation]
            row = next(
                r for r in value["activations"]["personality"] if r["body"] == body
            )
            if mutation.endswith("_flag"):
                row["native_return_flag_model"] = "not_a_backend"
            else:
                row["longitude_speed"] += 0.25
        value["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in value.items() if k != "run_metadata"}
        )
        verification = verify_human_design_reading(value)
        rows.append({"mutation": mutation, "verification": verification})
    rejected = sum(r["verification"]["status"] == "rejected" for r in rows)
    return {
        "status": (
            "bounded_provenance_contradictions_rejected"
            if control["status"] == "verified_fixed_template_reading"
            and rejected == len(rows)
            else "failed"
        ),
        "valid_control": control,
        "contradictions_checked": len(rows),
        "contradictions_rejected": rejected,
        "rows": rows,
        "scope": "One current full run and seven deliberately contradictory model/flag/speed/policy variants, each with a recomputed business hash. Local consistency only; not original-producer authentication, TT-to-coordinate proof, complete source doctrine, arbitrary text or prediction certification.",
    }


def ut1_context_checks() -> dict:
    """Check internal clock-policy consistency, without treating it as EOP."""
    rows = []
    for year in (1800, 1850, 1900, 1955, 1959, 1960, 1961, 1965, 1972, 2000, 2399):
        moment = datetime.fromisoformat(f"{year}-01-01T12:00:00+00:00")
        forward = ephemeris_time(moment)
        context = epoch_context_at_tt(forward.jd_tt, method="audit")["time"]
        rows.append(
            {
                "civil_label": moment.isoformat(),
                "forward_method": forward.method,
                "jd_tt": forward.jd_tt,
                "forward_jd_ut1": forward.jd_ut1,
                "sample_jd_ut1": context["jd_ut1"],
                "sample_minus_forward_seconds": (context["jd_ut1"] - forward.jd_ut1)
                * 86400,
                "exact_model_round_trip": context["jd_ut1"] == forward.jd_ut1
                and tt_from_ut1(context["jd_ut1"]) == forward.jd_tt,
            }
        )
    return {
        "status": (
            "bounded_model_round_trip_passed"
            if all(r["exact_model_round_trip"] for r in rows)
            else "failed"
        ),
        "cases_checked": len(rows),
        "cases_passed": sum(r["exact_model_round_trip"] for r in rows),
        "rows": rows,
        "independent_time_accuracy_certified": False,
        "scope": "11 finite clocks under the current configuration; TT sampler UT1 equals the declared civil forward policy and inverts to the same TT. No measured DUT1, independent Delta T accuracy or birth-clock authentication.",
    }


def historical_utc_checks() -> dict:
    """Compare to unmodified, independently compiled official SOFA routines."""
    path = ROOT / "tests/fixtures/historical-utc-sofa.json"
    reference = json.loads(path.read_text())
    rows = []
    if (
        len(reference["cases"]) != 233
        or reference["comparison_tolerance_seconds"] != 0.0002
    ):
        raise ValueError("The fixed SOFA clock cohort or declared tolerance changed")
    for case in reference["cases"]:
        actual = ephemeris_time(datetime.fromisoformat(case["utc"]))
        error = (
            abs(math.fsum([actual.jd_tt, *(-p for p in case["tt_jd_parts"])])) * 86400
        )
        rows.append(
            {
                "utc": case["utc"],
                "method": actual.method,
                "error_seconds": error,
                "within_tolerance": error <= 0.0002
                and case["statuses"] == [0, 0, 0, 0],
            }
        )
    return {
        "status": (
            "bounded_source_time_checks_passed"
            if all(r["within_tolerance"] for r in rows)
            else "failed"
        ),
        "cases_checked": len(rows),
        "cases_within_tolerance": sum(r["within_tolerance"] for r in rows),
        "maximum_error_seconds": max(r["error_seconds"] for r in rows),
        "tolerance_seconds": 0.0002,
        "source_url": reference["source_url"],
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": rows,
        "scope": "233 fixed calendar clocks from 1960 through the 1972 boundary; official SOFA C UTC/TAI/TT pipeline, independent of FateBridge and Swiss. No measured UT1, local birth-clock authentication or astronomical longitude certification.",
    }


def node_astronomy_checks() -> dict:
    """Independent DE440/ERFA reference; preserve failures of either backend."""
    reference = json.loads(
        (ROOT / "tests/fixtures/human-design-node-de440.json").read_text()
    )
    if reference["tolerance_arcseconds"] != 1.0:
        raise ValueError(
            "Node reference tolerance changed from the declared 1 arcsecond"
        )
    checks = {}
    for label, requested_flag in (
        ("selected", runtime.swe.FLG_SWIEPH),
        ("moshier_diagnostic", runtime.swe.FLG_MOSEPH),
    ):
        rows = []
        for row in reference["rows"]:
            coordinates, flags = runtime.ephemeris_call(
                "calc",
                row["jd_tt"],
                runtime.swe.TRUE_NODE,
                requested_flag | runtime.swe.FLG_SPEED,
            )
            actual = float(coordinates[0])
            error = abs((actual - row["node_longitude"] + 180) % 360 - 180) * 3600
            before = longitude_activation(actual)
            expected = longitude_activation(row["node_longitude"])
            rows.append(
                {
                    "label": row["label"],
                    "jd_tt": row["jd_tt"],
                    "ephemeris_model": runtime.ephemeris_model_from_retflag(flags),
                    "return_flags": flags,
                    "actual_longitude": actual,
                    "reference_longitude": row["node_longitude"],
                    "error_arcseconds": error,
                    "within_tolerance": flags >= 0 and error <= 1.0,
                    "different_levels": [
                        k
                        for k in ("gate", "line", "color", "tone", "base")
                        if before[k] != expected[k]
                    ],
                }
            )
        checks[label] = {
            "status": (
                "bounded_node_reference_checks_passed"
                if all(r["within_tolerance"] for r in rows)
                else "failed"
            ),
            "observations_checked": len(rows),
            "observations_within_tolerance": sum(r["within_tolerance"] for r in rows),
            "models": sorted({r["ephemeris_model"] for r in rows}),
            "maximum_error_arcseconds": max(r["error_arcseconds"] for r in rows),
            "different_level_counts": {
                k: sum(k in r["different_levels"] for r in rows)
                for k in ("gate", "line", "color", "tone", "base")
            },
            "rows": rows,
        }
    return {
        "method_id": reference["method_id"],
        "tolerance_arcseconds": 1.0,
        "kernel_sha256": reference["kernel_sha256"],
        "reference_sha256": hashlib.sha256(
            (ROOT / "tests/fixtures/human-design-node-de440.json").read_bytes()
        ).hexdigest(),
        **checks,
        "scope": reference["scope"],
    }


@contextmanager
def _moshier_reference_context():
    """Pin this finite regression's backend and restore the operator exactly."""
    with ephemeris_runtime.preserve_ephemeris_path():
        previous = ephemeris_runtime.configured_ephemeris_path()
        previous_env = os.environ.get("SE_EPHE_PATH")
        with TemporaryDirectory(prefix="human-design-node-regression-") as path:
            try:
                os.environ["SE_EPHE_PATH"] = path
                ephemeris_runtime.configure_ephemeris_path(path)
                yield
            finally:
                if previous_env is None:
                    os.environ.pop("SE_EPHE_PATH", None)
                else:
                    os.environ["SE_EPHE_PATH"] = previous_env
                # The enclosing runtime context restores the C path and the
                # thread signature after this exact Optional value is restored.
                ephemeris_runtime._configured_path = previous


def interval_regression_check() -> dict:
    """An observed backend regression, not an independent celestial oracle."""
    case = json.loads(
        (ROOT / "tests/fixtures/human-design-uncertainty-case.json").read_text()
    )
    with _moshier_reference_context():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]))
        report = assess_birth_interval(nominal, case["plus_minus_minutes"], "true")
    variants = [
        a
        for a in report.get("activation_variants", [])
        if a["side"] == "personality" and a["body"] == "NorthNode"
    ]
    endpoints_missed = len(report.get("comparisons", [])) == 2 and all(
        not any(
            a["side"] == "personality" and a["body"] == "NorthNode"
            for a in c["changed_activations"]
        )
        for c in report.get("comparisons", [])
    )
    seen = variants[0]["observed_values"] if variants else {}
    sampling = report.get("sampling", {})
    passed = (
        endpoints_missed
        and seen.get("base") == [1, 2]
        and sampling.get("grid_sample_count") == 721
        and sampling.get("continuous_interval_certified") is False
    )
    return {
        "status": "observed_regression_passed" if passed else "failed",
        "case": case,
        "old_endpoints_miss_node_variant": endpoints_missed,
        "observed_node_values": seen,
        "sampling": sampling,
        "station_candidate_count": len(report.get("station_candidates", [])),
        "scope": "Fixed Moshier regression selected by a station search, not independent astronomical acceptance. Finite sampling and speed candidates do not certify a continuous interval.",
    }


def joint_variant_regression_checks() -> dict:
    """Replay an engine-selected counterexample; independently check its graph sets."""
    case_path = ROOT / "tests/fixtures/human-design-joint-variant-case.json"
    reference_path = ROOT / "tests/fixtures/human-design-joint-bridge-oracle.json"
    case = json.loads(case_path.read_text())
    reference = json.loads(reference_path.read_text())
    plan_path = ROOT / reference["plan_path"]
    plan = json.loads(plan_path.read_text())
    for path, expected in (
        (plan_path, reference["plan_sha256"]),
        (ROOT / reference["oracle_source_path"], reference["oracle_source_sha256"]),
        (ROOT / reference["source_table_path"], reference["source_table_sha256"]),
        (
            ROOT / "scripts/build_human_design_bridge_reference.py",
            reference["generator_sha256"],
        ),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Joint bridge oracle source changed")
    if (
        hashlib.sha256(reference["raw_output"].encode()).hexdigest()
        != reference["raw_output_sha256"]
    ):
        raise ValueError("Joint bridge oracle raw output changed")
    if [c["id"] for c in plan["cases"]] != ["left", "right"] or [
        c["id"] for c in reference["cases"]
    ] != ["left", "right"]:
        raise ValueError("Fixed joint regression endpoint cohort changed")
    with _moshier_reference_context():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]))
        report = assess_birth_interval(
            nominal, case["birth_input"]["birth_time_uncertainty_minutes"], "true"
        )
    summary = report.get("joint_evidence_summary") or {}
    variants = report.get("classification_variants", [])
    snapshots_valid = bool(variants) and all(
        verify_joint_snapshot(row["value"])["status"]
        == "verified_local_snapshot_mechanics"
        for row in variants
    )
    endpoint_rows = []
    for input_case, expected in zip(plan["cases"], reference["cases"]):
        side = input_case["id"]
        frozen = JointSnapshotCache().snapshot(case[side])
        gates = frozen["activated_gates"]
        subsets = sum(
            math.comb(64 - len(gates), k)
            for k in range(expected["minimum_added_gate_count"] + 1)
        )
        actual = report["comparisons"][0 if side == "left" else 1]["snapshot"]
        endpoint_rows.append(
            {
                "id": side,
                "matched": input_case["activated_gates"] == gates
                and actual["activations"] == frozen["activations"]
                and actual["definition_bridging"]["minimum_added_gate_count"]
                == expected["minimum_added_gate_count"]
                and [
                    s["added_gates"]
                    for s in actual["definition_bridging"]["minimum_solutions"]
                ]
                == expected["minimum_sets"]
                and subsets == expected["candidate_subsets_checked"],
                "minimum_solution_count": len(expected["minimum_sets"]),
                "oracle_subsets_checked": subsets,
            }
        )
    passed = (
        snapshots_valid
        and all(r["matched"] for r in endpoint_rows)
        and summary.get("bridge_families_changed") is True
        and summary.get("bridge_minimum_gate_count_changed") is False
        and summary.get("distinct_joint_projection_count", 0) >= 2
        and report.get("sampling", {}).get("continuous_interval_certified") is False
    )
    return {
        "status": "observed_joint_regression_passed" if passed else "failed",
        "nominal_birth_utc": case["nominal_birth_utc"],
        "old_classification_variant_count": case["old_classification_variant_count"],
        "joint_evidence_summary": summary,
        "joint_evidence_cache": report.get("joint_evidence_cache"),
        "local_snapshot_mechanics_valid": snapshots_valid,
        "endpoint_oracle_checks": endpoint_rows,
        "oracle_subsets_checked": sum(
            r["oracle_subsets_checked"] for r in endpoint_rows
        ),
        "regression_source_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "graph_reference_sha256": hashlib.sha256(
            reference_path.read_bytes()
        ).hexdigest(),
        "scope": case["scope"]
        + " C oracle independently checks only fixed graph mathematics, not the TT-to-position witnesses.",
    }


def transition_fixture_diagnostics(actual: dict, frozen: dict) -> dict:
    """Retain bitwise drift; use pre-existing position thresholds only.

    This is not independent astronomy. No tolerance certifies speed or derived
    distance accuracy; all discrete classifications and flags stay exact.
    """
    physical = json.loads(
        (ROOT / "tests/fixtures/human-design-astronomy-plan.json").read_text()
    )["comparison_tolerance_arcseconds"]
    node = json.loads(
        (ROOT / "tests/fixtures/human-design-node-de440.json").read_text()
    )["tolerance_arcseconds"]
    positions, float_differences = [], []
    discrete_match = True
    discrete_fields = (
        "body",
        "gate",
        "center",
        "line",
        "color",
        "tone",
        "base",
        "tone_orientation",
        "gate_start_longitude",
        "ephemeris_model",
        "return_flags",
        "derived_from",
    )
    if set(actual) != set(frozen):
        return {
            "raw_activations_equal": False,
            "discrete_fields_equal": False,
            "positions_within_existing_reference_tolerances": False,
            "scope": "Activation side sets differ.",
        }
    for side, rows in actual.items():
        if len(rows) != len(frozen[side]):
            discrete_match = False
        for current, prior in zip(rows, frozen[side]):
            discrete_match &= all(
                current.get(k) == prior.get(k)
                and type(current.get(k)) is type(prior.get(k))
                for k in discrete_fields
            )
            error = (
                abs((current["longitude"] - prior["longitude"] + 180) % 360 - 180)
                * 3600
            )
            tolerance = (
                node if current["body"] in {"NorthNode", "SouthNode"} else physical
            )
            positions.append(
                {
                    "side": side,
                    "body": current["body"],
                    "error_arcseconds": error,
                    "preexisting_tolerance_arcseconds": tolerance,
                    "within_tolerance": error <= tolerance,
                }
            )
            for key, value in current.items():
                if type(value) is float and value != prior.get(key):
                    float_differences.append(
                        {
                            "side": side,
                            "body": current["body"],
                            "field": key,
                            "current": value,
                            "frozen": prior.get(key),
                            "difference": value - prior[key],
                        }
                    )
    return {
        "raw_activations_equal": actual == frozen,
        "discrete_fields_equal": discrete_match,
        "positions_within_existing_reference_tolerances": bool(positions)
        and all(r["within_tolerance"] for r in positions),
        "position_comparisons": positions,
        "raw_float_differences": float_differences,
        "position_tolerance_sources": [
            "tests/fixtures/human-design-astronomy-plan.json",
            "tests/fixtures/human-design-node-de440.json",
        ],
        "speed_accuracy_certified": False,
        "scope": "Raw frozen coordinates/speeds/distances are preserved and differences reported. Only positions inherit the already fixed2arcsecond physical/1arcsecond node reference thresholds; all discrete fields/flags must match exactly. Not independent astronomy, speed accuracy or bitwise identity.",
    }


def transition_regression_checks() -> dict:
    case_path = ROOT / "tests/fixtures/human-design-transition-case.json"
    case = json.loads(case_path.read_text())
    plan_path = ROOT / case["plan_path"]
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != case["plan_sha256"]:
        raise ValueError("Joint transition plan changed")
    with _moshier_reference_context():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]))
        report = assess_birth_interval(nominal, case["plus_minus_minutes"], "true")
    variants = report.get("classification_variants", [])
    cache = JointSnapshotCache()
    missed = cache.key(case["physical_samples"]["missed"])
    recovered = missed in {cache.key(row["value"]) for row in variants}
    physical = transition_fixture_diagnostics(
        nominal["activations"], case["physical_samples"]["nominal"]["activations"]
    )
    frozen_time = case["physical_samples"]["nominal"]["time_scales"]
    epochs = {
        "birth_tt_exact": nominal["time_scales"]["personality"]["jd_tt"]
        == frozen_time["personality"]["jd_tt"],
        "design_tt_difference_seconds": abs(
            nominal["time_scales"]["design"]["jd_tt"] - frozen_time["design"]["jd_tt"]
        )
        * 86400,
        "existing_solver_bracket_seconds": 0.0002,
    }
    trace = verify_transition_trace(
        report.get("joint_transition_refinement", {}),
        variants,
        report.get("sampling", {}),
        nominal["time_scales"]["personality"]["jd_tt"],
        case["plus_minus_minutes"] * 60,
        10,
    )
    passed = (
        recovered
        and physical["discrete_fields_equal"]
        and physical["positions_within_existing_reference_tolerances"]
        and epochs["birth_tt_exact"]
        and epochs["design_tt_difference_seconds"]
        <= epochs["existing_solver_bracket_seconds"]
        and trace["status"] == "verified_local_refinement_trace"
        and all(
            verify_joint_snapshot(row["value"])["status"]
            == "verified_local_snapshot_mechanics"
            for row in variants
        )
        and report["sampling"]["continuous_interval_certified"] is False
    )
    return {
        "status": "observed_transition_regression_passed" if passed else "failed",
        "nominal_birth_utc": case["nominal_birth_utc"],
        "legacy_joint_variant_count": case["legacy_joint_variant_count"],
        "current_joint_variant_count": len(variants),
        "missed_witness_recovered": recovered,
        "frozen_nominal_activations_raw_equal": physical["raw_activations_equal"],
        "frozen_nominal_replay_diagnostics": physical,
        "frozen_epoch_replay": epochs,
        "refinement_summary": report.get("joint_transition_refinement_summary"),
        "trace_verification": trace,
        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "search_samples_checked": case["search_samples_checked"],
        "scope": case["scope"]
        + " Finite trace verification does not authenticate TT astronomy or eliminate unobserved reversals.",
    }


def astronomy_checks() -> dict:
    reference = json.loads((ROOT / "tests/fixtures/western-horizons.json").read_text())
    results = []
    cache = {}
    for body in reference["references"]:
        for row in body["rows"]:
            key = row["utc"]
            if key not in cache:
                cache[key] = planetary_positions(datetime.fromisoformat(key))[
                    "positions"
                ]
            actual = cache[key][body["body"]]["longitude"]
            error = (
                abs((actual - row["apparent_ecliptic_longitude"] + 180) % 360 - 180)
                * 3600
            )
            results.append(
                {
                    "utc": key,
                    "source_timescale": "UT1" if key < "1962" else "UTC",
                    "body": body["body"],
                    "ephemeris_model": cache[key][body["body"]]["ephemeris_model"],
                    "error_arcseconds": error,
                    "within_tolerance": error <= reference["tolerance_arcseconds"],
                }
            )
    solar_reference = json.loads(
        (ROOT / "tests/fixtures/human-design-horizons.json").read_text()
    )
    solar = {row["utc"]: row["sun_longitude"] for row in solar_reference["rows"]}
    arcs = []
    for pair in solar_reference["pairs"]:
        arc = (solar[pair["birth_utc"]] - solar[pair["design_candidate_utc"]]) % 360
        error = abs(arc - 88) * 3600
        current_root = solve_design_epoch(datetime.fromisoformat(pair["birth_utc"]))
        reference_tt = ephemeris_time(
            datetime.fromisoformat(pair["design_candidate_utc"])
        ).jd_tt
        root_offset_seconds = abs(current_root["time"]["jd_tt"] - reference_tt) * 86400
        arcs.append(
            {
                **pair,
                "jpl_solar_arc_degrees": arc,
                "error_arcseconds": error,
                "within_tolerance": error <= solar_reference["tolerance_arcseconds"],
                "current_root_offset_seconds": root_offset_seconds,
                "current_root_tolerance_seconds": 2.0,
                "current_root_within_tolerance": root_offset_seconds <= 2.0,
            }
        )
    return {
        "status": (
            "bounded_reference_checks_passed"
            if len(results) == 120
            and len(arcs) == 4
            and all(r["within_tolerance"] for r in results + arcs)
            and all(r["current_root_within_tolerance"] for r in arcs)
            else "failed"
        ),
        "physical_longitude_count": len(results),
        "physical_ephemeris_models": sorted({r["ephemeris_model"] for r in results}),
        "ephemeris_version": runtime.swe.version,
        "physical_longitude_max_error_arcseconds": max(
            r["error_arcseconds"] for r in results
        ),
        "solar_arc_count": len(arcs),
        "solar_arc_max_error_arcseconds": max(r["error_arcseconds"] for r in arcs),
        "tolerance_arcseconds": 2.0,
        "physical_longitudes": results,
        "solar_arcs": arcs,
        "limits": [
            "JPL comparison does not independently validate lunar nodes, the mandala table or a full official Human Design chart.",
            "Design candidate times were chosen with this engine; the JPL longitudes at those times are independent.",
            "Selected 1900-2099 epochs only: Horizons uses UT1 for the two pre-1962 cases and UTC for later cases. This is not all supported years; 2 arcseconds does not certify fine subdivisions near boundaries.",
        ],
    }


def bridge_oracle_checks() -> dict:
    reference = json.loads(
        (ROOT / "tests/fixtures/human-design-bridge-oracle.json").read_text()
    )
    plan_path = ROOT / reference["plan_path"]
    plan = json.loads(plan_path.read_text())
    for path, expected in plan["source_fingerprints"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen official bridge input observations changed")
    if (
        hashlib.sha256(reference["raw_output"].encode()).hexdigest()
        != reference["raw_output_sha256"]
    ):
        raise ValueError("Independent bridge oracle raw output changed")
    for path, expected in (
        (plan_path, reference["plan_sha256"]),
        (ROOT / reference["oracle_source_path"], reference["oracle_source_sha256"]),
        (ROOT / reference["source_table_path"], reference["source_table_sha256"]),
        (
            ROOT / "scripts/build_human_design_bridge_reference.py",
            reference["generator_sha256"],
        ),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Independent bridge reference source fingerprint changed")
    if len(plan["cases"]) != len(reference["cases"]) or len(plan["cases"]) != 22:
        raise ValueError("The fixed bridge-oracle cohort changed")
    rows = []
    for case, expected in zip(plan["cases"], reference["cases"]):
        if case["id"] != expected["id"]:
            raise ValueError("Bridge reference case order changed")
        count = expected["minimum_added_gate_count"]
        subsets = (
            sum(
                math.comb(64 - len(case["activated_gates"]), k)
                for k in range(count + 1)
            )
            if count is not None
            else 0
        )
        actual = definition_bridging(bodygraph(case["activated_gates"], []))
        matched = (
            subsets == expected["candidate_subsets_checked"]
            and actual["minimum_added_gate_count"] == count
            and actual["original_component_count"]
            == expected["original_component_count"]
            and [row["added_gates"] for row in actual["minimum_solutions"]]
            == expected["minimum_sets"]
        )
        rows.append(
            {
                "id": case["id"],
                "matched": matched,
                "minimum_added_gate_count": actual["minimum_added_gate_count"],
                "minimum_solution_count": actual["minimum_solution_count"],
                "oracle_subsets_checked": subsets,
                "production_expanded_states": actual["search"]["expanded_states"],
            }
        )
    return {
        "status": (
            "declared_graph_cases_matched"
            if all(row["matched"] for row in rows)
            else "failed"
        ),
        "cases_checked": len(rows),
        "cases_matched": sum(row["matched"] for row in rows),
        "oracle_subsets_checked": sum(row["oracle_subsets_checked"] for row in rows),
        "cases": rows,
        "reference_path": "tests/fixtures/human-design-bridge-oracle.json",
        "reference_sha256": hashlib.sha256(
            (ROOT / "tests/fixtures/human-design-bridge-oracle.json").read_bytes()
        ).hexdigest(),
        "scope": reference["scope"],
    }


def node_comparison_regression_checks() -> dict:
    """Every original accepted contradiction, plus the corrected probe."""
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.replay_metadata import digest
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading

    before_path = ROOT / "docs/validation/human-design-comparison-before.json"
    plan_path = ROOT / "tests/fixtures/human-design-comparison-plan.json"
    before = json.loads(before_path.read_text())
    plan = json.loads(plan_path.read_text())
    if (
        hashlib.sha256(before_path.read_bytes()).hexdigest()
        != "eeda89591d9ce0cac38919112ebd13df0253e62d5a4fc025d06b1409240de318"
        or hashlib.sha256(plan_path.read_bytes()).hexdigest()
        != "ef5d8612a4df120d986c3db2f6151d3c9bb78f07ffbfa4760687855c28f3d229"
    ):
        raise ValueError("Frozen node comparison reproduction or plan changed")
    original_ids = {
        r["id"]
        for r in before["cases"]
        if r.get("status") == "verified_fixed_template_reading"
    }
    if (
        len(original_ids) != 12
        or len(plan["cases"]) != 13
        or not original_ids <= {r["id"] for r in plan["cases"]}
    ):
        raise ValueError("A before-fix accepted contradiction was removed")
    spec = next(s for s in CATALOG if s.key == "human_design")
    payload = execute_tool(spec, spec.request_model(**before["birth_input"]))
    control = verify_human_design_reading(payload)
    negatives = []
    for case in plan["cases"]:
        changed = deepcopy(payload)
        target = changed
        parts = case["path"].split(".")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        target[int(parts[-1]) if isinstance(target, list) else parts[-1]] = case[
            "replacement"
        ]
        changed["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in changed.items() if k != "run_metadata"}
        )
        direct = verify_node_comparison_reports(changed)
        reading = verify_human_design_reading(changed)
        negatives.append(
            {
                "id": case["id"],
                "direct_report_rejected": bool(direct["errors"]),
                "complete_rehashed_reading_status": reading["status"],
                "passed": bool(direct["errors"])
                and reading["status"] == case["expected_status"],
            }
        )
    passed = (
        control["status"] == "verified_fixed_template_reading"
        and control["checked_node_report_count"] == 2
        and all(x["passed"] for x in negatives)
    )
    return {
        "method_id": "human_design_node_comparison_witness_regression_v1",
        "status": "bounded_node_comparison_checks_passed" if passed else "failed",
        "before_sha256": hashlib.sha256(before_path.read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "original_before_fix_accepted_count": 12,
        "checked_negative_count": len(negatives),
        "control": control,
        "negative_controls": negatives,
        "scope": "All12 recorded before-fix accepted contradictions and one corrected path probe, using a complete synthetic run. Rebuild both full node reports from finite supplied native coordinates and same TT without recomputing the sky. Original eight served statements retained, new node explanation added. Not native execution authentication, full original reading, arbitrary live-model or physical accuracy certification.",
    }


def sampled_interval_regression_checks() -> dict:
    """Keep all15 before-fix accepted contradictions under the full verifier."""
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.replay_metadata import digest
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading
    from fatebridge.validation.human_design_sampling import verify_sampled_interval

    before_path = ROOT / "docs/validation/human-design-sampling-before.json"
    plan_path = ROOT / "tests/fixtures/human-design-sampling-plan.json"
    if (
        hashlib.sha256(before_path.read_bytes()).hexdigest()
        != "903a530e8b966cb81d4754e72aaac9bb89dd96ba9fff9f3566a8cc4c757d5992"
        or hashlib.sha256(plan_path.read_bytes()).hexdigest()
        != "5b35496e7c105d07432375fd31374b18345485ea803898090af5f15d2e216f73"
    ):
        raise ValueError("Frozen sampled-interval reproduction or plan changed")
    before = json.loads(before_path.read_text())
    plan = json.loads(plan_path.read_text())
    if (
        len(before["cases"]) != 15
        or [r["id"] for r in before["cases"]] != [r["id"] for r in plan["cases"]]
        or not all(
            r["actually_changed"]
            and r["old_status"] == "verified_fixed_template_reading"
            for r in before["cases"]
        )
    ):
        raise ValueError("An original accepted interval contradiction was removed")
    spec = next(s for s in CATALOG if s.key == "human_design")
    payload = execute_tool(spec, spec.request_model(**plan["birth_input"]))
    control = verify_human_design_reading(payload)
    negatives = []
    for case in plan["cases"]:
        changed = deepcopy(payload)
        target = changed
        parts = case["path"].split(".")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        key = int(parts[-1]) if isinstance(target, list) else parts[-1]
        if target[key] == case["replacement"]:
            raise ValueError("No-op interval negative control")
        target[key] = deepcopy(case["replacement"])
        changed["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in changed.items() if k != "run_metadata"}
        )
        direct = verify_sampled_interval(changed)
        reading = verify_human_design_reading(changed)
        negatives.append(
            {
                "id": case["id"],
                "direct_report_rejected": bool(direct["errors"]),
                "complete_rehashed_reading_status": reading["status"],
                "passed": bool(direct["errors"]) and reading["status"] == "rejected",
            }
        )
    passed = (
        control["status"] == "verified_fixed_template_reading"
        and control["checked_interval_evaluation_count"] == 25
        and all(r["passed"] for r in negatives)
    )
    return {
        "method_id": "human_design_sampled_interval_scalar_replay_regression_v1",
        "status": "bounded_interval_replay_passed" if passed else "failed",
        "before_sha256": hashlib.sha256(before_path.read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "original_before_fix_accepted_count": 15,
        "checked_negative_count": len(negatives),
        "control": control,
        "negative_controls": negatives,
        "scope": "Rebuild the actual finite evaluation set, station/refinement trace, every activation variant, endpoint report, aggregate metadata and fixed reading from supplied raw coordinates, speed and flags without another native call. All15 original accepted contradictions and all nine previous statements retained. Not native-execution authentication, independent physical accuracy, historical clock realization, continuous completeness, complete original-source prose or live-model certification.",
    }


def bounded_live_model_checks() -> dict:
    """Replay sealed actual first answers; this cannot grant full acceptance."""
    from scripts.audit_human_design_semantics import audit_review

    fixture = ROOT / "tests/fixtures/human_design_semantics_v1"
    if not fixture.is_dir():
        return {
            "status": "not_run",
            "scope": "No sealed live development evidence available.",
        }
    archive = fixture / "runtime-source.tar.gz"
    targets = []
    for name, review in (
        ("model-run-first", "model-run-first-review.json"),
        ("model-run-supported", "model-run-supported-review.json"),
        ("model-run-desktop", "review-desktop.json"),
    ):
        bound = audit_review(fixture / name, fixture / review, source_archive=archive)
        original = json.loads((fixture / name / "report.json").read_text())
        targets.append(
            {
                "target": name,
                "cli_version": original["cli_version"],
                "model": original["model"],
                "selected_case_count": original["selected_case_count"],
                "original_mechanical_checks_passed": original[
                    "mechanical_checks_passed"
                ],
                "unrun_case_ids": original["unrun_case_ids"],
                "binding": bound,
            }
        )
    desktop = targets[-1]
    return {
        "status": "bounded_first_answers_reviewed",
        "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "targets": targets,
        "desktop_first_answers": desktop["binding"]["reviewed_answers"],
        "reviewer_decisions": desktop["binding"]["reviewer_criterion_decisions"],
        "independent_held_out_cases": 0,
        "arbitrary_free_text_certified": False,
        "scope": "Eight predeclared known development cases, original actual desktop answers and same-run receipts; local reviewer judgments are not independently blinded. Both rejected PATH-runtime attempts and their seven unrun cases remain. Fixed-template checks, quote binding and this finite live run do not certify arbitrary future prose, all384line meanings or full professional acceptance.",
    }


def live_model_requirement_status(check: dict) -> str:
    if check["status"] == "not_run":
        return "not_run"
    if not check["targets"][-1]["original_mechanical_checks_passed"] or check[
        "reviewer_decisions"
    ].get("fail", 0):
        return "failed"
    # Passing a finite development cohort never closes the original full scope.
    return "incomplete"


def build_report() -> dict:
    paths = [
        "src/fatebridge/core/human_design_primary_diagrams.py",
        "src/fatebridge/data/human_design/primary-diagrams-2008-reference.json",
        "scripts/check_human_design_primary_diagrams.py",
        "tests/test_human_design_primary_diagrams.py",
        "tests/fixtures/human-design-primary-diagrams-plan.json",
        "tests/fixtures/human-design-primary-diagrams-extraction.json",
        "src/fatebridge/core/astro/clock_observation.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/physical_epoch.py",
        "src/fatebridge/core/human_design_clock_observation.py",
        "scripts/build_human_design_decimal_offset_reference.py",
        "scripts/build_human_design_fractional_leap_reference.py",
        "scripts/build_human_design_gate_context_reference.py",
        "scripts/build_human_design_reference_fraction_reference.py",
        "src/fatebridge/core/human_design_reference_clock.py",
        "tests/test_human_design_reference_fraction.py",
        "tests/test_human_design_reference_fraction_transports.py",
        "tests/fixtures/human_design_reference_fraction_v1/plan.json",
        "tests/fixtures/human_design_reference_fraction_v1/reference.json",
        "tests/fixtures/human_design_reference_fraction_v1/supplemental-plan.json",
        "tests/fixtures/human_design_reference_fraction_v1/before-clock-results.json",
        "tests/fixtures/human_design_reference_fraction_v1/before-full-results.json.gz",
        "src/fatebridge/core/human_design_gate_context.py",
        "tests/test_human_design_gate_context.py",
        "tests/test_human_design_gate_context_transports.py",
        "tests/test_human_design_gate_context_delivery.py",
        "src/fatebridge/application/result_delivery.py",
        "tests/fixtures/human_design_gate_context_v1/plan.json",
        "tests/fixtures/human_design_gate_context_v1/reference.json.gz",
        "tests/fixtures/human_design_gate_context_v1/source-identities.json",
        "tests/fixtures/human_design_gate_context_v1/longitude-source-disagreement.json",
        "tests/test_human_design_fractional_leap.py",
        "tests/test_human_design_fractional_leap_transports.py",
        "tests/fixtures/human_design_fractional_leap_v1/plan.json",
        "tests/fixtures/human_design_fractional_leap_v1/reference.json",
        "tests/fixtures/human_design_fractional_leap_v1/before-results.json",
        "tests/fixtures/human_design_fractional_leap_v1/before-9us-run.json.gz",
        "tests/fixtures/human_design_fractional_leap_v1/before-cycle-order.json",
        "tests/test_decimal_timezone_precision.py",
        "tests/test_human_design_decimal_offsets.py",
        "tests/test_human_design_decimal_offset_transports.py",
        "tests/test_human_design_subsecond_offsets.py",
        "tests/test_subsecond_offset_pipeline.py",
        "tests/fixtures/human_design_decimal_offset_v1/plan.json",
        "tests/fixtures/human_design_decimal_offset_v1/reference.json",
        "tests/fixtures/human_design_decimal_offset_v1/before-results.json",
        "tests/fixtures/human_design_decimal_offset_v1/before-root-run.json.gz",
        "tests/fixtures/human_design_decimal_offset_v1/precision-followup-plan.json",
        "src/fatebridge/utils/civil_time.py",
        "src/fatebridge/core/astro/native_execution.py",
        "src/fatebridge/core/human_design_cycles.py",
        "src/fatebridge/core/human_design_reference_order.py",
        "src/fatebridge/core/human_design_references.py",
        "tests/test_human_design_reference_snapshots.py",
        "tests/test_human_design_reference_transports.py",
        "tests/fixtures/human_design_reference_snapshot_v1/before-profile-run.json.gz",
        "src/fatebridge/utils/timezones.py",
        "tests/test_timezone_source_identity.py",
        "tests/test_human_design_timezone_sources.py",
        "tests/fixtures/human_design_timezone_source_v1/mixed-source-run.json.gz",
        "src/fatebridge/validation/human_design_clocks.py",
        "src/fatebridge/validation/human_design_cycles.py",
        "scripts/check_human_design_clock_replay.py",
        "tests/test_human_design_clock_replay.py",
        "tests/fixtures/human-design-clock-replay-plan.json",
        "docs/validation/human-design-interval-clock-before.json",
        "src/fatebridge/core/human_design_cycle_input.py",
        "src/fatebridge/api.py",
        "src/fatebridge/utils/errors.py",
        "scripts/check_human_design_cycle_input.py",
        "tests/test_human_design_cycle_input.py",
        "tests/test_human_design_cycle_input_transports.py",
        "tests/human_design_cycle_input_driver.py",
        "tests/fixtures/human-design-cycle-input-plan.json",
        "docs/validation/human-design-cycle-input-before.json",
        "docs/validation/human-design-ordinary-clock-before.json",
        "src/fatebridge/core/human_design_execution.py",
        "src/fatebridge/validation/human_design_execution.py",
        "src/fatebridge/core/astro/native_execution.py",
        "src/fatebridge/core/astro/_native_worker.py",
        "src/fatebridge/core/astro/source_session.py",
        "scripts/check_human_design_native_state.py",
        "scripts/human_design_source_fault_worker.py",
        "tests/test_human_design_native_state.py",
        "tests/human_design_native_state_driver.py",
        "tests/fixtures/human-design-native-state-plan.json",
        "docs/validation/human-design-native-state-before.json",
        "src/fatebridge/core/human_design_natal_sources.py",
        "src/fatebridge/validation/human_design_natal_sources.py",
        "src/fatebridge/validation/human_design_source_files.py",
        "scripts/check_human_design_natal_sources.py",
        "tests/test_human_design_natal_sources.py",
        "tests/test_human_design_natal_source_transports.py",
        "tests/fixtures/human-design-natal-source-plan.json",
        "docs/validation/human-design-natal-source-before.json",
        "docs/validation/human-design-natal-source-late-before.json",
        "src/fatebridge/core/human_design_sample_witness.py",
        "src/fatebridge/core/human_design_interval_summary.py",
        "src/fatebridge/validation/human_design_sampling.py",
        "tests/test_human_design_sampling.py",
        "tests/test_human_design_sampling_transports.py",
        "tests/fixtures/human-design-sampling-plan.json",
        "tests/fixtures/human-design-sampling-legacy-statements.json",
        "tests/fixtures/human-design-sampling-legacy-statements-linux.json",
        "docs/validation/human-design-sampling-before.json",
        "src/fatebridge/core/human_design_node_comparisons.py",
        "src/fatebridge/validation/human_design_comparisons.py",
        "tests/test_human_design_comparisons.py",
        "tests/test_human_design_comparison_transports.py",
        "tests/fixtures/human-design-comparison-plan.json",
        "tests/fixtures/human-design-comparison-legacy-statements.json",
        "docs/validation/human-design-comparison-before.json",
        "src/fatebridge/core/human_design_birth_clock.py",
        "src/fatebridge/validation/human_design_leap.py",
        "scripts/build_human_design_leap_reference.py",
        "tests/fixtures/human-design-leap-plan.json",
        "tests/fixtures/human-design-leap-sofa.json",
        "tests/test_human_design_birth_clock.py",
        "tests/test_human_design_birth_clock_transports.py",
        ".gitattributes",
        "src/fatebridge/core/human_design.py",
        "src/fatebridge/core/human_design_cycles.py",
        "tests/test_human_design_cycle_phase.py",
        "tests/fixtures/human-design-cycle-phase-plan.json",
        "docs/validation/human-design-cycle-phase-before.json",
        "src/fatebridge/core/human_design_cycle_sources.py",
        "src/fatebridge/validation/human_design_cycle_sources.py",
        "tests/test_human_design_cycle_sources.py",
        "src/fatebridge/validation/human_design_cycles.py",
        "src/fatebridge/validation/human_design_cycle_reference.py",
        "src/fatebridge/data/human_design/cycles-2026-reference.json",
        "tests/fixtures/human-design-cycles-plan.json",
        "tests/fixtures/human-design-cycles-reference.json",
        "tests/fixtures/human-design-cycles-horizons.json",
        "tests/test_human_design_cycles.py",
        "scripts/gen_human_design_cycles_reference.py",
        "scripts/check_human_design_cycle_horizons.py",
        "src/fatebridge/core/human_design_evidence.py",
        "src/fatebridge/core/human_design_source_variants.py",
        "src/fatebridge/data/human_design/source-variants-2026-reference.json",
        "scripts/build_human_design_source_variants.py",
        "tests/test_human_design_source_variants.py",
        "tests/test_human_design_source_variant_transports.py",
        "src/fatebridge/core/human_design_depth.py",
        "src/fatebridge/validation/human_design_fixing.py",
        "src/fatebridge/validation/human_design_primary_fixing.py",
        "scripts/check_human_design_primary_fixing.py",
        "tests/fixtures/human-design-primary-fixing-2024.json",
        "tests/test_human_design_primary_fixing_source.py",
        "scripts/gen_human_design_calendar_span_reference.py",
        "scripts/check_human_design_calendar_span.py",
        "tests/fixtures/human-design-calendar-span-plan.json",
        "tests/fixtures/human-design-calendar-span-de440.json",
        "tests/test_human_design_calendar_span_reference.py",
        "tests/test_human_design_ephemeris_installation.py",
        "src/fatebridge/data/human_design/fixing-2026-reference.json",
        "scripts/build_human_design_fixing_reference.py",
        "tests/fixtures/human-design-fixing-observation-plan.json",
        "tests/test_human_design_fixing.py",
        "tests/test_human_design_fixing_transports.py",
        "src/fatebridge/core/human_design_time.py",
        "src/fatebridge/core/human_design_solar_root.py",
        "src/fatebridge/validation/human_design_solar_root.py",
        "tests/test_human_design_solar_root.py",
        "tests/test_human_design_solar_root_transports.py",
        "tests/fixtures/human-design-solar-root-plan.json",
        "src/fatebridge/core/human_design_provenance.py",
        "src/fatebridge/validation/human_design_provenance.py",
        "src/fatebridge/core/human_design_circuitry.py",
        "src/fatebridge/core/human_design_circuit_topology.py",
        "src/fatebridge/core/human_design_cross_coverage.py",
        "src/fatebridge/data/human_design/cross-coverage-2026-reference.json",
        "scripts/plan_human_design_cross_coverage.py",
        "scripts/read_human_design_official_pdf.py",
        "scripts/build_human_design_cross_coverage.py",
        "tests/fixtures/human-design-cross-coverage-plan.json",
        "tests/fixtures/human-design-cross-coverage-observations.json",
        "tests/fixtures/human-design-official-cross-charts.json",
        "tests/fixtures/human-design-course-cross-disagreement.json",
        "tests/test_human_design_cross_coverage.py",
        "tests/test_human_design_cross_coverage_transports.py",
        "src/fatebridge/data/human_design/circuit-pages-1996-reference.json",
        "scripts/build_human_design_circuit_pages.py",
        "tests/fixtures/human-design-circuit-pages-plan.json",
        "tests/fixtures/human-design-circuit-pages-observations.json",
        "tests/test_human_design_circuit_topology.py",
        "tests/test_human_design_circuit_topology_transports.py",
        "src/fatebridge/data/human_design/circuit-group-2026-reference.json",
        "src/fatebridge/core/human_design_classification.py",
        "src/fatebridge/core/human_design_bridging.py",
        "src/fatebridge/core/human_design_joint.py",
        "src/fatebridge/core/human_design_backend.py",
        "src/fatebridge/core/human_design_profile.py",
        "src/fatebridge/validation/human_design_profile.py",
        "src/fatebridge/data/human_design/profile-2026-reference.json",
        "src/fatebridge/validation/human_design_backend.py",
        "src/fatebridge/validation/human_design_astronomy.py",
        "src/fatebridge/validation/human_design_joint.py",
        "src/fatebridge/core/human_design_sensitivity.py",
        "src/fatebridge/core/human_design_transition.py",
        "src/fatebridge/validation/human_design_transition.py",
        "src/fatebridge/core/human_design_precision.py",
        "src/fatebridge/core/human_design_variables.py",
        "src/fatebridge/validation/human_design_official.py",
        "src/fatebridge/validation/human_design_arithmetic.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/historical_utc.py",
        "src/fatebridge/core/jyotish.py",
        "src/fatebridge/data/knowledge/western-historical-utc.json",
        "src/fatebridge/data/knowledge/western-utc1960.json",
        "src/fatebridge/core/requests/human_design.py",
        "src/fatebridge/core/output_human_design.py",
        "src/fatebridge/services/human_design.py",
        "src/fatebridge/services/catalog/astrology.py",
        "src/fatebridge/data/human_design/rave-2001-reference.json",
        "src/fatebridge/data/human_design/rave-2001-depth.json",
        "src/fatebridge/data/human_design/circuitry-2026-reference.json",
        "src/fatebridge/validation/human_design.py",
        "src/fatebridge/validation/claims.py",
        "tests/fixtures/human-design-horizons.json",
        "tests/fixtures/western-horizons.json",
        "tests/fixtures/historical-utc-iers.txt",
        "tests/fixtures/historical-utc-sofa.json",
        "tests/fixtures/human-design-official-example.json",
        "tests/fixtures/human-design-sources.json",
        "tests/fixtures/human-design-uncertainty-case.json",
        "tests/fixtures/human-design-node-de440.json",
        "tests/fixtures/human-design-official-charts.json",
        "tests/fixtures/human-design-official-authority-charts.json",
        "tests/fixtures/human-design-authority-plan.json",
        "tests/fixtures/human-design-bridge-plan.json",
        "tests/fixtures/human-design-bridge-oracle.json",
        "tests/fixtures/human-design-joint-variant-case.json",
        "tests/fixtures/human-design-joint-bridge-plan.json",
        "tests/fixtures/human-design-joint-bridge-oracle.json",
        "tests/fixtures/human-design-astronomy-plan.json",
        "tests/fixtures/human-design-astronomy-de440.json",
        "tests/fixtures/human-design-astronomy-horizons.json",
        "tests/fixtures/human-design-full-backend-case.json",
        "tests/fixtures/human-design-transition-plan.json",
        "tests/fixtures/human-design-transition-case.json",
        "src/fatebridge/data/agent_examples.json",
        "tests/test_human_design.py",
        "tests/test_human_design_depth.py",
        "tests/test_human_design_circuitry.py",
        "tests/test_human_design_sensitivity.py",
        "tests/test_human_design_transition.py",
        "tests/test_human_design_precision.py",
        "tests/test_human_design_variables.py",
        "tests/test_human_design_opposition.py",
        "tests/test_human_design_authority.py",
        "tests/test_human_design_bridging.py",
        "tests/test_human_design_joint.py",
        "tests/test_human_design_astronomy.py",
        "tests/test_human_design_profile.py",
        "tests/test_human_design_transports.py",
        "tests/test_human_design_time.py",
        "tests/test_human_design_provenance.py",
        "tests/test_historical_utc.py",
        "tests/test_utc1960.py",
        "tests/test_jyotish_transports.py",
        "scripts/audit_human_design.py",
        "scripts/build_human_design_bridge_reference.py",
        "scripts/human_design_bridge_oracle.c",
        "scripts/gen_human_design_astronomy_reference.py",
        "scripts/gen_human_design_astronomy_horizons.py",
        "scripts/build_human_design_profile_reference.py",
        "scripts/build_human_design_circuit_group_reference.py",
        "scripts/check_human_design_transition_case.py",
        "scripts/build_human_design_depth_reference.py",
        "scripts/build_human_design_reference.py",
        "src/fatebridge/validation/human_design_publisher.py",
        "src/fatebridge/data/human_design/publisher-natal-2005-reference.json",
        "scripts/build_human_design_publisher_natal_reference.py",
        "scripts/audit_human_design_publisher_natal.py",
        "tests/fixtures/human-design-cycle-publisher-plan.json",
        "tests/test_human_design_publisher.py",
        "tests/fixtures/human-design-object-order-plan.json",
        "tests/test_human_design_object_order.py",
        "scripts/build_historical_utc_reference.py",
        "scripts/build_utc1960_reference.py",
        "scripts/gen_human_design_node_reference.py",
    ]
    example = json.loads(
        (ROOT / "tests/fixtures/human-design-official-example.json").read_text()
    )
    chart = chart_at(datetime.fromisoformat(example["nominal_birth_utc"]))
    matches = sum(
        {k: activation[k] for k in ("gate", "line")}
        == example["activations"][side][activation["body"]]
        for side, items in chart["activations"].items()
        for activation in items
    )
    catalogue = depth_reference()
    source_arrows = {
        (a["side"], a["body"], a["status"]) for a in example["line_fixing_arrows"]
    }
    example_activations = {
        side: [{"body": body, **fact} for body, fact in facts.items()]
        for side, facts in example["activations"].items()
    }
    computed_arrows = {
        (a["side"], a["body"], a["status"])
        for a in line_fixings(example_activations)
        if a["status"] in {"exaltation", "detriment", "juxtaposition"}
    }
    from fatebridge.application.examples import example_input
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading

    spec = next(s for s in CATALOG if s.key == "human_design")
    result = execute_tool(spec, spec.request_model(**example_input(spec)))
    reading_check = verify_human_design_reading(result)
    provenance = provenance_regression_checks(result)
    live_models = bounded_live_model_checks()
    if live_models["status"] != "not_run":
        paths += [
            str(p.relative_to(ROOT))
            for p in (ROOT / "tests/fixtures/human_design_semantics_v1").rglob("*")
            if p.is_file()
        ]
        paths += [
            "scripts/audit_human_design_semantics.py",
            "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json",
            "tests/test_human_design_semantic_binding.py",
            "tests/test_human_design_semantic_preparation.py",
            "tests/test_human_design_evaluation_runtime.py",
            "scripts/evaluate_agent.py",
            "src/fatebridge/diagnostics.py",
        ]
    calendar = astronomy_checks()
    physical = physical_astronomy_checks(ROOT)
    from scripts.check_human_design_calendar_span import checks as calendar_span_checks

    calendar_span_full = calendar_span_checks(ROOT)
    calendar_span = {
        **calendar_span_full,
        "backends": {
            key: {
                k: v
                for k, v in report.items()
                if k not in {"position_rows", "root_rows"}
            }
            for key, report in calendar_span_full["backends"].items()
        },
        "full_report_sha256": hashlib.sha256(
            (
                json.dumps(calendar_span_full, ensure_ascii=False, indent=2) + "\n"
            ).encode()
        ).hexdigest(),
        "projection_scope": "All failure rows and aggregate counts retained; passing row details are in the separately bound full seasonal report.",
    }
    cycles = independent_cycle_checks(ROOT)
    cycle_sources = cycle_source_checks()
    profile_facts = public_profile_checks(ROOT)
    arithmetic = check_opposition_arithmetic()
    historical = historical_utc_checks()
    ut1_context = ut1_context_checks()
    source = reference_table_audit()
    solar_roots = solar_root_resolution_checks()
    fixing_markers = fixing_marker_checks(ROOT)
    primary_fixing = primary_fixing_checks(ROOT)
    cycle_arithmetic = cycle_phase_arithmetic_checks()
    interval = interval_regression_check()
    nodes = node_astronomy_checks()
    bridges = bridge_oracle_checks()
    joint = joint_variant_regression_checks()
    transitions = transition_regression_checks()
    official = official_chart_checks(
        combine_official_chart_cohorts(
            *(
                json.loads((ROOT / "tests/fixtures" / filename).read_text())
                for filename in (
                    "human-design-official-charts.json",
                    "human-design-official-authority-charts.json",
                )
            )
        )
    )
    expanded_official = official_chart_checks(
        json.loads(
            (
                ROOT / "tests/fixtures/human-design-official-cross-charts.json"
            ).read_text()
        )
    )
    expanded_names = expanded_cross_audit()
    leap_labels = confirmed_leap_checks(ROOT)
    node_reports = node_comparison_regression_checks()
    sampled_interval = sampled_interval_regression_checks()
    from scripts.check_human_design_natal_sources import (
        regression_checks as natal_source_checks,
    )

    natal_sources = natal_source_checks()
    from scripts.check_human_design_native_state import (
        regression_checks as native_state_checks,
    )

    native_state = native_state_checks()
    from scripts.check_human_design_cycle_input import (
        ordinary_clock_checks,
    )
    from scripts.check_human_design_cycle_input import (
        regression_checks as cycle_input_checks,
    )

    cycle_input = cycle_input_checks()
    ordinary_clock = ordinary_clock_checks()
    from scripts.check_human_design_primary_diagrams import frozen_observation_check

    primary_diagrams = frozen_observation_check()
    requirements = [
        {
            "id": "bounded_two_public_primary_transcript_diagrams",
            "status": (
                "passed"
                if primary_diagrams["status"]
                == "bounded_two_unproofed_diagram_facts_matched"
                else "failed"
            ),
            "scope": primary_diagrams["scope"],
        },
        {
            "id": "bounded_cycle_request_clock_native_state_isolation",
            "status": (
                "passed"
                if cycle_input["status"]
                == "bounded_cycle_request_clock_isolation_passed"
                else "failed"
            ),
            "scope": cycle_input["scope"],
        },
        {
            "id": "complete_ordinary_civil_clock_record_consistency",
            "status": ordinary_clock["status"],
            "scope": ordinary_clock["scope"],
        },
        {
            "id": "bounded_dirty_parent_native_state_isolation",
            "status": (
                "passed"
                if native_state["status"] == "bounded_native_state_isolation_passed"
                else "failed"
            ),
            "scope": native_state["scope"],
        },
        {
            "id": "bounded_natal_root_interval_file_identity_consistency",
            "status": (
                "passed"
                if natal_sources["status"] == "bounded_natal_source_checks_passed"
                else "failed"
            ),
            "scope": natal_sources["scope"],
        },
        {
            "id": "served_finite_interval_scalar_replay_and_reading_fidelity",
            "status": (
                "passed"
                if sampled_interval["status"] == "bounded_interval_replay_passed"
                else "failed"
            ),
            "scope": sampled_interval["scope"],
        },
        {
            "id": "served_node_comparison_witness_and_reading_fidelity",
            "status": (
                "passed"
                if node_reports["status"] == "bounded_node_comparison_checks_passed"
                else "failed"
            ),
            "scope": node_reports["scope"],
        },
        {
            "id": "bounded_all27_published_leap_labels_against_sofa",
            "status": (
                "passed"
                if leap_labels["status"] == "bounded_81_sofa_labels_passed"
                else "failed"
            ),
            "scope": leap_labels["scope"],
        },
        {
            "id": "bounded_adjacent_float_solar_root_resolution",
            "status": (
                "passed"
                if solar_roots["status"] == "bounded_adjacent_float_root_passed"
                else "failed"
            ),
            "scope": solar_roots["scope"],
        },
        {
            "id": "bounded_cycle_file_context_identity_and_replay",
            "status": (
                "passed"
                if cycle_sources["status"] == "bounded_cycle_sources_verified"
                else "failed"
            ),
            "scope": cycle_sources["scope"],
        },
        {
            "id": "bounded_independent_first_cycle_contacts",
            "status": "passed" if cycles["bounded_acceptance_passed"] else "failed",
            "scope": cycles["scope"],
        },
        {
            "id": "bounded_multidecade_cycle_root_arithmetic",
            "status": (
                "passed"
                if cycle_arithmetic["status"] == "bounded_analytic_checks_passed"
                else "failed"
            ),
            "scope": "All 24 predeclared analytic roots and direct natal-relative residuals; original numerical thresholds retained. No physical timing or original source convention certificate.",
        },
        {
            "id": "original_cycle_origin_and_multiple_contact_priority",
            "status": "incomplete",
            "scope": "Captured primary definitions do not resolve Personality versus Design origin and first versus later retrograde-contact priority. No unique traditional phase assigned.",
        },
        {
            "id": "bounded_return_flag_and_model_policy_consistency",
            "status": (
                "passed"
                if provenance["status"] == "bounded_provenance_contradictions_rejected"
                else "failed"
            ),
            "scope": provenance["scope"],
        },
        {
            "id": "bounded_TT_UT1_context_policy_consistency",
            "status": (
                "passed"
                if ut1_context["status"] == "bounded_model_round_trip_passed"
                else "failed"
            ),
            "scope": ut1_context["scope"],
        },
        {
            "id": "bounded_observed_joint_transition_refinement",
            "status": (
                "passed"
                if transitions["status"] == "observed_transition_regression_passed"
                else "failed"
            ),
            "scope": transitions["scope"],
        },
        {
            "id": "bounded_public_circuit_group_memberships",
            "status": (
                "passed"
                if source["circuit_group_memberships"]["status"]
                == "bounded_public_group_membership_match"
                else "failed"
            ),
            "scope": source["circuit_group_memberships"]["scope"],
        },
        {
            "id": "bounded_public_profile_line_and_angle_facts",
            "status": (
                "passed"
                if profile_facts["status"] == "bounded_public_profile_facts_matched"
                else "failed"
            ),
            "scope": profile_facts["scope"],
        },
        {
            "id": "bounded_independent_full_target_positions_and_design_roots",
            "status": (
                "passed"
                if physical["selected"]["status"]
                == "bounded_independent_physical_checks_passed"
                and physical["horizons_reference_pipeline_anchors"]["status"]
                == "bounded_horizons_anchors_matched"
                else "failed"
            ),
            "scope": physical["scope"],
        },
        {
            "id": "bounded_coherent_joint_bridge_variants",
            "status": (
                "passed"
                if joint["status"] == "observed_joint_regression_passed"
                else "failed"
            ),
            "scope": joint["scope"],
        },
        {
            "id": "bounded_distinct_missing_gate_bridge_sets",
            "status": (
                "passed"
                if bridges["status"] == "declared_graph_cases_matched"
                else "failed"
            ),
            "scope": bridges["scope"],
        },
        {
            "id": "exact_opposition_sector_arithmetic",
            "status": (
                "passed"
                if arithmetic["status"] == "declared_arithmetic_probes_passed"
                else "failed"
            ),
            "scope": arithmetic["scope"],
        },
        {
            "id": "independent_1960_1971_historical_utc_epochs",
            "status": (
                "passed"
                if historical["status"] == "bounded_source_time_checks_passed"
                else "failed"
            ),
            "scope": historical["scope"],
        },
        {
            "id": "independent_physical_positions_and_replayed_88_degree_roots",
            "status": (
                "passed"
                if calendar["status"] == "bounded_reference_checks_passed"
                else "failed"
            ),
            "scope": "120 physical positions over selected 1900-2099 epochs and four independently observed solar-arc candidates, with current solver replay. Pre-1962 source labels are UT1, not UTC.",
        },
        {
            "id": "independent_osculating_node_positions_at_fixed_epochs",
            "status": (
                "passed"
                if nodes["selected"]["status"] == "bounded_node_reference_checks_passed"
                else "failed"
            ),
            "scope": "122 independently derived DE440/ERFA node positions, 1799-2399, at the predeclared 1 arcsecond threshold. Actual fallback flags and Moshier failures retained. Not a full-range error bound or official node-convention certificate.",
        },
        {
            "id": "bounded_official_rave_chart_examples",
            "status": (
                "passed"
                if official["status"] == "bounded_official_examples_matched"
                else "failed"
            ),
            "scope": "19 finite official charts: eight original winter inputs and 11 engine-selected branch inputs frozen before official output. 494 gate.lines, graph and displayed properties including newly checked literal cross names. 2001 variant numbers and spelling differences remain failures; no aliases, population benchmark or exhaustive certification.",
        },
        {
            "id": "bounded_official_chart_mechanics_without_name_equivalence",
            "status": (
                "passed"
                if official["charts_with_all_mechanics_matched"] == 19
                else "failed"
            ),
            "scope": "Only gate.lines, UTC, completed graph, Type/Authority/Definition/Profile/Cross angle and gates, and Variable in 19 charts; covers five displayed Types, eight authority IDs, 12 profiles, 16 Variable codes and three cross angles. Does not resolve the separately failed literal names or certify all possible charts.",
        },
        {
            "id": "full_supported_calendar_range_external_acceptance",
            "status": (
                "failed"
                if calendar_span["backends"]["selected"]["status"] == "failed"
                else "incomplete"
            ),
            "scope": "Selected epochs do not cover all 1800-2399 inputs, historical timezone records or all subdivision-critical ephemeris errors.",
        },
        {
            "id": "expanded_192_gate_angle_official_literal_conformance",
            "status": (
                "passed"
                if expanded_official["status"] == "bounded_official_examples_matched"
                and expanded_names["all_192_gate_angle_strata_observed"]
                else "failed"
            ),
            "scope": "Additional193 pre-frozen synthetic1980 inputs, all64 gates at3 angles and one extra quadruple definition. Literal2001 name comparison unchanged, including86 new failures. Earlier19 cases and15 failures remain separate and required. Not blind, whole-calendar, all-profiles-per-cross or full line-prose acceptance.",
        },
        {
            "id": "expanded_193_official_chart_mechanics",
            "status": (
                "passed"
                if expanded_official["charts_checked"]
                == expanded_official["charts_with_all_mechanics_matched"]
                == 193
                and expanded_names["all_192_gate_angle_strata_observed"]
                else "failed"
            ),
            "scope": "All5018 observed gate.lines, birth UTC, graph, five displayed Types, Authority/Definition/Profile/Cross angle and quartet, Variable and193 Strategy labels; includes4 quadruple definitions. Literal-name failures remain a separate failed requirement. No continuous range, real birth or prediction certification.",
        },
        {
            "id": "observed_birth_interval_interior_variation_regression",
            "status": (
                "passed"
                if interval["status"] == "observed_regression_passed"
                else "failed"
            ),
            "scope": "Observed interior Base variant missed by nominal/endpoints. Grid and station candidates remain non-exhaustive, not a full continuous stability proof.",
        },
        {
            "id": "complete_2001_source_numeric_consistency",
            "status": (
                "passed" if source["numeric_table_acceptance_passed"] else "failed"
            ),
            "scope": "Printed 29.1/29.2 boundary conflict remains visible; references are not rewritten.",
        },
        {
            "id": "bounded_channel_classification_consistency",
            "status": (
                "passed"
                if source["channel_classifications"]["status"]
                == "bounded_public_source_match"
                else "failed"
            ),
            "scope": "Six directly stated official channel classifications and 30 weaker inferences from matching 2001 endpoint gate labels. Not independent certification of all 36 circuit assignments.",
        },
        {
            "id": "bounded_visible_official_fixing_polarities",
            "status": (
                "passed"
                if fixing_markers["status"] == "bounded_visible_marker_match"
                else "failed"
            ),
            "scope": "All 19 unchanged official PDFs, 494 rendered slots and 138 visible polarities, including 11 node recipients. Blank glyphs do not independently certify complete fixing states or line prose.",
        },
        {
            "id": "bounded_archival_channel_page_observations",
            "status": (
                "passed"
                if source["archival_channel_pages"]["channels_checked"]
                == source["archival_channel_pages"]["channels_matched"]
                == 36
                and source["archival_channel_pages"]["source_pair_sets_equal"]
                and source["archival_channel_pages"]["ocr_digit_disagreements_retained"]
                == 2
                and all(
                    d["endpoint_observation_reproduced"] and not d["resolved"]
                    for d in source["archival_channel_pages"][
                        "source_label_disagreements"
                    ]
                )
                else "failed"
            ),
            "scope": "Seven visually reviewed lists in the attributed 1996 archival scan, all36 channel assignments; original OCR and conflicting Defense motor heading retained. Publisher master authenticity and whole-book semantic consistency are not certified.",
        },
        {
            "id": "complete_source_reading_and_fixing_acceptance",
            "status": "incomplete",
            "scope": "Factual identifiers/polarities,19 original and193 new official charts,138 original visible fixing polarities and36 archival channel assignments. All192 gate/angle strata and4 quadruple definitions observed. Source conflicts,86 new literal-name failures and blank-glyph limitations retained. Publisher master authenticity, full line prose, all fixing rules, every profile per cross and broader acceptance remain unproven.",
        },
        {
            "id": "served_fixed_template_reading_fidelity",
            "status": (
                "passed"
                if reading_check["status"] == "verified_fixed_template_reading"
                else "failed"
            ),
            "scope": "Exact served text, typed citations and internal derivations in a complete current run.",
        },
        {
            "id": "live_model_consultation_fidelity",
            "status": live_model_requirement_status(live_models),
            "scope": "Original full live-model fidelity requirement retained. Eight known development first answers are now reviewed, with both PATH infrastructure failures preserved; no independent holdout, arbitrary-free-text or384line certification follows from a bounded run or quote binding.",
        },
    ]
    professional_passed = all(item["status"] == "passed" for item in requirements)
    return {
        "method_id": "human_design_four_axis_evidence_v1",
        "bounded_live_model_development": live_models,
        "scope": "Finite evidence report; no aggregate authority or prediction score.",
        "calendar": calendar,
        "confirmed_utc_leap_labels": leap_labels,
        "node_comparison_witness_fidelity": node_reports,
        "solar_root_resolution": solar_roots,
        "cycle_phase_arithmetic": cycle_arithmetic,
        "independent_physical_design_reference": physical,
        "independent_first_cycle_contacts": cycles,
        "cycle_source_identity": cycle_sources,
        "public_profile_facts": profile_facts,
        "publisher_preview_natal_example": publisher_natal_checks(ROOT),
        "opposition_arithmetic": arithmetic,
        "historical_utc": historical,
        "ut1_context": ut1_context,
        "provenance_regression": provenance,
        "node_astronomy": nodes,
        "official_chart_examples": official,
        "expanded_official_chart_examples": expanded_official,
        "expanded_official_cross_names": expanded_names,
        "definition_bridge_examples": bridges,
        "joint_variant_regression": joint,
        "joint_transition_regression": transitions,
        "birth_time_interval": interval,
        "professional_acceptance": {
            "requested_axes": [
                "calendar",
                "source_fidelity",
                "interpretation_fidelity",
            ],
            "requirements": requirements,
            "all_three_axes_full_marks": professional_passed,
            "status": "achieved" if professional_passed else "not_achieved",
        },
        "source_fidelity": {
            **reference_table_audit(),
            "official_visible_fixing_markers": fixing_markers,
            "source_version_diagnostics": source_variant_audit(),
            "official_example": {
                "count": 1,
                "gate_lines_checked": 26,
                "gate_lines_matched": matches,
                "birth_input_status": example["nominal_birth_input_status"],
                "scope": example["scope"],
                "source": example["source"],
                "fixing_arrows_checked": len(source_arrows),
                "fixing_arrow_sets_equal": source_arrows == computed_arrows,
            },
            "depth_catalogue": {
                "gate_identifiers": len(catalogue["gates"]),
                "cross_identifiers": sum(
                    len(row["cross_identifiers"]) for row in catalogue["gates"]
                ),
                "line_polarity_records": sum(
                    len(row["line_polarities"]) for row in catalogue["gates"]
                ),
                "dual_polarity_records": sum(
                    line["polarity_kind"] == "dual"
                    for row in catalogue["gates"]
                    for line in row["line_polarities"]
                ),
                "source_pdf_sha256": catalogue["source"]["pdf_sha256"],
                "full_independent_semantic_review": False,
            },
            "target": "Ra Uru Hu, The Complete Rave I'Ching, 2001 numeric tables; Jovian Archive 2016 handbook and public mechanics pages",
            "outstanding": [
                "Resolve the printed 29.1/29.2 boundary discrepancy without changing the frozen source",
                "Resolve or explicitly version the 15 observed cross-name differences between unchanged 2001 identifiers and the current official calculator without erasing original text",
                "Broader acceptance beyond19 original and193 new finite inputs: all192 gate/angle strata and4 quadruple definitions observed, but not every profile per cross, continuous range or all source interpretation; engine-selected synthetic clocks are not a blind population or authenticated real birth records",
                "Verified node convention of the reference software",
                "Independent channel-page acceptance beyond six direct classifications; 30 endpoint-label inferences retain their weaker evidence status",
                "Complete independent acceptance of line meanings and fixing rules beyond the supported public natal rule",
            ],
        },
        "interpretation": {
            "status": "structured_field_grounding_implemented",
            "free_text_semantics_certified": False,
            "live_model_behavior_acceptance": (
                "bounded_development_reviewed_full_acceptance_incomplete"
                if live_models["status"] != "not_run"
                else "not_run"
            ),
            "mechanism": "Deterministic paraphrases, completed-channel connection witnesses, ordered authority-center checks and same-run typed claims; graph paths and source metadata are rebuilt during verification. References are not truth certificates.",
            "fixed_template_reading_verification": reading_check,
        },
        "prediction": {
            "status": "not_tested",
            "real_world_sample_size": 0,
            "registered_prediction_rule": None,
            "authority_certified": False,
            "required_evidence": [
                "A falsifiable preregistered forecasting rule with a fixed population and target",
                "External timestamped predictions before outcomes; untouched holdout and fixed baselines",
                "Independent outcomes, uncertainty intervals, full coverage, leakage checks and replication",
            ],
        },
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "sampled_interval_regression": sampled_interval,
        "natal_source_regression": natal_sources,
        "native_state_regression": native_state,
        "cycle_request_clock_regression": cycle_input,
        "ordinary_clock_record_regression": ordinary_clock,
        "primary_transcript_diagram_observation": primary_diagrams,
        "primary_2024_written_fixing_examples": primary_fixing,
        "additional_calendar_span_external_reference": calendar_span,
        "fingerprints": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in dict.fromkeys([*paths, *human_design_input_paths(ROOT)])
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-acceptance", action="store_true")
    parser.add_argument(
        "--require-professional-acceptance",
        action="store_true",
        help="Require all three requested professional axes; reality prediction remains a separate record",
    )
    args = parser.parse_args()
    result = build_report()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    print(
        json.dumps(
            {
                "all_three_axes_full_marks": result["professional_acceptance"][
                    "all_three_axes_full_marks"
                ],
                **{
                    key: result[key]
                    for key in ("all_four_axes_full_marks", "authority_certified")
                },
            },
            ensure_ascii=False,
        )
    )
    return int(
        result["calendar"]["status"] == "failed"
        or result["additional_calendar_span_external_reference"]["status"] == "failed"
        or result["primary_2024_written_fixing_examples"]["status"] == "failed"
        or args.require_full_acceptance
        and not result["all_four_axes_full_marks"]
        or args.require_professional_acceptance
        and not result["professional_acceptance"]["all_three_axes_full_marks"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
