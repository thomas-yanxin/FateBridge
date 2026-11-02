"""Missed real bridge family variation, coherent local paths and false summaries."""

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import chart_at_tt
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_sensitivity import (
    assess_birth_interval,
    compare_charts,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_joint import verify_joint_snapshot
from tests.golden.runner import golden_ephemeris

ROOT = Path(__file__).resolve().parents[1]
CASE = json.loads(
    (ROOT / "tests/fixtures/human-design-joint-variant-case.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


def legacy_structure(chart):
    return {
        **{
            k: chart["bodygraph"][k]
            for k in (
                "type",
                "subtype",
                "authority",
                "strategy",
                "definition",
                "channels",
            )
        },
        "profile": chart["profile"],
        "incarnation_cross": chart["incarnation_cross"],
        "variables": {k: chart["variables"][k] for k in ("status", "code")},
    }


def test_real_old_projection_collapses_two_distinct_minimum_bridge_families():
    a, b = CASE["left"], CASE["right"]
    assert legacy_structure(a) == legacy_structure(b)
    assert CASE["old_classification_variant_count"] == 1
    assert CASE["old_observed_changed_structure_fields"] == []
    changes = compare_charts(a, b, include_snapshots=True)
    assert changes["changed_classifications"] == []
    assert changes["variable_changed"] is False
    assert changes["minimum_bridge_count_changed"] is False
    assert changes["minimum_bridge_sets_changed"] is True
    assert (
        changes["selected_structure"]["definition_bridging"]["minimum_solution_count"]
        == 8
    )
    assert (
        changes["reference_structure"]["definition_bridging"]["minimum_solution_count"]
        == 8
    )
    assert changes["line_fixing_changes"]
    assert all(
        verify_joint_snapshot(changes[k])["status"]
        == "verified_local_snapshot_mechanics"
        for k in ("selected_structure", "reference_structure")
    )


def test_actual_interval_keeps_coherent_joint_evidence_and_replayable_witnesses():
    with golden_ephemeris():
        from fatebridge.core.human_design import chart_at

        nominal = chart_at(datetime.fromisoformat(CASE["nominal_birth_utc"]))
        report = assess_birth_interval(nominal, 10, "true")
        assert len(report["classification_variants"]) >= 2
        assert {"definition_bridging", "depth_evidence", "activations"} <= set(
            report["observed_changed_structure_fields"]
        )
        assert report["joint_evidence_summary"]["bridge_families_changed"] is True
        assert (
            report["joint_evidence_summary"]["bridge_minimum_gate_count_changed"]
            is False
        )
        cache = report["joint_evidence_cache"]
        assert cache["distinct_gate_union_bridge_calculations"] == 2
        assert cache["distinct_gate_line_depth_calculations"] == 2
        assert (
            cache["distinct_mechanical_projections"]
            < report["sampling"]["grid_sample_count"]
        )
        families = set()
        for row in report["classification_variants"]:
            value = row["value"]
            witness = row["first_observed_witness"]
            replay = chart_at_tt(witness["birth_jd_tt"])
            assert value == JointSnapshotCache().snapshot(replay)
            assert witness["design_jd_tt"] == replay["time_scales"]["design"]["jd_tt"]
            assert (
                verify_joint_snapshot(value)["status"]
                == "verified_local_snapshot_mechanics"
            )
            families.add(
                tuple(
                    tuple(x["added_gates"])
                    for x in value["definition_bridging"]["minimum_solutions"]
                )
            )
        assert len(families) == 2
        assert report["sampling"]["continuous_interval_certified"] is False


def test_gate_line_and_variable_paths_resolve_within_each_snapshot():
    value = JointSnapshotCache().snapshot(CASE["left"])
    for fix in value["depth_evidence"]["line_fixings"]:
        _, side, index = fix["calculation_path"].split(".")
        row = value["activations"][side][int(index)]
        assert (row["body"], row["gate"], row["line"]) == (
            fix["body"],
            fix["gate"],
            fix["line"],
        )
        for triggers in fix["fixing_planets"].values():
            for trigger in triggers:
                _, side, index = trigger["calculation_path"].split(".")
                donor = value["activations"][side][int(index)]
                assert (donor["body"], donor["gate"], donor["line"]) == (
                    trigger["body"],
                    trigger["gate"],
                    trigger["line"],
                )
    for arrow in value["variables"]["arrows"]:
        for basis in arrow["basis"]:
            _, side, index, field = basis["path"].split(".")
            assert value["activations"][side][int(index)][field] == basis["value"]


def test_cache_is_local_and_does_not_collapse_typed_invalid_tones():
    cache = JointSnapshotCache()
    a = deepcopy(CASE["left"])
    first = cache.snapshot(a)
    b = deepcopy(a)
    sun = next(r for r in b["activations"]["personality"] if r["body"] == "Sun")
    sun["tone"] = True
    invalid = cache.snapshot(b)
    assert len(cache.snapshots) == 2
    assert invalid["variables"]["status"] == "incomplete_or_inconsistent"
    first["definition_bridging"]["minimum_solutions"].clear()
    assert (
        JointSnapshotCache().snapshot(a)["definition_bridging"][
            "minimum_solution_count"
        ]
        == 8
    )
    assert (
        len(
            JointSnapshotCache().snapshot(a)["definition_bridging"]["minimum_solutions"]
        )
        == 8
    )


@pytest.mark.parametrize(
    "bad",
    [
        "gate",
        "line",
        "tone",
        "opposition",
        "bridge",
        "fixing",
        "basis",
        "profile",
        "unknown",
    ],
)
def test_snapshot_corruption_is_rejected_without_a_position_oracle(bad):
    value = deepcopy(JointSnapshotCache().snapshot(CASE["left"]))
    if bad == "gate":
        value["activations"]["personality"][0]["gate"] = True
    elif bad == "line":
        value["activations"]["personality"][0]["line"] = 7
    elif bad == "tone":
        value["activations"]["personality"][0]["tone"] = True
    elif bad == "opposition":
        next(a for a in value["activations"]["personality"] if a["body"] == "Earth")[
            "gate"
        ] = 1
    elif bad == "bridge":
        value["definition_bridging"]["minimum_solutions"].pop()
    elif bad == "fixing":
        value["depth_evidence"]["line_fixings"][0]["status"] = "invented"
    elif bad == "basis":
        value["variables"]["arrows"][0]["basis"][0]["value"] = True
    elif bad == "profile":
        value["profile"] = "6/3"
    else:
        value["unreviewed_claim"] = "These gates forecast reality."
    check = verify_joint_snapshot(value)
    assert check["status"] == "rejected"
    assert check["astronomical_witness_certified"] is False


@pytest.fixture(scope="module")
def complete_joint_run():
    with golden_ephemeris():
        return execute_tool(SPEC, SPEC.request_model(**CASE["birth_input"]))


def test_complete_run_checks_all_joint_snapshots(complete_joint_run):
    check = verify_human_design_reading(complete_joint_run)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_joint_snapshot_count"] >= 7


@pytest.mark.parametrize(
    "bad",
    [
        "interval_family",
        "interval_summary",
        "interval_certification",
        "endpoint",
        "convention_non_node",
        "backend_family",
        "backend_summary",
    ],
)
def test_fresh_hash_does_not_certify_corrupted_joint_context(complete_joint_run, bad):
    value = deepcopy(complete_joint_run)
    if bad == "interval_family":
        value["time_sensitivity"]["classification_variants"][0]["value"][
            "definition_bridging"
        ]["minimum_solutions"].pop()
    elif bad == "interval_summary":
        value["time_sensitivity"]["joint_evidence_summary"][
            "bridge_families_changed"
        ] = False
    elif bad == "interval_certification":
        value["time_sensitivity"]["sampling"]["continuous_interval_certified"] = True
    elif bad == "endpoint":
        value["time_sensitivity"]["comparisons"][0]["minimum_bridge_sets_changed"] = (
            not value["time_sensitivity"]["comparisons"][0][
                "minimum_bridge_sets_changed"
            ]
        )
    elif bad == "convention_non_node":
        value["node_convention_comparison"]["reference_structure"]["activations"][
            "personality"
        ][2]["gate"] = 1
    elif bad == "backend_family":
        value["node_backend_comparison"]["reference_structure"]["definition_bridging"][
            "minimum_solutions"
        ].pop()
    else:
        value["node_backend_comparison"]["joint_evidence_summary"][
            "minimum_bridge_sets_changed"
        ] = True
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"


def test_regression_endpoint_families_match_separate_exhaustive_c_oracle():
    import hashlib
    import math

    ref = json.loads(
        (ROOT / "tests/fixtures/human-design-joint-bridge-oracle.json").read_text()
    )
    plan = json.loads((ROOT / ref["plan_path"]).read_text())
    assert (
        hashlib.sha256((ROOT / ref["plan_path"]).read_bytes()).hexdigest()
        == ref["plan_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / ref["oracle_source_path"]).read_bytes()).hexdigest()
        == ref["oracle_source_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / ref["source_table_path"]).read_bytes()).hexdigest()
        == ref["source_table_sha256"]
    )
    assert (
        hashlib.sha256(
            (ROOT / "scripts/build_human_design_bridge_reference.py").read_bytes()
        ).hexdigest()
        == ref["generator_sha256"]
    )
    assert sum(r["candidate_subsets_checked"] for r in ref["cases"]) == 1982
    for selected, expected in zip(plan["cases"], ref["cases"]):
        assert selected["id"] == expected["id"]
        chart = CASE[selected["id"]]
        assert selected["activated_gates"] == chart["bodygraph"]["activated_gates"]
        actual = JointSnapshotCache().snapshot(chart)["definition_bridging"]
        assert [r["added_gates"] for r in actual["minimum_solutions"]] == expected[
            "minimum_sets"
        ]
        assert (
            actual["minimum_added_gate_count"]
            == expected["minimum_added_gate_count"]
            == 2
        )
        assert len(expected["minimum_sets"]) == 8
        assert expected["candidate_subsets_checked"] == sum(
            math.comb(64 - len(selected["activated_gates"]), k) for k in range(3)
        )


def test_audit_does_not_accept_omitted_joint_family_variation(monkeypatch):
    from scripts import audit_human_design as audit

    original = audit.assess_birth_interval

    def omitted(*args, **kwargs):
        result = original(*args, **kwargs)
        result["joint_evidence_summary"]["bridge_families_changed"] = False
        return result

    assert (
        audit.joint_variant_regression_checks()["status"]
        == "observed_joint_regression_passed"
    )
    monkeypatch.setattr(audit, "assess_birth_interval", omitted)
    assert audit.joint_variant_regression_checks()["status"] == "failed"
