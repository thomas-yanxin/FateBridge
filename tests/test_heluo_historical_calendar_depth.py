"""Historic printed dates without choosing a variant to make a horoscope agree."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_day_ganzhi
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import NumerologyBirthClock

ROOT = Path(__file__).parent / "fixtures/heluo_historical_calendar_v1"
REF = json.loads((ROOT / "reference.json").read_text())
DILA = json.loads((ROOT / "dila-excerpt.json").read_text())


@pytest.mark.parametrize("row", REF["readings"], ids=lambda r: r["id"] + r["reading"])
def test_printed_day_and_dila_month_agree_without_rewriting_heluo(row):
    month = next(r for r in DILA["t_month"] if r[0] == row["month_id"])
    assert month[4] == 0 and month[10] == "S"
    assert month[6] + row["day"] - 1 == row["jdn"] <= month[7]
    assert (
        date.fromordinal(row["jdn"] - 1721425).isoformat() == row["proleptic_gregorian"]
    )
    cycle = (row["day_cycle_addend"] + row["day"] - 1) % 60
    # Book page 12: add lunar day, not day minus one; 1=甲子.
    assert (
        "甲乙丙丁戊己庚辛壬癸"[cycle % 10] + "子丑寅卯辰巳午未申酉戌亥"[cycle % 12]
        == row["calendar_day_ganzhi"]
    )
    d = date.fromisoformat(row["proleptic_gregorian"])
    assert get_day_ganzhi(d.year, d.month, d.day) == row["calendar_day_ganzhi"]
    assert (month[8] == row["printed_year_ganzhi"]) is row["year_caption_agrees"]


def test_source_conflicts_and_same_named_eras_are_retained():
    rows = REF["readings"]
    assert [
        r["id"] + ":" + r["reading"]
        for r in rows
        if r["calendar_day_ganzhi"] != r["printed_day_ganzhi"]
    ] == ["yihai_bailu:NLC", "bingyin_kai_xi:both", "wuzi_dongzhi:both"]
    song = next(r for r in DILA["t_month"] if r[0] == 30978)
    liao = next(r for r in DILA["t_month"] if r[0] == 30980)
    assert song[5] != liao[5] and song[1] == 25 and liao[1] == 5
    assert song[6:9] == liao[6:9]  # Matching dates do not settle era attribution.
    assert REF["validated_historical_birth_instants"] == 0
    assert REF["independent_historical_solar_term_instants"] == 0
    assert not REF["all_literal_source_days_agree"]


def test_original_witness_bytes_and_license_are_preserved():
    for item in REF["images"] + REF["data_files"]:
        assert (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    assert "Attribution-ShareAlike 3.0" in (ROOT / "DILA-README.txt").read_text()
    source = ROOT.parent / REF["source_worked_fixture"]
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == REF["source_worked_fixture_sha256"]
    )


@pytest.mark.parametrize("build", [build_heluo_result, build_canping_result])
@pytest.mark.parametrize("day", ["1150-08-23", "1582-10-10", "1990-06-15"])
def test_public_date_is_explicitly_proleptic_gregorian_without_an_era_conversion(
    build, day
):
    # Synthetic clock/offset only tests software semantics, not a historic birth instant.
    result = build(
        date=day, time="17:00", zone="+08:00", gender="男", use_true_solar_time=False
    )
    clock = result["numerology_evidence"]["birth_clock"]
    policy = clock["calendar_policy"]
    assert policy["input_calendar"] == "proleptic_gregorian"
    assert policy["automatic_reform_cutover"] is False
    assert policy["historical_lunar_date_conversion"] is False
    assert policy["historical_official_calendar_reconstruction"] is False
    assert "推算格里历" in result["snapshot_text"]
    trace = next(
        t
        for t in result["numerology_evidence"]["rule_trace"]
        if t["rule_id"] == clock["policy_id"]
    )
    assert trace["facts"]["calendar_policy"] == policy
    assert (
        NumerologyBirthClock.model_validate(clock).calendar_policy.input_calendar
        == "proleptic_gregorian"
    )


@pytest.mark.parametrize("build", [build_heluo_result, build_canping_result])
def test_julian_label_is_not_silently_interpreted_as_converted_gregorian(build):
    args = dict(time="17:00", zone="+08:00", gender="男", use_true_solar_time=False)
    gregorian = build(date="1150-08-23", **args)
    julian_label_as_input = build(date="1150-08-16", **args)
    assert gregorian["four_pillars"]["day"] == {"stem": "丙", "branch": "申"}
    assert (
        julian_label_as_input["four_pillars"]["day"] != gregorian["four_pillars"]["day"]
    )


@pytest.mark.parametrize("build", [build_heluo_result, build_canping_result])
def test_julian_only_leap_day_is_not_accepted_as_gregorian(build):
    with pytest.raises(ValueError):
        build(
            date="1700-02-29",
            time="17:00",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )


def test_historical_audit_retains_disagreements_in_a_passing_integrity_check():
    from scripts.audit_numerology import historical_caption_checks

    report = historical_caption_checks()
    assert report["checks_passed"] and not report["all_literal_source_days_agree"]
    assert len(report["literal_day_disagreements"]) == 3
    assert report["validated_historical_birth_instants"] == 0
    assert report["year_caption_conflicts"] == ["wuzi_dongzhi"]
