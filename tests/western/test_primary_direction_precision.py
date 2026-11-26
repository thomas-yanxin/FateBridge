"""Bounded geometry and clock references for primary-direction calculations."""

import gzip
import math
from dataclasses import replace
from datetime import date, datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.predictive import western_timing
from fatebridge.core.predictive._common import (
    build_lot_payloads,
    build_predictive_birth_info,
    extract_reference_points,
)
from fatebridge.core.predictive.native_chart import NativePoint, NativeSubject
from fatebridge.core.predictive.primary_directions import (
    build_primary_direction_bounds_overlay,
    build_primary_directions_payload,
    build_shifted_lot_payloads,
    build_shifted_reference_points,
    build_sign_change_payloads,
)
from fatebridge.services.western_timing import calculate_western_timing_module_analysis


class EventIdentity(BaseModel):
    promissor: str
    significator: str
    aspect_degree: int
    variant: int


class EventOrb(EventIdentity):
    unrounded_orb_degrees: float


class PrimaryCase(BaseModel):
    id: str
    direction: Literal[0, 1]
    analysis_UTC: datetime
    expected_phase: Literal["past", "future", "exact"]
    source_selected_event: EventIdentity
    expected_directed_longitudes: dict[str, float]
    expected_event_orbs: list[EventOrb]


class PrimaryReference(BaseModel):
    birth_UTC: datetime
    birth_longitude: float
    birth_latitude: float
    TT_parts: tuple[float, float]
    adopted_UT1: float
    geometric_Sun_altitude_degrees: float
    points: dict[str, float]
    rows: list[PrimaryCase]


REFERENCE = PrimaryReference.model_validate_json(
    (
        Path(__file__).parents[1]
        / "fixtures/primary-direction-rounding-reference-v1.json"
    ).read_text()
)


class PrimaryClockEvent(EventIdentity):
    event_age_years: float
    expected_UTC: datetime
    expected_offset_seconds: int


class PrimaryClockCase(BaseModel):
    id: str
    birth_date: date
    birth_timezone: str
    analysis_datetime: datetime
    direction: Literal[0, 1]
    time_key: Literal["Ptolemy", "Naibod", "Cardan"]
    natal_subject: NativeSubject
    events: list[PrimaryClockEvent]


class PrimaryClockReference(BaseModel):
    profile_id: str
    seconds_before_limit: float
    seconds_after_limit: float
    longitude: float
    latitude: float
    cases: list[PrimaryClockCase]


CLOCK_DIRECTORY = Path(__file__).parents[1] / "data/primary_direction_clock_temporal_v1"
CLOCK_REFERENCE = PrimaryClockReference.model_validate_json(
    gzip.decompress((CLOCK_DIRECTORY / "reference.json.gz").read_bytes())
)


