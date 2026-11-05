"""Same-edition moving-Si exceptions preserve raw relations and other controls."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.liuyao_moving_si import PROFILE
from fatebridge.core.output_liuyao_control import DirectedControl
from fatebridge.core.output_liuyao_growth import GrowthConditions, MovingSiGrowth
from scripts.liuyao.build_liuyao_moving_si_profile import build
from tests.liuyao.test_liuyao_conditions import conditional_case
from tests.liuyao.test_liuyao_metal_moving import read_path

BASE = Path(__file__).parents[1] / "fixtures/liuyao_moving_si_v40"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


def check(result, case):
    p = case["metal_position"]
    growth = result["growth_conditions"]["lines"][p - 1]
    context = growth.get("moving_si")
    GrowthConditions.model_validate(result["growth_conditions"])
    if not case["expected_visible_si_encounter"]:
        assert context is None
        return
    assert (
        context["ruleset_id"]
        == result["growth_conditions"]["ruleset_id"]
        == PROFILE["ruleset_id"]
    )
    assert context["source_sha256"] == PROFILE["source"]["sha256"]
    assert result["growth_conditions"]["clauses"] == PROFILE["clauses"]
    assert context["combined_effect_adjudicated"] is False
    assert context["cross_passage_source_urls"] == [
        PROFILE["source"]["url"] + "#page=85",
        PROFILE["source"]["url"] + "#page=97",
    ]
    assert context["actual_si_positions"] == case["si_positions"]
    assert context["textual_encounter_condition"] is True
    assert read_path(result, context["source_path"]) == context
    if case["expected_independent_calendar_root"]:
        assert (
            context["calendar_supports"] and context["support_condition_match"] is True
        )
    else:
        assert not context["calendar_supports"]
    for root in context["calendar_supports"]:
        actor = read_path(result, root["source_path"])
        assert (actor["location"], actor["branch"]) == (
            root["location"],
            root["branch"],
        )
    if moving := context.get("moving_support"):
        assert moving["excluded_target_position"] == p
        for candidate in moving["candidates"]:
            for step in candidate["root_proof"]:
                assert step["position"] != p and step.get("source_position") != p
                assert (
                    read_path(result, step["source_path"])["branch"] == step["branch"]
                )
    if case["pattern"] == "si_back_controlled":
        expected = False
    elif case["id"].endswith(("si-void", "si-binding")):
        expected = None
    elif case["id"].endswith("unproven-root") and case["pattern"] != "si_and_earth":
        expected = None
    else:
        expected = True
    assert context["condition_match"] is expected
    if case["id"] == "si_and_earth-unproven-root":
        assert context["moving_support"]["condition_match"] is True
        assert any(
            s["kind"] == "calendar"
            for c in context["moving_support"]["candidates"]
            if c["condition_match"]
            for s in c["root_proof"]
        )
    for source in context["sources"]:
        assert source["growth_condition_match"] is expected
        control = read_path(result, source["control_source_path"])
        DirectedControl.model_validate(control)
        assert control["relation"] == source["raw_relation"] == "克爻"
        assert source["source_branch"] == control["source_branch"] == "巳"
        assert control["raw_condition_match"] is source["raw_control_condition"]
        assert control["metal_si_growth_source_path"] == source["source_path"]
        assert read_path(result, source["source_path"]) == source
        assert source["qualified_control_condition"] is source["raw_control_condition"]
        assert source["combined_effect_condition"] is None
        actor = next(
            a
            for a in result["classical_assessment"]["lines"][p - 1]["strength"][
                (
                    "blocked_oppositions"
                    if source["qualified_control_condition"] is False
                    else "oppositions"
                )
            ]
            if a["location"] == "visible" and a["position"] == source["source_position"]
        )
        assert actor["control_condition_match"] is source["qualified_control_condition"]
        assert actor["metal_si_growth_condition"] is expected
        edge = next(
            e
            for e in result["interaction_edges"]
            if e["source_kind"] == "base"
            and (e["source_position"], e["target_position"])
            == (source["source_position"], p)
        )
        assert edge["relation"] == "克爻"
        assert edge["control_condition_match"] is source["qualified_control_condition"]
        assert edge["metal_si_growth_condition"] is expected
    strength = result["classical_assessment"]["lines"][p - 1]["strength"]
    if case["id"].endswith("month-root"):
        assert any(
            a["location"] == "day" and a["branch"] == "午"
            for a in strength["oppositions"]
        )
    if case["id"].endswith("day-root"):
        assert any(
            a["location"] == "month" and a["branch"] == "午"
            for a in strength["oppositions"]
        )
    if case["pattern"] == "si_and_wu" and case["id"].endswith(
        ("month-root", "day-root")
    ):
        wu = next(
            c
            for c in result["control_conditions"]["controls"]
            if c["source_branch"] == "午" and c["target_position"] == p
        )
        assert wu["condition_match"] is True and "metal_si_growth_condition" not in wu
    assert all("_metal_moving_si_growth" not in line for line in result["lines"])
    assert context["actual_total_effect_adjudicated"] is False


def test_original_scan_and_frozen_material_match_the_generated_profile():
    assert build() == PROFILE
    freeze = json.loads((BASE / "freeze.json").read_text())
    for name, digest in freeze["files_sha256"].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert len(CASES) == 35


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_specific_directed_qualification_preserves_other_conditions(case):
    check(conditional_case(case), case)


@pytest.mark.parametrize("value", [0, 1, "true", "false"])
def test_projected_qualification_never_coerces_truth_values(value):
    with pytest.raises(ValidationError):
        MovingSiGrowth.model_validate({"condition_match": value})
    with pytest.raises(ValidationError):
        DirectedControl.model_validate({"metal_si_growth_condition": value})


@pytest.mark.parametrize(
    "case",
    json.loads((BASE / "precedence-cases.json").read_text())["cases"],
    ids=lambda c: c["id"],
)
def test_specific_yin_precedence_cannot_be_bypassed_by_moving_si_growth(case):
    for name, digest in json.loads(
        (BASE / "precedence-freeze.json").read_text()
    ).items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    result = conditional_case(case)
    rescue = result["back_generation_conditions"]["sources"][0]
    assert rescue["raw_condition_match"] is True
    assert rescue["condition_match"] is case["expected_back_generation"]
    growth = result["growth_conditions"]["lines"][4]["moving_si"]
    assert growth["support_condition_match"] is True
    assert growth["condition_match"] is case["expected_moving_si_growth"]
    if case["expected_back_generation"] is False:
        assert growth["sources"][0]["source_control_admission"] is None
        assert growth["sources"][0]["qualified_control_condition"] is None
    else:
        assert growth["sources"][0]["qualified_control_condition"] is True
        assert growth["sources"][0]["combined_effect_condition"] is None


def test_same_edition_explicit_control_example_prevents_automatic_exemption():
    original = json.loads((BASE.parent / "liuyao_control_v9/cases.json").read_text())
    case = next(c for c in original["cases"] if c["id"] == "scan22-kun-shi")
    assert [2, 6, True] in case["expected_controls"]
    result = conditional_case(case)
    growth = result["growth_conditions"]["lines"][5]["moving_si"]
    assert any(
        r["location"] == "day" and r["branch"] == "未"
        for r in growth["calendar_supports"]
    )
    assert growth["condition_match"] is True
    source = growth["sources"][0]
    assert source["raw_control_condition"] is True
    assert source["qualified_control_condition"] is True
    assert source["combined_effect_condition"] is None
    assert growth["combined_effect_adjudicated"] is False
    assert any(85 in c["pdf_pages"] for c in result["growth_conditions"]["clauses"])
