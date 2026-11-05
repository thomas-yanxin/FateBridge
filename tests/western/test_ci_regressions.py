"""Related contract regressions with shared imports; original cases retained."""

import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.astrology_lifespan import (
    _house_containing,
    build_age_point_payload,
    build_harmonic_payload,
    build_persian_directed_payload,
)
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
from tests.support.transports import SPECS, business, native, rest, surface_calls


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Australia/Lord_Howe"])
def test_month_segments_partition_elapsed_time_across_offset_changes(zone):
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


def test_index_uses_the_same_representable_boundaries_as_the_timeline():
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
@pytest.mark.parametrize("return_timezone", ["UTC", "America/New_York"])
def test_leap_birth_year_and_active_month_agree_on_all_transports(
    analysis_year,
    analysis_day,
    expected_start,
    expected_end,
    return_timezone,
    surface_calls,
):
    spec = SPECS["givenyear"]
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
        "return_timezone": return_timezone,
    }
    fields = [
        "givenyear.year_start",
        "givenyear.year_end",
        "givenyear.monthly_profections",
        "givenyear.annual_profection",
        "givenyear.analysis_datetime",
    ]
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[("fields", field) for field in fields],
        options={"fields": fields},
        flags=["--fields", *fields],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    outputs = [response.json(), local, protocol.structured_content]
    results = [output["givenyear"] for output in outputs]
    assert results[0] == results[1] == results[2]
    result = results[0]
    zone = parse_timezone_name(return_timezone)
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


def test_harmonic_product_keeps_the_supplied_coordinate_on_its_side_of_each_sign():
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


def test_harmonic_conjunction_orb_uses_the_product_before_float_display():
    # 1.6 is a binary double above the exact decimal; the exact separation
    # of these supplied values times20 exceeds2, although float products tie.
    result = build_harmonic_payload(
        {"sun": {"absolute_degree": 1.5}, "moon": {"absolute_degree": 1.6}},
        harmonic=20,
        orb=2,
    )
    assert result["resonant_conjunctions"] == []


def test_harmonic_contacts_are_ordered_before_rounding_four_decimal_labels():
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
def test_age_point_keeps_the_preceding_float_in_the_preceding_house(ascendant):
    cusps = [(ascendant + index * 30) % 360 for index in range(12)]
    for house, cusp in enumerate(cusps):
        assert _house_containing(cusp, cusps)[0] == house
        containing, fraction = _house_containing(math.nextafter(cusp, -math.inf), cusps)
        assert containing == (house - 1) % 12
        assert 0 < fraction < 1


def test_age_point_orders_near_cycle_end_before_the_exact_cycle_closure():
    cusps = [1 + index * 30 for index in range(12)]
    result = build_age_point_payload(
        {"Sun": 1, "Moon": math.nextafter(1.0, -math.inf)},
        cusps,
        max_age_years=72,
    )
    assert [row["body"] for row in result["contacts"]] == ["Moon", "Sun"]


def test_age_point_year_annotation_does_not_round_the_contact_twice():
    # Equal30-degree houses advance5degrees/year:12.505degrees is2.501years.
    # Its two-decimal label2.50 must not promote the actual contact to age2.
    result = build_age_point_payload(
        {"Sun": 12.505}, [index * 30 for index in range(12)], max_age_years=6
    )
    assert result["contacts"][0]["age"] == 2.5
    assert result["points"][2]["aspect_to"] is None
    assert result["points"][3]["aspect_to"] == "Sun"


def test_persian_hit_limit_keeps_the_first_actual_age_with_equal_display_labels():
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
        ("astro_harmonic", "harmonic_chart", {"harmonic": 7}),
        ("astro_agepoint", "age_point", {"max_age_years": 72}),
        ("astro_persiandirected", "persian_directed", {"max_age_years": 90}),
    ],
)
def test_derived_calculations_reach_all_three_transports(
    tool, field, options, surface_calls
):
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
    query = [("fields", field), ("strict_fields", "true")]
    query += [("include_snapshot_text", "false"), ("response_char_limit", 0)]
    http, protocol, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    assert field in outputs[0]


@pytest.mark.parametrize("failure", ["exception", "negative_flags", "nonfinite"])
def test_sidereal_return_offset_failure_never_becomes_linear_success(
    monkeypatch, failure
):
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        if failure == "exception":
            raise RuntimeError("Synthetic native offset failure")
        return (-1, 23.0) if failure == "negative_flags" else (2, math.nan)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(RuntimeError, match="Native Lahiri ayanamsha unavailable"):
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)


def test_sidereal_return_preserves_source_integrity_failure(monkeypatch):
    original = geometry.runtime.ephemeris_call
    failure = EphemerisSourceError("physical_configuration_changed")

    def unavailable(operation, *args, **kwargs):
        if operation in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            raise failure
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(EphemerisSourceError) as caught:
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)
    assert caught.value is failure


@pytest.mark.parametrize("body", [swe.SUN, swe.MOON])
@pytest.mark.parametrize("tt", [2451545.0, 2460462.7708333335])
def test_return_longitude_matches_native_sidereal_coordinates_at_the_same_tt(body, tt):
    with preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        coordinates, flags = ephemeris_call(
            "calc", tt, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        )
    assert flags >= 0
    actual = _longitude_tt(body, tt, sidereal=True)
    difference = (actual - coordinates[0] + 180) % 360 - 180
    assert abs(difference) < 1e-10