@pytest.fixture(scope="module")
def frozen_primary_subject() -> NativeSubject:
    # House and motion fields are unassessed here. The checked algorithms use
    # only these external longitudes, the known frame and external Sun altitude.
    points = {
        name.lower(): NativePoint(
            name=name,
            abs_pos=value,
            position=value % 30,
            sign=SIGNS[int(value // 30)],
            sign_num=int(value // 30),
            house="Unassessed",
        )
        for name, value in REFERENCE.points.items()
        if name not in {"Fortune", "Spirit"}
    }
    return NativeSubject(
        name="external-primary-operands",
        lng=REFERENCE.birth_longitude,
        lat=REFERENCE.birth_latitude,
        tz_str="UTC",
        iso_formatted_utc_datetime=REFERENCE.birth_UTC.isoformat(),
        iso_formatted_local_datetime=REFERENCE.birth_UTC.isoformat(),
        ut1=UT1Instant.from_float(REFERENCE.adopted_UT1),
        tt=TTInstant.from_float(math.fsum(REFERENCE.TT_parts)),
        houses_system_identifier="P",
        zodiac_type="Tropic",
        sidereal_mode=None,
        is_diurnal=REFERENCE.geometric_Sun_altitude_degrees >= 0,
        points=points,
        calculation_basis={
            "ayanamsha_degrees": 0.0,
            "julian_day_tt": math.fsum(REFERENCE.TT_parts),
            "julian_day_ut1": REFERENCE.adopted_UT1,
        },
    )


def test_linear_direction_classifies_working_angles_before_display(
    frozen_primary_subject: NativeSubject,
) -> None:
    epsilon = 2.0**-53
    longitudes = {"ascendant": 0.0, "sun": epsilon, "moon": 15.0, "mercury": 38.0}
    subject = replace(
        frozen_primary_subject,
        is_diurnal=True,
        points={
            **frozen_primary_subject.points,
            **{
                name: replace(
                    frozen_primary_subject.points[name],
                    abs_pos=longitude,
                    position=longitude % 30,
                    sign=SIGNS[int(longitude // 30)],
                    sign_num=int(longitude // 30),
                )
                for name, longitude in longitudes.items()
            },
        },
    )

    # Fortune = 0 + 15 - epsilon; adding 15 stays below the sign boundary.
    directed_lots = build_shifted_lot_payloads(subject, arc_degrees=15.0)
    fortune = directed_lots["lot_of_fortune"]
    assert (fortune["longitude"], fortune["sign"], fortune["house"]) == (
        math.nextafter(30.0, 0.0),
        "Aries",
        1,
    )
    changes = build_sign_change_payloads(
        extract_reference_points(subject),
        build_shifted_reference_points(subject, arc_degrees=15.0),
        build_lot_payloads(subject),
        directed_lots,
    )
    assert all(change["point"] != "Fortune" for change in changes)

    # Mercury's exact directed degree is just below the second Taurus bound.
    points = build_shifted_reference_points(subject, arc_degrees=-epsilon)
    bounds = build_primary_direction_bounds_overlay(points, {}, enabled=True)
    assert points["Mercury"]["sign"] == "Taurus"
    assert points["Mercury"]["degree"] == math.nextafter(8.0, 0.0)
    assert bounds["points"]["Mercury"]["bound_lord"] == "Venus"


@pytest.mark.parametrize("direction", [0, 1], ids=["direct", "converse"])
@pytest.mark.parametrize("offset", [0.0, 2.0**-53], ids=["at-limit", "above-limit"])
def test_primary_direction_window_compares_before_rounding(
    direction: int, offset: float, frozen_primary_subject: NativeSubject
) -> None:
    # The wrapped arc is 100 + offset in either direction. Both offsets
    # deliver the same float age, but only exact equality owns the upper limit.
    ascendant, sun = (260.0, offset) if direction == 0 else (offset, 260.0)
    subject = replace(
        frozen_primary_subject,
        points={
            **frozen_primary_subject.points,
            **{
                name: replace(
                    frozen_primary_subject.points[name],
                    abs_pos=longitude,
                    position=longitude % 30,
                    sign=SIGNS[int(longitude // 30)],
                    sign_num=int(longitude // 30),
                )
                for name, longitude in {"ascendant": ascendant, "sun": sun}.items()
            },
        },
    )
    natal = REFERENCE.birth_UTC
    birth = build_predictive_birth_info(
        birth_year=natal.year,
        birth_month=natal.month,
        birth_day=natal.day,
        birth_hour=natal.hour,
        birth_minute=natal.minute,
        birth_timezone="UTC",
        birth_longitude=REFERENCE.birth_longitude,
        birth_latitude=REFERENCE.birth_latitude,
    )
    result = build_primary_directions_payload(
        birth,
        subject,
        analysis_datetime=natal,
        pd_method="astroapp_alchabitius",
        pd_time_key="Ptolemy",
        pd_type=direction,
        pd_aspects=[0],
    )
    ages = [
        hit["event_age_years"]
        for hit in result["timeline"]
        if hit["promissor"] == "Ascendant" and hit["significator"] == "Sun"
    ]
    assert ages == ([100.0] if offset == 0.0 else [])


@pytest.mark.parametrize("case", REFERENCE.rows, ids=lambda case: case.id)
def test_primary_services_keep_external_model_precision(
    case: PrimaryCase,
    frozen_primary_subject: NativeSubject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        western_timing,
        "build_natal_subject",
        lambda birth_info, *, house_system, zodiac_type: frozen_primary_subject,
    )
    birth, target = REFERENCE.birth_UTC, case.analysis_UTC
    kwargs = dict(
        birth_year=birth.year,
        birth_month=birth.month,
        birth_day=birth.day,
        birth_hour=birth.hour,
        birth_minute=birth.minute,
        birth_timezone="UTC",
        birth_longitude=REFERENCE.birth_longitude,
        birth_latitude=REFERENCE.birth_latitude,
        analysis_year=target.year,
        analysis_month=target.month,
        analysis_day=target.day,
        analysis_hour=target.hour,
        analysis_minute=target.minute,
        pd_method="astroapp_alchabitius",
        pd_time_key="Ptolemy",
        pd_type=case.direction,
    )
    result = calculate_western_timing_module_analysis(
        technique="primarydirect", **kwargs
    )
    chart_result = calculate_western_timing_module_analysis(
        technique="primarydirchart", **kwargs
    )
    directions = result["directions"]["primary_directions"]
    selected = case.source_selected_event
    hit = next(
        hit
        for hit in directions["timeline"]
        if (
            hit["promissor"],
            hit["significator"],
            hit["aspect_degree"],
            hit["aspect_variant_degrees"],
        )
        == (
            selected.promissor,
            selected.significator,
            selected.aspect_degree,
            selected.variant,
        )
    )
    assert hit["timing_phase"] == case.expected_phase
    orbs = {
        (row.promissor, row.significator, row.aspect_degree, row.variant): row
        for row in case.expected_event_orbs
    }
    for current in directions["current_window"]:
        expected = orbs[
            current["promissor"],
            current["significator"],
            current["aspect_degree"],
            current["aspect_variant_degrees"],
        ]
        assert current["coordinate_context"]["current_orb_degrees"] == pytest.approx(
            expected.unrounded_orb_degrees, abs=0.00005 + 1e-10, rel=0
        )
    chart = chart_result["directions"]["primary_direction_chart"]
    for group in ("directed_points", "directed_lots"):
        for point in chart[group].values():
            expected = case.expected_directed_longitudes[point["point"]]
            assert abs(math.remainder(point["longitude"] - expected, 360)) <= 1e-10


def test_primary_services_accept_extended_utc_birth_clock(
    frozen_primary_subject: NativeSubject, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        western_timing,
        "build_natal_subject",
        lambda birth_info, *, house_system, zodiac_type: frozen_primary_subject,
    )
    kwargs = dict(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=13,
        birth_minute=59,
        birth_timezone="Etc/GMT-14",
        birth_longitude=0.0,
        birth_latitude=0.0,
        analysis_year=40,
        analysis_month=6,
        analysis_day=1,
        analysis_hour=12,
        analysis_minute=0,
        pd_aspects=[0],
    )
    result = calculate_western_timing_module_analysis(
        technique="primarydirect", **kwargs
    )
    chart_result = calculate_western_timing_module_analysis(
        technique="primarydirchart", **kwargs
    )
    directions = result["directions"]["primary_directions"]
    chart = chart_result["directions"]["primary_direction_chart"]
    hit = next(
        event
        for event in directions["timeline"]
        if event["promissor"] == "Ascendant" and event["significator"] == "Saturn"
    )
    # Independent integer Gregorian/TZif reference for the frozen sky operands.
    assert directions["current_age_years"] == 39.414683015013615
    assert hit["event_datetime"] == "0007-12-11T20:22:41+14:00"
    assert chart["current_arc_degrees"] == directions["current_arc_degrees"]
    assert chart["hits"] == directions["current_window"][:8]


@pytest.mark.parametrize("case", CLOCK_REFERENCE.cases, ids=lambda case: case.id)
def test_primary_event_clocks_match_independent_temporal_instants(
    case: PrimaryClockCase,
) -> None:
    # The native sky operands are frozen product outputs, not an independent
    # celestial reference. Temporal independently supplies the clock results.
    birth = build_predictive_birth_info(
        birth_year=case.birth_date.year,
        birth_month=case.birth_date.month,
        birth_day=case.birth_date.day,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=case.birth_timezone,
        birth_longitude=CLOCK_REFERENCE.longitude,
        birth_latitude=CLOCK_REFERENCE.latitude,
    )
    payload = build_primary_directions_payload(
        birth,
        case.natal_subject,
        analysis_datetime=case.analysis_datetime,
        pd_method="astroapp_alchabitius",
        pd_time_key=case.time_key,
        pd_type=case.direction,
    )
    expected = {
        (row.promissor, row.significator, row.aspect_degree, row.variant): row
        for row in case.events
    }
    # The frozen ages describe the former rounded-arc calculation. Check
    # current ages from the frozen sky operands and keep Temporal's clock gate.
    degrees = {
        name: Fraction(point.abs_pos)
        for name, point in case.natal_subject.points.items()
    }
    moon_from_sun = degrees["moon"] - degrees["sun"]
    fortune_offset = moon_from_sun if case.natal_subject.is_diurnal else -moon_from_sun
    degrees["fortune"] = degrees["ascendant"] + fortune_offset
    degrees["spirit"] = degrees["ascendant"] - fortune_offset
    rate = Fraction(
        {"Ptolemy": 1.0, "Naibod": 0.98564733, "Cardan": 0.98666667}[case.time_key]
    )
    sense = 1 if case.direction == 0 else -1
    assert len(expected) == len(case.events) == len(payload["timeline"])
    for group in (
        "timeline",
        "current_window",
        "past_window",
        "future_window",
        "exact_window",
    ):
        for hit in payload[group]:
            row = expected[
                hit["promissor"],
                hit["significator"],
                hit["aspect_degree"],
                hit["aspect_variant_degrees"],
            ]
            offset_angle = (
                degrees[row.significator.lower()]
                + row.variant
                - degrees[row.promissor.lower()]
            )
            assert hit["event_age_years"] == float((sense * offset_angle % 360) / rate)
            actual = datetime.fromisoformat(hit["event_datetime"])
            offset = actual.utcoffset()
            assert offset is not None
            assert offset.total_seconds() == row.expected_offset_seconds
            difference = (
                actual.astimezone(timezone.utc) - row.expected_UTC
            ).total_seconds()
            # Original second-only display line plus10microseconds for the
            # existing float-duration representation; no physical-time claim.
            assert -1.00001 <= difference <= 0.00001
