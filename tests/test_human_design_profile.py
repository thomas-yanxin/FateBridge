"""Source-classified role geometry, P/D binding and unassigned cycle phases."""

import ast
import copy
import json
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_profile import (
    profile_evidence,
    profile_reading,
    profile_reference,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_profile import public_profile_checks
from tests.golden.runner import golden_ephemeris

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (ROOT / "src/fatebridge/data/human_design/profile-2026-reference.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")
CASES = [
    case
    for name in (
        "human-design-official-charts.json",
        "human-design-official-authority-charts.json",
    )
    for case in json.loads((ROOT / "tests/fixtures" / name).read_text())["cases"]
]


def paired(profile, angle=None):
    p, d = map(int, profile.split("/"))
    chart = {
        "profile": profile,
        "activations": {
            "personality": [
                {"body": "Moon", "line": 6},
                {"body": "Earth", "line": p},
                {"body": "Sun", "line": p},
            ],
            "design": [
                {"body": "Sun", "line": d},
                {"body": "Moon", "line": 6},
                {"body": "Earth", "line": d},
            ],
        },
    }
    if angle:
        chart["incarnation_cross"] = {"angle": angle}
    return chart


def resolve(payload, path):
    for part in path.split("."):
        payload = payload[int(part)] if isinstance(payload, list) else payload[part]
    return payload


@pytest.mark.parametrize("fact", REFERENCE["profiles"], ids=lambda r: r["profile"])
def test_all_source_profile_headers_keep_polarity_trigram_geometry_and_actual_paths(
    fact,
):
    chart = paired(fact["profile"], fact["angle"])
    result = profile_evidence(chart)
    assert result["status"] == "computed"
    p, d = result["lines"]
    assert (p["line"], d["line"]) == (fact["personality_line"], fact["design_line"])
    assert (p["traditional_polarity"], d["traditional_polarity"]) == (
        "conscious",
        "unconscious",
    )
    for row in result["lines"]:
        assert row["archetype"] == REFERENCE["line_archetypes"][str(row["line"])]
        assert row["trigram"] == ("lower" if row["line"] <= 3 else "upper")
        assert len(row["basis"]) == 2
        for basis in row["basis"]:
            assert resolve(chart, basis["path"]) == basis["value"]
    assert result["geometry"]["angle"] == fact["angle"]
    phases = result["sixth_line_process"]
    assert phases["applicable"] is (6 in [p["line"], d["line"]])
    assert phases["current_phase"] is None and phases["computed_return_dates"] is None


def test_four_six_is_right_despite_two_upper_lines_and_four_one_is_distinct():
    result = profile_evidence(paired("4/6"))
    assert [r["trigram"] for r in result["lines"]] == ["upper", "upper"]
    assert result["geometry"]["angle"] == "right"
    assert "不能改标左角" in profile_reading(result)
    fixed = profile_evidence(paired("4/1"))
    assert fixed["geometry"]["angle"] == "juxtaposition"
    assert fixed["geometry"]["source_term"] == "Fixed Fate"
    assert "不表示现实结局不可改变" in profile_reading(fixed)
    assert (
        profile_evidence(paired("4/6", "left"))["status"]
        == "inconsistent_profile_cross_angle"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "missing_earth",
        "duplicate_sun",
        "pair_disagrees",
        "bool_line",
        "invalid_pair",
        "claimed_profile",
    ],
)
def test_incomplete_or_false_basis_does_not_receive_invented_role_themes(bad):
    chart = paired("1/3")
    if bad == "missing_earth":
        chart["activations"]["personality"].pop(1)
    elif bad == "duplicate_sun":
        chart["activations"]["personality"][1]["body"] = "Sun"
    elif bad == "pair_disagrees":
        chart["activations"]["design"][0]["line"] = 4
    elif bad == "bool_line":
        for row in chart["activations"]["personality"]:
            if row["body"] in ["Sun", "Earth"]:
                row["line"] = True
    elif bad == "invalid_pair":
        chart = paired("1/1")
    else:
        chart["profile"] = "3/1"
    result = profile_evidence(chart)
    assert result["status"] != "computed"
    assert "lines" not in result and "geometry" not in result


