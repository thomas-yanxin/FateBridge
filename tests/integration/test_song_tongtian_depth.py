"""Tongtian source arithmetic, printed rounding examples and retained conflicts."""

import hashlib
import json
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

import fatebridge.core.song_qi as song

ROOT = Path(__file__).parents[1] / "fixtures/song_tongtian_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
PROFILE = "songshi_tongtian_mei_v1"


def frac(r):
    return Fraction(r["numerator"], r["denominator"])


@pytest.mark.parametrize("row", REFERENCE["printed_worked_calculations"])
def test_mei_printed_working_is_reproduced_without_rewriting_observations(row):
    result = song.source_term_remainder(
        profile_id=PROFILE, accumulated_years=row["accumulated"], term_index=0
    )
    assert (
        result["source_big_remainder"],
        result["source_small_remainder"],
        result["ganzhi_day"],
    ) == (row["big"], row["small"], row["ganzhi"])
    trace = result["winter_correction"]
    assert trace["distance_years"] == row["distance"]
    assert trace["rounded_chant_source_units"] == row["chant"]
    assert trace["rounded_correction_source_units"] == row["correction"]
    assert trace["fan_accumulation_source_units"] == row["fan"]
    assert trace["corrected_accumulation_source_units"] == row["corrected"]
    assert trace["reading_source"]["sha256"] == REFERENCE["sources"]["mei"]["sha256"]
    if "alternate_two_place" in row:
        assert result["ganzhi_day"] != row["alternate_two_place"]["ganzhi"]
        assert result["source_small_remainder"] != row["alternate_two_place"]["small"]


@pytest.mark.parametrize("row", REFERENCE["derived_worksheets"])
def test_preimplementation_derived_worksheets_are_separate_from_printed_cases(row):
    result = song.source_qi_sequence(profile_id=PROFILE, year_label=row["year"])
    assert result["accumulated_years"] == row["accumulated"]
    trace = result["winter_correction"]
    assert trace["rounded_correction_source_units"] == row["rounded_correction"]
    assert trace["corrected_accumulation_source_units"] == row["winter_integral_units"]
    for expected in row["rows"]:
        actual = result["terms"][expected["index"]]
        assert actual["source_big_remainder"] == expected["big"]
        assert frac(actual["source_day_fraction"]) == Fraction(expected["fraction"])
        assert actual["ganzhi_day"] == expected["ganzhi"]


def test_source_constants_are_not_mixed_with_interlinear_calendars_or_annotations():
    result = song.source_qi_sequence(profile_id=PROFILE, year_label=1194)
    assert result["source_reference_accumulated_years"] == 3830
    assert result["source_reference_year_caption"] == "绍熙五年甲寅"
    assert frac(result["source_year_days"]) == Fraction(146097, 400)
    assert frac(result["source_qi_interval_days"]) == Fraction(48699, 3200)
    assert 24 * frac(result["source_qi_interval_days"]) == frac(
        result["source_year_days"]
    )
    assert result["winter_correction"]["gas_offset_source_units"] == 237811
    assert result["terms"][1]["source_day_divisor"] == 12000
    # The 21.84 day-percent annotation is an alternative expression of 2621少,
    # not an additional small-unit value or a modern-second count.
    origin_step = song.source_term_remainder(
        profile_id=PROFILE, accumulated_years=3830, term_index=1
    )
    assert origin_step["interval_days_from_winter_solstice"] == {
        "numerator": 48699,
        "denominator": 3200,
    }


