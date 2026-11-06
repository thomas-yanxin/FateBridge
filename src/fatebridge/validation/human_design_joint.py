"""Check local joint-variant mathematics without certifying its TT witness."""

from typing import Any

from fatebridge.core.human_design_depth import cross_identifier
from fatebridge.core.human_design_joint import (
    EXPECTED_BODIES,
    SIDES,
    VARIABLE_BODIES,
    JointSnapshotCache,
    joint_changes,
    joint_evidence_summary,
)
from fatebridge.core.human_design_mechanics import GATE_ORDER, VALID_PROFILES, bodygraph
from fatebridge.core.public_output import same_public_value as _same_value
from fatebridge.validation.human_design_transition import verify_transition_trace


def verify_joint_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Rebuild local mathematics; TT-to-position authenticity remains unproven."""
    errors: list[str] = []
    try:
        activations = snapshot["activations"]
        if set(activations) != set(SIDES) or any(
            len(activations[s]) != 13
            or {a["body"] for a in activations[s]} != EXPECTED_BODIES
            for s in SIDES
        ):
            raise ValueError("incomplete_activation_projection")
        for side, rows in activations.items():
            for row in rows:
                if any(
                    type(row[k]) is not int or not 1 <= row[k] <= limit
                    for k, limit in (("gate", 64), ("line", 6))
                ):
                    raise ValueError("invalid_gate_line_projection")
                if row["body"] in VARIABLE_BODIES and (
                    type(row.get("tone")) is not int or not 1 <= row["tone"] <= 6
                ):
                    raise ValueError("invalid_variable_tone_projection")
                if (
                    side == "personality"
                    and row["body"] in VARIABLE_BODIES
                    and (
                        type(row.get("color")) is not int or not 1 <= row["color"] <= 6
                    )
                ):
                    raise ValueError("invalid_personality_color_projection")
        for side in SIDES:
            bodies = {a["body"]: a for a in activations[side]}
            for source, opposite in (("Sun", "Earth"), ("NorthNode", "SouthNode")):
                a, b = bodies[source], bodies[opposite]
                if (
                    b["gate"] != GATE_ORDER[(GATE_ORDER.index(a["gate"]) + 32) % 64]
                    or a["line"] != b["line"]
                    or a["tone"] != b["tone"]
                    or (side == "personality" and a["color"] != b["color"])
                ):
                    raise ValueError("inconsistent_opposition_projection")
        suns = {s: next(a for a in activations[s] if a["body"] == "Sun") for s in SIDES}
        profile = f"{suns['personality']['line']}/{suns['design']['line']}"
        if profile not in VALID_PROFILES:
            raise ValueError("invalid_profile_projection")
        angle = (
            "juxtaposition"
            if profile == "4/1"
            else "right" if suns["personality"]["line"] <= 4 else "left"
        )
        cross = {
            "gates": [
                next(a["gate"] for a in activations[s] if a["body"] == b)
                for s, b in (
                    ("personality", "Sun"),
                    ("personality", "Earth"),
                    ("design", "Sun"),
                    ("design", "Earth"),
                )
            ],
            "order": [
                "personality_sun",
                "personality_earth",
                "design_sun",
                "design_earth",
            ],
            "angle": angle,
            **cross_identifier(suns["personality"]["gate"], angle),
        }
        reconstructed = {
            "activations": activations,
            "bodygraph": bodygraph(
                (a["gate"] for a in activations["personality"]),
                (a["gate"] for a in activations["design"]),
            ),
            "profile": profile,
            "incarnation_cross": cross,
        }
        expected = JointSnapshotCache().snapshot(reconstructed)
        if not _same_value(snapshot, expected):
            errors.append("joint_snapshot_derivation_mismatch")
    except (KeyError, TypeError, ValueError, StopIteration, IndexError, AttributeError):
        errors.append("incomplete_or_invalid_joint_snapshot")
    return {
        "status": "verified_local_snapshot_mechanics" if not errors else "rejected",
        "errors": errors,
        "astronomical_witness_certified": False,
        "scope": "仅核对本快照的门线/Tone投影及数学派生，不认证该联合状态真实出现于声称的TT时刻，也不认证完整原典或预测效力。",
    }


def verify_run_joint_snapshots(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    checked = 0
    nominal = JointSnapshotCache().snapshot(payload)

    def check(snapshot: dict[str, Any], path: str) -> None:
        nonlocal checked
        checked += 1
        if (
            verify_joint_snapshot(snapshot)["status"]
            != "verified_local_snapshot_mechanics"
        ):
            errors.append({"code": "joint_snapshot_derivation_mismatch", "path": path})

    def pair(report: dict[str, Any], path: str, comparison: dict[str, Any]) -> None:
        selected, reference = (
            report["selected_structure"],
            report["reference_structure"],
        )
        check(selected, path + ".selected_structure")
        check(reference, path + ".reference_structure")
        if not _same_value(selected, nominal):
            errors.append({"code": "joint_selected_snapshot_mismatch", "path": path})
        for side in SIDES:
            expected = [
                a
                for a in nominal["activations"][side]
                if a["body"] not in {"NorthNode", "SouthNode"}
            ]
            actual = [
                a
                for a in reference["activations"][side]
                if a["body"] not in {"NorthNode", "SouthNode"}
            ]
            if not _same_value(expected, actual):
                errors.append(
                    {
                        "code": "node_only_comparison_changed_other_activations",
                        "path": path,
                    }
                )
        for key, value in joint_changes(selected, reference).items():
            if not _same_value(comparison.get(key), value):
                errors.append(
                    {
                        "code": "joint_comparison_derivation_mismatch",
                        "path": path + "." + key,
                    }
                )
        if not _same_value(
            report.get("joint_evidence_summary"),
            comparison.get("joint_evidence_summary"),
        ):
            errors.append({"code": "joint_comparison_summary_mismatch", "path": path})

    try:
        convention = payload["node_convention_comparison"]
        pair(convention, "node_convention_comparison", convention)
        backend = payload["node_backend_comparison"]
        if (
            backend["status"]
            not in {
                "cross_backend_compared",
                "same_backend_not_independent",
                "analytic_mean_node_not_cross_validated",
                "reference_unavailable",
                "reference_disabled_by_strict_jpl_policy",
            }
            or backend["independent_astronomy_certified"] is not False
            or backend["subdivision_accuracy_certified"] is not False
        ):
            errors.append(
                {
                    "code": "invalid_joint_backend_status_or_certification",
                    "path": "node_backend_comparison",
                }
            )
        if backend["status"] == "reference_disabled_by_strict_jpl_policy" and (
            payload["calculation_policy"].get("physical_backend_policy") != "strict_jpl"
            or backend.get("reference_computation_performed") is not False
            or backend.get("unavailable_reason") != "jpl_mixed_request"
        ):
            errors.append(
                {
                    "code": "invalid_disabled_backend_policy",
                    "path": "node_backend_comparison",
                }
            )
        if backend["status"] in {
            "cross_backend_compared",
            "same_backend_not_independent",
        }:
            pair(backend, "node_backend_comparison", backend["mechanical_comparison"])
        interval = payload["time_sensitivity"]
        if interval["status"] not in {
            "not_assessed",
            "grid_and_station_candidates_compared",
        }:
            errors.append(
                {"code": "invalid_joint_interval_status", "path": "time_sensitivity"}
            )
        if (
            interval["status"] == "not_assessed"
            and interval.get("joint_evidence_summary") is not None
        ):
            errors.append(
                {
                    "code": "unassessed_interval_has_joint_claim",
                    "path": "time_sensitivity",
                }
            )
        if interval["status"] == "not_assessed" and (
            interval.get("joint_transition_refinement") is not None
            or interval.get("joint_transition_refinement_summary") is not None
        ):
            errors.append(
                {
                    "code": "unassessed_interval_has_transition_claim",
                    "path": "time_sensitivity",
                }
            )
        if interval["status"] != "not_assessed":
            if interval["sampling"]["continuous_interval_certified"] is not False:
                errors.append(
                    {
                        "code": "invented_continuous_interval_certification",
                        "path": "time_sensitivity.sampling",
                    }
                )
            variants = interval["classification_variants"]
            if not variants:
                errors.append(
                    {"code": "missing_joint_variants", "path": "time_sensitivity"}
                )
            changed: set[str] = set()
            has_nominal = False
            lo, hi = (interval["interval"][k]["birth_jd_tt"] for k in ("start", "end"))
            for index, row in enumerate(variants):
                path = f"time_sensitivity.classification_variants.{index}"
                value = row["value"]
                check(value, path + ".value")
                witness = row["first_observed_witness"]
                if (
                    not lo <= witness["birth_jd_tt"] <= hi
                    or not witness["design_jd_tt"] < witness["birth_jd_tt"]
                ):
                    errors.append(
                        {
                            "code": "joint_witness_outside_declared_interval",
                            "path": path,
                        }
                    )
                has_nominal |= _same_value(value, nominal)
                changed.update(
                    k for k, v in value.items() if not _same_value(v, nominal.get(k))
                )
            if (
                not has_nominal
                or sorted(changed) != interval["observed_changed_structure_fields"]
            ):
                errors.append(
                    {
                        "code": "joint_interval_summary_mismatch",
                        "path": "time_sensitivity",
                    }
                )
            if not _same_value(
                interval.get("joint_evidence_summary"),
                joint_evidence_summary(nominal, variants),
            ):
                errors.append(
                    {
                        "code": "joint_evidence_summary_mismatch",
                        "path": "time_sensitivity.joint_evidence_summary",
                    }
                )
            radius = interval["plus_minus_minutes"]
            transition = interval["joint_transition_refinement"]
            if (
                type(radius) is not int
                or not 1 <= radius <= 60
                or interval["interval"]["radius_seconds"] != radius * 60
                or not _same_value(
                    interval["joint_transition_refinement_summary"],
                    transition["summary"],
                )
                or verify_transition_trace(
                    transition,
                    variants,
                    interval["sampling"],
                    payload["time_scales"]["personality"]["jd_tt"],
                    radius * 60,
                    10,
                )["status"]
                != "verified_local_refinement_trace"
            ):
                errors.append(
                    {
                        "code": "invalid_joint_transition_refinement",
                        "path": "time_sensitivity.joint_transition_refinement",
                    }
                )
            if len(interval["comparisons"]) != 2:
                errors.append(
                    {
                        "code": "missing_joint_endpoint_snapshots",
                        "path": "time_sensitivity.comparisons",
                    }
                )
            for index, row in enumerate(interval["comparisons"]):
                path = f"time_sensitivity.comparisons.{index}"
                check(row["snapshot"], path + ".snapshot")
                if row["witness"]["birth_jd_tt"] != (lo if index == 0 else hi):
                    errors.append(
                        {"code": "joint_endpoint_witness_mismatch", "path": path}
                    )
                for key, value in joint_changes(nominal, row["snapshot"]).items():
                    if not _same_value(row.get(key), value):
                        errors.append(
                            {
                                "code": "joint_endpoint_comparison_mismatch",
                                "path": path + "." + key,
                            }
                        )
    except (KeyError, TypeError, ValueError, StopIteration, IndexError, AttributeError):
        errors.append({"code": "incomplete_joint_variant_report"})
    return {
        "checked_snapshot_count": checked,
        "errors": errors,
        "astronomical_witness_certified": False,
    }
