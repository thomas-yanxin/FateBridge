"""Related contract regressions with shared imports; original cases retained."""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.astro.astrology_lifespan import (
    _house_containing,
    build_age_point_payload,
    build_balbillus_payload,
    build_harmonic_payload,
    build_persian_directed_payload,
)
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.core.predictive.profections import (
    monthly_profection_index,
    monthly_profection_segment,
)
from fatebridge.core.predictive.returns import _longitude_tt
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name
from tests.support.horizon_reference import horizon_vector_reference
from tests.support.transports import SPECS, business, native, rest, surface_calls


@pytest.mark.parametrize(
    "planet,exaltation,years",
    [
        ("Sun", 19.0, 19),
        ("Moon", 33.0, 25),
        ("Saturn", 201.0, 30),
        ("Jupiter", 105.0, 12),
        ("Mars", 298.0, 15),
        ("Venus", 357.0, 8),
        ("Mercury", 165.0, 20),
    ],
)
@pytest.mark.parametrize("distance,fraction", [(0, 1), (180, 0.5)])
def test_balbillus_matches_source_exaltation_and_129_subperiod_shares(
    planet: str, exaltation: float, years: int, distance: int, fraction: float | int
) -> None:
    # Independent literal controls for the selected continuous-angle reading:
    # CCAG VIII.4 (1921), p237.16-28 and p238.1-2:
    # https://archive.org/download/ccagtome-08-part-3/CCAGTome08Part4.pdf
    # Full small years at exaltation, half at the opposite degree. The former
    # planet-specific fit violated both conditions for Sun, Moon and Mars.
    natal = {
        name.lower(): {"absolute_degree": longitude}
        for name, longitude in (
            ("Sun", 19.0),
            ("Moon", 33.0),
            ("Saturn", 201.0),
            ("Jupiter", 105.0),
            ("Mars", 298.0),
            ("Venus", 357.0),
            ("Mercury", 165.0),
        )
    }
    natal[planet.lower()]["absolute_degree"] = (exaltation + distance) % 360
    result = build_balbillus_payload(natal, start_planet=planet, mode="nearest")
    first = result["periods"][0]
    assert first["planet"] == planet
    assert first["duration_years"] == years * fraction
    # The critical edition corrects the manuscript total119 to129 and Sun119
    # to19 in note24. Each parent gives its own period these seven proportions;
    # no child's separately reduced duration or final filler enters this rule.
    source_years = {
        "Sun": 19,
        "Moon": 25,
        "Saturn": 30,
        "Jupiter": 12,
        "Mars": 15,
        "Venus": 8,
        "Mercury": 20,
    }
    assert len(first["sub_periods"]) == 7
    assert first["sub_periods"][0]["planet"] == planet
    for child in first["sub_periods"]:
        assert child["duration_years"] == round(
            years * fraction * source_years[child["planet"]] / 129, 4
        )
    assert result["reduction_model"]["fitted_offsets_used"] is False
    assert not result["reduction_model"]["whole_procedure_certified"]


@pytest.mark.parametrize("code", [b"A", b"E"])
def test_equal_house_aliases_match_independent_polar_vector(code: bytes) -> None:
    # The 100-digit vector oracle uses the actual reported angle model.
    # A new rotation model can cross this grazing endpoint: the frozen v4
    # ARMC is checked separately, without binding this public path to it.
    # Swiss documents A/E as the same method, with cusp 1 at the Ascendant:
    # https://www.astro.com/swisseph/swephprg.htm
    jd_ut1, latitude, longitude = 2415020.5208333335, -89.0, -105.40281632765013
    with preserve_ephemeris_path():
        cusps, axes = ephemeris_call("houses_ex", jd_ut1, latitude, longitude, code)
        cusps, axes, receipt = canonical_house_geometry(
            julian_day_ut1=jd_ut1,
            latitude=latitude,
            longitude=longitude,
            house_code=code,
            native_cusps=cusps,
            native_angles=axes,
        )
    precision = receipt["eastern_direction_precision"]
    expected_asc = horizon_vector_reference(
        latitude, axes[2], precision["true_obliquity"]
    )["ascendant"]
    assert abs(math.remainder(axes[0] - expected_asc, 360)) * 3600 <= 1
    for index, cusp in enumerate(cusps):
        assert abs(math.remainder(cusp - (expected_asc + index * 30), 360)) * 3600 <= 1


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Australia/Lord_Howe"])
def test_month_segments_partition_elapsed_time_across_offset_changes(zone: str) -> None:
    tz = parse_timezone_name(zone)
    start = datetime(2023, 3, 1, 12, tzinfo=tz)
    end = datetime(2024, 3, 1, 12, tzinfo=tz)
    utc_start, utc_end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    previous_end = utc_start
    for index in range(12):
        left, right = monthly_profection_segment(start, end, index)
        left, right = left.astimezone(timezone.utc), right.astimezone(timezone.utc)
        assert left == previous_end
        assert left == utc_start + (utc_end - utc_start) * index / 12
        assert right == utc_start + (utc_end - utc_start) * (index + 1) / 12
        assert monthly_profection_index(start, end, left) == index
        assert (
            monthly_profection_index(start, end, right - timedelta(microseconds=1))
            == index
        )
        previous_end = right
    assert previous_end == utc_end


