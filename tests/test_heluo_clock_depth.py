"""Printed counts, conditional closure and one consistent Ganzhi year context."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo_clock as clock
from fatebridge.core.heluo import calculate
from fatebridge.core.heluo_timing import (
    CYCLE,
    HeluoYearContextError,
    annual_timeline,
    build_heluo_timing,
    year_context,
)
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import HeluoSourceClock, HeluoTimingYearContext
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures/heluo_clock_v1"
REF = json.loads((ROOT / "reference.json").read_text())
SHIFT_REF = json.loads((ROOT / "branch-shift-reference.json").read_text())


def chart():
    return calculate(
        four_pillars=dict(year="甲子", month="丁卯", day="庚申", hour="庚辰"),
        gender="男",
        birth_year=1924,
        month_zhi="卯",
        hour_zhi="辰",
    )


def ratio(value):
    return [value["numerator"], value["denominator"]]


def test_before_bug_mixed_year_changes_the_gua_and_is_now_rejected():
    c = chart()
    good = build_heluo_timing(c, "甲子", analysis_year=1924)
    assert good["selected_annual"]["gua"] == "天風姤"
    assert (
        good["selected_annual"]["ganzhi"] == "甲子"
        and good["year_context"]["cycle_year"] == 1924
    )
    # Before the guard this returned 泽风大过 labeled1924/乙丑.
    for build in [annual_timeline, build_heluo_timing]:
        with pytest.raises(HeluoYearContextError, match="1924.*甲子.*乙丑"):
            build(c, "乙丑")


def test_all_sixty_label_links_and_wrong_valid_ganzhi_are_not_mixed():
    for i, gz in enumerate(CYCLE):
        assert year_context(dict(cycleYear=1984 + i), gz)["matches"] is True
        with pytest.raises(HeluoYearContextError):
            year_context(dict(cycleYear=1984 + i), CYCLE[(i + 1) % 60])
    assert year_context(dict(cycleYear=1504), "甲子")["expected_ganzhi"] == "甲子"
    assert year_context(dict(cycleYear=1484), "甲辰")["expected_ganzhi"] == "甲辰"
    with pytest.raises(HeluoYearContextError):
        year_context(dict(cycleYear=1484), "甲子")


@pytest.mark.parametrize("cy", [True, False, None, "1924", 1924.0])
def test_year_context_needs_an_actual_integer_label(cy):
    with pytest.raises(HeluoYearContextError):
        year_context(dict(cycleYear=cy), "甲子")


def test_original_counts_make_a_hundred_without_uniform_branches():
    expected = REF["cyclic_partition_from_zi"]
    rows = clock.source_branch_partition(origin_branch="子")
    assert [
        {k: r[k] for k in ["branch", "start_ke", "end_ke"]} for r in rows
    ] == expected
    assert [r["length_ke"] for r in rows] == [8, 8, 9, 8, 8, 9, 8, 8, 9, 8, 8, 9]
    assert sum(r["length_ke"] for r in rows) == 100
    for branch in clock.BRANCHES:
        rotated = clock.source_branch_partition(origin_branch=branch)
        assert rotated[0]["branch"] == branch and rotated[0]["start_ke"] == 0
        assert rotated[-1]["end_ke"] == 100
        assert sum(r["length_ke"] for r in rotated) == 100
        for a, b in zip(rotated, rotated[1:]):
            assert a["end_ke"] == b["start_ke"]


@pytest.mark.parametrize(
    "ke,branch",
    [
        (0, "子"),
        (Fraction(7999, 1000), "子"),
        (8, "丑"),
        (Fraction(15999, 1000), "丑"),
        (16, "寅"),
        (Fraction(24999, 1000), "寅"),
        (25, "卯"),
        (91, "亥"),
        (Fraction(99999, 1000), "亥"),
    ],
)
def test_exact_source_clock_boundaries_without_a_physical_epoch(ke, branch):
    value = clock.source_branch_at_ke(ke, origin_branch="子")
    assert value["branch"] == branch and value["physical_epoch_established"] is False
    assert clock.source_branch_at_ke(0, origin_branch="寅")["branch"] == "寅"


@pytest.mark.parametrize("ke", [True, False, 0.5, 100, -1, "16"])
def test_no_float_boolean_or_silent_next_cycle_wrap(ke):
    with pytest.raises(ValueError):
        clock.source_branch_at_ke(ke, origin_branch="子")


def test_origin_and_fen_scale_have_no_implicit_defaults():
    with pytest.raises(TypeError):
        clock.source_branch_partition()
    with pytest.raises(TypeError):
        clock.source_branch_at_ke(0)
    with pytest.raises(TypeError):
        clock.compare_daily_extra()
    for origin in ["", None, 0, "子初", "午夜"]:
        with pytest.raises(ValueError):
            clock.source_branch_partition(origin_branch=origin)
    for scale in [True, 0, -1, 18.0, "18"]:
        with pytest.raises(ValueError):
            clock.compare_daily_extra(fen_per_ke=scale)


def test_six_day_blocks_follow_unequal_branch_lengths_without_selecting_fen():
    rows = clock.source_six_day_blocks(origin_branch="未", blocks=12)
    keys = ("branch", "next_branch", "start_ke", "end_ke", "extra_ke")
    assert [{k: row[k] for k in keys} for row in rows] == SHIFT_REF[
        "origin_wei_first_twelve"
    ]
    for row in rows:
        assert row["nominal_days"] == 6 and row["branch_start_only"] is True
        assert row["physical_epoch_established"] is False
        assert row["end_ke"] - row["start_ke"] == 600 + row["extra_ke"]
    assert [r["extra_ke"] for r in rows] == [8, 9, 8, 8, 9, 8, 8, 9, 8, 8, 9, 8]
    assert clock.source_clock_evidence()["daily_extra_literal"]["fen_per_ke"] is None


def test_sixty_branch_shifts_close_the_source_year_for_every_explicit_origin():
    for origin in clock.BRANCHES:
        rows = clock.source_six_day_blocks(origin_branch=origin, blocks=60)
        assert len(rows) == 60 and rows[-1]["next_branch"] == origin
        assert rows[-1]["end_ke"] == SHIFT_REF["total_ke"] == 36500
        assert sum(row["extra_ke"] for row in rows) == 500
        for a, b in zip(rows, rows[1:]):
            assert a["end_ke"] == b["start_ke"]
            assert a["next_branch"] == b["branch"]
        # The year total is origin-invariant; its individual boundaries are not.
        assert rows[0]["end_ke"] == (609 if origin in "寅申巳亥" else 608)


@pytest.mark.parametrize("blocks", [True, False, 0, -1, 61, 6.0, "6"])
def test_source_block_scope_does_not_silently_wrap_or_coerce(blocks):
    with pytest.raises(ValueError):
        clock.source_six_day_blocks(origin_branch="未", blocks=blocks)


def test_six_day_blocks_require_an_explicit_branch_start_and_count():
    with pytest.raises(TypeError):
        clock.source_six_day_blocks(blocks=12)
    with pytest.raises(TypeError):
        clock.source_six_day_blocks(origin_branch="未")
    with pytest.raises(ValueError):
        clock.source_six_day_blocks(origin_branch="未初三刻", blocks=12)


@pytest.mark.parametrize(
    "row", REF["equal_shi_projection"]["assumed_scale_comparisons"]
)
def test_conditional_arithmetic_does_not_certify_a_favorable_scale(row):
    actual = clock.compare_daily_extra(fen_per_ke=row["fen_per_ke"])
    assert ratio(actual["extra_ke_per_day"]) == row["extra_ke_per_day"]
    assert ratio(actual["year_days"]) == row["year_days"]
    assert (
        ratio(actual["difference_from_printed_year_days"])
        == row["difference_from365_days"]
    )
    assert actual["arithmetic_closes"] is (row["fen_per_ke"] == 18)
    assert (
        actual["source_fen_scale_verified"] is actual["physical_clock_applied"] is False
    )


def test_public_evidence_keeps_the_source_scale_and_origin_unresolved():
    p = clock.source_clock_evidence()
    HeluoSourceClock.model_validate(p)
    assert p["daily_extra_literal"]["fen_per_ke"] is p["physical_origin_branch"] is None
    assert ratio(p["equal_shi_projection"]["extra_ke_per_nominal_day"]) == [25, 18]
    assert ratio(
        p["equal_shi_projection"]["fen_per_ke_required_for_numeric_closure"]
    ) == [18, 1]
    assert p["equal_shi_projection"]["source_fen_scale_verified"] is False
    assert p["physical_clock_applied"] is p["calendar_mapping_complete"] is False
    shift = p["branch_shift_projection"]
    assert shift["extra_ke"] == 500 and ratio(shift["total_source_days"]) == [365, 1]
    assert shift["branch_start_only"] is shift["derived_only"] is True
    assert shift["source_fen_scale_selected"] is False
    assert shift["daily_internal_distribution_resolved"] is False
    assert (
        p["loaded_sha256"] == hashlib.sha256(clock.SOURCE_PATH.read_bytes()).hexdigest()
    )
    assert (
        REF["new_original_horoscopes"]
        == REF["new_calendar_instants"]
        == REF["independent_second_reviews"]
        == 0
    )
    for w in REF["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"birth_ganzhi": "乙丑"},
        {"expected_ganzhi": "乙丑"},
        {"cycle_year": 1925},
        {"matches": False},
        {"matches": 1},
    ],
)
def test_typed_year_facts_cannot_mix_labels_or_coerce_booleans(patch):
    value = year_context(chart(), "甲子")
    value.update(patch)
    with pytest.raises(ValidationError):
        HeluoTimingYearContext.model_validate(value)
    assert HeluoTimingYearContext.model_validate(dict(matches=True)).cycle_year is None


@pytest.mark.parametrize(
    "patch",
    [
        {"physical_clock_applied": True},
        {"physical_clock_applied": 0},
        {"calendar_mapping_complete": True},
        {"physical_origin_branch": "子"},
    ],
)
def test_typed_source_clock_is_not_a_physical_time_override(patch):
    p = clock.source_clock_evidence()
    p.update(patch)
    with pytest.raises(ValidationError):
        HeluoSourceClock.model_validate(p)


@pytest.mark.parametrize(
    "field,patch",
    [
        ("daily_extra_literal", {"ke": True}),
        ("daily_extra_literal", {"fen_per_ke": 18}),
        ("branch_shift_projection", {"derived_only": 1}),
        ("branch_shift_projection", {"branch_start_only": False}),
        ("branch_shift_projection", {"source_fen_scale_selected": True}),
        ("branch_shift_projection", {"daily_internal_distribution_resolved": 0}),
        (
            "branch_shift_projection",
            {"total_source_days": {"numerator": 360, "denominator": 1}},
        ),
        (
            "equal_shi_projection",
            {
                "fen_per_ke_required_for_numeric_closure": {
                    "numerator": 10,
                    "denominator": 1,
                }
            },
        ),
    ],
)
def test_typed_relative_arithmetic_cannot_be_promoted_to_resolved_clock(field, patch):
    p = clock.source_clock_evidence()
    p[field].update(patch)
    with pytest.raises(ValidationError):
        HeluoSourceClock.model_validate(p)


def test_same_run_year_and_clock_trace_is_not_a_mutable_alias():
    r = build_heluo_result(
        date="2001-01-24",
        time="09:33",
        gender="男",
        use_true_solar_time=False,
        analysis_year=2000,
        month_index=7,
        day_index=13,
    )
    timing = r["heluo_timing"]
    e = r["numerology_evidence"]
    trace = next(
        t["facts"] for t in e["rule_trace"] if t["rule_id"] == clock.RULESET_ID
    )
    assert (
        timing["year_context"]["cycle_year"] == 2000
        and timing["year_context"]["birth_ganzhi"] == "庚辰"
    )
    assert trace == dict(
        clock_profile=timing["source_clock"], year_context=timing["year_context"]
    )
    assert (
        "[卷一百刻原式]" in r["snapshot_text"]
        and "每刻18分不作原典默认值" in r["snapshot_text"]
    )
    timing["source_clock"]["branch_lengths"][0]["length_ke"] = 9
    assert trace["clock_profile"]["branch_lengths"][0]["length_ke"] == 8
    assert clock.source_clock_evidence()["branch_lengths"][0]["length_ke"] == 8


@pytest.mark.parametrize(
    "patch",
    [
        {"day_ke": 99},
        {"extra_branches_in_printed_order": ["寅", "卯", "巳", "亥"]},
        {"source_fen_per_ke": 18},
        {"nominal_year_days": True},
        {"ruleset_id": "other"},
    ],
)
def test_source_file_cannot_be_fitted_to_make_the_arithmetic_close(
    patch, tmp_path, monkeypatch
):
    d = json.loads(clock.SOURCE_PATH.read_text())
    d.update(patch)
    p = tmp_path / "source.json"
    p.write_text(json.dumps(d))
    clock._source.cache_clear()
    try:
        with monkeypatch.context() as m:
            m.setattr(clock, "SOURCE_PATH", p)
            with pytest.raises(NumerologySourceError) as error:
                clock.source_clock_evidence()
            assert error.value.reason == "invalid_heluo_clock_source"
    finally:
        clock._source.cache_clear()


def test_audit_rejects_choosing_a_convenient_fen_scale(monkeypatch):
    from scripts import audit_numerology as audit

    original = clock.source_clock_evidence

    def convenient():
        p = original()
        p["daily_extra_literal"]["fen_per_ke"] = 18
        return p

    monkeypatch.setattr(clock, "source_clock_evidence", convenient)
    r = audit.source_clock_checks()
    assert r["checks_passed"] is False
    assert {"kind": "heluo_clock_unestablished_epoch_or_scale"} in r["failures"]


def test_audit_rejects_promoting_the_closed_year_to_resolved_daily_distribution(
    monkeypatch,
):
    from scripts import audit_numerology as audit

    original = clock.source_clock_evidence

    def overclaim():
        p = original()
        p["branch_shift_projection"]["daily_internal_distribution_resolved"] = True
        return p

    monkeypatch.setattr(clock, "source_clock_evidence", overclaim)
    r = audit.source_clock_checks()
    assert r["checks_passed"] is False
    assert {"kind": "heluo_clock_branch_projection_scope"} in r["failures"]


def test_audit_rejects_silent_year_repair_instead_of_explicit_validation(monkeypatch):
    from fatebridge.core import heluo_timing
    from scripts import audit_numerology as audit

    original = heluo_timing.build_heluo_timing

    def silent(c, gz, **kwargs):
        return original(c, CYCLE[(c["cycleYear"] - 4) % 60], **kwargs)

    monkeypatch.setattr(heluo_timing, "build_heluo_timing", silent)
    r = audit.source_clock_checks()
    assert r["checks_passed"] is False
    assert {"kind": "heluo_timing_mixed_year_context"} in r["failures"]
