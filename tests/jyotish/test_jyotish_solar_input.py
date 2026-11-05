"""Explicit historical clock labels must resolve before Jyotish calculations."""

from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.jyotish import calculate_vimshottari

LMT = dict(
    birth_year=1879,
    birth_month=5,
    birth_day=14,
    birth_hour=23,
    birth_longitude=10,
    birth_latitude=53.55,
    birth_clock_basis="local_mean_solar",
    divisions=[],
)


def test_explicit_lmt_native_and_periods_equal_the_known_civil_instant():
    solar = calculate_core_chart_analysis(**LMT, chart_variant="india_chart")
    assert "error" not in solar, solar
    assert solar["person_info"]["utc_datetime"] == "1879-05-14T22:20:00+00:00"
    civil = {k: v for k, v in LMT.items() if k != "birth_clock_basis"}
    civil.update(birth_timezone="UTC", birth_hour=22, birth_minute=20)
    ordinary = calculate_core_chart_analysis(**civil, chart_variant="india_chart")
    assert solar["india"]["charts"] == ordinary["india"]["charts"]
    stage = calculate_vimshottari(**LMT, analysis_year=2026)
    assert "error" not in stage, stage
    assert (
        stage["vimshottari"]["current_major"]
        == calculate_vimshottari(**civil, analysis_year=2026)["vimshottari"][
            "current_major"
        ]
    )


import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock
from fatebridge.core.jyotish import build_india
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroIndiaRequest,
    AstroVimshottariRequest,
)
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401

FIXTURES = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURES / "jyotish-solar-input-reference.json").read_text())
SKY = json.loads((FIXTURES / "jyotish-horizons.json").read_text())


def payload(wall, basis, longitude):
    return dict(
        birth_year=wall.year,
        birth_month=wall.month,
        birth_day=wall.day,
        birth_hour=wall.hour,
        birth_minute=wall.minute,
        birth_second=wall.second,
        birth_microsecond=wall.microsecond,
        birth_clock_basis=basis,
        birth_longitude=longitude,
        birth_latitude=0,
        divisions=[9, 30],
    )


@pytest.mark.parametrize("row", REFERENCE["cases"])
def test_independent_solar_labels_preserve_the_three_nasa_epochs_and_sky(row):
    data = payload(
        datetime.fromisoformat(row["input_wall_datetime"]),
        row["basis"],
        row["longitude"],
    )
    result = calculate_core_chart_analysis(**data, chart_variant="india_chart")
    assert "error" not in result, result
    context = result["india"]["profile"]["clock_context"]
    actual = datetime.fromisoformat(context["calculation_utc_datetime"])
    expected = datetime.fromisoformat(row["utc"])
    assert abs((actual - expected).total_seconds()) < REFERENCE["utc_tolerance_seconds"]
    assert context["input_wall_datetime"] == row["input_wall_datetime"]
    assert context["input_clock_basis"] == row["basis"]
    assert context["recorded_datetime"] is None
    assert context["birth_timezone_role"] == "UTC_carrier_for_solar_input"
    civil = calculate_core_chart_analysis(
        **payload(actual, "civil", row["longitude"]),
        birth_timezone="UTC",
        chart_variant="india_chart",
    )
    for key in ["charts", "nakshatras", "strengths", "reading_basis", "topic_evidence"]:
        assert result["india"][key] == civil["india"][key], key
    jd = result["india"]["profile"]["julian_day_tt"]
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        _, offset = runtime.swe.get_ayanamsa_ex(jd, runtime.swe.FLG_SWIEPH)
    planets = {
        p["id"]: p["longitude"] for p in result["india"]["charts"]["D1"]["planets"]
    }
    for body in SKY["references"]:
        expected_long = next(
            x["apparent_ecliptic_longitude"]
            for x in body["rows"]
            if x["utc"] == row["utc"]
        )
        actual_long = (planets[body["body"]] + offset) % 360
        error = abs((actual_long - expected_long + 180) % 360 - 180) * 3600
        assert error < REFERENCE["sky_tolerance_arcseconds"], (row, body["body"], error)


