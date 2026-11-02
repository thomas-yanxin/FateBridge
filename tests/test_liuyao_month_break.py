"""Fixed primary-source expectations plus separate hidden wiring regressions."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.liuyao_judgment import build_conditional_analysis
from fatebridge.core.liuyao_month_break import PROFILE, day_value_exception
from fatebridge.core.local_techniques.sixyao import (
    _BAGONG_BASES,
    _build_sixyao_enrichment,
)
from scripts.build_liuyao_month_break_profile import build
from tests.test_liuyao_conditions import mounted

REFERENCE = Path(__file__).parent / "fixtures/liuyao_month_break_v24"
CASES = json.loads((REFERENCE / "cases-r1.json").read_text())["cases"]


def analysis(case, hidden=None, focus_kind=None):
    info, lines = mounted(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=hidden or [],
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        focus_kind=focus_kind,
        timing_days=0,
    )


def test_frozen_source_and_all_original_erroneous_expectations_are_retained():
    assert build() == PROFILE
    old = json.loads((REFERENCE / "cases.json").read_text())["cases"]
    assert len(old) == 9 and len(CASES) == 13
    assert old[0]["expected_supported"] is True
    assert CASES[0]["expected_supported"] is None
    assert (
        "qualified dark activity"
        in json.loads((REFERENCE / "expectation-errata.json").read_text())["reason"]
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_source_backed_day_value_and_independent_control_counterexamples(case):
    result = analysis(case)
    p = case["focus_line"]
    month = result["month_break_conditions"]["lines"][p - 1]
    strength = result["classical_assessment"]["lines"][p - 1]["strength"]
    generation = result["generation_conditions"]
    back = result["back_generation_conditions"]["sources"][p - 1]
    assert month["branch"] == case["expected_branch"]
    assert month["raw_month_break"] is case["raw_month_break"]
    assert month["day_value_exception"] is case["day_value_exception"]
    if case["raw_month_break"]:
        assert result["lines"][p - 1]["monthly_strength"]["category"] == "月破"
    checks = {
        "expected_calendar_month_opposition": any(
            h["location"] == "month" and h["reason"] == "月破"
            for h in strength["oppositions"]
        ),
        "expected_supported": strength["is_supported"],
        "expected_target_admission": generation["focus"]["target_reception_condition"],
        "expected_source_generation": generation["sources"][p - 1]["condition_match"],
        "expected_own_changed_branch": back["changed_branch"],
        "expected_changed_raw_month_break": back["changed_month_break"],
        "expected_raw_back_generation": back["raw_condition_match"],
        "expected_qualified_back_generation": back["condition_match"],
    }
    for source, key in [
        (3, "expected_control_from3"),
        (3, "expected_static_control_from3"),
        (5, "expected_control_from5"),
    ]:
        if key in case:
            checks[key] = next(
                c["condition_match"]
                for c in result["control_conditions"]["controls"]
                if c["source_position"] == source and c["target_position"] == p
            )
    for key, value in checks.items():
        if key in case:
            assert value == case[key], key
    if case["id"] in {
        "static-day-value-excludes-month-opposition",
        "moving-day-value-retains-independent-day-root",
    }:
        actor = next(
            c
            for c in result["control_conditions"]["controls"]
            if c["source_position"] == 3 and c["target_position"] == p
        )
        assert actor["source_active"] is True and actor["source_activity_match"] is True
    assert (
        result["month_break_conditions"]["source_sha256"] == PROFILE["source"]["sha256"]
    )


@pytest.mark.parametrize(
    "code,position,month,day",
    [("001101", 3, "寅", "甲申"), ("000011", 1, "丑", "乙未")],
)
def test_actual_hidden_mounting_does_not_release_day_valued_flying_month_break(
    code, position, month, day
):
    # Post-freeze integration checks, not additional independent ancient cases.
    info, rows = _build_sixyao_enrichment(code, code, day[0])
    palace = next(c for p, c, _ in _BAGONG_BASES if p == info["current_palace"])
    _, pure = _build_sixyao_enrichment(palace, palace, day[0])
    present = {r["liuqin"] for r in rows}
    hidden = [
        {**r, "flying_branch": rows[i]["branch"]}
        for i, r in enumerate(pure)
        if r["liuqin"] not in present
    ]
    target = next(h for h in hidden if h["position"] == position)
    assert day_value_exception(target["flying_branch"], month, day[1])
    case = dict(
        base_code=code,
        changed_code=code,
        month=month,
        day_ganzhi=day,
        focus_line=position,
    )
    result = analysis(case, hidden, "hidden")
    h = next(h for h in result["hidden_conditions"] if h["position"] == position)
    assert "flying_void_or_month_break_release" not in h["reception"]["support_reasons"]
    assert "calendar_strikes_flying" not in h["reception"]["support_reasons"]
    rule = next(
        c for c in h["supporting_conditions"] if c["rule_id"] == "flying_struck"
    )
    assert rule["matched"] is True and rule["qualified_matched"] is False
    fact = next(
        x
        for x in result["month_break_conditions"]["hidden"]
        if x["position"] == position
    )
    assert fact["flying"]["raw_month_break"] is True
    assert fact["flying"]["calendar_month_opposition"] is False
    assert result["month_break_conditions"]["focus"] is None


def test_role_conditions_do_not_reintroduce_the_excluded_month_control():
    case = next(c for c in CASES if c["id"] == "pure-static-day-value-no-active-metal")
    result = analysis({**case, "focus_line": 1})
    role = next(r for r in result["role_effects"]["lines"] if r["position"] == 3)
    assert role["role"] == "忌神"
    assert role["atom_values"]["injured_relation"] is True
    assert role["atom_values"]["void_or_break"] is True
    assert role["conditional_atom_values"]["injured_relation"] is False
    assert role["conditional_atom_values"]["calendar_moving_controls"] is False
    assert role["conditional_atom_values"]["void_or_break"] is False
