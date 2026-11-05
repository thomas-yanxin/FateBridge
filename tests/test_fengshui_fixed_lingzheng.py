"""Original fixed directions, separate flying stars and explicit physical facts."""

import asyncio
import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.lingzheng import analyze_fixed_lingzheng
from fatebridge.core.fengshui.lingzheng_inputs import (
    FixedLingzhengRequest,
    LingzhengObservation,
)
from fatebridge.core.fengshui.models import XuankongInterpretationRequest
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.fengshui_lingzheng import audit_lingzheng_reference
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

DIRS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
REF = Path(__file__).parent / "data/fengshui_lingzheng_v1/reference.json"


def observation(direction, **facts):
    return dict(
        direction=direction,
        observation_basis="measured",
        evidence="已核对全宅磁北八宫及实际地形",
        **facts,
    )


def inputs(current=8, half=None, natal=2, angle=0):
    fixed = {
        "observations": [
            observation(
                d,
                high_solid_terrain_present=True,
                low_lying_terrain_present=True,
                river_water_present=True,
            )
            for d in DIRS
        ]
    }
    if half:
        fixed.update(five_period_half=half, half_evidence="明确核对评价五运的前后十年")
    config = {"fixed_lingzheng": fixed}
    if current is not None:
        config.update(
            current_period_number=current, period_evidence="独立评价时运，不取历史宅运"
        )
    return dict(
        house={"facing_degrees": angle, "north_reference": "magnetic"},
        period={
            "basis": "expert_confirmed",
            "period_number": natal,
            "evidence": "历史宅运独立确认",
        },
        interpretation=config,
    )


def fixed_result(request):
    return calculate_xuankong_natal(**request)["layers"]["xuankong_natal"][
        "interpretation"
    ]["fixed_lingzheng_analysis"]


def test_all_original_period_and_hosting_cases_and_incomplete_audit_rejected():
    reference = json.loads(REF.read_text())
    audit = audit_lingzheng_reference(reference)
    assert audit["matched_numeric_cases"] == audit["checked_numeric_cases"] == 10
    assert audit["whole_book_conformity_established"] is False
    assert audit["real_world_prediction"] == "not_tested"
    reference["cases"].pop()
    with pytest.raises(ValueError):
        audit_lingzheng_reference(reference)
    reference = json.loads(REF.read_text())
    reference["cases"][0]["ling_direction"] = "E"
    assert not audit_lingzheng_reference(reference)["scoped_acceptance_passed"]


def test_fifth_period_unknown_is_two_candidates_not_a_favourable_selection():
    unknown = fixed_result(inputs(5))
    assert unknown["calculation_status"] == "complete"
    assert unknown["selection_status"] == "requires_five_period_half"
    assert unknown["status"] == "partial"
    assert [
        (v["zheng_number"], v["zheng_direction"], v["ling_number"], v["ling_direction"])
        for v in unknown["candidates"]
    ] == [(5, "SW", 8, "NE"), (5, "NE", 2, "SW")]
    for candidate in unknown["candidates"]:
        assert candidate["candidate_only"]
        for p in candidate["palaces"].values():
            assert p["form_assessment"]["condition_match"] is None
    for half in ("first_decade", "second_decade"):
        result = fixed_result(inputs(5, half))
        assert len(result["candidates"]) == 1
        assert result["selection_status"] == "resolved"
        assert result["candidates"][0]["zheng_native_palace"] == "C"
        assert (
            result["candidates"][0]["five_hosting_scope"]
            == "fixed_ground_only_not_natal_seed_borrowing"
        )


def test_water_and_low_terrain_are_independent_three_valued_conditions():
    for low, water, high in itertools.product((True, False, None), repeat=3):
        raw = observation(
            "SW",
            low_lying_terrain_present=low,
            river_water_present=water,
            high_solid_terrain_present=high,
        )
        config = FixedLingzhengRequest.model_validate(
            {"observations": [raw]}
            if any(x is not None for x in (low, water, high))
            else {}
        )
        a = analyze_fixed_lingzheng(config, 8, {})["candidates"][0]["palaces"]["SW"][
            "form_assessment"
        ]
        expected = (
            False if False in (low, water) else None if None in (low, water) else True
        )
        assert a["condition_match"] is expected
    req = inputs()
    req["interpretation"]["fixed_lingzheng"]["observations"] = [
        observation("SW", river_water_present=True, high_solid_terrain_present=False)
    ]
    result = fixed_result(req)
    assert (
        result["candidates"][0]["palaces"]["SW"]["form_assessment"]["condition_match"]
        is None
    )
    assert any(
        p.endswith("SW.low_lying_terrain_present") for p in result["missing_inputs"]
    )