def test_ordinary_activation_six_and_return_teaching_never_assign_current_age_phase():
    plain = profile_evidence(paired("1/3"))
    assert plain["sixth_line_process"]["applicable"] is False
    assert plain["sixth_line_process"]["source_cycle_markers"] is None
    source = profile_evidence(paired("6/3"))
    cycle = source["sixth_line_process"]
    assert cycle["phase_assignment_status"] == "not_assessed_in_natal_profile_evidence"
    assert cycle["source_cycle_markers"]["saturn_return"][
        "approximate_teaching_age_years"
    ] == [28, 29]
    assert cycle["source_cycle_markers"]["kiron_return"][
        "approximate_teaching_age_years"
    ] == [50, 51]
    assert source["profile"] == "6/3" and source["lines"][0]["line"] == 6
    cycle["source_cycle_markers"]["saturn_return"]["approximate_teaching_age_years"][
        0
    ] = 999
    again = profile_evidence(paired("6/3"))
    assert again["sixth_line_process"]["source_cycle_markers"]["saturn_return"][
        "approximate_teaching_age_years"
    ] == [28, 29]
    assert profile_reference()["sixth_line_cycle_markers"]["saturn_return"][
        "approximate_teaching_age_years"
    ] == [28, 29]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_every_official_profile_replays_in_real_run_and_joint_snapshots(case):
    with golden_ephemeris():
        run = execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))
    assert run["profile_evidence"]["status"] == "computed"
    assert run["profile_evidence"]["profile"] == case["properties"]["Profile"]
    assert (
        verify_human_design_reading(run)["status"] == "verified_fixed_template_reading"
    )
    for row in run["profile_evidence"]["lines"]:
        for fact in row["basis"]:
            assert resolve(run, fact["path"]) == fact["value"]
    comparison = run["node_convention_comparison"]
    assert (
        comparison["selected_structure"]["profile_evidence"] == run["profile_evidence"]
    )
    for key in ["selected_structure", "reference_structure"]:
        snap = comparison[key]
        for row in snap["profile_evidence"]["lines"]:
            for fact in row["basis"]:
                assert resolve(snap, fact["path"]) == fact["value"]
    assert (
        JointSnapshotCache().snapshot(run)["profile_evidence"]
        == run["profile_evidence"]
    )


@pytest.fixture(scope="module")
def real_sixth_profile_run():
    case = next(c for c in CASES if "6" in c["properties"]["Profile"])
    with golden_ephemeris():
        return execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))


@pytest.mark.parametrize(
    "bad",
    [
        "geometry",
        "polarity",
        "line",
        "basis",
        "phase",
        "dates",
        "applicable",
        "joint",
        "catalog",
        "text",
        "rule_version",
    ],
)
def test_rehashed_role_or_cycle_assertions_cannot_override_actual_chart(
    real_sixth_profile_run, bad
):
    run = copy.deepcopy(real_sixth_profile_run)
    role = run["profile_evidence"]
    if bad == "geometry":
        role["geometry"]["angle"] = "unjustified"
    elif bad == "polarity":
        role["lines"][0]["traditional_polarity"] = "unconscious"
    elif bad == "line":
        role["lines"][0]["line"] = 0
    elif bad == "basis":
        role["lines"][0]["basis"][0]["path"] = "activations.design.0.line"
    elif bad == "phase":
        role["sixth_line_process"]["current_phase"] = "post_kiron_return"
    elif bad == "dates":
        role["sixth_line_process"]["computed_return_dates"] = {
            "saturn_return": "2000-01-01"
        }
    elif bad == "applicable":
        role["sixth_line_process"]["applicable"] = 1
    elif bad == "joint":
        run["node_convention_comparison"]["reference_structure"]["profile_evidence"][
            "lines"
        ][0]["theme"] = "guaranteed"
    elif bad == "catalog":
        role["source_catalog_sha256"] = "0" * 64
    elif bad == "rule_version":
        role["ruleset"]["version"] = "1.10.0"
    else:
        run["interpretation"]["profile_meaning"] = "30岁生日后人生角色自动变为3/3。"
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(run)["status"] == "rejected"


def test_public_fact_audit_keeps_bounded_scope_and_extractor_independent():
    result = public_profile_checks(ROOT)
    assert result["status"] == "bounded_public_profile_facts_matched"
    assert result["angle_profile_counts"] == {"right": 7, "juxtaposition": 1, "left": 4}
    assert result["official_charts_matched"] == 19
    source = ast.parse(
        (ROOT / "scripts/build_human_design_profile_reference.py").read_text()
    )
    imports = [
        node.module or ""
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
    ]
    assert all(not name.startswith(("fatebridge", "tests")) for name in imports)
