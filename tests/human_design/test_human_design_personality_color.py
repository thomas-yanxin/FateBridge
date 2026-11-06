"""Independent taxonomy facts, real lost-Color cases and source-bound replays."""

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design import bodygraph
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_personality_color import personality_colors
from fatebridge.core.human_design_transition import (
    changed_dependencies,
    dependency_projection,
)
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_joint import verify_joint_snapshot

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-personality-color-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.fixture(scope="module")
def source_runs():
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        env.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return {
            case["id"]: {
                mode: execute_tool(
                    SPEC, SPEC.request_model(**case["input"], node_mode=mode)
                )
                for mode in ("true", "mean")
            }
            for case in PLAN["cases"]
        }


def forbidden(*args, **kwargs):
    raise AssertionError("Pure Color verification called native producer")


def test_original_lost_projection_and_independent_taxonomy_are_frozen():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "92a8abe35757f99e04ed0896f4595c2345f09607b22a5df0794fd37020965aa6"
    )
    p = ROOT / "src/fatebridge/data/human_design/personality-color-reference.json"
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == PLAN["source_catalog_sha256"]
        == "71005fa44011da9fa63b12a790b171ba2e562969816b9b5544e4da5532a256ec"
    )
    ref = json.loads(p.read_text())
    assert [r["source_term"] for r in ref["categories"]["motivation"]] == [
        "Fear",
        "Hope",
        "Desire",
        "Need",
        "Guilt",
        "Innocence",
    ]
    assert [r["source_term"] for r in ref["categories"]["view"]] == [
        "Survival",
        "Possibility",
        "Power",
        "Wanting",
        "Probability",
        "Personal",
    ]
    assert len(PLAN["cases"]) == 2
    tree = ast.parse(
        (
            ROOT
            / "scripts/human_design/build_human_design_personality_color_reference.py"
        ).read_text()
    )
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fatebridge")
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("kind", ["motivation", "view"])
@pytest.mark.parametrize("color", range(1, 7))
def test_all_twelve_source_category_mappings_have_actual_local_basis(
    kind, color, source_runs
):
    chart = deepcopy(source_runs[PLAN["cases"][0]["id"]]["true"])
    pair = ("Sun", "Earth") if kind == "motivation" else ("NorthNode", "SouthNode")
    for row in chart["activations"]["personality"]:
        if row["body"] in pair:
            row["color"] = color
    value = personality_colors(chart["activations"])
    r = value[kind]
    assert r["status"] == "computed" and r["color"] == color
    assert r["source_term"] == PLAN["source_categories"][kind][color - 1]["source_term"]
    for b in r["basis"]:
        root, side, index, key = b["path"].split(".")
        assert side == "personality" and key == "color"
        assert chart[root][side][int(index)][key] == b["value"] == color
    assert (
        value["observed_transference"]
        is value["observed_distraction"]
        is value["observed_alignment"]
        is None
    )
    assert value["psychological_measurement_certified"] is False


@pytest.mark.parametrize("bad", [None, True, 0, 7, "3", "mismatch"])
def test_invalid_or_inconsistent_color_pair_cannot_acquire_a_source_label(
    bad, source_runs
):
    chart = deepcopy(source_runs[PLAN["cases"][0]["id"]]["true"])
    p = chart["activations"]["personality"]
    earth = next(r for r in p if r["body"] == "Earth")
    if bad is None:
        for r in p:
            r.pop("color", None)
    elif bad == "mismatch":
        earth["color"] = earth["color"] % 6 + 1
    else:
        earth["color"] = bad
    value = variables_from_activations(chart["activations"])
    assert value["code"] == chart["variables"]["code"]
    assert value["personality_colors"]["status"] == "incomplete_or_inconsistent"
    assert value["personality_colors"]["motivation"]["source_term"] is None


def test_design_color_and_valid_tone_cannot_substitute_for_personality_color(
    source_runs,
):
    chart = deepcopy(source_runs[PLAN["cases"][0]["id"]]["true"])
    for r in chart["activations"]["personality"]:
        r.pop("color", None)
    value = personality_colors(chart["activations"])
    assert value["status"] == "incomplete_or_inconsistent"
    assert value["motivation"]["source_term"] is value["view"]["source_term"] is None
    assert (
        variables_from_activations(chart["activations"])["code"]
        == chart["variables"]["code"]
    )


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_same_arrow_and_legacy_key_do_not_collapse_distinct_real_color_categories(
    case, source_runs
):
    a, b = (source_runs[case["id"]][mode] for mode in ("true", "mean"))
    cache = JointSnapshotCache()
    assert a["variables"]["code"] == b["variables"]["code"]
    assert JointSnapshotCache.key(a) != JointSnapshotCache.key(b)
    x, y = cache.snapshot(a), cache.snapshot(b)
    assert len(cache.snapshots) == 2
    assert [
        s["variables"]["personality_colors"]["view"]["color"] for s in (x, y)
    ] == case["expected_personality_node_colors"]
    assert (
        x["variables"]["personality_colors"]["view"]["source_term"]
        != y["variables"]["personality_colors"]["view"]["source_term"]
    )
    assert (
        verify_joint_snapshot(x)["status"]
        == verify_joint_snapshot(y)["status"]
        == "verified_local_snapshot_mechanics"
    )
    assert (
        changed_dependencies(
            dependency_projection(a["activations"]),
            dependency_projection(b["activations"]),
        )
        == 1
    )
    for s in (x, y):
        for r in s["activations"]["personality"]:
            if r["body"] in {"Sun", "Earth", "NorthNode", "SouthNode"}:
                assert type(r["color"]) is int