def test_independent_reference_provenance_and_epoch_count_are_honest():
    for name, expected in REFERENCE["source_hashes"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected
    assert len(REFERENCE["cases"]) == 36
    assert (
        len({r["utc"] for r in REFERENCE["cases"]}) == REFERENCE["unique_epochs"] == 3
    )
    assert REFERENCE["utc_tolerance_seconds"] == 1
    assert REFERENCE["sky_tolerance_arcseconds"] == 2


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_solar_input_interval_maps_its_wall_bounds_before_sampling_all_periods(basis):
    wall = datetime(2000, 2, 29, 23, 1, 17, 123456)
    data = payload(wall, basis, 10)
    result = calculate_vimshottari(
        **data, analysis_year=2026, birth_time_uncertainty_minutes=1
    )
    assert "error" not in result, result
    sensitivity = result["india"]["birth_time_sensitivity"]
    interval = sensitivity["clock_interval"]
    stage = result["vimshottari"]["birth_time_sensitivity"]
    assert interval["input_wall_start"] == (wall - timedelta(minutes=1)).isoformat()
    assert interval["input_wall_end"] == (wall + timedelta(minutes=1)).isoformat()
    born = datetime.fromisoformat(result["person_info"]["utc_datetime"])
    subset = stage["samples"]
    first = born + timedelta(seconds=subset[0]["offset_seconds"])
    last = born + timedelta(seconds=subset[-1]["offset_seconds"])
    assert first.isoformat() == interval["calculation_utc_start"]
    assert last.isoformat() == interval["calculation_utc_end"]
    for actual, label in [
        (first, wall - timedelta(minutes=1)),
        (last, wall + timedelta(minutes=1)),
    ]:
        _, receipt = resolve_solar_birth_clock(label, 10, basis)
        assert (
            abs(
                (
                    actual - datetime.fromisoformat(receipt["converted_utc"])
                ).total_seconds()
            )
            < 0.0002
        )
    assert stage["requested_sample_count"] == sensitivity["sample_count"]
    assert stage["evaluated_sample_count"] == sensitivity["sample_count"]
    assert (
        sum(v["sample_count"] for v in stage["stage_variants"])
        == stage["evaluated_sample_count"]
    )


def test_expanded_physical_interval_is_not_clamped_to_481_points():
    from fatebridge.core.jyotish_clock import birth_grid

    data = payload(datetime(2000, 1, 2, 12), "local_apparent_solar", 10)
    birth = build_astro_birth_info(
        **{k: v for k, v in data.items() if k != "divisions"}
    )
    offsets, interval = birth_grid(birth, 120, "auto")
    assert offsets[0] < 0 < offsets[-1]
    assert offsets[-1] - offsets[0] > 14400
    assert len(offsets) > 481
    assert 0 in offsets
    assert all(0 < b - a <= 30 for a, b in zip(offsets, offsets[1:]))


@pytest.mark.parametrize(
    "model", [AstroIndiaRequest, AstroVimshottariRequest, AstroChartPolyRequest]
)
@pytest.mark.parametrize(
    "conflict", [{"birth_timezone": "UTC"}, {"use_true_solar_time": True}]
)
def test_double_clock_corrections_are_rejected(model, conflict):
    data = {**LMT, **conflict}
    if model is AstroChartPolyRequest:
        data["chart_variant"] = "india_chart"
    with pytest.raises(ValidationError, match="Local solar birth clocks"):
        model.model_validate(data)
    assert "error" in calculate_vimshottari(
        **{k: v for k, v in data.items() if k != "chart_variant"}, analysis_year=2026
    )


def test_solar_digits_in_a_civil_DST_gap_are_not_relocalized_as_zone_time():
    data = payload(datetime(2024, 3, 10, 2, 30), "local_mean_solar", -74)
    result = calculate_core_chart_analysis(
        **data, birth_place="纽约", chart_variant="india_chart"
    )
    assert "error" not in result, result
    assert (
        result["india"]["profile"]["clock_context"]["input_wall_datetime"]
        == "2024-03-10T02:30:00"
    )
    assert result["person_info"]["birth_timezone"] == "UTC"


def test_independent_target_zone_preserves_equal_physical_analysis_instants():
    a = calculate_vimshottari(
        **LMT,
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=8,
        analysis_timezone="Asia/Shanghai",
    )
    b = calculate_vimshottari(
        **LMT,
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=0,
        analysis_timezone="UTC",
    )
    c = calculate_vimshottari(**LMT, analysis_year=2026)
    for key in ["current_major", "current_sub", "timeline", "timeline_scope"]:
        assert a["vimshottari"][key] == b["vimshottari"][key] == c["vimshottari"][key]
    assert a["analysis_context"]["timezone"] == "Asia/Shanghai"
    assert a["analysis_context"]["timezone_basis"] == "explicit_analysis_timezone"
    assert c["analysis_context"]["timezone"] == "UTC"
    assert c["analysis_context"]["timezone_basis"] == "UTC_default_for_solar_input"
    assert a["person_info"]["utc_datetime"] == b["person_info"]["utc_datetime"]


def test_invalid_target_zone_or_DST_gap_is_not_hidden_by_solar_birth_input():
    for zone in ["Not/AZone", ""]:
        assert "error" in calculate_vimshottari(
            **LMT, analysis_year=2026, analysis_timezone=zone
        )
    bad = calculate_vimshottari(
        **LMT,
        analysis_year=2024,
        analysis_month=3,
        analysis_day=10,
        analysis_hour=2,
        analysis_minute=30,
        analysis_timezone="America/New_York",
    )
    assert bad["error_code"] == "validation_error"


def test_strict_LAT_conversion_rejects_early_fallback_instead_of_later_masking(
    data18,
    monkeypatch,
):
    # The controlled retflag transition needs genuine, valid Swiss contexts.
    # Otherwise an inherited native slot can reject the forged SWIEPH flag
    # before this test reaches the intended mixed-model comparison.
    original = runtime.ephemeris_call
    calls = []

    def mixed(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name == "calc" and args[1] == runtime.swe.SUN:
            calls.append(name)
            coords, flag = result
            return coords, (flag & ~7) | (
                runtime.swe.FLG_MOSEPH if len(calls) == 1 else runtime.swe.FLG_SWIEPH
            )
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", mixed)
    with pytest.raises(ValueError, match="Local solar clock requires data files"):
        resolve_solar_birth_clock(
            datetime(2000, 1, 1, 12),
            10,
            "local_apparent_solar",
            ephemeris_policy="require_data_files",
        )
    assert len(calls) == 1
    calls.clear()
    from fatebridge.utils.errors import EphemerisSourceError

    with pytest.raises(EphemerisSourceError) as caught:
        resolve_solar_birth_clock(datetime(2000, 1, 1, 12), 10, "local_apparent_solar")
    assert caught.value.reason == "birth_clock_source_mismatch"
    assert len(calls) == 2


def test_domain_cannot_upgrade_a_previously_automatic_LAT_conversion_to_strict():
    birth = build_astro_birth_info(
        **{
            k: v
            for k, v in payload(
                datetime(2000, 1, 1, 12), "local_apparent_solar", 10
            ).items()
            if k != "divisions"
        }
    )
    with pytest.raises(ValueError, match="LAT birth clock"):
        build_india(birth, divisions=[], ephemeris_policy="require_data_files")


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_mean_model_window_uses_converted_TT_rather_than_original_solar_year(basis):
    data = payload(datetime(2051, 1, 1), basis, 180)
    result = calculate_core_chart_analysis(
        **data, chart_variant="india_chart", cheshta_model="simon1994_j2000"
    )
    assert "error" not in result, result
    assert result["person_info"]["utc_datetime"].startswith("2050-12-31T")
    assert (
        result["india"]["strengths"]["cheshta_bala"]["model_context"]["status"]
        == "computed_declared_secular_model"
    )


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
@pytest.mark.parametrize("radius", [0, 1e-10])
def test_zero_and_unresolvable_solar_uncertainty_keep_the_nominal_instant(
    basis, radius
):
    result = calculate_vimshottari(
        **payload(datetime(2000, 2, 29, 23, 1, 17, 123456), basis, 10),
        analysis_year=2026,
        birth_time_uncertainty_minutes=radius,
    )
    assert "error" not in result, result
    sensitivity = result["vimshottari"]["birth_time_sensitivity"]
    assert sensitivity["requested_sample_count"] == 1
    assert sensitivity["evaluated_sample_count"] == 1
    assert sensitivity["samples"][0]["offset_seconds"] == 0
