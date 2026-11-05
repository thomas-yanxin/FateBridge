"""Independent arithmetic oracles and structural counterexamples for BaZi timing."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core import timing
from fatebridge.core.almanac import (
    SolarTerm,
    elapsed_days_between,
    get_solar_terms_for_year,
    localize_datetime,
)
from fatebridge.core.timing import TimingAnalysis
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.timing_state import build_current_timing_state
from fatebridge.utils.birth_input import create_person_info

NATAL = {
    "year": ("甲", "子"),
    "month": ("丙", "寅"),
    "day": ("戊", "辰"),
    "hour": ("壬", "戌"),
}


def fixed_jie(monkeypatch, birth, elapsed):
    """Freeze a physical jie interval; expected calendar offsets are hand-set."""
    aware = localize_datetime(birth, "Asia/Shanghai")
    previous = SolarTerm("立夏", aware - timedelta(days=1), "20000430", "戊午")
    following = SolarTerm("芒种", aware + elapsed, "20000506", "甲子")
    monkeypatch.setattr(
        timing,
        "get_bazi_month_boundaries",
        lambda *args: (previous, following, "巳", 3),
    )
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2000)


def test_three_days_conversion_matches_one_year_nine_months_example(monkeypatch):
    # 三命通会·论大运: five days + three two-hour periods -> 630 nominal
    # days -> one year nine months. This expected offset is not engine output.
    birth = datetime(2000, 5, 1)
    fixed_jie(monkeypatch, birth, timedelta(days=5, hours=6))
    result = TimingAnalysis.calculate_dayun_timeline(birth, "男", ("辛", "巳"))
    assert result["calendar_offset"] == {
        "years": 1,
        "months": 9,
        "days": 0,
        "microseconds": 0,
    }
    assert result["start_at"] == "2002-02-01T00:00:00+08:00"
    assert result["periods"][1]["start_at"] == "2012-02-01T00:00:00+08:00"


@pytest.mark.parametrize(
    "delta,status,period",
    [
        (timedelta(microseconds=-1), "before_dayun", None),
        (timedelta(0), None, 1),
        (timedelta(days=3653), None, 2),
    ],
)
def test_dayun_starts_at_boundary_without_waiting_for_birthday(
    monkeypatch, delta, status, period
):
    birth = datetime(2000, 5, 1)
    fixed_jie(monkeypatch, birth, timedelta(days=5, hours=6))
    result = TimingEffectsAnalysis.analyze_dayun_effects(
        NATAL, birth, "男", 1, analysis_moment=datetime(2002, 2, 1) + delta
    )
    assert result.get("status") == status
    if period is not None:
        assert result["dayun_info"]["period"] == period
        assert result["age_info"]["selection_basis"] == "civil_calendar_moment"


@pytest.mark.parametrize("offset,period", [(-1, 1), (0, 2), (1, 2)])
def test_exact_decade_boundary_uses_half_open_intervals(monkeypatch, offset, period):
    birth = datetime(2000, 5, 1)
    fixed_jie(monkeypatch, birth, timedelta(days=5, hours=6))
    moment = datetime(2012, 2, 1) + timedelta(microseconds=offset)
    result = TimingEffectsAnalysis.analyze_dayun_effects(
        NATAL, birth, "男", 11, analysis_moment=moment
    )
    same = TimingEffectsAnalysis.analyze_dayun_effects(
        NATAL,
        birth,
        "男",
        11,
        analysis_moment=localize_datetime(moment, "Asia/Shanghai").astimezone(
            timezone.utc
        ),
    )
    assert result["dayun_info"]["period"] == period
    assert same["dayun_info"] == result["dayun_info"]


def test_age_reference_does_not_round_before_period_selection(monkeypatch):
    birth = datetime(2000, 5, 1)
    fixed_jie(monkeypatch, birth, timedelta(days=3.012))  # 1.004 reference years
    result = TimingEffectsAnalysis.analyze_dayun_effects(NATAL, birth, "男", 11)
    assert result["dayun_info"]["period"] == 1
    assert result["timing_context"]["selection_basis"] == "explicit_age_reference"


def test_moment_and_explicit_age_are_separate_and_old_eighty_year_limit_is_gone(
    monkeypatch,
):
    birth = datetime(2000, 5, 1)
    fixed_jie(monkeypatch, birth, timedelta(days=5, hours=6))
    by_age = TimingEffectsAnalysis.analyze_dayun_effects(NATAL, birth, "男", 1)
    by_moment = TimingEffectsAnalysis.analyze_dayun_effects(
        NATAL, birth, "男", 1, analysis_moment=datetime(2002, 3, 1)
    )
    assert by_age["status"] == "before_dayun"
    assert by_moment["dayun_info"]["period"] == 1
    assert (
        TimingEffectsAnalysis.analyze_dayun_effects(NATAL, birth, "男", 90)[
            "dayun_info"
        ]["period"]
        == 9
    )


def test_all_shared_date_consumers_select_new_dayun_before_next_birthday(monkeypatch):
    person = create_person_info(2000, 5, 1, 0, gender="男", use_true_solar_time=False)
    context = build_birth_computation_context(person)
    fixed_jie(monkeypatch, datetime(2000, 5, 1), timedelta(days=5, hours=6))
    result = build_current_timing_state(context, analysis_date=datetime(2012, 3, 1))
    assert result["dayun_analysis"]["dayun_info"]["period"] == 2
    override = build_current_timing_state(
        context, analysis_date=datetime(2012, 3, 1), analysis_age=11
    )
    assert override["dayun_analysis"]["dayun_info"]["period"] == 1


def test_comprehensive_low_level_year_uses_lichun_not_civil_january():
    result = TimingEffectsAnalysis.comprehensive_timing_analysis(
        NATAL, datetime(2000, 5, 1), "男", analysis_date=datetime(2026, 1, 20)
    )
    assert result["liunian_analysis"]["liunian_info"]["pillar"] == "乙巳"


@pytest.mark.parametrize("god", ["正印", "七杀", "食神", "伤官", "正财", "偏财"])
def test_ten_god_label_does_not_establish_fortune_or_financial_advice(god):
    facts = TimingAnalysis._analyze_liuyue_fortune(god, [], {"nayin": "海中金"})
    assert facts["fortune_score"] is None
    assert facts["overall_fortune"] == "未判定"
    advice = TimingAnalysis._generate_liuyue_suggestions(god, [], facts)
    assert not any(
        word in "".join(advice) for word in ("财运不错", "投资理财", "宜保守", "好时机")
    )


def test_combine_and_clash_never_receive_fixed_good_or_bad_score():
    for left, right in (("子", "丑"), ("子", "午"), ("子", "卯")):
        result = TimingEffectsAnalysis._analyze_branch_combination(
            left, right, "流年", "大运"
        )
        assert result["total_impact_score"] is None
        assert result["assessment_status"] == "context_required"


def test_percentage_redistribution_is_not_a_strength_measure():
    result = TimingEffectsAnalysis.analyze_element_strength_changes(
        NATAL, {"liunian": {"stem": "甲", "branch": "子"}}
    )
    assert sum(result["original_distribution"].values()) == pytest.approx(100)
    assert sum(result["new_distribution"].values()) == pytest.approx(100)
    assert "结构占比" in result["overall_effect"]
    assert result["method_id"] == "structural_element_share_v1"


def test_suiyun_repeat_keeps_positions_and_has_no_event_or_fortune_claim():
    timing_pillars = {
        "dayun": {"stem": "甲", "branch": "子"},
        "liunian": {"stem": "甲", "branch": "子"},
    }
    before = deepcopy(timing_pillars)
    result = analyze_timing_interactions(NATAL, timing_pillars)
    events = [e for e in result["relations"] if e["rule_id"] == "suiyun_binglin"]
    assert len(events) == 1
    assert events[0]["participants"] == ["timing.dayun", "timing.liunian"]
    assert events[0]["scope"] == "timing_timing"
    assert timing_pillars == before
    assert result["assessment_status"] == "structural_evidence_only"


def test_dynamic_completion_requires_three_distinct_branches_and_keeps_competing_clash():
    # Natal 子辰 plus timing 申 completes a water triad, while natal 寅
    # simultaneously clashes with 申. Neither match erases the other.
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "庚", "branch": "申"}}
    )
    events = result["relations"]
    full = [e for e in events if e["rule_id"] == "triple_combination"]
    assert len(full) == 1 and full[0]["bureau"] == "水局"
    assert full[0]["transformation"] == "not_assessed"
    assert any(
        e["rule_id"] == "branch_clash"
        and e["participants"] == ["natal.month", "timing.liunian"]
        for e in events
    )
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "甲", "branch": "子"}}
    )
    assert not any(e["rule_id"] == "triple_combination" for e in result["relations"])


def test_partial_punishment_is_not_reported_as_complete():
    partial = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "乙", "branch": "巳"}}
    )
    assert any(
        e["rule_id"] == "partial_punishment" and e["complete"] is False
        for e in partial["relations"]
    )
    assert not any(
        e["rule_id"] == "branch_punishment" and e.get("group") == "寅巳申"
        for e in partial["relations"]
    )
    full = analyze_timing_interactions(
        NATAL,
        {
            "dayun": {"stem": "庚", "branch": "申"},
            "liunian": {"stem": "乙", "branch": "巳"},
        },
    )
    assert any(
        e["rule_id"] == "branch_punishment" and e["group"] == "寅巳申" and e["complete"]
        for e in full["relations"]
    )


def test_timing_ten_gods_and_roots_are_facts_about_the_day_master():
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "甲", "branch": "子"}}
    )
    context = result["ten_god_context"][0]
    assert context["stem_ten_god"] == "七杀"  # 戊土日主，甲木为七杀
    assert context["hidden_stems"] == [{"stem": "癸", "ten_god": "正财", "rank": 1}]
    assert {r["position"] for r in context["natal_same_element_roots"]} == {
        "month",
        "day",
    }


def test_all_timing_relations_have_a_moving_participant_and_unique_id():
    result = analyze_timing_interactions(
        NATAL,
        {
            "dayun": {"stem": "甲", "branch": "申"},
            "liunian": {"stem": "甲", "branch": "子"},
            "liuyue": {"stem": "甲", "branch": "辰"},
        },
    )
    assert all(
        any(p.startswith("timing.") for p in e["participants"])
        for e in result["relations"]
    )
    assert len({e["id"] for e in result["relations"]}) == len(result["relations"])


def test_invalid_ganzhi_is_rejected_instead_of_becoming_false_evidence():
    with pytest.raises(ValueError, match="六十甲子"):
        analyze_timing_interactions(NATAL, {"liunian": {"stem": "甲", "branch": "丑"}})


HKO = json.loads((Path(__file__).parent / "data/bazi-timing-hko-2026.json").read_text())


@pytest.mark.parametrize("case", HKO["cases"], ids=lambda case: case["term"])
def test_solar_terms_against_independent_hko_published_minutes(case):
    terms = {
        term.name: term for term in get_solar_terms_for_year(2026, HKO["timezone"])
    }
    actual = terms[case["term"]].moment
    expected = datetime.fromisoformat(case["at"])
    assert (
        abs(elapsed_days_between(expected, actual) * 86400) <= HKO["tolerance_seconds"]
    )


@pytest.mark.parametrize(
    "birth,zone,seconds,expected",
    [
        (
            datetime(2026, 3, 7, 2, 30),
            "America/New_York",
            720,
            "2026-03-08T03:30:00-04:00",
        ),
        (
            datetime(2026, 10, 31, 1, 30),
            "America/New_York",
            720,
            "2026-11-01T01:30:00-04:00",
        ),
    ],
)
def test_civil_dayun_boundary_dst_gap_and_fold_are_explicit(
    monkeypatch, birth, zone, seconds, expected
):
    monkeypatch.setattr(
        TimingAnalysis,
        "calculate_dayun_start_details",
        lambda *args: {
            "elapsed_seconds": seconds,
            "year_stem": "甲",
            "start_age_unrounded": seconds / 86400 / 3,
        },
    )
    result = TimingAnalysis.calculate_dayun_timeline(birth, "男", ("丙", "寅"), zone)
    assert result["start_at"] == expected


def test_decades_do_not_accumulate_leap_day_clipping(monkeypatch):
    monkeypatch.setattr(
        TimingAnalysis,
        "calculate_dayun_start_details",
        lambda *args: {
            "elapsed_seconds": 0,
            "year_stem": "甲",
            "start_age_unrounded": 0,
        },
    )
    result = TimingAnalysis.calculate_dayun_timeline(
        datetime(2024, 2, 29), "男", ("丙", "寅")
    )
    assert result["periods"][1]["start_at"] == "2034-02-28T00:00:00+08:00"
    assert result["periods"][2]["start_at"] == "2044-02-29T00:00:00+08:00"
