"""One physical bearing interval must reach every requested house calculation."""

import asyncio
import json
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import BazhaiRequest, XuankongRequest
from fatebridge.services.fengshui import (
    assess,
    calculate_bazhai,
    calculate_xuankong_natal,
)
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

# Authored compass facts, independent of the production sector iterator.
DIVIDERS = [
    (22.5, "离", "坤"),
    (67.5, "坤", "兑"),
    (112.5, "兑", "乾"),
    (157.5, "乾", "坎"),
    (202.5, "坎", "艮"),
    (247.5, "艮", "震"),
    (292.5, "震", "巽"),
    (337.5, "巽", "离"),
]
TRIGRAMS = {
    "N": "坎",
    "NE": "艮",
    "E": "震",
    "SE": "巽",
    "S": "离",
    "SW": "坤",
    "W": "兑",
    "NW": "乾",
}
STAR_NAMES = {
    "伏": "伏位",
    "生": "生气",
    "天": "天医",
    "延": "延年",
    "祸": "祸害",
    "六": "六煞",
    "五": "五鬼",
    "绝": "绝命",
}
SOURCE = json.loads(
    (
        Path(__file__).parent / "fixtures/fengshui_classical_v1/reference.json"
    ).read_text()
)


def house(angle=67.2, radius=1):
    return {
        "object_id": "home",
        "facing_degrees": angle,
        "north_reference": "magnetic",
        "bearing_uncertainty_degrees": radius,
    }


def request(angle=67.2, radius=1, legacy=False):
    declared = house(angle, radius)
    natal = {
        "period": {
            "basis": "expert_confirmed",
            "period_number": 8,
            "evidence": "合成验收输入，独立确认八运",
        }
    }
    if legacy:
        declared.pop("bearing_uncertainty_degrees")
        natal["bearing_uncertainty_degrees"] = radius
    return {
        "methods": ["bazhai", "xuankong_natal"],
        "analyze_layout": True,
        "house": declared,
        "occupants": [
            {
                "subject_id": "a",
                "effective_birth_year": 1990,
                "gender_convention": "male",
            }
        ],
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "S"}
        ],
        "xuankong": natal,
    }


def assert_literal_chart(candidate):
    trigram = candidate["sitting_trigram"]
    verse = next(v for v in SOURCE["you_nian_verses"] if v["base"] == trigram)
    names = {
        trigram: "伏位",
        **{
            t: STAR_NAMES[c] for t, c in zip(verse["destinations"], verse["star_codes"])
        },
    }
    assert {d: p["star"]["name"] for d, p in candidate["sectors"].items()} == {
        d: names[t] for d, t in TRIGRAMS.items()
    }


@pytest.mark.parametrize("divider,left,right", DIVIDERS)
@pytest.mark.parametrize("offset", [-0.3, 0.3])
@pytest.mark.parametrize("legacy", [False, True])
def test_all_eight_shared_boundaries_retain_both_house_charts(
    divider, left, right, offset, legacy
):
    result = assess(**request(divider + offset, legacy=legacy))
    b, x = result["layers"]["bazhai"], result["layers"]["xuankong_natal"]
    assert b["house"] is None and b["status"] == "partial"
    assert {c["sitting_trigram"] for c in b["house_candidates"]} == {left, right}
    assert {TRIGRAMS[c["sitting"]["direction"]] for c in x["candidates"]} == {
        left,
        right,
    }
    for candidate in b["house_candidates"]:
        assert candidate["candidate_only"] is True
        assert_literal_chart(candidate)
    findings = [f for f in b["placement_findings"] if f["subject_kind"] == "house"]
    assert {f["house_sitting_trigram"] for f in findings} == {left, right}
    assert all(f["candidate_only"] for f in findings)
    personal = [f for f in b["placement_findings"] if f["subject_kind"] == "occupant"]
    assert len(personal) == 1 and personal[0]["candidate_only"] is False
    assert result["layout_analysis"]["status"] == "partial"
    assert (
        "house.unambiguous_sitting_trigram"
        in result["layout_analysis"]["missing_inputs"]
    )
    for option in result["layout_analysis"]["adjustment_options"]:
        scopes = [s for s in option["scopes"] if s["subject_kind"] == "house"]
        assert {s["house_sitting_trigram"] for s in scopes} == {left, right}
        assert all(s["candidate_only"] for s in scopes)
        assert option["candidate_scopes_excluded_from_intersection"] is True
    for trigram in [left, right]:
        assert f"house-sitting:{trigram}" in result["snapshot_text"]
        assert f"坐卦{trigram}" in result["snapshot_text"]


