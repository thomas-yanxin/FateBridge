"""Independent source rules, pairing choice and real calendar boundaries."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.core.canping import calculate
from fatebridge.core.canping_timing import (
    APPENDIX,
    CONTINUOUS,
    SOURCE_SHA256,
    appendix_age,
    luck_timeline,
)
from fatebridge.core.output_chinese import CanpingTiming
from fatebridge.core.requests.divination import CanpingRequest
from fatebridge.services.divination import calculate_canping_analysis

ROOT = Path(__file__).parent / "fixtures/canping_najda_v1"
REF = json.loads((ROOT / "reference.json").read_text())
INPUT = dict(
    date="2026-02-06",
    time="04:02:00",
    zone="Asia/Shanghai",
    gender="女",
    use_true_solar_time=False,
)


def run_at(at=None, **changes):
    return calculate_canping_analysis(**{**INPUT, **changes}, analysis_datetime=at)


def test_primary_source_identity_and_separate_appendix_are_preserved():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["pdf_sha256"] == REF["source_pdf_sha256"] == SOURCE_SHA256
    assert [i["pdf_page"] for i in manifest["images"]] == [50, 105, 106]
    for image in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert "not proof" in REF["scope"] and "rule-derived" in REF["annotation_method"]


@pytest.mark.parametrize("case", REF["rounding"])
def test_source_rounding_rule_derived_cases(case):
    birth = datetime(2000, 1, 15, 12, tzinfo=timezone.utc)
    for direction in (-1, 1):
        offset = appendix_age(birth, birth + timedelta(days=case["days"] * direction))
        assert offset["civil_days_to_reference"] == case["days"]
        assert offset["whole_years"] == case["years"]


@pytest.mark.parametrize("case", REF["directions"])
def test_month_pillar_direction_from_named_appendix(case):
    birth = datetime.fromisoformat(
        "1990-06-15T09:33:00+08:00"
        if case["year"] == "庚午"
        else "1991-09-15T09:33:00+08:00"
    )
    timeline = luck_timeline(
        birth, case["gender"], tuple(case["month"]), "Asia/Shanghai", APPENDIX
    )
    assert timeline["start_details"]["forward_direction"] == case["forward"]
    assert timeline["periods"][0]["pillar"] == case["first"]
    assert len(timeline["periods"]) == 12


def test_independent_hko_civil_day_anchor_is_not_claimed_as_a_classical_horoscope():
    result = run_at()
    anchor = REF["modern_hko_anchor"]
    timing = result["canping_timing"]
    assert timing["start_at"] == anchor["start_at"]
    assert timing["start_details"]["reference_term"]["name"] == anchor["reference_term"]
    assert timing["calendar_offset"]["civil_days_to_reference"] == anchor["days"]
    assert timing["calendar_offset"]["whole_years"] == anchor["years"]
    assert result["dayun"][0]["pillar"] == anchor["first"]
    assert timing["selected"] is None
    assert "not_a_classical_worked_example" in anchor["classification"]
    assert "not_heluo" in timing["heluo_period_distinction"]


def test_continuous_and_day_rounding_are_separately_named_and_not_silently_merged():
    rounded = run_at()["canping_timing"]
    continuous = run_at(dayun_method=CONTINUOUS)["canping_timing"]
    assert rounded["profile_id"] == APPENDIX and continuous["profile_id"] == CONTINUOUS
    assert rounded["start_at"] != continuous["start_at"]
    assert rounded["start_details"]["start_age_years"] == 1
    assert "start_age_unrounded" not in rounded["start_details"]
    assert continuous["start_details"]["start_age_unrounded"] < 1


def test_unstarted_and_first_dayun_are_split_within_the_same_lichun_year():
    result = run_at()
    row = result["liunian_series"]["rows"][1]
    assert row["year"] == 2027 and row["ganzhi"] == "丁未"
    assert row["status"] == "split" and "numShun" not in row
    a, b = row["segments"]
    assert a["status"] == "not_started" and "verses" not in a and "numShun" not in a
    assert a["end_at"] == b["start_at"] == "2027-02-06T04:02:00+08:00"
    assert b["status"] == "active" and b["dayun_pillar"] == "己丑"
    assert (b["numShun"], b["numNi"]) == (2738, 2738)


def test_exact_decade_boundary_changes_branch_and_both_numbers():
    at = datetime.fromisoformat("2037-02-06T04:02:00+08:00")
    a = run_at((at - timedelta(microseconds=1)).isoformat())["canping_timing"][
        "selected"
    ]
    b = run_at(at.isoformat())["canping_timing"]["selected"]
    assert (a["dayun_pillar"], b["dayun_pillar"]) == ("己丑", "戊子")
    assert (a["numShun"], a["numNi"]) == (2936, 2536)
    assert (b["numShun"], b["numNi"]) == (2835, 2635)
    assert a["end_at"] == b["start_at"]


def test_lichun_not_civil_new_year_selects_taisui_and_no_first_period_fallback():
    before = run_at("2027-02-02T12:00:00+08:00")["canping_timing"]["selected"]
    assert before["ganzhi"] == "丙午" and before["year"] == 2026
    assert before["status"] == "not_started" and "numShun" not in before
    after = run_at("2027-02-06T04:02:00+08:00")["canping_timing"]["selected"]
    assert after["ganzhi"] == "丁未" and after["dayunBranch"] == "丑"


def test_every_annual_segment_is_contiguous_and_bounded_by_its_actual_dayun():
    result = run_at()
    rows = result["liunian_series"]["rows"]
    assert len(rows) == 120 and rows[0]["start_at"] == "2026-02-06T04:02:00+08:00"
    for index, row in enumerate(rows):
        if index:
            assert rows[index - 1]["end_at"] == row["start_at"]
        assert row["segments"][0]["start_at"] == row["start_at"]
        assert row["segments"][-1]["end_at"] == row["end_at"]
        for i, segment in enumerate(row["segments"]):
            if i:
                assert row["segments"][i - 1]["end_at"] == segment["start_at"]
            lo, hi = (
                datetime.fromisoformat(segment[k]) for k in ("start_at", "end_at")
            )
            assert lo < hi
            if segment["status"] == "active":
                period = result["dayun"][segment["dayun_index"]]
                assert (
                    datetime.fromisoformat(period["start_at"])
                    <= lo
                    < hi
                    <= datetime.fromisoformat(period["end_at"])
                )
                assert period["branch"] == segment["dayunBranch"]


def test_date_counting_uses_civil_days_across_dst_not_fractional_elapsed_days():
    zone = ZoneInfo("America/New_York")
    a = datetime(2024, 3, 9, 12, tzinfo=zone)
    b = datetime(2024, 3, 11, 12, tzinfo=zone)
    assert (
        b.astimezone(timezone.utc) - a.astimezone(timezone.utc)
    ).total_seconds() == 47 * 3600
    assert appendix_age(a, b)["whole_years"] == 1
    assert appendix_age(a, b)["civil_days_to_reference"] == 2


def test_true_solar_hour_correction_does_not_shift_the_birth_to_jie_interval():
    a = run_at(lon="75", use_true_solar_time=False)
    b = run_at(lon="75", use_true_solar_time=True)
    assert a["canping_timing"]["start_at"] == b["canping_timing"]["start_at"]
    assert a["canping_timing"]["start_details"] == b["canping_timing"]["start_details"]
    assert a["four_pillars"]["hour"] != b["four_pillars"]["hour"]


def test_query_instant_is_offset_invariant_and_evidence_matches_selected_texts():
    a = run_at("2037-02-06T04:02:00+08:00")
    b = run_at("2037-02-05T20:02:00Z")
    assert a["canping_timing"]["selected"] == b["canping_timing"]["selected"]
    selected = a["canping_timing"]["selected"]
    quote = a["numerology_evidence"]["selected_texts"][-1]
    assert quote["verses"] == selected["verses"] and quote["kind"] == "luck"
    assert quote["dayun_pillar"] == "戊子"
    assert "大运戊子：顺2835" in a["snapshot_text"]
    waiting = run_at("2026-02-07T12:00:00+08:00")
    assert len(waiting["numerology_evidence"]["selected_texts"]) == 1
    assert "尚未起运；不取第一运代替" in waiting["snapshot_text"]


def test_legacy_schedule_is_explicit_and_does_not_replace_the_new_default():
    legacy = run_at(dayun_method="legacy_minggong_v1")
    modern = run_at()
    assert legacy["canping_timing"]["profile_id"] == "legacy_minggong_v1"
    assert legacy["dayun"][0]["ageStart"] == 1
    assert modern["ming_gong"] is None
    assert legacy["dayun"][0]["branch"] != modern["dayun"][0]["branch"]


def test_raw_single_year_calculation_requires_the_explicit_active_branch():
    args = dict(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        liunian_branch="戌",
    )
    with pytest.raises(ValueError, match="active_dayun_branch"):
        calculate(**args)
    a = calculate(**args, active_dayun_branch="申")
    b = calculate(**args, active_dayun_branch="酉")
    assert a["liunian"]["numShun"] != b["liunian"]["numShun"]


@pytest.mark.parametrize(
    "change",
    [
        {"gender": None},
        {"gender": "未知"},
        {"analysis_datetime": "2027-01-01T12:00:00"},
        {
            "analysis_datetime": "2030-02-01T00:00:00Z",
            "dayun_method": "legacy_minggong_v1",
        },
        {"dayun_method": "typo"},
    ],
)
def test_invalid_public_inputs_do_not_silently_select_a_sex_clock_or_method(change):
    with pytest.raises(ValidationError):
        CanpingRequest.model_validate({**INPUT, **change})


@pytest.mark.parametrize("at", ["2025-01-01T00:00:00Z", "2200-01-01T00:00:00Z"])
def test_query_before_birth_or_beyond_coverage_is_rejected(at):
    with pytest.raises(ValueError):
        # Service guard returns an error payload, so exercise the domain adapter.
        from fatebridge.core.local_techniques.canping import build_canping_result

        build_canping_result(**INPUT, analysis_datetime=at)


def test_selected_numeric_fact_types_are_strict():
    with pytest.raises(ValidationError):
        CanpingTiming.model_validate({"selected": {"numShun": "2738"}})
