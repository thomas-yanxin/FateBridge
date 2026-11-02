"""Printed units/origins, exact carries and retained historical disagreements."""

import hashlib
import json
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.song_qi import source_qi_sequence, source_term_remainder

ROOT = Path(__file__).parent / "fixtures/song_qi_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


def frac(row):
    return Fraction(row["numerator"], row["denominator"])


@pytest.mark.parametrize("row", REFERENCE["derived_remainders"])
def test_frozen_derived_worksheets_are_not_claimed_as_original_examples(row):
    result = source_qi_sequence(profile_id=row["profile"], year_label=row["year"])
    actual = result["terms"][row["term_index"]]
    assert actual["source_big_remainder"] == row["big"]
    assert actual["source_small_remainder"] == row["small"]
    assert actual["source_subdivision_remainder"] == row["subdivision"]
    assert actual["ganzhi_day"] == row["ganzhi"]
    assert result["applied_to_public_four_pillars"] is False
    assert result["complete_historical_calendar"] is False
    assert "no_UTC" in result["time_frame"]


@pytest.mark.parametrize("p", REFERENCE["literal_profiles"], ids=lambda r: r["id"])
def test_source_units_year_interval_cycle_origin_and_endpoint(p):
    result = source_qi_sequence(profile_id=p["id"], year_label=p["base_year"])
    assert result["accumulated_years"] == p["accumulated_years"]
    assert frac(result["source_year_days"]) == Fraction(
        p["year_units"], p["day_divisor"]
    )
    assert 24 * frac(result["source_qi_interval_days"]) == frac(
        result["source_year_days"]
    )
    assert len(result["terms"]) == 25
    assert result["terms"][0]["term"] == result["terms"][24]["term"] == "冬至"
    origin = source_term_remainder(
        profile_id=p["id"], accumulated_years=0, term_index=0
    )
    assert origin["ganzhi_day"] == p["cycle_origin"]
    assert origin["source_day_fraction"] == {"numerator": 0, "denominator": 1}
    step = source_term_remainder(profile_id=p["id"], accumulated_years=0, term_index=1)
    assert step["source_small_remainder"] == p["qi_small"]
    assert step["source_subdivision_remainder"] == p["qi_subdivision"]
    assert step["source_subdivision_divisor"] == p["subdivision_divisor"]
    assert result["source_pdf_sha256"] == REFERENCE["sources"][p["source"]]["sha256"]
    for year in [1100, 1135, 1150, 1155, 1251]:
        current = source_qi_sequence(profile_id=p["id"], year_label=year)
        following = source_qi_sequence(profile_id=p["id"], year_label=year + 1)
        for key in [
            "ganzhi_day",
            "source_big_remainder",
            "source_small_remainder",
            "source_subdivision_remainder",
            "source_day_fraction",
        ]:
            assert current["terms"][24][key] == following["terms"][0][key]


def test_subdivision_is_not_a_modern_second_or_the_later_solar_motion_denominator():
    result = source_qi_sequence(profile_id="songshi_tongyuan_v1", year_label=1155)
    row = result["terms"][17]
    assert row["source_subdivision_divisor"] == 180
    assert frac(row["source_day_fraction"]) == Fraction(3287, 11880)
    assert frac(row["source_day_fraction"]) != Fraction(1917 * 100 + 75, 6930 * 100)
    # The winter fraction carries into the next day. Flooring the interval
    # alone cannot produce a date offset.
    current = source_qi_sequence(profile_id="songshi_tongyuan_v1", year_label=1251)
    assert current["terms"][1]["whole_day_offset_from_winter_day"] == 16
    assert frac(current["terms"][1]["interval_days_from_winter_solstice"]) < 16


@pytest.mark.parametrize("profile", ["songshi_jiyuan_v1", "songshi_tongyuan_v1"])
def test_date_only_links_retain_the_one_day_bailu_conflict(profile):
    dila_path = ROOT.parent / REFERENCE["prior_dila_excerpt"]
    dila = json.loads(dila_path.read_text())
    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    for link in REFERENCE["date_links"]:
        row = source_qi_sequence(profile_id=profile, year_label=link["year"])["terms"][
            link["term_index"]
        ]
        month = next(m for m in dila["t_month"] if m[0] == link["month_id"])
        offset = (cycle.index(row["ganzhi_day"]) - link["first_day_cycle_index"]) % 60
        assert offset < month[7] - month[6] + 1
        assert offset + 1 == link["expected_lunar_day"]
        assert (
            date.fromordinal(month[6] + offset - 1721425).isoformat()
            == link["expected_gregorian_date_label"]
        )
        assert (offset + 1 == link["source_term_claim_lunar_day"]) is link[
            "literal_term_day_agrees"
        ]
    assert REFERENCE["date_links"][1]["literal_term_day_agrees"] is False


def test_witnesses_prior_anchors_and_nominal_calendar_caution():
    for row in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    for name in ["prior_historical_reference", "prior_dila_excerpt"]:
        assert (
            hashlib.sha256((ROOT.parent / REFERENCE[name]).read_bytes()).hexdigest()
            == REFERENCE[name + "_sha256"]
        )
    assert "暗用紀元" in REFERENCE["calendar_use_issue"]["reading"]
    assert REFERENCE["validated_historical_utc_instants"] == 0


@pytest.mark.parametrize("bad", [True, 1155.0, "1155", 0, -1, 10000, None])
def test_year_label_is_an_explicit_integer_not_a_guessed_era(bad):
    with pytest.raises(ValueError):
        source_qi_sequence(profile_id="songshi_tongyuan_v1", year_label=bad)


@pytest.mark.parametrize("bad", [True, 17.0, "17", -1, 25, None])
def test_term_index_cannot_be_coerced_or_overrun_the_second_winter(bad):
    with pytest.raises(ValueError):
        source_term_remainder(
            profile_id="songshi_tongyuan_v1", accumulated_years=94251611, term_index=bad
        )


@pytest.mark.parametrize("bad", ["", "tongyuan", "auto", None])
def test_calendar_is_not_selected_by_a_partial_name_or_default(bad):
    with pytest.raises(ValueError):
        source_qi_sequence(profile_id=bad, year_label=1155)


@pytest.mark.parametrize("bad", [True, 94251611.0, "94251611", -1, None])
def test_accumulated_year_count_is_not_silently_coerced(bad):
    with pytest.raises(ValueError):
        source_term_remainder(
            profile_id="songshi_tongyuan_v1", accumulated_years=bad, term_index=17
        )


def test_audit_distinguishes_source_arithmetic_from_literal_agreement(monkeypatch):
    from dataclasses import replace

    import fatebridge.core.song_qi as song
    from scripts.audit_numerology import song_qi_source_checks

    valid = song_qi_source_checks()
    assert valid["checks_passed"] and not valid["all_examined_literal_term_days_agree"]
    assert valid["unique_literal_term_day_disagreements"] == 1
    # Simulate the common but incorrect assumption that all calendars name
    # day remainders from 甲子. The original profile and fixture are unmodified.
    wrong = dict(song._PROFILES)
    wrong["songshi_jiyuan_v1"] = replace(wrong["songshi_jiyuan_v1"], cycle_origin=0)
    monkeypatch.setattr(song, "_PROFILES", wrong)
    rejected = song_qi_source_checks()
    assert not rejected["checks_passed"]
    assert any(f["kind"] == "song_qi_derived_remainder" for f in rejected["failures"])
