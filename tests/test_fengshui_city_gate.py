"""Printed Shen clauses, independent period, exact yuan and conditional forms."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.city_gate_inputs import CityGateRequest
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.validation.fengshui import audit_city_gate_reference
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

FOLDER = Path(__file__).parent / "fixtures/fengshui_city_gate_v1"
REFERENCE = json.loads((FOLDER / "reference.json").read_text())
ANGLES = {
    "子": 0,
    "癸": 15,
    "丑": 30,
    "艮": 45,
    "寅": 60,
    "甲": 75,
    "卯": 90,
    "乙": 105,
    "辰": 120,
    "巽": 135,
    "巳": 150,
    "丙": 165,
    "午": 180,
    "丁": 195,
    "未": 210,
    "坤": 225,
    "申": 240,
    "庚": 255,
    "酉": 270,
    "辛": 285,
    "戌": 300,
    "乾": 315,
    "亥": 330,
    "壬": 345,
}


def request(facing="乾", period=2, observations=None):
    return {
        "house": {"facing_degrees": ANGLES[facing], "north_reference": "magnetic"},
        "city_gate": {
            "reference_period_number": period,
            "period_evidence": "虚构原文数值例，不是真实房屋",
            "observations": observations or [],
        },
    }


def analysis(data):
    return calculate_xuankong_natal(**data)["layers"]["xuankong_natal"][
        "city_gate_analysis"
    ]


def gate(data, name):
    return next(
        g
        for g in analysis(data)["candidates"][0]["gates"]
        if g["mountain"]["name"] == name
    )


def observation(**facts):
    return {
        "mountain": "子",
        "observation_basis": "user_confirmed",
        "evidence": "虚构观察；不是真实现场",
        **facts,
    }


def test_original_page_fingerprints_and_source_edition_are_explicit():
    for image in REFERENCE["images"]:
        assert (
            hashlib.sha256((FOLDER / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert not REFERENCE["historical_outcomes_used_for_predictive_validation"]
    assert "978-7-5117-0801-4" in REFERENCE["source"]["G2"]["source_version"]


def test_source_audit_keeps_negative_cases_and_detects_new_disagreements():
    audit = audit_city_gate_reference(REFERENCE)
    assert audit["checked"] == audit["matched"] == 20
    assert not audit["whole_book_conformity_established"]
    changed = deepcopy(REFERENCE)
    changed["zi_gate_nine_periods"][0]["eligible"] = True
    audit = audit_city_gate_reference(changed)
    assert not audit["scoped_acceptance_passed"] and len(audit["disagreements"]) == 1
    changed["zi_gate_nine_periods"].pop()
    with pytest.raises(ValueError):
        audit_city_gate_reference(changed)


@pytest.mark.parametrize("case", REFERENCE["zi_gate_nine_periods"])
def test_all_nine_printed_zi_gate_period_clauses(case):
    actual = gate(request(case["facing"], case["period"]), case["gate"])
    assert actual["seed_star_number"] == case["seed"]
    assert actual["mapped_mountain"] == case["mapped_mountain"]
    assert actual["reference_star_reaches_gate_by_reverse_flight"] == case["eligible"]
    if case["eligible"]:
        assert actual["star_at_gate"] == case["period"]


@pytest.mark.parametrize("case", REFERENCE["same_yuan_gates"])
def test_printed_adjacent_same_yuan_examples(case):
    actual = analysis(request(case["facing"]))["candidates"][0]["gates"]
    assert {g["mountain"]["name"] for g in actual} == set(case["gates"])


@pytest.mark.parametrize("case", REFERENCE["specific_numeric_cases"])
def test_specific_original_gate_examples(case):
    actual = gate(request(case["facing"], case["period"]), case["gate"])
    assert actual["reference_star_reaches_gate_by_reverse_flight"] == case["eligible"]
    for source_key, result_key in [
        ("seed", "seed_star_number"),
        ("mapped_mountain", "mapped_mountain"),
    ]:
        if source_key in case:
            assert actual[result_key] == case[source_key]


def test_numeric_gate_does_not_require_inventing_natal_period_or_site_facts():
    result = calculate_xuankong_natal(**request())
    raw = result["layers"]["xuankong_natal"]
    a = raw["city_gate_analysis"]
    assert raw["status"] == "partial" and raw["candidates"] == []
    assert a["status"] == a["calculation_status"] == "complete"
    assert a["missing_inputs"] == []
    assert all(
        g["form_assessment"]["status"] == "not_requested"
        for g in a["candidates"][0]["gates"]
    )
    assert result["coverage"]["city_gate_calculation_status"] == "complete"
    assert "独立沈氏城门" in result["snapshot_text"]


def test_reference_period_does_not_overwrite_historical_natal_numbers():
    data = {
        **request(),
        "period": {
            "basis": "expert_confirmed",
            "period_number": 8,
            "evidence": "虚构八运盘",
        },
    }
    original = calculate_xuankong_natal(
        **{k: v for k, v in data.items() if k != "city_gate"}
    )["layers"]["xuankong_natal"]
    changed = calculate_xuankong_natal(**data)["layers"]["xuankong_natal"]
    assert changed["chart"] == original["chart"]
    assert changed["period_context"] == original["period_context"]
    assert changed["source_comparison"] == original["source_comparison"]
    assert changed["city_gate_analysis"]["reference_period_context"]["number"] == 2
    assert [r["ruleset_id"] for r in calculate_xuankong_natal(**data)["rulesets"]] == [
        "xuankong_zhongzhou_v1",
        "shen_2011_natal_numeric_comparison_v2",
        "shen_city_gate_v1",
    ]


def test_image_and_uncertain_bearing_preserve_conditionality():
    obs = observation(
        water_present=True,
        encircling_form_present=True,
        sole_opening_with_water=True,
        observation_basis="image_observed",
    )
    a = analysis(request(observations=[obs]))
    g = next(g for g in a["candidates"][0]["gates"] if g["mountain"]["name"] == "子")
    assert g["form_assessment"]["raw_pattern_match"] is True
    assert g["combined_condition_match"] is None and a["status"] == "partial"
    data = request()
    data["house"]["facing_degrees"] = 307.5
    a = analysis(data)
    assert len(a["candidates"]) == 2 and all(
        c["candidate_only"] for c in a["candidates"]
    )
    assert all(
        g["combined_condition_match"] is None
        for c in a["candidates"]
        for g in c["gates"]
    )


def test_multiple_openings_exclude_pattern_even_when_numeric_rule_matches():
    g = gate(
        request(
            observations=[
                observation(
                    water_present=True,
                    multiple_openings_present=True,
                    three_way_water_junction_present=True,
                    water_reflects_towards_site=True,
                )
            ]
        ),
        "子",
    )
    assert g["reference_star_reaches_gate_by_reverse_flight"] is True
    assert (
        g["form_assessment"]["condition_match"] is False
        and g["combined_condition_match"] is False
    )


def test_confirmed_sole_opening_and_three_way_patterns_keep_actual_conditions():
    for facts in [
        dict(encircling_form_present=True, sole_opening_with_water=True),
        dict(
            water_present=True,
            multiple_openings_present=False,
            three_way_water_junction_present=True,
            water_reflects_towards_site=True,
        ),
        dict(
            multiple_openings_present=False,
            three_way_water_junction_present=True,
            water_reflects_towards_site=True,
        ),
    ]:
        g = gate(request(observations=[observation(**facts)]), "子")
        assert g["combined_condition_match"] is True
        assert g["form_assessment"]["scope"].endswith(
            "not_complete_form_quality_or_reality_verdict"
        )
    partial = gate(request(observations=[observation(water_present=True)]), "子")
    assert partial["combined_condition_match"] is None
    wrong = analysis(
        request(observations=[observation(mountain="壬", water_present=True)])
    )
    assert wrong["unmatched_observations"][0]["mountain"] == "壬"


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"reference_period_number": True, "period_evidence": "x"},
        {"reference_period_number": 2, "period_evidence": " "},
        {
            "reference_period_number": 2,
            "period_evidence": "x",
            "observations": [observation()],
        },
        {
            "reference_period_number": 2,
            "period_evidence": "x",
            "observations": [
                observation(water_present=False, sole_opening_with_water=True)
            ],
        },
        {
            "reference_period_number": 2,
            "period_evidence": "x",
            "observations": [
                observation(water_present=True),
                observation(water_present=False),
            ],
        },
    ],
)
def test_invalid_explicit_inputs_match_runtime_and_published_schema(patch):
    with pytest.raises(ValidationError):
        CityGateRequest.model_validate(patch)
    assert list(
        Draft202012Validator(CityGateRequest.model_json_schema()).iter_errors(patch)
    )


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_city_gate_matches_rest_mcp_cli(monkeypatch, tmp_path, capsys, tool):
    data = request(
        observations=[
            observation(encircling_form_present=True, sole_opening_with_water=True)
        ]
    )
    if tool == "assess":
        data = {"methods": ["xuankong_natal"], "xuankong": data}
    http = rest_client(monkeypatch).post("/api/fengshui/" + tool, json=data)
    protocol = asyncio.run(mcp_call(tool, data))
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_" + tool, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )


def test_real_mcp_strict_projection_preserves_branch_and_provenance():
    result = asyncio.run(
        mcp_call(
            "xuankong_natal",
            {
                **request(),
                "fields": [
                    "layers.xuankong_natal.city_gate_analysis",
                    "coverage.city_gate_status",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    assert result.structured_content["coverage"]["city_gate_status"] == "complete"
    a = result.structured_content["layers"]["xuankong_natal"]["city_gate_analysis"]
    assert a["ruleset"]["sources"][0]["source_id"] == "G1"
    assert len(a["candidates"][0]["gates"]) == 2


def test_city_gate_observations_respect_explicit_unconfirmed_floorplan_geometry():
    data = {
        "methods": ["xuankong_natal"],
        "xuankong": request(observations=[observation(water_present=True)]),
        "environmental_context": {
            "orientation": {
                "direction_confirmed": True,
                "north_reference": "magnetic",
                "floorplan_alignment_confirmed": False,
                "center_confirmed": False,
                "evidence": "虚构示例，立极尚未确认",
            }
        },
    }
    with pytest.raises(ValidationError, match="中心未确认"):
        AssessRequest.model_validate(data)
    data["xuankong"]["city_gate"]["observations"] = []
    # A theoretical bearing calculation is still possible; physical water
    # positions are not manufactured from the incomplete plan.
    assert AssessRequest.model_validate(data)


def test_complete_nine_by_twenty_four_domain_keeps_each_gate_chart_and_yuan():
    for period in range(1, 10):
        for facing in ANGLES:
            a = analysis(request(facing, period))
            assert a["calculation_status"] == "complete" and len(a["candidates"]) == 1
            candidate = a["candidates"][0]
            assert len(candidate["gates"]) == 2
            for g in candidate["gates"]:
                assert (
                    g["same_yuan"]
                    == candidate["facing"]["yuan"]
                    == g["mountain"]["yuan"]
                )
                assert sorted(g["gate_chart"].values()) == list(range(1, 10))
                assert (g["star_at_gate"] == period) == g[
                    "reference_star_reaches_gate_by_reverse_flight"
                ]
                assert g["home_star_number"] != 5