def test_images_unknown_period_and_missing_natal_are_not_confirmation():
    req = inputs()
    req["interpretation"]["fixed_lingzheng"]["observations"][5][
        "observation_basis"
    ] = "image_observed"
    a = fixed_result(req)
    assert a["status"] == "partial"
    assert (
        a["candidates"][0]["palaces"]["SW"]["form_assessment"]["raw_condition_match"]
        is True
    )
    assert (
        a["candidates"][0]["palaces"]["SW"]["form_assessment"]["condition_match"]
        is None
    )
    unknown = fixed_result(inputs(None))
    assert unknown["reference_period_number"] is None and unknown["candidates"] == []
    a = analyze_fixed_lingzheng(FixedLingzhengRequest(), 8, {})
    assert a["flying_star_comparison_status"] == "partial"
    req = inputs(angle=7.5)
    ambiguous = fixed_result(req)
    assert ambiguous["flying_star_comparison_status"] == "candidate_only"
    assert all(
        c["candidate_only"]
        for p in ambiguous["candidates"][0]["palaces"].values()
        for c in p["flying_star_comparisons"]
    )


def test_non_river_water_is_not_a_contradiction_or_a_confirmed_river():
    req = inputs()["interpretation"]
    req["external_forms"] = [
        dict(
            direction="SW",
            water_present=True,
            observation_basis="measured",
            evidence="一般有水已确认",
        )
    ]
    req["fixed_lingzheng"]["observations"][5]["river_water_present"] = False
    XuankongInterpretationRequest.model_validate(req)
    assert Draft202012Validator(
        XuankongInterpretationRequest.model_json_schema()
    ).is_valid(req)


def test_all_432_natal_charts_unchanged_and_current_not_historical_period_used():
    tested = 0
    both = set()
    for natal in range(1, 10):
        for mountain in range(24):
            for offset in (0, 6):
                req = inputs(8, natal=natal, angle=(mountain * 15 + offset) % 360)
                plain = deepcopy(req)
                plain["interpretation"].pop("fixed_lingzheng")
                base = calculate_xuankong_natal(**plain)["layers"]["xuankong_natal"]
                new = calculate_xuankong_natal(**req)["layers"]["xuankong_natal"]
                assert {k: v for k, v in base.items() if k != "interpretation"} == {
                    k: v for k, v in new.items() if k != "interpretation"
                }
                assert (
                    base["interpretation"]["candidates"]
                    == new["interpretation"]["candidates"]
                )
                fixed = new["interpretation"]["fixed_lingzheng_analysis"]["candidates"][
                    0
                ]
                assert (
                    fixed["zheng_direction"] == "NE" and fixed["ling_direction"] == "SW"
                )
                for direction, palace in fixed["palaces"].items():
                    p = new["chart"]["palaces"][direction]
                    c = palace["flying_star_comparisons"][0]
                    assert c["natal_period_number"] == natal
                    assert c["mountain_star_number"] == p["mountain_star_number"]
                    assert c["facing_star_number"] == p["facing_star_number"]
                    assert all(
                        p[r + "_star_number"] == 8
                        for r in c["matching_current_star_roles"]
                        + c["different_current_star_roles"]
                    )
                    if direction == "NE":
                        assert c["matching_current_star_roles"] == (
                            ["mountain"] if p["mountain_star_number"] == 8 else []
                        )
                        assert c["different_current_star_roles"] == (
                            ["facing"] if p["facing_star_number"] == 8 else []
                        )
                    elif direction == "SW":
                        assert c["matching_current_star_roles"] == (
                            ["facing"] if p["facing_star_number"] == 8 else []
                        )
                        assert c["different_current_star_roles"] == (
                            ["mountain"] if p["mountain_star_number"] == 8 else []
                        )
                    else:
                        assert (
                            not c["matching_current_star_roles"]
                            and not c["different_current_star_roles"]
                        )
                    both.update(c["matching_current_star_roles"])
                    both.update(c["different_current_star_roles"])
                tested += 1
    assert tested == 432 and both == {"mountain", "facing"}


