"""Shared month-qualified metal/Si growth and preserved raw phase facts."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.liuyao_growth import PROFILE
from scripts.build_liuyao_growth_profile import build
from tests.test_liuyao_roles import classical

BASE = Path(__file__).parent / "fixtures/liuyao_growth_v18"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]
ERRATA = json.loads((BASE / "input-errata.json").read_text())
for change in ERRATA["changes"]:
    case = next(c for c in CASES if c["id"] == change["case_id"])
    assert case[change["field"]] == change["old_value"]
    case[change["field"]] = change["new_value"]


def test_frozen_original_book_clauses_and_expectations():
    assert build() == PROFILE
    for name, digest in json.loads((BASE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert len(CASES) == 10
    assert (
        hashlib.sha256((BASE / "input-errata.json").read_bytes()).hexdigest()
        == json.loads((BASE / "input-errata-freeze.json").read_text())["sha256"]
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_month_qualified_growth_and_independent_strength(case):
    result = classical(case)
    index = case["position"] - 1
    growth = result["growth_conditions"]["lines"][index]
    assert growth["branch"] == case["branch"]
    assert growth["position_match"] is case["expected_raw_growth"]
    assert growth["condition_match"] is case["expected_growth"]
    assert (
        result["classical_assessment"]["lines"][index]["strength"]["is_supported"]
        is case["expected_strength"]
    )
    role = next(
        r for r in result["role_effects"]["lines"] if r["position"] == case["position"]
    )
    assert role["atom_values"]["day_growth_peak"] is case["expected_raw_growth"]
    assert role["conditional_atom_values"]["day_growth_peak"] is case["expected_growth"]
    clause = next(
        r
        for r in role["supporting_conditions"]
        if r["rule_id"]
        == ("yuan_support_3" if role["role"] == "元神" else "ji_support_4")
    )
    assert clause["matched"] is case["expected_raw_growth"]
    assert clause["conditional_matched"] is case["expected_growth"]
    for path in growth["month_support_fact_paths"]:
        value = {"liuyao_evidence": {"conditional_analysis": result}}
        for part in path.split("."):
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert value["location"] == "month"


def test_shared_source_qualification_changes_without_erasing_element_relation():
    case = {**CASES[0], "changed_code": "000001"}
    result = classical(case)
    growth = result["growth_conditions"]["lines"][5]
    assert growth["raw_day_element_relation"] == "克爻"
    assert growth["day_control_in_calendar_oppositions"] is False
    source = result["generation_conditions"]["sources"][5]
    assert source["condition_match"] is True
    assert source["back_generation_condition"] is False
    assert not any(
        a["location"] == "day" for a in source["retained_calendar_oppositions"]
    )
    pair = next(
        p
        for p in result["generation_conditions"]["generations"]
        if (p["source_position"], p["target_position"]) == (6, 5)
    )
    assert pair["condition_match"] is True
    role = next(r for r in result["role_effects"]["lines"] if r["position"] == 6)
    assert role["atom_values"]["calendar_moving_controls"] is True
    assert role["conditional_atom_values"]["calendar_moving_controls"] is False
    assert role["conditional_atom_values"]["injured_relation"] is False
    assert any(
        a["location"] == "day"
        and a["relation"] == "克爻"
        and a["control_condition_match"] is False
        for a in role["actors"]
    )


def test_growth_does_not_override_own_back_control_or_fill_target_void():
    back = classical(CASES[5])
    assert back["growth_conditions"]["lines"][2]["condition_match"] is True
    assert back["generation_conditions"]["sources"][2]["condition_match"] is False
    assert any(
        a["location"] == "changed"
        for a in back["classical_assessment"]["lines"][2]["strength"]["oppositions"]
    )
    void = classical(CASES[4])
    assert void["lines"][0]["activity"]
    assert void["void_conditions"]["focus"]["is_xunkong"] is True


def test_updated_old_static_case_uses_calendar_growth_not_hypothetical_back_support():
    from tests.test_liuyao_conditions import conditional_case
    from tests.test_liuyao_rescue import CASES as OLD_CASES

    case = next(
        c for c in OLD_CASES if c["id"] == "static-raw-transformation-not-borrowed"
    )
    result = conditional_case(case)
    source = result["back_generation_conditions"]["sources"][4]
    assert (
        source["is_actual_moving"] is False
        and source["changed_branch"] is None
        and source["condition_match"] is False
    )
    control = next(
        c
        for c in result["control_conditions"]["controls"]
        if (c["source_position"], c["target_position"]) == (5, 2)
    )
    assert control["condition_match"] is True
    assert control["source_rescue_used"] is False
    assert control["source_calendar_supported"] is True
    assert result["growth_conditions"]["lines"][4]["independent_month_support"] is True


def test_hidden_metal_uses_same_qualified_day_and_flying_metal_is_not_falsely_struck():
    from fatebridge.core.local_techniques.sixyao import (
        build_sixyao_result as build_result,
    )

    metal = build_result(
        date="2004-10-05",
        time="12:00:00",
        gua_code="111001",
        focus_kind="hidden",
        focus_line=3,
    )
    row = next(
        h
        for h in metal["liuyao_evidence"]["conditional_analysis"]["hidden_conditions"]
        if h["position"] == 3
    )
    assert row["branch"] == "申" and row["reception"]["condition_match"] is True
    assert row["reception"]["calendar_growth_rule_applied"] is True
    assert row["reception"]["calendar_growth_source_url"].endswith("#page=97")
    struck = next(
        c
        for c in row["obstructing_conditions"]
        if c["rule_id"] == "hidden_calendar_struck"
    )
    assert struck["matched"] is True and struck["qualified_matched"] is False
    assert "伏神被日月冲克" not in metal["snapshot_text"]
    assert (
        "hidden_calendar_opposition_requires_resolution"
        not in row["reception"]["pending_reasons"]
    )
    flying = build_result(
        date="2004-10-05",
        time="12:00:00",
        gua_code="001101",
        focus_kind="hidden",
        focus_line=3,
    )
    row = next(
        h
        for h in flying["liuyao_evidence"]["conditional_analysis"]["hidden_conditions"]
        if h["position"] == 3
    )
    assert row["branch"] == "亥" and row["flying_branch"] == "申"
    assert "calendar_strikes_flying" not in row["reception"]["support_reasons"]
    assert row["reception"]["flying_growth_source_path"].endswith(
        "growth_conditions.lines.2"
    )
    struck = next(
        c for c in row["supporting_conditions"] if c["rule_id"] == "flying_struck"
    )
    assert struck["matched"] is True and struck["qualified_matched"] is False
    assert "日月动爻冲克飞神" not in flying["snapshot_text"]
