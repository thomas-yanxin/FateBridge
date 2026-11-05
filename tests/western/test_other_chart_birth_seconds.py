"""Recorded seconds, historical source distinctions and independent angle algebra."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroGermanyRequest,
    AstroSpecialtyRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from tests.fixtures.surface_payloads import astro_payload

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/uranian-witte1919-natal.json").read_text()
)
SOURCE_INPUT = REFERENCE["adopted_input"]
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


def _historical_angles(moment, longitude, latitude):
    # The source's 1879 GMT number is treated as UT1. Compute its JD from the
    # Gregorian ordinal, without FateBridge's clock helper or Swiss houses.
    moment = moment.astimezone(timezone.utc)
    jd = moment.toordinal() + 1721424.5
    jd += (moment.hour * 3600 + moment.minute * 60 + moment.second) / 86400
    swe = runtime.swe
    theta = math.radians((swe.sidtime(jd) * 15 + longitude) % 360)
    epsilon = math.radians(swe.calc_ut(jd, swe.ECL_NUT)[0][0])
    phi = math.radians(latitude)
    mc = (
        math.degrees(math.atan2(math.sin(theta), math.cos(theta) * math.cos(epsilon)))
        % 360
    )
    # Intersect the horizon and ecliptic planes in equatorial Cartesian space,
    # selecting the eastern intersection. This is not a house-cusp algorithm.
    normal = (
        math.cos(phi) * math.cos(theta),
        math.cos(phi) * math.sin(theta),
        math.sin(phi),
    )
    pole = (0.0, -math.sin(epsilon), math.cos(epsilon))
    vector = (
        normal[1] * pole[2] - normal[2] * pole[1],
        normal[2] * pole[0] - normal[0] * pole[2],
        normal[0] * pole[1] - normal[1] * pole[0],
    )
    east = (-math.sin(theta), math.cos(theta), 0.0)
    if sum(a * b for a, b in zip(vector, east)) < 0:
        vector = tuple(-v for v in vector)
    asc = (
        math.degrees(
            math.atan2(
                vector[1] * math.cos(epsilon) + vector[2] * math.sin(epsilon), vector[0]
            )
        )
        % 360
    )
    return jd, mc, asc


@HAS_SWE
@pytest.mark.parametrize("variant", ["germany", "chart13"])
def test_seconds_reach_public_core_coordinates_and_snapshot(variant):
    model = AstroChartPolyRequest.model_validate(
        {**SOURCE_INPUT, "chart_variant": variant}
    )
    result = calculate_core_chart_analysis(**model.model_dump())
    base = result["base_chart"] if variant == "germany" else result
    assert base["person_info"]["utc_datetime"] == REFERENCE["adopted_utc_label"]
    assert "22:20:50" in base["person_info"]["birth_datetime"]
    if variant == "chart13":
        assert "22:20:50" in result["snapshot_text"]
    instant = datetime.fromisoformat(REFERENCE["adopted_utc_label"])
    jd, mc, asc = _historical_angles(instant, 10.0, 53.55)
    if variant == "germany":
        layer = result["midpoint_analysis"]
        assert layer["time_sensitivity"]["status"] == "not_assessed"
        assert layer["time_sensitivity"]["uncertainty_minutes"] is None
        assert layer["profile"]["julian_day_ut1"] == jd
        actual = {row["id"]: row["longitude"] for row in layer["factors"]}
        assert actual["Midheaven"] == pytest.approx(mc, abs=1e-8)
        assert actual["Ascendant"] == pytest.approx(asc, abs=1e-8)
    else:
        assert result["time_sensitivity"]["status"] == "not_assessed"
        assert result["sector_profile"]["anchor_longitude"] == pytest.approx(
            asc, abs=1e-8
        )


@HAS_SWE
def test_source_seconds_change_real_contacts_instead_of_being_silently_truncated():
    exact = calculate_germany_chart_analysis(**SOURCE_INPUT)["midpoint_analysis"]
    minute = calculate_germany_chart_analysis(**{**SOURCE_INPUT, "birth_second": 0})[
        "midpoint_analysis"
    ]
    coords = [
        {row["id"]: row["longitude"] for row in layer["factors"]}
        for layer in (exact, minute)
    ]
    assert coords[0]["Midheaven"] != coords[1]["Midheaven"]
    for period in ("90", "45"):
        # Keep the existing one-degree policy; the actual source-derived clock
        # changes the geometry. No outcome-driven time rectification is used.
        exact_set = {
            row["equation"] for row in exact["dials"][period]["four_factor_contacts"]
        }
        minute_set = {
            row["equation"] for row in minute["dials"][period]["four_factor_contacts"]
        }
        assert exact_set != minute_set


@HAS_SWE
@pytest.mark.parametrize("variant", ["germany", "chart13"])
def test_utc_sample_endpoints_keep_recorded_seconds_across_minute_rollover(variant):
    result = calculate_core_chart_analysis(
        **SOURCE_INPUT, chart_variant=variant, birth_time_uncertainty_minutes=0.25
    )
    sensitivity = (
        result["midpoint_analysis"]["time_sensitivity"]
        if variant == "germany"
        else result["time_sensitivity"]
    )
    assert [row["recorded_utc"] for row in sensitivity["samples"]] == [
        "1879-05-14T22:20:35+00:00",
        "1879-05-14T22:20:50+00:00",
        "1879-05-14T22:21:05+00:00",
    ]
    assert sensitivity["uncertainty_minutes"] == 0.25
    assert sensitivity["sample_frequency_is_probability"] is False


@HAS_SWE
def test_exact_second_is_preserved_in_zero_arc_and_day_meridian():
    result = calculate_germany_chart_analysis(
        **SOURCE_INPUT,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime.fromisoformat(REFERENCE["adopted_utc_label"]),
    )["midpoint_analysis"]
    solar = result["solar_arc_analysis"]
    assert solar["profile"]["birth_effective_utc"] == REFERENCE["adopted_utc_label"]
    assert solar["profile"]["solar_arc_degrees"] == 0
    assert solar["profile"]["elapsed_calendar_days"] == 0
    assert (
        solar["birth_time_sensitivity"]["samples"][0]["effective_utc"]
        == REFERENCE["adopted_utc_label"]
    )
    points = {row["id"]: row["longitude"] for row in result["factors"]}
    assert (
        solar["daily_meridian"]["profile"]["upper_meridian_longitude"]
        == points["Midheaven"]
    )


@HAS_SWE
def test_equivalent_fractional_timezone_does_not_change_recorded_second_or_geometry():
    first = calculate_germany_chart_analysis(**SOURCE_INPUT)
    # A synthetic equivalent clock representation, not a claim about Hamburg's
    # historical timezone. The instant and geographic coordinates stay fixed.
    second = calculate_germany_chart_analysis(
        **{
            **SOURCE_INPUT,
            "birth_day": 15,
            "birth_hour": 4,
            "birth_minute": 5,
            "birth_timezone": "+05:45",
        }
    )
    assert (
        first["base_chart"]["person_info"]["utc_datetime"]
        == second["base_chart"]["person_info"]["utc_datetime"]
    )
    for field in ("factors", "midpoint_axes", "dials", "interpretations"):
        assert first["midpoint_analysis"][field] == second["midpoint_analysis"][field]


@HAS_SWE
def test_omitted_seconds_preserve_previous_default_business_output():
    assert calculate_germany_chart_analysis(
        **astro_payload()
    ) == calculate_germany_chart_analysis(**astro_payload(), birth_second=0)


@pytest.mark.parametrize(
    "model", [AstroSpecialtyRequest, AstroGermanyRequest, AstroChartPolyRequest]
)
@pytest.mark.parametrize("value", [-1, 60, 59.5, None])
def test_invalid_recorded_seconds_fail_the_public_request(model, value):
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                **SOURCE_INPUT,
                "birth_second": value,
                **(
                    {"chart_variant": "germany"}
                    if model is AstroChartPolyRequest
                    else {}
                ),
            }
        )


@pytest.mark.parametrize(
    "variant", ["chart", "hellen_chart", pytest.param("guolao_chart", marks=HAS_SWE)]
)
def test_nonzero_seconds_cannot_be_silently_ignored_in_other_variants(variant):
    if variant != "guolao_chart":
        with pytest.raises(ValidationError, match="nonzero birth_second"):
            AstroChartPolyRequest.model_validate(
                {**SOURCE_INPUT, "chart_variant": variant}
            )
        return
    # Guolao's current dedicated and polymorphic contracts support seconds.
    # Keep the case and verify actual use, rather than expecting rejection.
    request = AstroChartPolyRequest.model_validate(
        {**SOURCE_INPUT, "chart_variant": variant}
    )
    assert request.birth_second == 50
    exact, minute = [
        calculate_core_chart_analysis(
            **{**SOURCE_INPUT, "birth_second": second}, chart_variant=variant
        )
        for second in (50, 0)
    ]
    assert "guolao" in exact and "guolao" in minute
    assert exact["person_info"]["utc_datetime"] == REFERENCE["adopted_utc_label"]
    assert minute["person_info"]["utc_datetime"] == "1879-05-14T22:20:00+00:00"
    suns = [
        next(
            row["longitude"] for row in result["guolao"]["bodies"] if row["id"] == "Sun"
        )
        for result in (exact, minute)
    ]
    assert suns[0] != suns[1]


@HAS_SWE
def test_india_supported_seconds_reach_the_actual_clock_and_positions():
    # India now supports seconds explicitly. Retain the no-silent-truncation
    # requirement with real calculations instead of rejecting a supported field.
    request = AstroChartPolyRequest.model_validate(
        {**SOURCE_INPUT, "chart_variant": "india_chart"}
    )
    assert request.birth_second == 50
    results = [
        calculate_core_chart_analysis(
            **{**SOURCE_INPUT, "birth_second": second},
            chart_variant="india_chart",
            divisions=[],
        )
        for second in (50, 0)
    ]
    exact, minute = results
    assert exact["person_info"]["utc_datetime"] == REFERENCE["adopted_utc_label"]
    assert (
        exact["india"]["profile"]["clock_context"]["calculation_utc_datetime"]
        == REFERENCE["adopted_utc_label"]
    )
    assert minute["person_info"]["utc_datetime"] == "1879-05-14T22:20:00+00:00"
    longitudes = [
        {row["id"]: row["longitude"] for row in result["planets"]} for result in results
    ]
    assert longitudes[0]["Sun"] != longitudes[1]["Sun"]


def test_original_natal_table_and_later_clock_conversion_are_kept_distinct():
    assert (
        REFERENCE["source"]["pdf_sha256"]
        == "18fcf0aa0ce530fc3c594ed9ff42c92b536948b716c1b1e2ca7f69432dd345a2"
    )
    assert len(REFERENCE["printed_natal_positions"]) == 12
    assert REFERENCE["clock_reworking"]["author"] != REFERENCE["source"]["author"]
    assert REFERENCE["complete_original_numeric_case_accepted"] is False
    assert REFERENCE["event_claims_adopted"] is False
    assert REFERENCE["empirical_outcomes"] == 0


@HAS_SWE
def test_cli_birth_second_flag_reaches_the_actual_public_clock(capsys):
    code = run(
        [
            "astro_germany_chart",
            "--birth-year",
            "1879",
            "--birth-month",
            "5",
            "--birth-day",
            "14",
            "--birth-hour",
            "22",
            "--birth-minute",
            "20",
            "--birth-second",
            "50",
            "--birth-timezone",
            "UTC",
            "--birth-longitude",
            "10",
            "--birth-latitude",
            "53.55",
            "--fields",
            "base_chart.person_info",
            "--strict-fields",
            "--no-include-snapshot-text",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert code == 0, body
    assert (
        body["base_chart"]["person_info"]["utc_datetime"]
        == REFERENCE["adopted_utc_label"]
    )