def test_two_half_up_steps_cannot_be_replaced_by_bankers_or_final_only_rounding():
    p = song._PROFILES[PROFILE]
    _, first_tie = song._winter_units(p, 4330)  # distance500, 6.35 -> 6.4
    assert frac(first_tie["rounded_chant_source_units"]) == Fraction(32, 5)
    assert first_tie["rounded_correction_source_units"] == 3200
    _, second_tie = song._winter_units(p, 3835)  # 0.1 *5 =0.5 ->1
    assert second_tie["rounded_correction_source_units"] == 1
    # The printed distance2076 distinguishes two-step rounding from evaluating
    # the exact quadratic and rounding once.
    _, printed = song._winter_units(p, 1754)
    assert printed["rounded_correction_source_units"] == 54806
    assert printed["rounded_correction_source_units"] != round(
        Fraction(127 * 2076**2, 10000)
    )
    _, before = song._winter_units(p, 3825)
    assert (
        before["corrected_accumulation_source_units"]
        == before["fan_accumulation_source_units"] - 1
    )


def test_cumulative_endpoint_does_not_hide_secular_next_winter_difference():
    current = song.source_qi_sequence(profile_id=PROFILE, year_label=1281)
    following = song.source_qi_sequence(profile_id=PROFILE, year_label=1282)
    assert frac(current["recomputed_next_winter_minus_endpoint_days"]) == -Fraction(
        1, 12000
    )
    assert (
        current["terms"][24]["source_small_remainder"]
        == following["terms"][0]["source_small_remainder"] + 1
    )
    assert "no_interpolated" in current["endpoint_policy"]
    assert "not_separately_recomputed" in current["terms"][24]["endpoint_policy"]


def test_existing_kai_xi_case_retains_day_and_before_daxue_disagreements():
    link = REFERENCE["date_link"]
    dila = json.loads(
        (ROOT.parent / "heluo_historical_calendar_v1/dila-excerpt.json").read_text()
    )
    month = next(m for m in dila["t_month"] if m[0] == link["month_id"])
    result = song.source_qi_sequence(profile_id=PROFILE, year_label=1206)
    row = result["terms"][23]
    offset = (song.CYCLE.index(row["ganzhi_day"]) - link["first_day_cycle_index"]) % 60
    assert offset + 1 == link["expected_lunar_day"] == 28
    assert date.fromordinal(month[6] + offset - 1721425).isoformat() == "1206-12-06"
    assert row["ganzhi_day"] == "乙亥" != link["birth_caption_ganzhi"]
    assert row["source_day_fraction"] == link["source_day_fraction"]
    assert (
        offset + 1 - link["birth_caption_lunar_day"]
        == 0
        != link["printed_before_daxue_days"]
    )
    assert result["applied_to_public_four_pillars"] is False
    assert "no_UTC" in result["time_frame"]
    assert not REFERENCE["date_link"]["birth_clock_resolved"]


def test_frozen_pages_prior_anchors_and_source_scope():
    for item in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    for path, digest in REFERENCE["prior_fixture_hashes"].items():
        assert (
            hashlib.sha256((ROOT.parents[2] / path).read_bytes()).hexdigest() == digest
        )
    assert len(REFERENCE["printed_worked_calculations"]) == 2
    assert REFERENCE["new_original_heluo_births"] == 0
    assert REFERENCE["independent_second_reviews"] == 0
    assert REFERENCE["validated_historical_utc_instants"] == 0


def test_audit_rejects_loss_of_secular_correction_without_hiding_source_conflicts(
    monkeypatch,
):
    from dataclasses import replace

    from scripts.numerology.audit_numerology import tongtian_source_checks

    valid = tongtian_source_checks()
    assert valid["checks_passed"]
    assert not valid["birth_day_ganzhi_agrees"]
    assert not valid["before_daxue_claim_agrees"]
    profiles = dict(song._PROFILES)
    p = profiles[PROFILE]
    profiles[PROFILE] = replace(
        p, winter_correction=replace(p.winter_correction, distance_rate=0)
    )
    monkeypatch.setattr(song, "_PROFILES", profiles)
    rejected = tongtian_source_checks()
    assert not rejected["checks_passed"]
    assert any(f["kind"] == "tongtian_printed_working" for f in rejected["failures"])
