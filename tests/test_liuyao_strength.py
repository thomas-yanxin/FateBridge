"""Frozen classical structures and counterexamples for support and three tombs."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.liuyao_judgment import build_conditional_analysis
from fatebridge.core.liuyao_strength import PROFILE
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from scripts.build_liuyao_strength_profile import build
from tests.test_liuyao_conditions import mounted

REFERENCE = Path(__file__).parent / "fixtures/liuyao_strength_v5"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]
ERRATUM = json.loads(
    (REFERENCE.parent / "liuyao_clash_v10/prior-strength-errata.json").read_text()
)
RECEPTION_REFINEMENT = json.loads(
    (
        REFERENCE.parent / "liuyao_generation_v11/prior-strength-refinement.json"
    ).read_text()
)


def classical(case):
    info, lines = mounted(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=[],
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        timing_days=0,
    )


def test_frozen_source_defines_three_locations_despite_the_other_numeral():
    assert build() == PROFILE
    frozen = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, expected in frozen["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == expected
    assert "入日墓入動墓動而化墓" in PROFILE["clauses"][1]["quote"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_hand_transcribed_tomb_structures_and_strength_counterexamples(case):
    result = classical(case)
    assessment = result["classical_assessment"]
    focus = assessment["focus"]
    if "expected_focus_branch" in case:
        assert focus["branch"] == case["expected_focus_branch"]
    assert [r["location"] for r in focus["tombs"]] == case["expected_tomb_locations"]
    if "expected_tomb_branch" in case:
        assert focus["tomb_branch"] == case["expected_tomb_branch"]
    if "expected_supported" in case:
        assert focus["strength"]["is_supported"] is case["expected_supported"]
    if "expected_weak" in case:
        assert focus["strength"]["is_weak"] is case["expected_weak"]
    if "expected_true_tomb" in case:
        expected = case["expected_true_tomb"]
        if case["id"] == ERRATUM["case_id"]:
            assert expected is True  # Preserve the old overconfident annotation.
            assert result["lines"][3]["activity_condition_match"] is None
            assert any(
                a["position"] == 4 and a["branch"] == "丑"
                for a in focus["tombs"][0]["pending_breakers"]
            )
            expected = ERRATUM["corrected_condition"]
        assert focus["entered_tomb"] is expected
    if "expected_strength_status" in case:
        expected_status = case["expected_strength_status"]
        if case["id"] == RECEPTION_REFINEMENT["case_id"]:
            assert (
                expected_status
                == RECEPTION_REFINEMENT["original_expected_strength_status"]
            )
            assert focus["strength"]["is_failing"] is True
            assert any(
                a.get("target_reception_condition") is False
                for a in focus["strength"]["blocked_supports"]
            )
            expected_status = RECEPTION_REFINEMENT["new_expected_strength_status"]
        assert focus["strength"]["status"] == expected_status
        assert focus["strength"]["is_supported"] is (
            False if case["id"] == RECEPTION_REFINEMENT["case_id"] else None
        )
        assert focus["strength"]["is_weak"] is (
            True if case["id"] == RECEPTION_REFINEMENT["case_id"] else None
        )
    for location in ("day", "month"):
        if case.get(f"expected_tomb_broken_by_{location}"):
            assert all(
                any(a["location"] == location for a in c["breakers"])
                for c in focus["tombs"]
            )
            assert all(c["is_true_tomb"] is False for c in focus["tombs"])
    assert "score" not in assessment and "outcome" not in assessment


def test_numeral_variant_gets_a_same_edition_definition_update():
    result = classical(CASES[0])
    issue = result["role_effects"]["textual_issues"][0]
    assert issue["scan_reading"] == "元神入五墓；忌神入五墓"
    assert (
        issue["resolution_update"]["status"]
        == "three_locations_explicitly_defined_in_same_edition"
    )


def test_role_atoms_reuse_the_same_run_strength_and_tomb_assessment():
    result = classical(CASES[-1])
    for role in result["role_effects"]["lines"]:
        p = role["position"]
        assessed = result["classical_assessment"]["lines"][p - 1]
        assert (
            role["atom_values"]["strength_wang"] is assessed["strength"]["is_supported"]
        )
        assert role["atom_values"]["strength_weak"] is assessed["strength"]["is_weak"]
        assert role["atom_values"]["entered_tomb"] is assessed["entered_tomb"]
        assert role["strength_source_path"].endswith(f".lines.{p - 1}.strength")


def test_month_tomb_is_separate_and_static_tomb_does_not_become_a_moving_actor():
    focus = classical(CASES[2])["classical_assessment"]["focus"]
    assert focus["month_tomb_relation"] is True
    assert all(c["location"] != "month" for c in focus["tombs"])
    static = classical(CASES[5])["classical_assessment"]["focus"]
    assert static["tombs"] == [] and static["entered_tomb"] is False


def test_original_moving_clash_cannot_break_a_transformed_tomb():
    # Daguo lower Xun: line 3 is You metal; lower Dui makes its own
    # transformation Chou. Original line 6 is Wei and actually moves.
    case = {
        "base_code": "011110",
        "changed_code": "110001",
        "month": "辰",
        "day_ganzhi": "甲子",
        "focus_line": 3,
    }
    focus = classical(case)["classical_assessment"]["focus"]
    transformed = next(t for t in focus["tombs"] if t["location"] == "changed")
    assert transformed["branch"] == "丑" and transformed["position"] == 3
    assert any(
        a["location"] == "visible" and a["position"] == 6 and a["branch"] == "未"
        for a in transformed["ignored_breakers"]
    )
    assert all(a["location"] != "visible" for a in transformed["breakers"])
    assert all(a["location"] != "visible" for a in transformed["pending_breakers"])


def test_day_tomb_opening_is_a_day_condition_without_an_event_prediction():
    # This is a modern synthetic cast, not a recovered Gregorian year for
    # the original Heng example. Jan 8 is Yi-Chou; Jan 14 is Xin-Wei.
    result = build_sixyao_result(
        date="2000-01-08",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="011100",
        focus_line=3,
        timing_days=12,
    )
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assert detail["classical_assessment"]["focus"]["tombs"][0]["location"] == "day"
    windows = detail["timing_candidates"]
    opening = [
        w for w in windows["windows"] if "三墓关系逢冲开候选" in w["matched_rules"]
    ]
    assert [(w["effective_date"], w["day_ganzhi"]) for w in opening] == [
        ("2000-01-14", "辛未")
    ]
    assert windows["status"] == "condition_windows_only"
    assert opening[0]["start_at"] == "2000-01-13T23:00:00+08:00"
    assert "probability" not in windows and "predicted_success" not in windows


def test_snapshot_keeps_the_same_run_tomb_verdict_and_does_not_apply_it_to_changed_focus():
    arguments = dict(
        date="2000-01-08",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="011001",
        changed_code="110001",
        focus_line=3,
    )
    result = build_sixyao_result(**arguments)
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assessed = detail["classical_assessment"]["focus"]
    assert [(t["location"], t["branch"]) for t in assessed["tombs"]] == [
        ("day", "丑"),
        ("moving", "丑"),
        ("changed", "丑"),
    ]
    for tomb in assessed["tombs"]:
        verdict = (
            "原典真墓条件匹配"
            if tomb["is_true_tomb"] is True
            else "当前不作真墓" if tomb["is_true_tomb"] is False else "真墓效力待审"
        )
        location = {"day": "日墓", "moving": "动墓", "changed": "本位化墓"}[
            tomb["location"]
        ]
        assert f"{location}丑：{verdict}" in result["snapshot_text"]
    changed = build_sixyao_result(**arguments, focus_kind="changed", timing_days=12)
    assert (
        changed["liuyao_evidence"]["conditional_analysis"]["classical_assessment"][
            "focus"
        ]
        is None
    )
    assert "第3爻原典生扶裁定" not in changed["snapshot_text"]
    assert all(
        "三墓关系逢冲开候选" not in w["matched_rules"]
        for w in changed["liuyao_evidence"]["conditional_analysis"][
            "timing_candidates"
        ]["windows"]
    )