def test_same_source_color_tone_and_derived_mirror_count_as_one_dependency(source_runs):
    a = deepcopy(source_runs[PLAN["cases"][0]["id"]]["true"])
    b = deepcopy(a)
    for r in b["activations"]["personality"]:
        if r["body"] in {"Sun", "Earth"}:
            r["color"] = r["color"] % 6 + 1
            r["tone"] = r["tone"] % 6 + 1
    assert (
        changed_dependencies(
            dependency_projection(a["activations"]),
            dependency_projection(b["activations"]),
        )
        == 1
    )
    c = deepcopy(a)
    for r in c["activations"]["design"]:
        r["color"] = r["color"] % 6 + 1
    assert JointSnapshotCache.key(a) == JointSnapshotCache.key(c)


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("mode", PLAN["modes"])
@pytest.mark.parametrize("empty_files", [False, True])
def test_real_public_cases_both_conventions_and_backends_are_fully_replayed(
    case, mode, empty_files, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(SPEC, SPEC.request_model(**case["input"], node_mode=mode))
    value = run["variables"]["personality_colors"]
    assert value["status"] == "computed"
    raw = next(r for r in run["activations"]["personality"] if r["body"] == "NorthNode")
    assert value["view"]["color"] == raw["color"]
    if not empty_files:
        expected = case["expected_personality_node_colors"][0 if mode == "true" else 1]
        assert value["view"]["color"] == expected
        assert run["node_convention_comparison"]["personality_colors_changed"] is True
        assert run["node_convention_comparison"]["variable_changed"] is False
        assert "四箭头编码虽相同" in run["interpretation"]["personality_color_meaning"]
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(
            SPEC,
            SPEC.request_model(
                **PLAN["cases"][0]["input"], birth_time_uncertainty_minutes=1
            ),
        )


@pytest.mark.parametrize("bad", PLAN["negative_receipts"])
def test_rehashed_false_color_labels_states_and_projection_witnesses_rejected(
    complete, bad, monkeypatch
):
    run = deepcopy(complete)
    value = run["variables"]["personality_colors"]
    if bad == "wrong_label":
        value["view"]["source_term"] = "Fear"
    elif bad == "wrong_source":
        value["source_catalog_sha256"] = "0" * 64
    elif bad == "wrong_basis":
        value["view"]["basis"][0]["path"] = "activations.design.0.color"
    elif bad == "forged_transference_state":
        value["observed_transference"] = True
    elif bad == "forged_distraction_state":
        value["observed_distraction"] = True
    elif bad == "missing_joint_color":
        p = run["node_convention_comparison"]["reference_structure"]["activations"][
            "personality"
        ]
        del next(r for r in p if r["body"] == "NorthNode")["color"]
    elif bad == "forged_joint_color":
        report = run["node_convention_comparison"]
        s = report["reference_structure"]
        for r in s["activations"]["personality"]:
            if r["body"] in {"NorthNode", "SouthNode"}:
                r["color"] = r["color"] % 6 + 1
        chart = {
            "activations": s["activations"],
            "bodygraph": bodygraph(
                (r["gate"] for r in s["activations"]["personality"]),
                (r["gate"] for r in s["activations"]["design"]),
            ),
            "profile": s["profile"],
            "incarnation_cross": s["incarnation_cross"],
        }
        report["reference_structure"] = JointSnapshotCache().snapshot(chart)
        assert (
            verify_joint_snapshot(report["reference_structure"])["status"]
            == "verified_local_snapshot_mechanics"
        )
    elif bad == "forged_transition_color":
        states = run["time_sensitivity"]["joint_transition_refinement"]["states"]
        states[0][0][3] = states[0][0][3] % 6 + 1
    elif bad == "missing_backend_color":
        p = run["ephemeris_backend_comparison"]["reference_chart"]["activations"][
            "personality"
        ]
        del next(r for r in p if r["body"] == "NorthNode")["color"]
    elif bad == "wrong_reading":
        run["interpretation"]["personality_color_meaning"] = "本次已测量你处于转移状态"
    else:
        raise AssertionError(bad)
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(run)["status"] == "rejected"
