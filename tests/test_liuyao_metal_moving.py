"""Independent moving-earth support qualifies only the local metal/Si credit."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.liuyao_metal_change import PROFILE as OWN_PROFILE
from fatebridge.core.liuyao_metal_moving import PROFILE, moving_support_context
from scripts.build_liuyao_metal_moving_profile import build
from tests.test_liuyao_conditions import conditional_case

BASE = Path(__file__).parent / "fixtures/liuyao_metal_moving_v34"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


def read_path(result, path):
    value = {"liuyao_evidence": {"conditional_analysis": result}}
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def check(result, case):
    g = result["growth_conditions"]["lines"][5]
    s = result["generation_conditions"]["sources"][case["source_position"] - 1]
    target = result["generation_conditions"]["sources"][5]
    pair = next(
        x
        for x in result["generation_conditions"]["generations"]
        if (x["source_position"], x["target_position"]) == (case["source_position"], 6)
    )
    assert g["branch"] == "酉" and g["position_match"] is True
    assert g["condition_match"] is case["expected_growth"]
    assert g["raw_day_element_relation"] == "克爻"
    assert s["condition_match"] is case["expected_source"]
    assert result["lines"][5]["monthly_strength"]["monthly_supported"] is False
    assert g["independent_month_support"] is False
    outer = result["growth_conditions"]
    adjudication = None
    if "own_changed_si" in g:
        folder = BASE.parent / "liuyao_metal_own_si_v35"
        for name, digest in json.loads(
            (folder / "v34-case-adjudication-freeze.json").read_text()
        ).items():
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
        adjudication = json.loads((folder / "v34-case-adjudication.json").read_text())
        assert case["id"] == adjudication["case_id"]
        assert (
            hashlib.sha256((BASE / "cases.json").read_bytes()).hexdigest()
            == adjudication["original_fixture_sha256"]
        )
        assert outer["ruleset_id"] == OWN_PROFILE["ruleset_id"]
        assert outer["ruleset_version"] == OWN_PROFILE["ruleset_version"]
        own = g["own_changed_si"]
        assert own["condition_match"] is adjudication["new_own_growth"]
        assert own["raw_back_control"] is adjudication["raw_back_control_remains"]
        assert (
            own["qualified_back_control_condition"]
            is adjudication["new_qualified_back_control"]
        )
    elif "moving_support" in g:
        assert outer["ruleset_id"] == PROFILE["ruleset_id"]
        assert outer["ruleset_version"] == PROFILE["ruleset_version"]
    else:
        assert outer["ruleset_id"] == "zengshan_metal_si_growth_v18"
        assert outer["ruleset_version"] == "18.0.0"
    if "expected_target_reception" in case:
        assert pair["target_reception_condition"] is case["expected_target_reception"]
    if "expected_target_source" in case:
        if adjudication is not None:
            assert (
                case["expected_target_source"]
                is adjudication["original_expected_target_source"]
            )
            assert (
                target["condition_match"] is adjudication["new_expected_target_source"]
            )
            assert any(a["location"] == "month" for a in g["other_oppositions"])
        else:
            assert target["condition_match"] is case["expected_target_source"]
    if case["expected_growth"] is True:
        assert not g["day_control_in_calendar_oppositions"]
        proof = g["moving_support"]
        assert (
            proof["condition_match"] is True and proof["excluded_target_position"] == 6
        )
        accepted = [x for x in proof["candidates"] if x["condition_match"]]
        assert accepted and all(x["source_condition_match"] is True for x in accepted)
        for candidate in accepted:
            assert candidate["activity_condition_match"] is True
            assert (
                candidate["independent_root_proven"] is True and candidate["root_proof"]
            )
            for step in candidate["root_proof"]:
                assert step["position"] != 6 and step.get("source_position") != 6
                actor = read_path(result, step["source_path"])
                assert actor["branch"] == step["branch"]
        if case.get("retained_month_control"):
            assert any(x["location"] == "month" for x in g["other_oppositions"])
        if case.get("target_own_back_control"):
            if adjudication is not None:
                assert not any(
                    x["location"] == "changed" for x in g["other_oppositions"]
                )
            else:
                assert any(x["location"] == "changed" for x in g["other_oppositions"])
        if case.get("target_month_break"):
            assert result["lines"][5]["monthly_strength"]["category"] == "月破"
            assert any(x["location"] == "month" for x in g["other_oppositions"])
    else:
        assert g["day_control_in_calendar_oppositions"] is True
    assert all("_metal_si_moving_support" not in x for x in result["lines"])
    return g


def test_original_book_profile_and_preregistered_inputs():
    assert build() == PROFILE
    frozen = json.loads((BASE / "freeze.json").read_text())["files_sha256"]
    for name, h in frozen.items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == h
    assert len(CASES) == 8


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_moving_earth_source_and_receiver_remain_separate(case):
    check(conditional_case(case), case)


def cycle(anchors=None):
    # Adversarial DTO graph, not six legally mounted lines or extra chart cases.
    elements = ["土", "火", "木", "水", "金", "金"]
    branches = ["戌", "午", "寅", "子", "申", "酉"]
    lines = [
        dict(position=i + 1, element=e, branch=b, change=i < 5)
        for i, (e, b) in enumerate(zip(elements, branches))
    ]
    parent = {1: 2, 2: 3, 3: 4, 4: 5, 5: 1}
    rows = []
    for p in range(1, 7):
        supports = []
        if p in parent:
            q = parent[p]
            supports.append(
                dict(
                    location="visible",
                    position=q,
                    branch=branches[q - 1],
                    source_grounded=True,
                    held=False,
                    activity_pending=False,
                )
            )
        supports += deepcopy((anchors or {}).get(p, []))
        rows.append(dict(position=p, strength=dict(supports=supports)))
    generation = dict(
        sources=[
            dict(
                position=i + 1,
                branch=b,
                condition_match=True,
                activity_condition_match=i < 5,
                source_path=f"sources.{i}",
            )
            for i, b in enumerate(branches)
        ],
        generations=[
            dict(source_position=q, target_position=p, benefit_now=True)
            for p, q in parent.items()
        ],
    )
    return dict(
        element="金",
        subject_position=6,
        lines=lines,
        assessment=dict(lines=rows),
        generation=generation,
        day_ganzhi="乙巳",
        source_path="growth.moving_support",
    )


@pytest.mark.parametrize(
    "anchor",
    ["none", "other_metal_si", "queried_metal", "earth_si", "earth_changed_si"],
)
def test_source_true_or_cycle_cannot_prove_its_own_independent_root(anchor):
    anchors = {
        "none": {},
        "other_metal_si": {5: [dict(location="day", branch="巳")]},
        "queried_metal": {6: [dict(location="month", branch="丑")]},
        "earth_si": {1: [dict(location="day", branch="巳")]},
        "earth_changed_si": {
            1: [dict(location="changed", branch="巳", back_generation_condition=True)]
        },
    }
    result = moving_support_context(**cycle(anchors[anchor]))
    assert result["condition_match"] is False
    assert result["candidates"][0]["source_condition_match"] is True
    assert result["candidates"][0]["independent_root_proven"] is False


@pytest.mark.parametrize("anchor", ["month_wood", "day_fire", "qualified_own_back"])
def test_independent_anchor_resolves_a_real_dependency_path(anchor):
    anchors = {
        "month_wood": {3: [dict(location="month", branch="亥")]},
        "day_fire": {2: [dict(location="day", branch="巳")]},
        "qualified_own_back": {
            1: [dict(location="changed", branch="午", back_generation_condition=True)]
        },
    }
    result = moving_support_context(**cycle(anchors[anchor]))
    assert result["condition_match"] is True
    proof = result["candidates"][0]["root_proof"]
    assert proof[0]["location"] in ("day", "month", "changed")
    assert proof[-1]["position"] == 1
    assert all(x["position"] != 6 and x.get("source_position") != 6 for x in proof)


def test_hidden_subject_does_not_borrow_a_different_visible_subject_identity():
    args = cycle({6: [dict(location="month", branch="丑")]})
    args["subject_position"] = None
    # The added metal has no declared supporting edge to the cycle.
    result = moving_support_context(**args)
    assert result["excluded_target_position"] is None
    assert result["condition_match"] is False


def test_partial_output_accepts_only_the_new_proof_object():
    from fatebridge.core.output_liuyao_growth import GrowthLine
    from fatebridge.core.output_liuyao_hidden import HiddenReception

    for model in (GrowthLine, HiddenReception):
        value = model.model_validate({"moving_support": {"condition_match": True}})
        assert value.moving_support.condition_match is True


def test_output_rejects_a_boolean_in_place_of_root_steps():
    from pydantic import ValidationError

    from fatebridge.core.output_liuyao_growth import MetalMovingSupport

    with pytest.raises(ValidationError):
        MetalMovingSupport.model_validate({"candidates": [{"root_proof": False}]})