def test_original_counterexample_keeps_the_opposing_house_findings():
    b = assess(**request(legacy=True))["layers"]["bazhai"]
    findings = {
        f["house_sitting_trigram"]: f
        for f in b["placement_findings"]
        if f["subject_kind"] == "house"
    }
    assert (findings["坤"]["star"]["name"], findings["坤"]["matches_convention"]) == (
        "六煞",
        False,
    )
    assert (findings["兑"]["star"]["name"], findings["兑"]["matches_convention"]) == (
        "五鬼",
        False,
    )
    assert (
        b["house_orientation_context"]["uncertainty_input_path"]
        == "xuankong.bearing_uncertainty_degrees"
    )


def test_a_boundary_that_changes_the_basic_polarity_keeps_both_truth_values():
    b = assess(**request(angle=22.2, legacy=True))["layers"]["bazhai"]
    findings = {
        f["house_sitting_trigram"]: f
        for f in b["placement_findings"]
        if f["subject_kind"] == "house"
    }
    assert (findings["离"]["star"]["name"], findings["离"]["matches_convention"]) == (
        "伏位",
        True,
    )
    assert (findings["坤"]["star"]["name"], findings["坤"]["matches_convention"]) == (
        "六煞",
        False,
    )
    assert all(f["candidate_only"] for f in findings.values())


@pytest.mark.parametrize("divider,left,right", DIVIDERS)
def test_exact_binary_endpoint_does_not_round_a_narrow_interval_across_a_line(
    divider, left, right
):
    angle = math.nextafter(divider, -math.inf)
    ulp = math.ulp(divider)
    single = calculate_bazhai(house=house(angle, ulp / 2))["layers"]["bazhai"]
    assert {c["sitting_trigram"] for c in single["house_candidates"]} == {left}
    assert single["house"]["sitting_trigram"] == left
    # The exact endpoint now actually touches the line; closed-cell policy
    # preserves both limits without adding an arbitrary epsilon.
    touched = calculate_bazhai(house=house(angle, ulp))["layers"]["bazhai"]
    assert {c["sitting_trigram"] for c in touched["house_candidates"]} == {left, right}
    for candidate in touched["house_candidates"]:
        for region in candidate["bearing_support"]["regions"]:
            start, end = (
                Fraction(region[k])
                for k in ["from_facing_degrees_exact", "until_facing_degrees_exact"]
            )
            assert (
                Fraction(angle) - Fraction(ulp)
                <= start
                <= end
                <= Fraction(angle) + Fraction(ulp)
            )


@pytest.mark.parametrize(
    "angle,radius,expected",
    [(359, 24, {"巽", "离", "坤"}), (0, 180, set(TRIGRAMS.values())), (360, 1, {"离"})],
)
def test_wrap_and_wide_intervals_cover_all_supported_cells_without_duplicates(
    angle, radius, expected
):
    b = calculate_bazhai(house=house(angle, radius))["layers"]["bazhai"]
    assert {c["sitting_trigram"] for c in b["house_candidates"]} == expected
    assert len(b["house_candidates"]) == len(expected)
    for candidate in b["house_candidates"]:
        assert_literal_chart(candidate)


@pytest.mark.parametrize("legacy", [False, True])
def test_independently_confirmed_trigram_filters_the_interval_even_opposite_the_nominal_side(
    legacy,
):
    inputs = request(legacy=legacy)
    inputs["house"]["sitting_trigram"] = "兑"
    result = assess(**inputs)
    b = result["layers"]["bazhai"]
    assert b["house"]["sitting_trigram"] == "兑"
    assert len(b["house_candidates"]) == 1
    assert b["house_candidates"][0]["candidate_only"] is False
    assert all(
        c["sitting"]["direction"] == "W"
        for c in result["layers"]["xuankong_natal"]["candidates"]
    )
    inputs["house"]["sitting_trigram"] = "坎"
    with pytest.raises(ValidationError):
        assess(**inputs)


def test_nested_house_is_not_lost_when_bazhai_is_explicitly_requested():
    inputs = request()
    inputs["scene"] = "home"
    inputs["xuankong"]["house"] = inputs.pop("house")
    result = assess(**inputs)
    b = result["layers"]["bazhai"]
    assert {c["sitting_trigram"] for c in b["house_candidates"]} == {"坤", "兑"}
    assert b["house_orientation_context"]["house_input_path"] == "xuankong.house"
    scopes = [
        layer["input_scopes"]
        for family in result["method_policy"]["method_priority"]
        for layer in family["layer_availability"]
        if layer["engine_layer"] == "bazhai"
    ]
    assert len(scopes) == 1
    assert (
        "house.sitting_trigram_or_confirmed_facing"
        not in scopes[0][0]["missing_inputs"]
    )