def test_index_uses_the_same_representable_boundaries_as_the_timeline() -> None:
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=365, microseconds=5)
    for index in range(1, 12):
        boundary, _ = monthly_profection_segment(start, end, index)
        assert monthly_profection_index(start, end, boundary) == index
        assert (
            monthly_profection_index(start, end, boundary - timedelta(microseconds=1))
            == index - 1
        )


@pytest.mark.parametrize(
    "analysis_year,analysis_day,expected_start,expected_end",
    [
        (2024, 28, "2023-02-28", "2024-02-29"),
        (2024, 29, "2024-02-29", "2025-02-28"),
        (2025, 28, "2025-02-28", "2026-02-28"),
    ],
)
def test_leap_birth_year_and_active_month_agree_on_all_transports(
    analysis_year: int,
    analysis_day: int,
    expected_start: str,
    expected_end: str,
    surface_calls,
) -> None:
    spec = SPECS["chart_for_year"]
    payload = {
        "name": "Leap boundary reference",
        "birth_year": 2000,
        "birth_month": 2,
        "birth_day": 29,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_place": "Greenwich",
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
        "analysis_year": analysis_year,
        "analysis_month": 2,
        "analysis_day": analysis_day,
    }
    fields = [
        "chart_for_year.year_start",
        "chart_for_year.year_end",
        "chart_for_year.monthly_profections",
        "chart_for_year.annual_profection",
        "chart_for_year.analysis_datetime",
    ]
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[("fields", field) for field in fields],
        options={"fields": fields},
        flags=["--fields", *fields],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    results = [output["chart_for_year"] for output in outputs]
    assert results[0] == results[1] == results[2]
    result = results[0]
    zone = parse_timezone_name("UTC")
    expected_start = datetime.fromisoformat(expected_start + "T10:30:00+00:00")
    expected_end = datetime.fromisoformat(expected_end + "T10:30:00+00:00")
    assert result["year_start"] == expected_start.astimezone(zone).isoformat()
    assert result["year_end"] == expected_end.astimezone(zone).isoformat()
    target = datetime(analysis_year, 2, analysis_day, 10, 30, tzinfo=timezone.utc)
    assert datetime.fromisoformat(result["analysis_datetime"]) == target
    months = result["monthly_profections"]
    assert months[0]["start"] == result["year_start"]
    assert months[-1]["end"] == result["year_end"]
    for row in months:
        duration = datetime.fromisoformat(row["end"]) - datetime.fromisoformat(
            row["start"]
        )
        assert abs(duration - (expected_end - expected_start) / 12) <= timedelta(
            microseconds=1
        )
    active = [row for row in months if row["active"]]
    assert len(active) == 1
    assert active[0]["house"] == result["annual_profection"]["monthly_house"]


