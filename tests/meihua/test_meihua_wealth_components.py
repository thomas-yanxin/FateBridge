"""The selected wealth supplement keeps every actual role and source atom."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import SPECS, business, rest, surface_calls

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_wealth_components_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
ROLES = ("use", "body_mutual", "use_mutual", "changed_use")
COMPONENTS = {"gain": ("体克用", "用生体"), "loss": ("用克体", "体生用")}


def at_path(out, path):
    value = out
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_hand_geometry_and_all_four_wealth_components(case):
    out = calculate_meihua_cast(casting=case["casting"], interpretation_topic="wealth")
    cast = out["meihua"]
    assert cast["base_hexagram"]["binary_code"] == case["base_code"]
    assert cast["changed_hexagram"]["binary_code"] == case["changed_code"]
    assert cast["mutual_hexagram"]["binary_code"] == case["mutual_code"]
    assert cast["body_trigram"]["name"] == case["body"]
    assert [r["trigram"] for r in cast["stage_relations"]] == case["stage_trigrams"]
    assert [r["relation"] for r in cast["stage_relations"]] == case["stage_relations"]
    reading = out["interpretation"]["wealth_components"]
    assert reading["scope"] == "original_static_body_vs_four_actual_auxiliary_roles"
    assert [r["role"] for r in reading["roles"]] == list(ROLES)
    for index, row in enumerate(reading["roles"]):
        assert row["trigram"] == case["stage_trigrams"][index]
        assert row["relation"] == case["stage_relations"][index]
        assert at_path(out, row["fact_path"])["name"] == row["trigram"]
        assert at_path(out, row["relation_fact_path"]) == row["relation"]
        assert row["body"] == case["body"]
        assert row["seasonal_strength"] is None
        assert row["effect_after_all_qualifications"] is None
    for side, relations in COMPONENTS.items():
        group = reading["source_groups"][side]
        assert [c["relation"] for c in group["components"]] == list(relations)
        for component in group["components"]:
            expected = [
                role
                for role, relation in zip(ROLES, case["stage_relations"])
                if relation == component["relation"]
            ]
            assert component["matching_roles"] == expected
            assert component["present"] is bool(expected)
        assert group["all_named_components_present"] is all(
            c["present"] for c in group["components"]
        )
        assert group["junction_semantics"] == "not_adjudicated"
        assert group["full_clause_applies"] is None
    assert (
        reading["event_time"]
        is reading["real_financial_change"]
        is reading["success_probability"]
        is None
    )
    assert reading["independent_observations"] == 0
    assert (
        reading["source_groups"]["gain"]["quote"]
        == json.loads((FIXTURE / "source-reading.json").read_text())["quote_gain"]
    )
    assert (
        reading["source_groups"]["loss"]["quote"]
        == json.loads((FIXTURE / "source-reading.json").read_text())["quote_loss"]
    )


def test_original_fixture_bytes_and_hand_scope_are_locked():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["expected_values_generated_by_production"] is False
    assert manifest["new_implementation_not_yet_present"] is True
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("index", [7, 9])
def test_every_count_candidate_uses_own_body_and_component_paths(basis, index):
    casting = {**CASES[index]["casting"], "line_sum_basis": basis}
    out = calculate_meihua_cast(
        casting=casting, interpretation_topic="wealth", season_month_branch="午"
    )
    readings = out["interpretation"]["casting_readings"]
    assert len(readings) == 2
    for i, candidate in enumerate(readings):
        component = candidate["wealth_components"]
        fixture = next(
            c
            for c in CASES[index : index + 2]
            if c["casting"]["line_sum_basis"] == candidate["line_sum_basis"]
        )
        assert [r["relation"] for r in component["roles"]] == fixture["stage_relations"]
        assert component["body"] == fixture["body"]
        for role in component["roles"]:
            assert role["fact_path"].startswith(f"meihua.counting_variants.{i}.")
            assert at_path(out, role["relation_fact_path"]) == role["relation"]
            assert (
                at_path(out, role["strength_fact_path"])["strength"]
                == role["seasonal_strength"]
            )
            assert (
                at_path(out, role["control_qualification_fact_path"])
                == role["countercontrol_qualification"]
            )
    selected = next(r for r in readings if r["selected"])["wealth_components"]
    assert [(r["trigram"], r["relation"]) for r in selected["roles"]] == [
        (r["trigram"], r["relation"])
        for r in out["interpretation"]["wealth_components"]["roles"]
    ]


@pytest.mark.parametrize(
    "topic", ["general", "weather", "planning", "reputation", "transaction"]
)
def test_other_topics_never_borrow_wealth_components(topic):
    out = calculate_meihua_cast(casting=CASES[0]["casting"], interpretation_topic=topic)
    assert out["interpretation"]["wealth_components"] is None


def test_mixed_incoming_and_leaking_relations_are_visible_in_summary():
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="wealth"
    )
    summary = out["summary"]
    assert all(text in summary for text in ["初用坎", "体互兑", "用互离", "变用坤"])
    assert all(text in summary for text in ["用生体", "用克体", "体生用", "体克用"])
    assert (
        out["interpretation"]["topic_reading"]["clause_id"]
        == "wealth_use_generates_body"
    )
    assert "未综合" in summary


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_wealth_field_card_agrees_on_rest_mcp_cli(tool, surface_calls):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = (
        {"casting": CASES[0]["casting"]}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 22,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    payload["interpretation_topic"] = "wealth"
    fields = suggested_fields(spec, view="wealth")
    assert "interpretation.wealth_components" in fields
    response, result, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
        cli_first=False,
    )
    assert response.status_code == 200, response.text
    assert not result.is_error, result
    assert code == 0, cli
    assert (
        business(response.json())
        == business(result.structured_content)
        == business(cli)
    )


def test_qualification_does_not_erase_relation_or_turn_into_money():
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic="wealth",
        season_month_branch="酉",
    )
    roles = out["interpretation"]["wealth_components"]["roles"]
    assert (
        roles[0]["countercontrol_qualification"]["qualification"]
        == "support_constrained"
    )
    assert roles[1]["countercontrol_qualification"]["qualification"] == "partial_relief"
    assert [r["relation"] for r in roles] == CASES[0]["stage_relations"]
    assert roles[0]["seasonal_strength"] == "原文未定"
    assert all(r["effect_after_all_qualifications"] is None for r in roles)
    for role in roles:
        assert (
            at_path(out, role["strength_fact_path"])["strength"]
            == role["seasonal_strength"]
        )


def test_partial_and_absent_source_components_never_become_whole_clause_match():
    partial = calculate_meihua_cast(
        casting=CASES[2]["casting"], interpretation_topic="wealth"
    )["interpretation"]["wealth_components"]
    none = calculate_meihua_cast(
        casting=CASES[6]["casting"], interpretation_topic="wealth"
    )["interpretation"]["wealth_components"]
    assert any(c["present"] for c in partial["source_groups"]["gain"]["components"])
    assert not partial["source_groups"]["gain"]["all_named_components_present"]
    assert partial["source_groups"]["gain"]["full_clause_applies"] is None
    assert not any(
        c["present"] for g in none["source_groups"].values() for c in g["components"]
    )
    assert all(g["full_clause_applies"] is None for g in none["source_groups"].values())


def test_cached_profile_and_role_evidence_are_isolated_from_returned_mutation():
    from fatebridge.core.meihua_wealth import wealth_component_ruleset

    profile = wealth_component_ruleset()
    profile["rules"][0]["named_relations"].clear()
    assert wealth_component_ruleset()["rules"][0]["named_relations"] == list(
        COMPONENTS["gain"]
    )
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="wealth"
    )
    original = out["interpretation"]["internal_countercontrol"]["qualifications"][
        0
    ].copy()
    out["interpretation"]["wealth_components"]["roles"][0][
        "countercontrol_qualification"
    ]["qualification"] = "forged"
    assert (
        out["interpretation"]["internal_countercontrol"]["qualifications"][0]
        == original
    )
