"""Source-position expectations, causal counterexamples and public contracts."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.analysis.career import CareerAnalysis
from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "data/bazi_classical_routes_v1/reference.json"
REFERENCE = json.loads(FIXTURE.read_text())


def pillars(values):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, values)))


def test_source_observations_remain_frozen_and_distinct_from_global_adjudication():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == FIXTURE.with_suffix(".sha256").read_text().strip()
    )
    assert len(REFERENCE["cases"]) == 8
    assert "not" in REFERENCE["annotation_origin"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["id"])
def test_original_positions_and_roots(case):
    evidence = build_natal_evidence(pillars(case["pillars"]))
    graph = evidence["classical_routes"]
    expected = case["expected"]
    assert graph["selected_month_role"]["ten_god"] == expected["month_god"]
    assert graph["source"]["source_sha256"] == REFERENCE["source_sha256"]
    if "edge" in expected:
        edge = expected["edge"]
        route = next(r for r in graph["routes"] if r["id"] == edge["route"])
        assert route["status"] == "observed_route"
        assert any(
            (r["from_star"], r["to_star"], r["relation"])
            == (edge["from"], edge["to"], edge["relation"])
            for r in route["edges"]
        )
        if "rooted_helper" in expected:
            assert (
                expected["rooted_helper"]
                in route["helper_root_context"]["with_hidden_root"]
            )
    for expectation, actual in (
        ("shared_root", "output_wealth_shared_roots"),
        ("separation", "wealth_seal_positions"),
    ):
        if expectation in expected:
            assert any(
                all(
                    row.get(key) == value
                    for key, value in expected[expectation].items()
                )
                for row in graph[actual]
            )
    # The finite source observations do not supply missing whole-chart force.
    assert all(r["formation_status"] == "not_adjudicated" for r in graph["routes"])


def test_every_edge_is_resolvable_to_actual_evidence_in_the_same_output():
    for case in REFERENCE["cases"]:
        evidence = build_natal_evidence(pillars(case["pillars"]))
        ids = {
            star["evidence_id"]
            for entries in evidence["ten_gods"].values()
            for star in entries
        }
        assert len(ids) == sum(len(v) for v in evidence["ten_gods"].values())
        for route in evidence["classical_routes"]["routes"]:
            assert route["source_ref"] in {s["id"] for s in evidence["rulesets"]}
            assert set(route["star_refs"]) <= ids
            for edge in route["edges"]:
                assert {edge["from_star"], edge["to_star"]} <= ids


def test_selected_officer_is_not_replaced_by_the_first_hidden_candidate():
    evidence = build_natal_evidence(pillars(["壬戌", "丁未", "戊申", "乙卯"]))
    month = evidence["month_command"]
    assert month["candidates"][0]["ten_god"] == "劫财"
    assert month["selected_god"]["ten_god"] == "正官"
    check = next(
        r for r in evidence["structure_checks"] if r["id"] == "officer_with_wealth_seal"
    )
    assert (
        next(c for c in check["conditions"] if c["id"] == "month_command_anchor")[
            "status"
        ]
        == "matched"
    )


def test_food_month_with_killer_is_not_confused_with_an_unselected_food_pattern():
    shu = build_natal_evidence(pillars(["丁亥", "壬子", "辛巳", "丁酉"]))
    check = next(
        r for r in shu["structure_checks"] if r["id"] == "food_controls_killer"
    )
    assert (
        next(c for c in check["conditions"] if c["id"] == "month_command_anchor")[
            "status"
        ]
        == "matched"
    )
    other = build_natal_evidence(pillars(["辛丑", "丁巳", "丙子", "乙未"]))
    route = next(
        r
        for r in other["classical_routes"]["routes"]
        if r["id"] == "food_generates_wealth"
    )
    assert route["edges"]  # the elemental relation really exists
    assert route["status"] == "not_applicable_to_selected_month"


def test_multiple_matching_stems_do_not_get_arbitrarily_combined_away():
    evidence = build_natal_evidence(pillars(["庚寅", "乙酉", "甲子", "乙亥"]))
    route = next(
        r
        for r in evidence["classical_routes"]["routes"]
        if r["id"] == "peer_combines_killer"
    )
    edges = [e for e in route["edges"] if e["to_star"] == "year:stem:庚"]
    assert len(edges) == 2
    assert all(e["other_matching_stem_positions"] for e in edges)
    assert all(
        e["effect_status"] == "other_matching_stems_require_position_review"
        for e in edges
    )
    assert route["formation_status"] == "not_adjudicated"


def test_shared_month_root_disappears_when_the_actual_root_is_removed():
    chart = pillars(["己卯", "丁丑", "丙寅", "庚寅"])
    before = build_natal_evidence(chart)["classical_routes"][
        "output_wealth_shared_roots"
    ]
    assert any(r["is_month_command"] for r in before)
    chart["month"] = ("丁", "亥")
    after = build_natal_evidence(chart)["classical_routes"][
        "output_wealth_shared_roots"
    ]
    assert not any(r["is_month_command"] for r in after)


def test_career_counts_include_day_hidden_stems_and_preserve_all_top_ties():
    chart = pillars(["甲子", "丙寅", "戊申", "壬戌"])
    result = CareerAnalysis._analyze_dominant_ten_gods(chart, "戊")
    # Manually counted non-day stems and four branches; not engine-generated.
    expected = {
        "比肩": 1.5,
        "劫财": 0,
        "食神": 0.5,
        "伤官": 0.5,
        "偏财": 1.5,
        "正财": 0.5,
        "七杀": 1.5,
        "正官": 0,
        "偏印": 1.5,
        "正印": 0.5,
    }
    assert result["weighted_counts"] == expected
    assert {g["ten_god"] for g in result["top_gods"]} == {
        "比肩",
        "偏财",
        "七杀",
        "偏印",
    }
    assert set(result["tied_primary_gods"]) == {"比肩", "偏财", "七杀", "偏印"}
    assert result["counting_basis"]["excluded_pillars"] == []
    assert result["primary_career_type"].startswith("并列：")


def test_career_signals_and_entrepreneurship_use_the_same_observed_day_stars():
    chart = pillars(["辛酉", "甲午", "甲子", "丙寅"])
    result = CareerAnalysis.analyze_career(chart)
    assert result["dominant_ten_gods"]["weighted_counts"]["正印"] == 0.5
    assert any(
        r["label"] == "官印相生" for r in result["career_structure"]["rule_signals"]
    )
    counts = result["entrepreneurship"]["weighted_counts"]
    assert counts["正印"] == 0.5
    assert result["career_structure"]["score_kind"] == "uncalibrated_rule_index"
    assert result["career_structure"]["level"].startswith("规则索引")


@pytest.mark.parametrize("key", ["bazi_career", "bazi_wealth", "bazi_birth"])
def test_classical_route_evidence_has_the_same_schema_and_facts_on_all_surfaces(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    args = {
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_timezone": "Asia/Shanghai",
        "gender": "男",
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 12,
    }
    response = rest.post(spec.rest_path, json=args)
    code, local = call_cli(
        spec, args, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, args))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        evidence = (
            output["bazi_birth"]["structure_profile"]["evidence_chain"]
            if key == "bazi_birth"
            else output[key.removeprefix("bazi_") + "_analysis"]["evidence_chain"]
        )
        assert (
            evidence["classical_routes"]["selected_month_role"]
            == evidence["month_command"]["selected_god"]
        )


@pytest.mark.parametrize(
    "topic",
    [
        "birth",
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ],
)
def test_published_classical_view_preserves_resolvable_star_references(topic, rest):
    spec = SPECS["bazi_" + topic]
    args = {
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_timezone": "Asia/Shanghai",
        "gender": "男",
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 12,
    }
    fields = suggested_fields(spec, view="classical_routes")
    response = rest.post(
        spec.rest_path,
        json=args,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    evidence = (
        result["bazi_birth"]["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else result[topic + "_analysis"]["evidence_chain"]
    )
    ids = {e["evidence_id"] for rows in evidence["ten_gods"].values() for e in rows}
    for route in evidence["classical_routes"]["routes"]:
        assert set(route["star_refs"]) <= ids