def test_harmonic_product_keeps_the_supplied_coordinate_on_its_side_of_each_sign() -> (
    None
):
    with localcontext() as context:
        context.prec = 100
        for harmonic in range(1, 361):
            for boundary in range(30, 361, 30):
                value = boundary / harmonic
                for longitude in (
                    math.nextafter(value, -math.inf),
                    value,
                    math.nextafter(value, math.inf),
                ):
                    exact = Decimal.from_float(longitude) * harmonic % 360
                    result = build_harmonic_payload(
                        {"sun": {"absolute_degree": longitude}},
                        harmonic=harmonic,
                        orb=2,
                    )
                    displayed = result["positions"]["sun"]["absolute_degree"]
                    assert 0 <= displayed < 360
                    assert int(displayed // 30) == int(exact // 30)


def test_harmonic_conjunction_orb_uses_the_product_before_float_display() -> None:
    # 1.6 is a binary double above the exact decimal; the exact separation
    # of these supplied values times20 exceeds2, although float products tie.
    result = build_harmonic_payload(
        {"sun": {"absolute_degree": 1.5}, "moon": {"absolute_degree": 1.6}},
        harmonic=20,
        orb=2,
    )
    assert result["resonant_conjunctions"] == []


def test_harmonic_contacts_are_ordered_before_rounding_four_decimal_labels() -> None:
    result = build_harmonic_payload(
        {
            "sun": {"absolute_degree": 0},
            "moon": {"absolute_degree": 1.00004},
            "mercury": {"absolute_degree": 1.00001},
        },
        harmonic=1,
        orb=2,
    )
    assert [row["points"] for row in result["resonant_conjunctions"]] == [
        ["Moon", "Mercury"],
        ["Sun", "Mercury"],
        ["Sun", "Moon"],
    ]


@pytest.mark.parametrize("ascendant", [0, 1, 3.038038378856752, 60, 120])
def test_age_point_keeps_the_preceding_float_in_the_preceding_house(
    ascendant: float | int,
) -> None:
    cusps = [(ascendant + index * 30) % 360 for index in range(12)]
    for house, cusp in enumerate(cusps):
        assert _house_containing(cusp, cusps)[0] == house
        containing, fraction = _house_containing(math.nextafter(cusp, -math.inf), cusps)
        assert containing == (house - 1) % 12
        assert 0 < fraction < 1


def test_age_point_orders_near_cycle_end_before_the_exact_cycle_closure() -> None:
    cusps = [1 + index * 30 for index in range(12)]
    result = build_age_point_payload(
        {"Sun": 1, "Moon": math.nextafter(1.0, -math.inf)},
        cusps,
        max_age_years=72,
    )
    assert [row["body"] for row in result["contacts"]] == ["Moon", "Sun"]


def test_age_point_year_annotation_does_not_round_the_contact_twice() -> None:
    # Equal30-degree houses advance5degrees/year:12.505degrees is2.501years.
    # Its two-decimal label2.50 must not promote the actual contact to age2.
    result = build_age_point_payload(
        {"Sun": 12.505}, [index * 30 for index in range(12)], max_age_years=6
    )
    assert result["contacts"][0]["age"] == 2.5
    assert result["points"][2]["aspect_to"] is None
    assert result["points"][3]["aspect_to"] == "Sun"


def test_persian_hit_limit_keeps_the_first_actual_age_with_equal_display_labels() -> (
    None
):
    result = build_persian_directed_payload(
        {"Sun": 0, "Uranus": 1.004, "Neptune": 1.001},
        [],
        max_age_years=2,
        limit=1,
    )
    assert result["hit_count"] == 1
    assert result["hits"][0]["age"] == 1
    assert result["hits"][0]["significator"] == "Neptune"


@pytest.mark.parametrize(
    ("tool", "field", "options"),
    [
        ("harmonic_chart", "harmonic_chart", {"harmonic": 7}),
        ("age_point", "age_point", {"max_age_years": 72}),
        ("persian_directions", "persian_directions", {"max_age_years": 90}),
        (
            "balbillus_periods",
            "balbillus",
            {"mode": "nearest", "max_age_years": 30},
        ),
        (
            "balbillus_periods",
            "balbillus",
            {"mode": "forward", "max_age_years": 30},
        ),
        (
            "zodiacal_releasing",
            "zodiacal_releasing",
            {"analysis_year": 2030, "analysis_month": 1, "analysis_day": 1},
        ),
        (
            "zodiacal_releasing",
            "zodiacal_releasing",
            {
                "birth_year": 1995,
                "birth_month": 7,
                "birth_day": 27,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_longitude": 116.4,
                "birth_latitude": 39.9,
                "analysis_year": 2030,
                "analysis_month": 1,
                "analysis_day": 1,
            },
        ),
        (
            "zodiacal_releasing",
            "zodiacal_releasing",
            {
                "birth_year": 1990,
                "birth_month": 5,
                "birth_day": 17,
                "birth_hour": 15,
                "birth_minute": 30,
                "birth_longitude": 121.4737,
                "birth_latitude": 31.2304,
                "analysis_year": 2030,
                "analysis_month": 1,
                "analysis_day": 1,
            },
        ),
        (
            "zodiacal_releasing",
            "zodiacal_releasing",
            {
                "birth_year": 1984,
                "birth_month": 1,
                "birth_day": 15,
                "birth_hour": 6,
                "birth_minute": 30,
                "birth_timezone": "Australia/Sydney",
                "birth_longitude": 151.2093,
                "birth_latitude": -33.8688,
                "analysis_year": 2030,
                "analysis_month": 1,
                "analysis_day": 1,
            },
        ),
    ],
)
def test_derived_calculations_reach_all_three_transports(
    tool: str, field: str, options, surface_calls
) -> None:
    spec = SPECS[tool]
    inputs = {
        "birth_year": 2000,
        "birth_month": 12,
        "birth_day": 10,
        "birth_hour": 9,
        "birth_minute": 55,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 120.45,
        "birth_latitude": 32.54,
        **options,
    }
    fields = [field]
    query = [("fields", field)]
    http, protocol, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={"fields": fields},
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    assert field in outputs[0]
    if field == "balbillus":
        calculation = outputs[0][field]
        assert calculation["mode"] == options["mode"]
        assert calculation["reduction_model"]["method_id"] == (
            "balbillus_continuous_proportional_v3"
        )
        assert not calculation["reduction_model"]["fitted_offsets_used"]
        assert not calculation["reduction_model"]["whole_procedure_certified"]
    else:
        pass
    if field == "zodiacal_releasing":
        # Independent Kerykeion6.0.5 natal factories agree on Can/Leo and
        # Lib/Lib. Brennan/Schaim episode192 fixes Fortune as angular reference
        # and shifts only same-sign Spirit. Kerykeion's missing shift and its
        # tropical-year convention are not used as the historical rule oracle.
        calculation = outputs[0][field]
        spirit = calculation["spirit"]
        fortune, natal_spirit, origin, peaks, relative, phase = {
            1995: (
                "Libra",
                "Libra",
                "Scorpio",
                ["Libra", "Capricorn", "Aries", "Cancer"],
                2,
                "succedent",
            ),
            2000: (
                "Cancer",
                "Leo",
                "Leo",
                ["Cancer", "Libra", "Capricorn", "Aries"],
                2,
                "succedent",
            ),
            1990: (
                "Gemini",
                "Capricorn",
                "Capricorn",
                ["Gemini", "Virgo", "Sagittarius", "Pisces"],
                8,
                "succedent",
            ),
            1984: (
                "Gemini",
                "Virgo",
                "Virgo",
                ["Gemini", "Virgo", "Sagittarius", "Pisces"],
                4,
                "angular",
            ),
        }[inputs["birth_year"]]
        assert spirit["lot"]["sign"] == natal_spirit
        assert spirit["release_start_sign"] == origin
        assert spirit["angular_reference_sign"] == fortune
        assert [row["sign"] for row in spirit["peak_signs"]] == peaks
        first = spirit["level_1_timeline"][0]
        assert first["sign"] == origin
        assert first["relative_sign_index"] == relative
        assert first["phase"] == phase
        assert first["is_peak_period"] == (phase == "angular")
        # Published 20x360days from the physical birth instant. A civil-time
        # addition used to add an hour when the historical DST offset changed.
        source_boundary = {
            1990: "2010-02-01T14:30:00+08:00",
            1984: "2003-10-02T05:30:00+10:00",
        }.get(inputs["birth_year"])
        if source_boundary is not None:
            assert (
                calculation["fortune"]["level_1_timeline"][0]["end"] == source_boundary
            )
        else:
            pass
        basis = calculation["calculation_basis"]
        assert basis["year_days"] == 360.0
        assert basis["interval_time_basis"] == "elapsed_utc_days"
        assert basis["published_levels"] == [1, 2, 3, 4]
        assert "whole_procedure_certified" not in basis
        for track in (calculation["fortune"], calculation["spirit"]):
            for period in track["level_3_timeline"]:
                assert period["duration_unit"] == "days"
                elapsed = (
                    datetime.fromisoformat(period["end"])
                    - datetime.fromisoformat(period["start"])
                ) / timedelta(days=1)
                assert 0 < elapsed <= period["duration_value"]
    else:
        pass


@pytest.mark.parametrize("failure", ["exception", "negative_flags", "nonfinite"])
def test_sidereal_return_offset_failure_never_becomes_linear_success(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        else:
            pass
        if failure == "exception":
            raise RuntimeError("Synthetic native offset failure")
        else:
            pass
        return (-1, 23.0) if failure == "negative_flags" else (2, math.nan)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(RuntimeError, match="Native Lahiri ayanamsha unavailable"):
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)


def test_sidereal_return_preserves_source_integrity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = geometry.runtime.ephemeris_call
    failure = EphemerisSourceError("physical_configuration_changed")

    def unavailable(operation, *args, **kwargs):
        if operation in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            raise failure
        else:
            pass
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(EphemerisSourceError) as caught:
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)
    assert caught.value is failure


@pytest.mark.parametrize("body", [swe.SUN, swe.MOON])
@pytest.mark.parametrize("tt", [2451545.0, 2460462.7708333335])
def test_return_longitude_matches_native_sidereal_coordinates_at_the_same_tt(
    body, tt: float
) -> None:
    with preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        coordinates, flags = ephemeris_call(
            "calc", tt, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        )
    assert flags >= 0
    actual = _longitude_tt(body, tt, sidereal=True)
    difference = (actual - coordinates[0] + 180) % 360 - 180
    assert abs(difference) < 1e-10
