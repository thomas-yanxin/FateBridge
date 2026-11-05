"""Current independent numeric and source checks, without historical code replay.

This report keeps physical, arithmetic and local-witness validation separate.
It does not accept complete original teaching or real-world prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tempfile import TemporaryDirectory

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time, tt_from_ut1
from fatebridge.core.human_design import (
    chart_at,
    chart_at_tt,
    longitude_activation,
    planetary_positions,
)
from fatebridge.core.human_design_bridging import definition_bridging
from fatebridge.core.human_design_cycles import derive_body_contacts
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_mechanics import bodygraph
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.core.human_design_time import (
    epoch_context_at_tt,
    solve_design_epoch,
    solve_solar_root,
)
from fatebridge.validation.human_design_joint import verify_joint_snapshot
from fatebridge.validation.human_design_transition import verify_transition_trace

ROOT = Path(__file__).resolve().parents[1]


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
    """Recalculate given endpoint inputs and check independently enumerated graph sets."""
    case_path = ROOT / "tests/data/human_design/joint-variant-inputs.json"
    reference_path = ROOT / "tests/data/human_design/joint_bridge/reference.json"
    case = json.loads(case_path.read_text())
    reference = json.loads(reference_path.read_text())
    plan_path = ROOT / reference["plan_path"]
    plan = json.loads(plan_path.read_text())
    for path, expected in (
        (plan_path, reference["plan_sha256"]),
        (ROOT / reference["oracle_source_path"], reference["oracle_source_sha256"]),
        (ROOT / reference["source_table_path"], reference["source_table_sha256"]),
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
        with _moshier_reference_context():
            endpoint = chart_at_tt(case["endpoint_jd_tt"][side], backend="moshier")
        witness = JointSnapshotCache().snapshot(endpoint)
        gates = witness["activated_gates"]
        subsets = sum(
            math.comb(64 - len(gates), k)
            for k in range(expected["minimum_added_gate_count"] + 1)
        )
        actual = report["comparisons"][0 if side == "left" else 1]["snapshot"]
        endpoint_rows.append(
            {
                "id": side,
                "matched": input_case["activated_gates"] == gates
                and actual["activations"] == witness["activations"]
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


def transition_regression_checks() -> dict:
    case_path = ROOT / "tests/data/human_design/transition-inputs.json"
    case = json.loads(case_path.read_text())
    with _moshier_reference_context():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]))
        report = assess_birth_interval(nominal, case["plus_minus_minutes"], "true")
        witnesses = {
            label: chart_at_tt(tt, backend="moshier")
            for label, tt in case["given_witness_jd_tt"].items()
        }
    variants = report.get("classification_variants", [])
    cache = JointSnapshotCache()
    variant_keys = {cache.key(row["value"]) for row in variants}
    recovered_witnesses = {
        label: cache.key(chart) in variant_keys for label, chart in witnesses.items()
    }
    recovered = recovered_witnesses["missed"]
    solver_brackets = {
        label: chart["design_solver"]["bracket_width_seconds"]
        for label, chart in witnesses.items()
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
        all(recovered_witnesses.values())
        and all(width <= 0.0002 for width in solver_brackets.values())
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
        "current_joint_variant_count": len(variants),
        "missed_witness_recovered": recovered,
        "current_given_witnesses_recovered": recovered_witnesses,
        "current_design_solver_bracket_seconds": solver_brackets,
        "existing_solver_bracket_seconds": 0.0002,
        "refinement_summary": report.get("joint_transition_refinement_summary"),
        "trace_verification": trace,
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
    from fatebridge.validation.human_design_arithmetic import (
        check_opposition_arithmetic,
    )
    from fatebridge.validation.human_design_astronomy import physical_astronomy_checks
    from fatebridge.validation.human_design_leap import confirmed_leap_checks

    report = {
        "method_id": "human_design_current_numeric_audit_v1",
        "physical_astronomy": physical_astronomy_checks(ROOT),
        "opposition_arithmetic": check_opposition_arithmetic(),
        "cycle_phase_arithmetic": cycle_phase_arithmetic_checks(),
        "solar_root_resolution": solar_root_resolution_checks(),
        "historical_utc": historical_utc_checks(),
        "confirmed_leap_labels": confirmed_leap_checks(ROOT),
        "node_astronomy": node_astronomy_checks(),
        "source_completeness": "bounded_current_reference_cases_only",
        "original_source_acceptance": False,
        "interpretation_acceptance": False,
        "prediction_acceptance": False,
        "scope": "Current numeric/source checks and all recorded model failures; no historical implementation replays, continuous completeness, full original-source or real-world predictive certification.",
    }

    checks = [
        report["physical_astronomy"]["selected"],
        *[
            report[k]
            for k in (
                "opposition_arithmetic",
                "cycle_phase_arithmetic",
                "solar_root_resolution",
                "historical_utc",
                "confirmed_leap_labels",
                "node_astronomy",
            )
        ],
    ]
    report["current_numeric_checks_passed"] = all(
        c["status"] not in {"failed", "not_verified"} for c in checks
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-professional-acceptance", action="store_true")
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return (
        1
        if args.require_professional_acceptance
        or not report["current_numeric_checks_passed"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
