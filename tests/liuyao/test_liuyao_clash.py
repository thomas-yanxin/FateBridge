"""Original clash distinctions, source structures and synthetic counterexamples."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.liuyao.build_profile import build_profile
from tests.liuyao.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_clash_v10"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]


def test_clash_reference_remains_frozen():
    from fatebridge.core.liuyao_clash import PROFILE

    assert build_profile("clash") == PROFILE
    frozen = json.loads((REFERENCE / "freeze.json").read_text())
    for name, digest in frozen["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_day_clash_break_fill_and_scatter_are_different(case):
    result = conditional_case(case)
    detail = result["clash_conditions"]["focus"]
    assert detail["branch"] == case["expected_branch"]
    assert detail["is_day_clash"] is case["expected_day_clash"]
    assert detail["day_void_fill_condition"] is case["expected_fill"]
    assert detail["day_break_condition"] is case["expected_day_break"]
    assert detail["moving_scatter_condition"] is case["expected_scattered"]
    assert detail["scatter_status"] and detail["day_break_status"]
    if case["id"] == "synthetic-earth-peer-and-clash":
        assert result["lines"][3]["activity_condition_match"] is None
        assert result["control_conditions"]["activity_resolution_passes"] >= 2
        assert result["control_conditions"]["activity_resolution_passes"] <= 7
    strength = result["classical_assessment"]["focus"]["strength"]
    for expected, field in [
        ("expected_weak", "is_weak"),
        ("expected_supported", "is_supported"),
    ]:
        if expected in case:
            assert strength[field] is case[expected]
    if "expected_activity" in case:
        assert (
            result["lines"][case["focus_line"] - 1]["activity_condition_match"]
            is case["expected_activity"]
        )
    if "expected_day_injury" in case:
        assert detail["day_clash_harm_condition"] is case["expected_day_injury"]
    if "expected_back_clash" in case:
        assert detail["back_clash"] is case["expected_back_clash"]
        assert detail["back_control"] is case["expected_back_control"]
    if "expected_moving_clash_positions" in case:
        assert [
            a["position"] for a in detail["clash_actors"] if a["location"] == "visible"
        ] == case["expected_moving_clash_positions"]
    assert "probability" not in detail and "predicted_success" not in detail


def test_raw_role_day_clash_is_not_an_applied_injury_without_a_harm_condition():
    result = conditional_case({**CASES[3], "focus_line": 2})
    water = next(r for r in result["role_effects"]["lines"] if r["position"] == 4)
    assert water["atom_values"]["injured_relation"] is True
    assert water["conditional_atom_values"]["injured_relation"] is False


def test_confirmed_current_void_filling_is_not_the_same_as_no_longer_in_xunkong():
    result = conditional_case(CASES[6])
    assert result["clash_conditions"]["focus"]["day_void_fill_condition"] is True
    void = result["void_conditions"]["focus"]
    assert void["is_xunkong"] is True
    assert (
        next(
            r for r in void["not_empty_conditions"] if r["rule_id"] == "day_void_fill"
        )["matched"]
        is True
    )


def test_not_scattered_does_not_remove_own_back_control():
    result = conditional_case(CASES[9])
    assert result["clash_conditions"]["focus"]["moving_scatter_condition"] is False
    assert result["lines"][4]["outgoing_obstructions"]

    huan = conditional_case(CASES[0])
    assert huan["clash_conditions"]["focus"]["moving_scatter_condition"] is False
    assert any(
        h["location"] == "day" and h["reason"] == "日月克爻"
        for h in huan["classical_assessment"]["focus"]["strength"]["oppositions"]
    )


def test_unresolved_dark_activity_is_not_confirmed_harmony_or_nonvoid_activity():
    from tests.liuyao.test_liuyao_control import CASES as CONTROL_CASES

    result = conditional_case(CONTROL_CASES[3])
    gold = next(
        c
        for c in result["three_harmony"]["candidates"]
        if c["group_branches"] == list("巳酉丑")
        and c["pattern"] == "base_three_branches"
    )
    assert gold["active_positions"] == [3, 5]
    assert gold["qualified_active_positions"] == [3]
    assert gold["unresolved_activity_positions"] == [5]
    assert gold["status"] == "formation_requires_activity_resolution"
    active = next(
        r
        for r in result["void_conditions"]["lines"][4]["not_empty_conditions"]
        if r["rule_id"] == "active"
    )
    assert active["matched"] is None and active["status"] == "unresolved"


def test_canonical_hidden_water_does_not_borrow_unresolved_dark_metal():
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    # Modern synthetic input, independently mounted by the public builder.
    result = build_sixyao_result(
        date="2000-02-27", time="12:00:00", gua_code="000101", changed_code="000111"
    )
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assert detail["lines"][3]["activity_condition_match"] is None
    hidden = next(h for h in detail["hidden_conditions"] if h["position"] == 1)
    assert hidden["branch"] == "子" and hidden["flying_branch"] == "未"
    generated = next(
        r
        for r in hidden["supporting_conditions"]
        if r["rule_id"] == "moving_generates_hidden"
    )
    assert generated["matched"] is None
    assert any(
        a["position"] == 4 and a["effect_status"] == "activity_qualification_pending"
        for a in generated["actors"]
    )


def test_static_day_break_snapshot_does_not_mislabel_it_as_elemental_control():
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    result = build_sixyao_result(
        date="2000-03-24", time="12:00:00", gua_code="110110", focus_line=4
    )
    assert result["nongli"]["dayGanZi"] == "辛巳"
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assert detail["clash_conditions"]["focus"]["day_break_condition"] is True
    assert "静爻日破条件匹配，未见已列独立生扶" in result["snapshot_text"]


def test_clash_focus_does_not_apply_original_day_clash_to_changed_or_hidden_focus():
    result = conditional_case(CASES[0], focus_kind="changed")
    assert result["focus"]["selected"]["branch"] == "子"
    assert result["clash_conditions"]["focus"] is None


def test_clash_models_accept_leaf_projection_without_siblings():
    from fatebridge.core.output_liuyao_clash import ClashConditions, LineClash

    assert (
        LineClash.model_validate({"day_break_status": "no_day_clash"}).day_break_status
        == "no_day_clash"
    )
    assert (
        ClashConditions.model_validate({"source_sha256": "test"}).source_sha256
        == "test"
    )


def test_prior_true_tomb_annotation_retains_unknown_opening_and_clear_counterfactual():
    from tests.liuyao.test_liuyao_strength import CASES as STRENGTH_CASES
    from tests.liuyao.test_liuyao_strength import classical

    original = next(c for c in STRENGTH_CASES if c["id"] == "synthetic-weak-day-tomb")
    assert original["expected_true_tomb"] is True
    focus = classical(original)["classical_assessment"]["focus"]
    assert focus["strength"]["is_weak"] is True
    assert focus["entered_tomb"] is None
    # A distinct synthetic upper trigram removes the potential Chou breaker.
    # It retains lower Kun's third Mao, Shen month, Yi-Wei day and one upper move.
    clear = classical({**original, "base_code": "000111", "changed_code": "000110"})
    focus = clear["classical_assessment"]["focus"]
    assert focus["branch"] == "卯" and focus["strength"]["is_weak"] is True
    assert focus["entered_tomb"] is True and not focus["tombs"][0]["pending_breakers"]