@pytest.mark.parametrize("value", [-1, 181, float("inf"), float("nan"), True])
def test_invalid_shared_radii_are_rejected(value):
    with pytest.raises(ValidationError):
        BazhaiRequest(house=house(radius=value))


def test_conflicting_radius_aliases_are_rejected_including_an_explicit_zero():
    for legacy in [0, 2]:
        inputs = request()
        inputs["xuankong"]["bearing_uncertainty_degrees"] = legacy
        with pytest.raises(ValidationError, match="必须一致"):
            assess(**inputs)
    inputs = request()
    inputs["xuankong"]["bearing_uncertainty_degrees"] = 1
    assert assess(**inputs)["layers"]["bazhai"]["house"] is None


def test_public_schemas_preserve_fields_and_the_required_bearing_and_natal_limit():
    schema = BazhaiRequest.model_json_schema()
    with pytest.raises(ValidationError):
        BazhaiRequest(house={"bearing_uncertainty_degrees": 1, "sitting_trigram": "坤"})
    assert list(
        Draft202012Validator(schema).iter_errors(
            {"house": {"bearing_uncertainty_degrees": 1, "sitting_trigram": "坤"}}
        )
    )
    natal = XuankongRequest.model_json_schema()
    assert {
        "house",
        "period",
        "ruleset_id",
        "interpretation",
        "city_gate",
        "bearing_uncertainty_degrees",
    } <= set(natal["properties"])
    assert list(Draft202012Validator(natal).iter_errors({"house": house(radius=8)}))
    with pytest.raises(ValidationError, match="7.5"):
        XuankongRequest(house=house(radius=8))
    assert not list(Draft202012Validator(natal).iter_errors({"house": house()}))


def test_proposal_keeps_the_same_house_candidates_and_cannot_become_ready():
    inputs = request(legacy=True)
    inputs["layout_constraints"] = [
        {"object_id": "bed", "can_relocate": True, "evidence": "合成输入，允许移动"}
    ]
    inputs["layout_alternatives"] = [
        {
            "candidate_id": "move-bed",
            "object_id": "bed",
            "changes": ["location"],
            "placement": {
                "object_id": "bed",
                "purpose": "bed",
                "location_direction": "N",
            },
            "physically_feasible": True,
            "evidence": "合成输入，新位置独立确认",
        }
    ]
    result = assess(**inputs)
    proposal = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert proposal["status"] == "candidate_only"
    comparisons = [
        c for c in proposal["rule_comparisons"] if c.get("subject_kind") == "house"
    ]
    assert {c["house_candidate_id"] for c in comparisons} == {
        "house-sitting:坤",
        "house-sitting:兑",
    }
    assert all(c["candidate_only"] for c in comparisons)
    assert {
        f["direction"]
        for f in proposal["placement_findings"]
        if f.get("subject_kind") == "house"
    } == {"N"}


@pytest.mark.parametrize("name", ["bazhai", "assess"])
def test_new_house_candidates_match_rest_real_mcp_and_cli(
    monkeypatch, tmp_path, capsys, name
):
    inputs = request()
    if name == "bazhai":
        inputs = {key: inputs[key] for key in ["house", "occupants", "placements"]}
    original = deepcopy(inputs)
    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    p = tmp_path / "bearing.json"
    p.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_" + name, "--request-file", str(p)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert inputs == original
    assert len(cli["layers"]["bazhai"]["house_candidates"]) == 2


def test_standalone_natal_uses_the_shared_field_without_changing_existing_numbers():
    inputs = request()["xuankong"]
    shared = calculate_xuankong_natal(**inputs, house=house())
    legacy_house = house()
    legacy_house.pop("bearing_uncertainty_degrees")
    old = calculate_xuankong_natal(
        **inputs, house=legacy_house, bearing_uncertainty_degrees=1
    )
    assert shared == old


def test_point_and_explicit_zero_keep_the_original_float_wire_representation():
    period = {
        "basis": "expert_confirmed",
        "period_number": 8,
        "evidence": "合成输入，已确认八运",
    }
    base = {"facing_degrees": 255, "north_reference": "magnetic"}
    for extra, declared_house in [
        ({}, base),
        ({"bearing_uncertainty_degrees": 0}, base),
        ({}, {**base, "bearing_uncertainty_degrees": 0}),
    ]:
        layer = calculate_xuankong_natal(house=declared_house, period=period, **extra)[
            "layers"
        ]["xuankong_natal"]
        assert type(layer["orientation_context"]["uncertainty_degrees"]) is float
        assert '"uncertainty_degrees": 0.0' in json.dumps(layer["orientation_context"])
