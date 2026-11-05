"""Printed literal anchors, civil month boundaries and unresolved identities."""

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.qimen import _qimen_stem_context_lines
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.validation.qimen_calendar_stems import audit_calendar_stems
from fatebridge.validation.qimen_study import Condition, FrozenQimenPolicy, apply_policy

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v7"
REFERENCE = json.loads((BUNDLE / "sources-and-anchors.json").read_text())


def calculate(at, *, solar=False, longitude=114.17):
    return calculate_qimen_analysis(
        analysis_year=at.year,
        analysis_month=at.month,
        analysis_day=at.day,
        analysis_hour=at.hour,
        analysis_minute=at.minute,
        analysis_timezone="Asia/Hong_Kong",
        analysis_longitude=longitude,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )


@pytest.mark.parametrize("case", REFERENCE["calendar_cases"], ids=lambda c: c["date"])
@pytest.mark.parametrize("solar", [False, True])
def test_hko_first_day_date_and_independently_advanced_ganzhi(case, solar):
    at = datetime.fromisoformat(case["date"]).replace(hour=12)
    anchor = calculate(at, solar=solar)["qimen"]["stem_context"]["lunar_month_start"]
    assert anchor["anchor_date"] == case["date"]
    assert anchor["calendar_year"] == case["lunar_year"]
    assert anchor["lunar_month"] == case["lunar_month"]
    assert anchor["is_leap_month"] == case["is_leap_month"]
    assert anchor["ganzhi"] == case["anchor_ganzhi"]
    assert anchor["effective_stem"] == (
        None if case["anchor_ganzhi"][0] == "甲" else case["anchor_ganzhi"][0]
    )


def test_two_printed_stem_examples_are_distinct_from_fifteen_modern_dates():
    report = audit_calendar_stems(BUNDLE)
    assert report["printed_literal_stem_examples"] == 2
    assert report["calendar_reference_count"] == 15
    assert report["disagreements"] == []
    assert not report["historical_example_dates_reconstructed"]
    assert not report["year_boundary_policy_certified"]
    assert not report["jia_substitution_certified"]
    assert not report["whole_book_conformance_established"]


@pytest.mark.parametrize("date", ["2026-02-05T12:00", "2025-01-30T12:00"])
def test_both_orders_of_lichun_and_lunar_new_year_keep_year_candidates_unselected(date):
    q = calculate(datetime.fromisoformat(date))["qimen"]
    year = q["stem_context"]["year"]
    assert year["status"] == "unresolved_year_boundary"
    assert year["effective_stem"] is None
    assert len({c["ganzhi"] for c in year["boundary_candidates"]}) == 2
    assert all(not c["adopted"] for c in year["boundary_candidates"])
    assert not any(p["rule_id"] == "year_stem_block" for p in q["patterns"])
    assert "年界待核" in "\n".join(_qimen_stem_context_lines(q))


def test_jia_year_and_jia_month_start_never_adopt_matching_hidden_instrument():
    q = calculate(datetime(2024, 2, 10, 0))["qimen"]
    for role in ("year", "lunar_month_start"):
        anchor = q["stem_context"][role]
        assert anchor["status"] == "unresolved_jia_identity"
        assert anchor["effective_stem"] is None
        assert all(not c["adopted"] for c in anchor["candidates"])
        assert [c["effective_stem"] for c in anchor["candidates"]] == ["壬", "戊"]
    assert not any(
        p["rule_id"] in {"year_stem_block", "lunar_month_start_block"}
        for p in q["patterns"]
    )


def test_month_start_uses_civil_midnight_not_bazi_zi_hour_or_solar_label():
    before = calculate(datetime(2026, 1, 18, 23, 30))["qimen"]
    midnight = calculate(datetime(2026, 1, 19, 0, 5), solar=True, longitude=100.0)
    anchor = midnight["qimen"]["stem_context"]["lunar_month_start"]
    assert before["day_ganzhi"] == "癸巳"
    assert before["stem_context"]["lunar_month_start"]["anchor_date"] == "2025-12-20"
    assert midnight["analysis_context"]["corrected_datetime"].startswith("2026-01-18")
    assert anchor["anchor_date"] == "2026-01-19" and anchor["civil_lunar_day"] == 1
    assert anchor["effective_stem"] == "癸"


def test_actual_month_block_is_gui_not_bazi_month_ji_and_keeps_same_stem_group():
    result = calculate(datetime(2026, 1, 21, 9))
    q = result["qimen"]
    match = next(p for p in q["patterns"] if p["rule_id"] == "lunar_month_start_block")
    assert result["four_pillars"]["month"]["stem"] == "己"
    assert match["facts"]["earth_stem"] == "癸"
    assert match["facts"]["anchor_date"] == "2026-01-19"
    assert "月朔干取用：癸巳，实际用干癸" in result["snapshot_text"]
    palace = next(p for p in q["palaces"] if p["name"] == match["palace"])
    assert "庚" in palace["heaven_stems"] and "癸" in palace["earth_stems"]
    assert not match["qualification"]["independent_outcome_evidence"]


@pytest.mark.parametrize(
    "rule,role",
    [("year_stem_block", "year"), ("lunar_month_start_block", "lunar_month_start")],
)
def test_frozen_research_policy_treats_unresolved_new_features_as_unknown(rule, role):
    q = calculate(datetime(2024, 2, 10, 0))["qimen"]
    policy = FrozenQimenPolicy(
        policy_id="synthetic",
        target_definition="synthetic",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "not-a-calibrated-predictor",
                "all_of": [
                    Condition(feature="pattern_present", pattern=rule, equals=False)
                ],
                "probability": 0.8,
            }
        ],
        fallback_probability=0.2,
    )
    decision = apply_policy(q, policy)
    assert decision["probability"] is None
    assert (
        decision["rules"][0]["conditions"][0]["evidence"]["reason"]
        == f"unresolved_{role}_stem_identity"
    )


def test_no_calendar_guess_outside_table_support():
    q = calculate(datetime(1800, 6, 1, 12))["qimen"]
    assert all(
        q["stem_context"][role]["status"] == "calendar_anchor_unavailable"
        for role in ("year", "lunar_month_start")
    )
    assert not any(
        p["rule_id"] in {"year_stem_block", "lunar_month_start_block"}
        for p in q["patterns"]
    )


def test_cannot_delete_hard_reference_rows_or_change_pdf(tmp_path):
    bundle = tmp_path / "fixture"
    shutil.copytree(BUNDLE, bundle)
    path = bundle / "sources-and-anchors.json"
    ref = json.loads(path.read_text())
    ref["calendar_cases"].pop()
    path.write_text(json.dumps(ref))
    with pytest.raises(ValueError, match="十五项"):
        audit_calendar_stems(bundle)
    path.write_text((BUNDLE / path.name).read_text())
    ref = json.loads(path.read_text())
    ref["source_files"].pop()
    path.write_text(json.dumps(ref))
    with pytest.raises(ValueError, match="完整岁月格来源"):
        audit_calendar_stems(bundle)
    path.write_text((BUNDLE / path.name).read_text())
    (bundle / "hko-lunar-2025.pdf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        audit_calendar_stems(bundle)
