"""Instantaneous modern phase must not adjudicate a historical calendar."""

import json
import math
from copy import deepcopy
from fractions import Fraction

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.local_techniques.suzhan import build_suzhan_result
from fatebridge.core.suzhan_lunar_phase import lunar_phase_reference
from fatebridge.utils.errors import EphemerisSourceError
from scripts.check_suzhan_lunar_phase import FIXTURE, compare_available, compare_row
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)

REFERENCES = json.loads(FIXTURE.read_bytes())


def captured(sun=0.0, moon=0.0):
    flags = runtime.swe.FLG_MOSEPH | runtime.swe.FLG_SPEED
    return {
        "states": {"Sun": {"longitude": sun}, "Moon": {"longitude": moon}},
        "julian_day_tt": 2451545.0,
        "julian_day_ut1": 2451544.999,
        "ephemeris_provenance": {
            "by_body": {
                name: {"ecliptic_model": "moshier", "ecliptic_return_flags": flags}
                for name in ("Sun", "Moon")
            }
        },
    }


@pytest.mark.parametrize("boundary", range(12, 360, 12))
def test_all_29_internal_boundaries_keep_both_adjacent_binary_sides(boundary):
    for moon, index in [
        (math.nextafter(boundary, -math.inf), boundary // 12),
        (float(boundary), boundary // 12 + 1),
        (math.nextafter(boundary, math.inf), boundary // 12 + 1),
    ]:
        result = lunar_phase_reference(captured(moon=moon))
        tithi = result["modern_tithi"]
        assert tithi["index"] == index
        assert tithi["lower_degrees_inclusive"] <= result["elongation_degrees"]
        assert result["elongation_degrees"] < tithi["upper_degrees_exclusive"]


@pytest.mark.parametrize(
    "sun,moon,index,adjusted",
    [
        (0.0, 0.0, 1, False),
        (0.0, math.ulp(0.0), 1, False),
        (math.ulp(0.0), 0.0, 30, True),
        (0.0, math.nextafter(360, -math.inf), 30, False),
        (math.nextafter(1, math.inf), 13.0, 1, True),
        (math.nextafter(1, math.inf), 181.0, 15, True),
        (300.0, 120.0, 16, False),
    ],
)
def test_wrap_and_subtraction_do_not_round_across_a_tithi(sun, moon, index, adjusted):
    result = lunar_phase_reference(captured(sun, moon))
    ratio = result["elongation_exact_binary_ratio"]
    assert isinstance(ratio["numerator"], str) and isinstance(ratio["denominator"], str)
    assert (
        Fraction(int(ratio["numerator"]), int(ratio["denominator"]))
        == (Fraction(moon) - Fraction(sun)) % 360
    )
    assert result["modern_tithi"]["index"] == index
    assert result["display_adjusted_for_half_open_interval"] is adjusted
    assert 0 <= result["elongation_degrees"] < 360


@pytest.mark.parametrize("bad", [None, True, "12", math.nan, math.inf, -1, 360])
def test_invalid_longitude_is_not_converted_into_a_phase(bad):
    with pytest.raises(EphemerisSourceError):
        lunar_phase_reference(captured(moon=bad))


@pytest.mark.parametrize(
    "flag",
    [
        "FLG_EQUATORIAL",
        "FLG_XYZ",
        "FLG_RADIANS",
        "FLG_J2000",
        "FLG_ICRS",
        "FLG_SIDEREAL",
        "FLG_TOPOCTR",
        "FLG_HELCTR",
        "FLG_BARYCTR",
        "FLG_TRUEPOS",
        "FLG_NONUT",
        "FLG_NOABERR",
        "FLG_NOGDEFL",
        "FLG_JPLHOR",
        "FLG_JPLHOR_APPROX",
    ],
)
def test_coordinate_frame_changes_cannot_relabel_ra_or_geometric_values(flag):
    raw = captured()
    raw["ephemeris_provenance"]["by_body"]["Moon"]["ecliptic_return_flags"] |= getattr(
        runtime.swe, flag
    )
    with pytest.raises(EphemerisSourceError) as error:
        lunar_phase_reference(raw)
    assert error.value.reason == "coordinate_contract_changed"


@pytest.mark.parametrize(
    "change",
    ["missing_body", "model", "missing_model", "ambiguous_bits", "flag_bool", "tt"],
)
def test_missing_or_changed_source_receipts_fail(change):
    raw = captured()
    receipt = raw["ephemeris_provenance"]["by_body"]["Moon"]
    if change == "missing_body":
        del raw["states"]["Moon"]
    elif change == "model":
        receipt["ecliptic_model"] = "swieph"
    elif change == "missing_model":
        del receipt["ecliptic_model"]
    elif change == "ambiguous_bits":
        receipt["ecliptic_return_flags"] |= runtime.swe.FLG_SWIEPH
    elif change == "flag_bool":
        receipt["ecliptic_return_flags"] = True
    else:
        raw["julian_day_tt"] = math.nan
    with pytest.raises(EphemerisSourceError):
        lunar_phase_reference(raw)


def test_reference_consumes_only_captured_coordinates_and_returns_detached_sources(
    monkeypatch,
):
    raw = captured(sun=357, moon=10)
    before = deepcopy(raw)

    def unexpected(*args, **kwargs):
        raise AssertionError("must not make a new native call")

    monkeypatch.setattr(runtime, "ephemeris_call", unexpected)
    a = lunar_phase_reference(raw)
    assert a["elongation_degrees"] == 13 and raw == before
    a["definitions"][0]["id"] = "changed"
    a["source_longitudes"]["Sun"] = 0
    b = lunar_phase_reference(raw)
    assert b["source_longitudes"]["Sun"] == 357
    assert b["definitions"][0]["id"] != "changed"


@pytest.mark.parametrize("row", REFERENCES["api_response"]["phasedata"])
def test_every_available_usno_minute_table_phase_uses_ut1_to_tt(row):
    checked = compare_row(row)
    assert checked["absolute_wrapped_elongation_residual_degrees"] <= 0.01


def test_partial_reference_coverage_does_not_pass_the_frozen_five_year_gate():
    report = compare_available()
    assert report["required_years"] == [1700, 1900, 2000, 2026, 2100]
    assert report["missing_years"] == [1700, 1900, 2000, 2100]
    assert report["all_available_rows_checked"] == 50
    assert report["available_rows_within_tolerance"]
    assert report["full_frozen_five_year_gate_met"] is False
    assert report["uniform_tolerance_degrees"] == 0.01
    assert report["copied_response_matches_frozen_extracted_identity"]
    assert {row["phase"] for row in REFERENCES["api_response"]["phasedata"]} == {
        "New Moon",
        "First Quarter",
        "Full Moon",
        "Last Quarter",
    }


def test_reference_rows_cannot_be_replaced_while_retaining_source_identity(
    monkeypatch, tmp_path
):
    import scripts.check_suzhan_lunar_phase as checker

    data = deepcopy(REFERENCES)
    data["api_response"]["phasedata"][0]["time"] = "00:00"
    target = tmp_path / "changed-reference.json"
    target.write_text(json.dumps(data))
    monkeypatch.setattr(checker, "FIXTURE", target)
    with pytest.raises(ValueError, match="differ from frozen extracted response"):
        checker.compare_available()


@pytest.mark.parametrize("mode", [0, 1])
def test_full_chart_keeps_calendar_naming_separate_from_physical_tithi(mode):
    result = build_suzhan_result(
        date="2026-10-24", time="05:30:00", zone="+08:00", szchart=mode
    )
    sky = result["astronomy"]
    phase = sky["lunar_phase_reference"]
    assert phase["julian_day_tt"] == sky["julian_day_tt"]
    by_name = {b["id"]: b for b in sky["bodies"]}
    assert phase["source_longitudes"] == {
        n: by_name[n]["longitude"] for n in ("Sun", "Moon")
    }
    assert not phase["ancient_ritual_condition_evaluated"]
    assert not phase["historical_day_boundary_or_half_established"]
    assert not phase["leap_short_month_priority_established"]
    assert result["sukuyo"]["calendar"]["lunar_day"] == 15
    assert result["sukuyo"]["calendar"]["natal_su27"] == "昴"
    assert "未算月宿合、日出历日或tithi终止时刻" in result["snapshot_text"]
    assert "原典以月满名白十五的用语另存" in result["snapshot_text"]


@pytest.mark.parametrize(
    "options", [{"doubing_su28": False}, {"mansion_method": "legacy_equal28"}]
)
def test_non_astronomical_modes_do_not_manufacture_phase_coordinates(options):
    result = build_suzhan_result(
        date="2026-10-24", time="05:30:00", zone="+08:00", **options
    )
    assert result["astronomy"] is None
    assert "现代月日黄经差未计算" in result["snapshot_text"]


@pytest.mark.parametrize("mode", [0, 1])
def test_actual_strict_deep_fields_agree_across_rest_native_mcp_and_cli(
    monkeypatch, capsys, mode
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": "2026-10-24", "time": "05:30:00", "zone": "+08:00", "szchart": mode},
        ["astronomy.lunar_phase_reference", "sukuyo.calendar", "validation"],
    )