@pytest.mark.parametrize(
    "mutation",
    [
        "half_other_period",
        "half_no_evidence",
        "duplicate",
        "coerced_bool",
        "empty_facts",
        "blank_evidence",
        "conflicting_water",
    ],
)
def test_runtime_and_published_schema_reject_invalid_facts(mutation):
    req = inputs()["interpretation"]
    fixed = req["fixed_lingzheng"]
    if mutation == "half_other_period":
        fixed.update(five_period_half="first_decade", half_evidence="确认分段")
    elif mutation == "half_no_evidence":
        req["current_period_number"] = 5
        fixed["five_period_half"] = "first_decade"
    elif mutation == "duplicate":
        fixed["observations"].append(fixed["observations"][0])
    elif mutation == "coerced_bool":
        fixed["observations"][0]["river_water_present"] = "true"
    elif mutation == "empty_facts":
        fixed["observations"] = [observation("N")]
    elif mutation == "blank_evidence":
        fixed["observations"][0]["evidence"] = " "
    else:
        req["external_forms"] = [
            dict(
                direction="N",
                water_present=False,
                observation_basis="measured",
                evidence="明确无水",
            )
        ]
    with pytest.raises(ValidationError):
        XuankongInterpretationRequest.model_validate(req)
    assert not Draft202012Validator(
        XuankongInterpretationRequest.model_json_schema()
    ).is_valid(req)


@pytest.mark.parametrize(
    "current,half,tool",
    [
        (8, None, "xuankong_natal"),
        (5, None, "assess"),
        (5, "second_decade", "assess"),
        (None, None, "assess"),
    ],
)
def test_real_surfaces_and_snapshot_preserve_authors_and_candidates(
    monkeypatch, tmp_path, capsys, current, half, tool
):
    req = inputs(current, half)
    if tool == "assess":
        req = {"methods": ["xuankong_natal"], "xuankong": req}
    spec = next(s for s in CATALOG if s.key == "fengshui_" + tool)
    http = rest_client(monkeypatch).post(spec.rest_path, json=req)
    assert http.status_code == 200, http.text
    protocol = asyncio.run(mcp_call(tool, req))
    assert not protocol.is_error
    p = tmp_path / "lingzheng.json"
    p.write_text(json.dumps(req))
    assert run(["fengshui_" + tool, "--request-file", str(p)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    Draft202012Validator(spec.output_model.model_json_schema()).validate(cli)
    result = cli["layers"]["xuankong_natal"]["interpretation"][
        "fixed_lingzheng_analysis"
    ]
    assert len(result["ruleset"]["sources"]) == 3
    assert result["ruleset"]["sources"][0]["author"] == "沈竹礽正文"
    assert any(r["ruleset_id"] == "shen_fixed_lingzheng_v1" for r in cli["rulesets"])
    assert "固定地盘与山向飞星分别读取" in cli["snapshot_text"]


@pytest.mark.parametrize("bad_fact", ["five_half_in_eight", "contradictory_water"])
def test_invalid_site_facts_fail_consistently_on_all_surfaces(
    monkeypatch, tmp_path, capsys, bad_fact
):
    req = inputs()
    if bad_fact == "five_half_in_eight":
        req["interpretation"]["fixed_lingzheng"].update(
            five_period_half="first_decade", half_evidence="分段只适用于五运"
        )
    else:
        req["interpretation"]["external_forms"] = [
            dict(
                direction="SW",
                water_present=False,
                observation_basis="measured",
                evidence="同一方向明确无水",
            )
        ]
    http = rest_client(monkeypatch).post("/api/fengshui/xuankong_natal", json=req)
    protocol = asyncio.run(mcp_call("xuankong_natal", req))
    p = tmp_path / "invalid.json"
    p.write_text(json.dumps(req))
    code = run(["fengshui_xuankong_natal", "--request-file", str(p)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 422 and protocol.is_error and code != 0
    for result in (http.json(), protocol.structured_content, cli):
        assert result["error_code"] == "validation_error"
        assert "layers" not in result
