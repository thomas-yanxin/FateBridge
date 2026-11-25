import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.predictive import profections, progressions, transit
from fatebridge.core.predictive._common import (
    TIMING_POINT_NAMES,
    TRANSIT_POINT_NAMES,
    build_lot_payloads,
    build_natal_subject,
    build_predictive_birth_info,
    normalize_angle,
    point_attribute_name,
)
from fatebridge.core.predictive._common import swe as predictive_swe
from fatebridge.core.predictive.native_chart import NativePoint, NativeSubject
from fatebridge.core.predictive.primary_directions import (
    build_primary_direction_equatorial_context,
    point_equatorial_position,
    project_absolute_degree_to_equatorial,
    semiarc_degrees_for_declination,
)
from fatebridge.core.predictive.western_timing import build_western_timing_payload
from fatebridge.core.predictive.zodiacal_releasing import (
    build_releasing_level_within_interval,
)
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.western_timing import calculate_western_timing_analysis
from fatebridge.services.western_timing_tools import calculate_timing_tool
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.timezones import parse_timezone_name

PREDICTIVE_TIME_REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/predictive-time-reference.json").read_text()
)
TRANSIT_EXACT_ORB_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/transit-exact-orb-reference.json"
    ).read_text()
)


@pytest.fixture
def predictive_clock_operands() -> NativeSubject:
    """Explicit scalar operands for clock tests; no independent sky assertion."""
    return NativeSubject(
        name="synthetic-clock-operands",
        lng=0,
        lat=40,
        tz_str="UTC",
        iso_formatted_utc_datetime=None,
        iso_formatted_local_datetime=None,
        ut1=UT1Instant.from_float(2451545),
        tt=TTInstant.from_float(2451545.0),
        houses_system_identifier="P",
        zodiac_type="Tropic",
        sidereal_mode=None,
        is_diurnal=True,
        calculation_basis={},
        points={
            point_attribute_name(name): NativePoint(
                name=name,
                abs_pos=0,
                position=0,
                sign="Ari",
                sign_num=0,
                house="First_House",
            )
            for name in TIMING_POINT_NAMES
        },
    )


@pytest.mark.parametrize(
    "case", TRANSIT_EXACT_ORB_REFERENCE["cases"], ids=lambda c: c["id"]
)
def test_transit_exact_hits_match_flint_supplied_angles(
    case, predictive_clock_operands, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FLINT membership over supplied angles, with only chart casting adapted."""
    subjects = []
    for sun, other in [
        (case["target_longitude"], 90.75),
        (case["source_longitude"], 181.2),
    ]:
        points = {}
        for name in TRANSIT_POINT_NAMES:
            degree = sun if name == "Sun" else other
            points[point_attribute_name(name)] = replace(
                predictive_clock_operands.sun,
                name=name,
                abs_pos=degree,
                position=degree % 30,
                sign="Ari" if name == "Sun" else "Can" if other < 180 else "Lib",
                sign_num=int(degree // 30),
                house=(
                    "First_House"
                    if name == "Sun"
                    else "Fourth_House" if other < 180 else "Seventh_House"
                ),
            )
        subjects.append(replace(predictive_clock_operands, points=points))
    natal, current = subjects
    monkeypatch.setattr(transit, "build_subject", lambda **parameters: current)
    birth = build_predictive_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
    )
    result = transit.build_transit_payload(
        birth,
        natal,
        analysis_datetime=datetime(2026, 11, 13, tzinfo=timezone.utc),
        transit_longitude=0,
        transit_latitude=40,
        transit_timezone="UTC",
        orb_limit=case["orb_limit"],
    )
    sun_hits = [
        row for row in result["exact_hits"] if row["source"] == row["target"] == "Sun"
    ]
    assert bool(sun_hits) is case["expected_exact_membership"]
    assert result["exact_orb_limit"] == case["exact_orb_limit"]
    assert result["orb_limit"] == case["orb_limit"]
    if sun_hits:
        assert sun_hits[0]["orb"] == case["delivered_orb"]
    else:
        pass


def _assert_predictive_reference_clock(moment: datetime, reference):
    assert moment.astimezone(timezone.utc) == datetime.fromisoformat(
        reference["UTC"].replace("Z", "+00:00")
    )
    assert (
        moment.replace(tzinfo=None).isoformat(timespec="microseconds")
        == reference["local_plain"]
    )
    assert moment.utcoffset().total_seconds() == reference["offset_seconds"]


@pytest.mark.parametrize("tool", ["profection", "givenyear"])
def test_generated_anniversary_requires_a_defined_local_clock(tool: str) -> None:
    for month, hour, minute in ((7, 12, 0), (11, 3, 30)):
        result = calculate_timing_tool(
            tool,
            birth_year=1993,
            birth_month=month,
            birth_day=1,
            birth_hour=hour,
            birth_minute=minute,
            birth_longitude=105,
            birth_latitude=0,
            birth_timezone="Antarctica/Vostok",
            house_system="W",
            analysis_year=1994,
            analysis_month=11,
            analysis_day=10,
            analysis_hour=12,
            analysis_minute=0,
        )
        assert result["status_code"] == 422
        assert result["issues"] == [
            {"path": "request", "code": "unresolved_timezone_offset"}
        ]
        assert "周年钟时" in result["error"]


@pytest.mark.parametrize(
    "tool, options, path, expected",
    [
        (
            "firdaria",
            {"firdaria_year_basis": "fixed_365_2425"},
            ("current_sub", "start"),
            "1994-03-15T19:20:24Z",
        ),
        (
            "firdaria",
            {"firdaria_year_basis": "calendar_anniversary"},
            ("current_sub", "start_display"),
            "1994-03-15 18:42Z",
        ),
        (
            "decennials",
            {},
            ("current_level_3", "start"),
            "1994-06-29T18:57:12.558140Z",
        ),
        ("zr", {}, ("fortune", "current_level_2", "start"), "1994-06-24T05:00:00Z"),
    ],
)
def test_period_boundaries_preserve_utc_when_local_offset_is_unspecified(
    tool: str, options, path, expected: str
) -> None:
    result = calculate_timing_tool(
        tool,
        birth_year=1992,
        birth_month=12,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Antarctica/Vostok",
        birth_longitude=0,
        birth_latitude=51.5,
        house_system="W",
        analysis_year=1994,
        analysis_month=11,
        analysis_day=2,
        analysis_hour=12,
        analysis_minute=0,
        **options,
    )
    boundary = result[tool]
    for field in path:
        boundary = boundary[field]
    assert boundary == expected


@pytest.mark.parametrize(
    "case", PREDICTIVE_TIME_REFERENCE["profection_clocks"], ids=lambda c: c["id"]
)
def test_profection_anniversary_and_months_match_temporal(
    case, predictive_clock_operands
) -> None:
    row = case["birth"]
    local = datetime.fromisoformat(row["local"])
    info = build_predictive_birth_info(
        birth_year=local.year,
        birth_month=local.month,
        birth_day=local.day,
        birth_hour=local.hour,
        birth_minute=local.minute,
        birth_timezone=row["zone"],
        birth_longitude=0,
        birth_latitude=40,
    )
    target = datetime.fromisoformat(case["analysis_UTC"].replace("Z", "+00:00"))
    zone = parse_timezone_name(row["zone"])
    output = profections.build_annual_profection_payload(
        info, predictive_clock_operands, analysis_datetime=target
    )
    assert output == profections.build_annual_profection_payload(
        info, predictive_clock_operands, analysis_datetime=target.astimezone(zone)
    )
    assert output["age_years"] == case["age"]
    assert output["calculation_options"]["anniversary_clock_policy"] == "compatible"
    start = datetime.fromisoformat(output["year_start"]).astimezone(zone)
    end = datetime.fromisoformat(output["year_end"]).astimezone(zone)
    expected = case["expected_window"]
    _assert_predictive_reference_clock(start, expected["start"])
    _assert_predictive_reference_clock(end, expected["end"])
    timeline = profections.build_monthly_profections_payload(
        annual_house=output["activated_house"],
        asc_sign="Aries",
        year_start=start,
        year_end=end,
        analysis_datetime=target,
    )
    assert [m["month_index"] for m in timeline if m["active"]] == [
        case["month_index"] + 1
    ]
    for index, month in enumerate(timeline):
        _assert_predictive_reference_clock(
            datetime.fromisoformat(month["start"]), expected["month_bounds"][index]
        )
        _assert_predictive_reference_clock(
            datetime.fromisoformat(month["end"]), expected["month_bounds"][index + 1]
        )
    assert output["monthly_house"] == (case["age"] + case["month_index"]) % 12 + 1


@pytest.mark.parametrize(
    "zone, month, birthday, hour, minute, target, expected",
    [
        pytest.param(
            "Asia/Tokyo",
            1,
            1,
            9,
            18,
            "0001-01-01T09:18:00+09:18:59",
            "分析时刻不能早于出生时刻",
            id="utc-year-zero-local-year-one",
        ),
        pytest.param(
            "Etc/GMT+5",
            12,
            31,
            19,
            1,
            "9999-12-31T19:00:00-05:00",
            ("9998-12-31T19:01:00-05:00", "9999-12-31T19:01:00-05:00", 8098, 11, 10),
            id="utc-year-10000-local-year-9999",
        ),
        pytest.param(
            "Asia/Tokyo",
            1,
            15,
            9,
            18,
            "0001-01-01T09:18:00+09:18:59",
            "分析时刻不能早于出生时刻",
            id="previous-anniversary-in-local-year-zero",
        ),
        pytest.param(
            "Etc/GMT+5",
            12,
            30,
            19,
            1,
            "9999-12-31T19:00:00-05:00",
            10000,
            id="next-anniversary-in-local-year-10000",
        ),
    ],
)
def test_profection_anniversary_intervals_at_local_calendar_edges(
    zone: str,
    month: int,
    birthday: int,
    hour: int,
    minute: int,
    target: str,
    expected,
    predictive_clock_operands,
) -> None:
    info = build_predictive_birth_info(
        birth_year=1900,
        birth_month=month,
        birth_day=birthday,
        birth_hour=hour,
        birth_minute=minute,
        birth_timezone=zone,
        birth_longitude=139.6917,
        birth_latitude=35.6895,
    )
    analysis = datetime.fromisoformat(target)
    if isinstance(expected, int):
        with pytest.raises(ValueError, match=f"year {expected} is out of range"):
            profections.build_annual_profection_payload(
                info, predictive_clock_operands, analysis_datetime=analysis
            )
        return
    else:
        pass
    if isinstance(expected, str):
        with pytest.raises(ValueError, match=expected):
            profections.build_annual_profection_payload(
                info, predictive_clock_operands, analysis_datetime=analysis
            )
        return
    else:
        pass
    result = profections.build_annual_profection_payload(
        info, predictive_clock_operands, analysis_datetime=analysis
    )
    assert (
        result["year_start"],
        result["year_end"],
        result["age_years"],
        result["activated_house"],
        result["monthly_house"],
    ) == expected


@pytest.mark.parametrize(
    "case", PREDICTIVE_TIME_REFERENCE["progression_clocks"], ids=lambda c: c["id"]
)
def test_secondary_progression_fixed_key_matches_flint(
    case, predictive_clock_operands, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed = []

    def capture_subject(**parameters):
        observed.append(parameters["local_datetime"])
        return predictive_clock_operands

    monkeypatch.setattr(progressions, "build_subject", capture_subject)
    info = build_predictive_birth_info(
        birth_year=1900,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
    )
    target = info.require_utc_datetime + timedelta(
        microseconds=case["elapsed_microseconds"]
    )
    result = progressions.build_secondary_progression_payload(
        info, predictive_clock_operands, analysis_datetime=target
    )
    expected = info.require_utc_datetime + timedelta(
        microseconds=case["V2_progressed_microseconds"]
    )
    assert observed == [expected]
    assert datetime.fromisoformat(result["progressed_datetime"]) == expected
    options = result["calculation_options"]
    assert options["year_key_numerator"] == 36524219
    assert options["year_key_denominator"] == 100000
    assert options["house_method"] == "quotidian_at_progressed_UTC"


def test_secondary_progression_labels_undefined_local_time_in_utc() -> None:
    result = calculate_western_timing_analysis(
        birth_year=1994,
        birth_month=1,
        birth_day=31,
        birth_hour=12,
        birth_timezone="Antarctica/Vostok",
        birth_longitude=0,
        birth_latitude=51.5,
        house_system="W",
        analysis_year=2000,
        analysis_month=1,
        analysis_day=31,
        analysis_hour=12,
        analysis_minute=0,
    )
    progressed = result["directions"]["secondary_progression"]
    assert progressed["progressed_datetime"] == "1994-02-06T04:58:12.807301Z"


@pytest.mark.parametrize(
    "case", PREDICTIVE_TIME_REFERENCE["profection_clocks"], ids=lambda c: c["id"]
)
def test_given_year_preserves_anniversary_interval_in_return_zone(
    case, predictive_clock_operands, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        profections, "build_subject", lambda **parameters: predictive_clock_operands
    )
    row = case["birth"]
    local = datetime.fromisoformat(row["local"])
    info = build_predictive_birth_info(
        birth_year=local.year,
        birth_month=local.month,
        birth_day=local.day,
        birth_hour=local.hour,
        birth_minute=local.minute,
        birth_timezone=row["zone"],
        birth_longitude=0,
        birth_latitude=40,
    )
    target = datetime.fromisoformat(case["analysis_UTC"].replace("Z", "+00:00"))
    annual = profections.build_annual_profection_payload(
        info, predictive_clock_operands, analysis_datetime=target
    )
    result = profections.build_given_year_payload(
        info,
        predictive_clock_operands,
        analysis_datetime=target,
        annual_profection=annual,
        return_longitude=139.69,
        return_latitude=35.68,
        return_timezone="Asia/Tokyo",
    )
    expected = case["expected_window"]
    assert datetime.fromisoformat(result["year_start"]).astimezone(
        timezone.utc
    ) == datetime.fromisoformat(expected["start"]["UTC"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(result["year_end"]).astimezone(
        timezone.utc
    ) == datetime.fromisoformat(expected["end"]["UTC"].replace("Z", "+00:00"))
    assert [m["month_index"] for m in result["monthly_profections"] if m["active"]] == [
        case["month_index"] + 1
    ]


def _governing_returns_for(analysis_month, analysis_day):
    """Run the western timing service for a fixed natal chart at a given
    analysis date and return (analysis_utc, solar_utc, lunar_utc)."""
    from datetime import timezone

    from dateutil import parser as _dtp

    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
    )
    tz = parse_timezone_name("Asia/Shanghai")
    analysis_utc = datetime(
        2025, analysis_month, analysis_day, 15, 30, tzinfo=tz
    ).astimezone(timezone.utc)
    solar_utc = _dtp.isoparse(
        result["returns"]["solar_return"]["return_datetime"]
    ).astimezone(timezone.utc)
    lunar_utc = _dtp.isoparse(
        result["returns"]["lunar_return"]["return_datetime"]
    ).astimezone(timezone.utc)
    return analysis_utc, solar_utc, lunar_utc


def test_solar_return_governs_analysis_date_before_birthday() -> None:
    # Analysis 2025-03-01 precedes the May 17 birthday: the governing solar
    # return is the prior birthday's (2024-05-17), NOT the upcoming 2025 one.
    analysis_utc, solar_utc, _ = _governing_returns_for(3, 1)
    assert solar_utc <= analysis_utc, (
        f"solar return {solar_utc.isoformat()} is after analysis "
        f"{analysis_utc.isoformat()} — it does not govern the analysis date"
    )
    assert (analysis_utc - solar_utc).days < 366


def test_lunar_return_governs_analysis_instant() -> None:
    # The active lunar return can fall in the previous calendar month; seeding
    # the search at the analysis-month start wrongly skips it for the next one.
    analysis_utc, _, lunar_utc = _governing_returns_for(3, 1)
    assert lunar_utc <= analysis_utc, (
        f"lunar return {lunar_utc.isoformat()} is after analysis "
        f"{analysis_utc.isoformat()} — it does not govern the analysis instant"
    )
    assert (analysis_utc - lunar_utc).days < 31


def test_monthly_profection_segments_are_equal_twelfths() -> None:
    # The declared monthly policy divides the profected year into 12 equal
    # elapsed-time parts. Every segment must have
    # the same duration, and exactly one must be active and agree with the
    # annual payload's monthly lord.
    from dateutil import parser as _dtp

    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=8,
        analysis_day=10,
    )
    segments = result["directions"]["given_year"]["monthly_profections"]
    assert len(segments) == 12
    durations = [
        (_dtp.isoparse(s["end"]) - _dtp.isoparse(s["start"])).total_seconds()
        for s in segments
    ]
    # Datetime boundaries have microsecond resolution; a minute is not rounding.
    assert max(durations) - min(durations) <= 1e-6, durations
    active = [s for s in segments if s["active"]]
    assert len(active) == 1
    assert (
        active[0]["house"]
        == result["directions"]["given_year"]["annual_profection"]["monthly_house"]
    )


def test_calculate_western_timing_analysis_returns_predictive_sections() -> None:
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="astroapp_alchabitius",
        pd_time_key="Naibod",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    assert result["analysis_type"] == "西占推运与返照分析"
    assert result["natal_reference"]["sun"]["sign"] == "Taurus"
    assert result["natal_reference"]["sun"]["sign_label"] == "金牛座"
    assert result["natal_reference"]["ascendant"]["sign"] == "Libra"
    assert result["natal_reference"]["ascendant"]["sign_label"] == "天秤座"
    assert result["natal_reference"]["lots"]["lot_of_fortune"]["sign"] == "Gemini"
    assert result["natal_reference"]["lots"]["lot_of_fortune"]["sign_label"] == "双子座"
    assert result["natal_reference"]["lots"]["lot_of_spirit"]["sign"] == "Capricorn"
    assert result["natal_reference"]["lots"]["lot_of_spirit"]["sign_label"] == "摩羯座"

    assert result["returns"]["solar_return"]["return_datetime"].startswith(
        "2025-05-17T01:47:"
    )
    assert result["returns"]["lunar_return"]["return_datetime"].startswith(
        "2025-05-20T01:30:"
    )

    assert result["directions"]["secondary_progression"][
        "progressed_datetime"
    ].startswith("1990-06-21")
    assert result["directions"]["solar_arc"]["arc_degrees"] == pytest.approx(
        33.5458, abs=0.01
    )
    transit = result["transits"]["current_transit"]
    assert transit["analysis_datetime"].startswith("2025-05-20T15:30:00+08:00")
    assert transit["location"]["timezone"] == "Asia/Shanghai"
    assert transit["transit_reference"]["uranus"]["point_label"] == "天王星"
    assert transit["natal_reference"]["pluto"]["point_label"] == "冥王星"
    assert len(transit["house_emphasis"]) > 0
    assert len(transit["hits"]) > 0
    assert transit["hits"][0]["orb"] <= 1.5
    given_year = result["directions"]["given_year"]
    assert given_year["analysis_datetime"].startswith("2025-05-20T15:30:00+08:00")
    assert given_year["sun"]["sign"] == "Taurus"
    assert given_year["ascendant"]["sign"] == "Libra"
    assert len(given_year["monthly_profections"]) == 12
    assert given_year["monthly_profections"][0]["house"] == 12
    assert given_year["monthly_profections"][0]["sign"] == "Virgo"
    primary_directions = result["directions"]["primary_directions"]
    assert primary_directions["method"] == "astroapp_alchabitius"
    assert primary_directions["time_key"] == "Naibod"
    assert primary_directions["coordinate_system"] == "ecliptic_longitude"
    assert primary_directions["coordinate_label"] == "Arc"
    assert primary_directions["aspects"] == [0, 90, 180]
    assert primary_directions["current_arc_degrees"] == pytest.approx(34.5072, abs=0.01)
    assert len(primary_directions["current_window"]) > 0
    assert len(primary_directions["past_window"]) > 0
    assert len(primary_directions["future_window"]) > 0
    assert "exact_window" in primary_directions
    assert primary_directions["past_window"][0]["relative_years_from_current"] <= 0
    assert primary_directions["future_window"][0]["relative_years_from_current"] >= 0

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["analysis_datetime"].startswith(
        "2025-05-20T15:30:00+08:00"
    )
    assert primary_direction_chart["show_pd_bounds"] is True
    assert primary_direction_chart["coordinate_system"] == "ecliptic_longitude"
    assert primary_direction_chart["coordinate_label"] == "Arc"
    assert primary_direction_chart["current_arc_degrees"] == pytest.approx(
        34.5072, abs=0.01
    )
    assert "exact_hits" in primary_direction_chart
    assert primary_direction_chart["bounds_overlay"]["system"] == "egyptian_bounds"
    assert primary_direction_chart["bounds_overlay"]["enabled"] is True
    assert (
        primary_direction_chart["bounds_overlay"]["points"]["Sun"]["sign"] == "Cancer"
    )
    assert (
        primary_direction_chart["bounds_overlay"]["points"]["Sun"]["bound_lord"]
        == "Mars"
    )
    assert (
        primary_direction_chart["bounds_overlay"]["points"]["Sun"]["bound_lord_label"]
        == "火星"
    )
    assert primary_direction_chart["directed_points"]["Sun"]["sign"] == "Cancer"
    assert primary_direction_chart["directed_points"]["Moon"]["sign"] == "Pisces"
    assert primary_direction_chart["directed_lots"]["lot_of_fortune"]["sign"] == "Leo"
    sun_sign_change = next(
        item
        for item in primary_direction_chart["sign_changes"]
        if item["point"] == "Sun"
    )
    assert sun_sign_change["from_sign"] == "Taurus"
    assert sun_sign_change["to_sign"] == "Cancer"

    profection = result["time_lords"]["annual_profection"]
    assert profection["activated_house"] == 12
    assert profection["activated_sign"] == "Virgo"
    assert profection["activated_sign_label"] == "处女座"
    assert profection["lord"] == "Mercury"
    assert profection["lord_label"] == "水星"

    firdaria = result["time_lords"]["firdaria"]
    assert firdaria["current_major"]["planet"] == "Moon"
    assert firdaria["current_major"]["planet_label"] == "月亮"
    assert firdaria["current_sub"]["planet"] == "Mars"
    assert firdaria["current_sub"]["planet_label"] == "火星"

    decennials = result["time_lords"]["decennials"]
    assert decennials["current_level_1"]["planet"] == "Moon"
    assert decennials["current_level_2"]["planet"] == "Mars"
    assert decennials["current_level_3"]["planet"] == "Moon"

    zodiacal_releasing = result["time_lords"]["zodiacal_releasing"]
    assert zodiacal_releasing["spirit"]["lot"]["sign"] == "Capricorn"
    assert zodiacal_releasing["fortune"]["lot"]["sign"] == "Gemini"
    assert zodiacal_releasing["spirit"]["current_level_1"]["sign"] == "Aquarius"
    assert zodiacal_releasing["spirit"]["current_level_2"]["sign"] == "Cancer"
    assert zodiacal_releasing["spirit"]["current_level_3"]["sign"] == "Gemini"
    assert zodiacal_releasing["fortune"]["current_level_1"]["sign"] == "Cancer"
    assert zodiacal_releasing["fortune"]["current_level_2"]["sign"] == "Taurus"
    assert zodiacal_releasing["fortune"]["current_level_3"]["sign"] == "Cancer"

    assert "太阳返照" in result["summary"]
    assert "法达" in result["summary"]
    assert "Spirit 黄道释放" in result["summary"]
    assert "行运太阳" in result["summary"]


def test_western_timing_transit_respects_transit_timezone() -> None:
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        return_timezone="UTC",
    )

    assert result["transits"]["current_transit"]["analysis_datetime"].endswith("+00:00")
    assert result["transits"]["current_transit"]["location"]["timezone"] == "UTC"
    assert result["directions"]["given_year"]["analysis_datetime"].endswith("+00:00")


def test_core_chart_supports_fixed_offset_timezones() -> None:
    result = calculate_core_chart_analysis(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="+08:00",
        birth_longitude=121.4667,
        birth_latitude=31.2167,
    )

    assert result["chart_profile"]["chart_type"] == "chart"
    expected_precision = (
        "ephemeris_runtime_model" if swe is not None else "approximate_orbital_model"
    )
    assert result["chart_profile"]["engine_precision"] == expected_precision


def test_primary_directions_expose_exact_window_for_exact_hit_moment() -> None:
    baseline_result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="astroapp_alchabitius",
        pd_time_key="Naibod",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )
    exact_moment = datetime.fromisoformat(
        baseline_result["directions"]["primary_directions"]["current_window"][0][
            "event_datetime"
        ]
    )
    birth_info = build_predictive_birth_info(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
    )

    exact_result = build_western_timing_payload(
        birth_info,
        analysis_datetime=exact_moment,
        pd_method="astroapp_alchabitius",
        pd_time_key="Naibod",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    exact_window = exact_result["directions"]["primary_directions"]["exact_window"]
    assert len(exact_window) > 0
    assert exact_window[0]["timing_phase"] == "exact"
    assert abs(exact_window[0]["relative_years_from_current"]) <= 0.01

    exact_hits = exact_result["directions"]["primary_direction_chart"]["exact_hits"]
    assert len(exact_hits) > 0
    assert exact_hits[0]["timing_phase"] == "exact"
    assert (
        exact_hits[0]["promissor"],
        exact_hits[0]["significator"],
        exact_hits[0]["aspect"],
    ) == (
        exact_window[0]["promissor"],
        exact_window[0]["significator"],
        exact_window[0]["aspect"],
    )


def test_primary_direction_windows_label_undefined_local_time_in_utc() -> None:
    result = calculate_timing_tool(
        "pd",
        birth_year=1994,
        birth_month=1,
        birth_day=31,
        birth_hour=12,
        birth_timezone="Antarctica/Vostok",
        birth_longitude=107.6,
        birth_latitude=51.5,
        house_system="W",
        analysis_year=1994,
        analysis_month=11,
        analysis_day=1,
        analysis_hour=7,
        analysis_minute=0,
    )
    assert result["pd"]["exact_window"][0]["event_datetime"] == "1994-10-29T22:12:05Z"


def test_western_timing_supports_fixed_offset_timezones() -> None:
    result = calculate_western_timing_analysis(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="+00:00",
        birth_longitude=174.5,
        birth_latitude=-41.433333,
        analysis_year=2031,
        analysis_month=4,
        analysis_day=6,
        return_timezone="+08:00",
        return_longitude=121.4667,
        return_latitude=31.2167,
    )

    assert result["analysis_type"] == "西占推运与返照分析"
    assert result["returns"]["solar_return"]["return_datetime"].endswith("+08:00")
    assert result["returns"]["lunar_return"]["return_datetime"].endswith("+08:00")


def test_profection_age_handles_leap_day_birth_in_common_year(
    predictive_clock_operands,
) -> None:
    birth_info = build_predictive_birth_info(
        name="Leap Native",
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
    )
    tzinfo = parse_timezone_name("Asia/Shanghai")

    before_adjusted_birthday = datetime(2025, 2, 27, 10, 30, tzinfo=tzinfo)
    adjusted_birthday = datetime(2025, 2, 28, 10, 30, tzinfo=tzinfo)

    for moment, age in ((before_adjusted_birthday, 24), (adjusted_birthday, 25)):
        result = profections.build_annual_profection_payload(
            birth_info, predictive_clock_operands, analysis_datetime=moment
        )
        assert result["age_years"] == age


def test_western_timing_handles_leap_day_births_for_profection_and_given_year() -> None:
    result = calculate_western_timing_analysis(
        name="Leap Native",
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=2,
        analysis_day=28,
        return_timezone="Asia/Shanghai",
        return_longitude=121.4737,
        return_latitude=31.2304,
    )

    profection = result["time_lords"]["annual_profection"]
    assert profection["activated_house"] == 2

    given_year = result["directions"]["given_year"]
    assert given_year["year_start"].startswith("2025-02-28T10:30:00+08:00")
    assert given_year["year_end"].startswith("2026-02-28T10:30:00+08:00")
    assert len(given_year["monthly_profections"]) == 12
    assert given_year["monthly_profections"][0]["active"] is True


def test_western_timing_uses_previous_real_leap_birthday_before_adjusted_birthday() -> (
    None
):
    result = calculate_western_timing_analysis(
        name="Leap Native",
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=2,
        analysis_day=27,
        return_timezone="Asia/Shanghai",
        return_longitude=121.4737,
        return_latitude=31.2304,
    )

    given_year = result["directions"]["given_year"]
    assert given_year["year_start"].startswith("2024-02-29T10:30:00+08:00")
    assert given_year["year_end"].startswith("2025-02-28T10:30:00+08:00")


def test_primary_directions_support_converse_mode() -> None:
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="astroapp_alchabitius",
        pd_time_key="Naibod",
        pd_aspects=[0, 90, 180],
        pd_type=1,
        show_pd_bounds=True,
    )

    primary_directions = result["directions"]["primary_directions"]
    assert primary_directions["direction_mode"] == "converse"
    assert primary_directions["direction_mode_label"] == "逆推"
    assert primary_directions["current_arc_degrees"] == pytest.approx(
        -34.5072, abs=0.01
    )
    assert primary_directions["current_arc_absolute_degrees"] == pytest.approx(
        34.5072, abs=0.01
    )
    assert primary_directions["current_window"][0]["promissor"] == "Ascendant"
    assert primary_directions["current_window"][0]["significator"] == "Sun"
    assert primary_directions["current_window"][0]["aspect"] == "square"
    assert primary_directions["current_window"][0]["arc_degrees"] == pytest.approx(
        37.0687, abs=0.01
    )
    first_timeline = primary_directions["timeline"][0]
    natal_promissor_coordinate = primary_directions["coordinate_points"][
        first_timeline["promissor"]
    ]["coordinate_degrees"]
    assert first_timeline["coordinate_context"]["promissor_current"][
        "coordinate_degrees"
    ] == pytest.approx(
        (natal_promissor_coordinate - first_timeline["arc_degrees"]) % 360.0,
        abs=0.01,
    )
    assert first_timeline["arc_applied_degrees"] == pytest.approx(
        -first_timeline["arc_degrees"],
        abs=0.01,
    )
    assert first_timeline["timing_phase"] == "past"
    assert first_timeline["relative_years_from_current"] < 0
    assert first_timeline["coordinate_context"]["current_orb_degrees"] == pytest.approx(
        0.0,
        abs=0.01,
    )

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["direction_mode"] == "converse"
    assert primary_direction_chart["bounds_overlay"]["enabled"] is True
    assert (
        primary_direction_chart["bounds_overlay"]["points"]["Sun"]["bound_lord"]
        == "Mars"
    )
    assert primary_direction_chart["directed_points"]["Sun"]["sign"] == "Aries"
    sun_sign_change = next(
        item
        for item in primary_direction_chart["sign_changes"]
        if item["point"] == "Sun"
    )
    assert sun_sign_change["from_sign"] == "Taurus"
    assert sun_sign_change["to_sign"] == "Aries"


def test_primary_direction_chart_omits_bounds_overlay_when_disabled() -> None:
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="astroapp_alchabitius",
        pd_time_key="Naibod",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=False,
    )

    bounds_overlay = result["directions"]["primary_direction_chart"]["bounds_overlay"]

    assert bounds_overlay["system"] == "egyptian_bounds"
    assert bounds_overlay["enabled"] is False
    assert bounds_overlay["points"] == {}


def test_equatorial_primary_directions_use_right_ascension_arc() -> None:
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="equatorial",
        pd_time_key="Ptolemy",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    primary_directions = result["directions"]["primary_directions"]
    assert primary_directions["coordinate_system"] == "right_ascension"
    assert primary_directions["coordinate_label"] == "赤经"
    assert primary_directions["current_window"][0]["promissor"] == "Ascendant"
    assert primary_directions["current_window"][0]["significator"] == "Mercury"
    assert primary_directions["current_window"][0]["aspect"] == "opposition"
    assert primary_directions["current_window"][0]["arc_degrees"] == pytest.approx(
        33.5787, abs=0.01
    )

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["coordinate_system"] == "right_ascension"
    assert primary_direction_chart["coordinate_label"] == "赤经"

    expected_precision = (
        "equatorial_runtime_projection"
        if predictive_swe is not None
        else "ecliptic_runtime_reference_fallback"
    )
    expected_backend = (
        "swisseph_equatorial_projection"
        if predictive_swe is not None
        else "native_ecliptic_reference_fallback"
    )

    primary_directions = result["directions"]["primary_directions"]
    assert primary_directions["coordinate_precision"] == expected_precision
    assert primary_directions["coordinate_backend"] == expected_backend

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["coordinate_precision"] == expected_precision
    assert primary_direction_chart["coordinate_backend"] == expected_backend

    if predictive_swe is not None:
        asc_diagnostic = primary_directions["coordinate_diagnostics"]["Ascendant"]
        sun_diagnostic = primary_directions["coordinate_diagnostics"]["Sun"]

        assert asc_diagnostic["projection"] == "equatorial"
        assert asc_diagnostic["right_ascension"] == pytest.approx(
            primary_directions["coordinate_points"]["Ascendant"]["coordinate_degrees"],
            abs=0.01,
        )
        assert "declination" in sun_diagnostic
    else:
        pass


def test_equatorial_primary_direction_chart_reconstructs_ecliptic_positions_from_ra() -> (
    None
):
    if predictive_swe is None:
        pytest.skip("Swiss Ephemeris is required for equatorial reconstruction")
    else:
        pass

    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="equatorial",
        pd_time_key="Ptolemy",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    birth_info = build_predictive_birth_info(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
    )
    natal_subject = build_natal_subject(birth_info)
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    arc_degrees = result["directions"]["primary_direction_chart"]["current_arc_degrees"]

    sun_ra, sun_declination = point_equatorial_position(
        "Sun",
        natal_subject,
        context=equatorial_context,
    )
    expected_sun_longitude, _expected_sun_latitude, _ = predictive_swe.cotrans(
        (normalize_angle(sun_ra + arc_degrees), sun_declination, 1.0),
        equatorial_context.obliquity,
    )

    fortune_payload = build_lot_payloads(natal_subject)["lot_of_fortune"]
    fortune_ra, fortune_declination, _ = predictive_swe.cotrans(
        (float(fortune_payload["absolute_degree"]), 0.0, 1.0),
        -equatorial_context.obliquity,
    )
    expected_fortune_longitude, _expected_fortune_latitude, _ = predictive_swe.cotrans(
        (normalize_angle(fortune_ra + arc_degrees), fortune_declination, 1.0),
        equatorial_context.obliquity,
    )

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["directed_points"]["Sun"][
        "absolute_degree"
    ] == pytest.approx(
        normalize_angle(expected_sun_longitude),
        abs=0.01,
    )
    assert primary_direction_chart["directed_points"]["Sun"]["sign"] == "Gemini"
    assert primary_direction_chart["directed_lots"]["lot_of_fortune"][
        "absolute_degree"
    ] == pytest.approx(normalize_angle(expected_fortune_longitude), abs=0.01)
    sun_sign_change = next(
        item
        for item in primary_direction_chart["sign_changes"]
        if item["point"] == "Sun"
    )
    assert sun_sign_change["to_sign"] == "Gemini"


def test_mundane_semiarc_primary_direction_chart_reconstructs_projection_from_mundane_arc() -> (
    None
):
    if predictive_swe is None:
        pytest.skip("Swiss Ephemeris is required for mundane semiarc reconstruction")
    else:
        pass

    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="fatebridge_mundane_semiarc",
        pd_time_key="Ptolemy",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    birth_info = build_predictive_birth_info(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
    )
    natal_subject = build_natal_subject(birth_info)
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    arc_degrees = result["directions"]["primary_direction_chart"]["current_arc_degrees"]
    primary_directions = result["directions"]["primary_directions"]

    def inverse_mundane_hour_angle(
        coordinate_degrees: float, semiarc_degrees: float
    ) -> float:
        normalized_coordinate = normalize_angle(coordinate_degrees)
        clamped_semiarc = min(max(semiarc_degrees, 1e-6), 179.999999)
        nocturnal_semiarc = max(180.0 - clamped_semiarc, 1e-6)
        if normalized_coordinate <= 90.0:
            return ((normalized_coordinate / 90.0) * clamped_semiarc) - clamped_semiarc
        else:
            pass
        if normalized_coordinate <= 180.0:
            return ((normalized_coordinate - 90.0) / 90.0) * clamped_semiarc
        else:
            pass
        if normalized_coordinate <= 270.0:
            return clamped_semiarc + (
                ((normalized_coordinate - 180.0) / 90.0) * nocturnal_semiarc
            )
        else:
            pass
        return -180.0 + (((normalized_coordinate - 270.0) / 90.0) * nocturnal_semiarc)

    sun_ra, sun_declination = point_equatorial_position(
        "Sun",
        natal_subject,
        context=equatorial_context,
    )
    sun_semiarc = semiarc_degrees_for_declination(
        birth_info.latitude,
        sun_declination,
    )
    sun_target_coordinate = normalize_angle(
        primary_directions["coordinate_points"]["Sun"]["coordinate_degrees"]
        + arc_degrees
    )
    sun_hour_angle = inverse_mundane_hour_angle(sun_target_coordinate, sun_semiarc)
    directed_sun_ra = normalize_angle(equatorial_context.armc - sun_hour_angle)
    expected_sun_longitude, _expected_sun_latitude, _ = predictive_swe.cotrans(
        (directed_sun_ra, sun_declination, 1.0),
        equatorial_context.obliquity,
    )

    fortune_payload = build_lot_payloads(natal_subject)["lot_of_fortune"]
    fortune_ra, fortune_declination = project_absolute_degree_to_equatorial(
        float(fortune_payload["absolute_degree"]),
        obliquity=equatorial_context.obliquity,
    )
    fortune_semiarc = semiarc_degrees_for_declination(
        birth_info.latitude,
        fortune_declination,
    )
    fortune_target_coordinate = normalize_angle(
        primary_directions["coordinate_lots"]["lot_of_fortune"]["coordinate_degrees"]
        + arc_degrees
    )
    fortune_hour_angle = inverse_mundane_hour_angle(
        fortune_target_coordinate,
        fortune_semiarc,
    )
    directed_fortune_ra = normalize_angle(equatorial_context.armc - fortune_hour_angle)
    expected_fortune_longitude, _expected_fortune_latitude, _ = predictive_swe.cotrans(
        (directed_fortune_ra, fortune_declination, 1.0),
        equatorial_context.obliquity,
    )

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["directed_points"]["Sun"][
        "absolute_degree"
    ] == pytest.approx(
        normalize_angle(expected_sun_longitude),
        abs=0.01,
    )
    assert primary_direction_chart["directed_points"]["Sun"]["sign"] == "Aries"
    assert primary_direction_chart["directed_lots"]["lot_of_fortune"][
        "absolute_degree"
    ] == pytest.approx(normalize_angle(expected_fortune_longitude), abs=0.01)
    assert (
        primary_direction_chart["directed_lots"]["lot_of_fortune"]["sign"] == "Taurus"
    )


def test_fatebridge_mundane_semiarc_method_exposes_mundane_projection() -> None:
    baseline_result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="astroapp_alchabitius",
        pd_time_key="Ptolemy",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )
    result = calculate_western_timing_analysis(
        name="Alice",
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=20,
        pd_method="fatebridge_mundane_semiarc",
        pd_time_key="Ptolemy",
        pd_aspects=[0, 90, 180],
        show_pd_bounds=True,
    )

    primary_directions = result["directions"]["primary_directions"]
    assert primary_directions["coordinate_system"] == "mundane_semiarc"
    assert primary_directions["coordinate_label"] == "SemiArc"
    assert primary_directions["approximation"] == "mundane_semiarc_static_key"
    assert (
        primary_directions["current_window"][0]["coordinate_system"]
        == "mundane_semiarc"
    )
    first_timeline = primary_directions["timeline"][0]
    natal_promissor_coordinate = primary_directions["coordinate_points"][
        first_timeline["promissor"]
    ]["coordinate_degrees"]
    assert first_timeline["coordinate_context"]["promissor_current"][
        "coordinate_degrees"
    ] == pytest.approx(
        (natal_promissor_coordinate + first_timeline["arc_degrees"]) % 360.0,
        abs=0.01,
    )
    assert first_timeline["arc_applied_degrees"] == pytest.approx(
        first_timeline["arc_degrees"],
        abs=0.01,
    )
    assert first_timeline["timing_phase"] == "past"
    assert first_timeline["relative_years_from_current"] < 0
    assert first_timeline["coordinate_context"]["current_orb_degrees"] == pytest.approx(
        0.0,
        abs=0.01,
    )
    assert first_timeline["coordinate_context"]["promissor_current"]["quadrant"] in {
        "above_east",
        "above_west",
        "below_west",
        "below_east",
    }
    assert (
        primary_directions["current_window"][0]["arc_degrees"]
        != baseline_result["directions"]["primary_directions"]["current_window"][0][
            "arc_degrees"
        ]
    )

    primary_direction_chart = result["directions"]["primary_direction_chart"]
    assert primary_direction_chart["coordinate_system"] == "mundane_semiarc"
    assert primary_direction_chart["coordinate_label"] == "SemiArc"
    assert primary_direction_chart["approximation"] == "mundane_semiarc_static_key"
    assert primary_direction_chart["natal_coordinate_points"]["Ascendant"][
        "coordinate_degrees"
    ] == pytest.approx(0.0, abs=0.01)
    assert primary_direction_chart["directed_coordinate_points"]["Ascendant"][
        "coordinate_degrees"
    ] == pytest.approx(primary_direction_chart["current_arc_degrees"], abs=0.01)
    assert primary_direction_chart["directed_coordinate_points"]["Medium_Coeli"][
        "coordinate_degrees"
    ] == pytest.approx(
        (90.0 + primary_direction_chart["current_arc_degrees"]) % 360.0,
        abs=0.01,
    )
    assert (
        primary_direction_chart["directed_coordinate_points"]["Ascendant"]["quadrant"]
        == "above_east"
    )
    first_hit = primary_direction_chart["hits"][0]
    lot_key_by_point = {"Fortune": "lot_of_fortune", "Spirit": "lot_of_spirit"}
    significator_entry = primary_direction_chart["natal_coordinate_points"].get(
        first_hit["significator"]
    )
    if significator_entry is None:
        significator_entry = primary_direction_chart["natal_coordinate_lots"][
            lot_key_by_point[first_hit["significator"]]
        ]
    else:
        pass
    assert (
        first_hit["coordinate_context"]["promissor_current"]["coordinate_degrees"]
        == primary_direction_chart["directed_coordinate_points"][
            first_hit["promissor"]
        ]["coordinate_degrees"]
    )
    assert (
        first_hit["coordinate_context"]["significator_natal"]["coordinate_degrees"]
        == significator_entry["coordinate_degrees"]
    )
    assert first_hit["coordinate_context"]["aspect_target"][
        "coordinate_degrees"
    ] == pytest.approx(
        (significator_entry["coordinate_degrees"] + first_hit["aspect_variant_degrees"])
        % 360.0,
        abs=0.01,
    )
    assert first_hit["coordinate_context"]["current_orb_degrees"] >= 0
    assert (
        primary_direction_chart["coordinate_hits"][0]["coordinate_context"][
            "promissor_current"
        ]["coordinate_degrees"]
        == first_hit["coordinate_context"]["promissor_current"]["coordinate_degrees"]
    )
    assert primary_direction_chart["coordinate_diagnostics"]["Ascendant"][
        "mundane_position_degrees"
    ] == pytest.approx(0.0, abs=0.01)
    assert primary_direction_chart["coordinate_diagnostics"]["Medium_Coeli"][
        "mundane_position_degrees"
    ] == pytest.approx(90.0, abs=0.01)
    assert (
        primary_direction_chart["coordinate_diagnostics"]["Sun"]["semiarc_degrees"] > 0
    )
    assert primary_direction_chart["coordinate_diagnostics"]["Sun"]["quadrant"] in {
        "above_east",
        "above_west",
        "below_west",
        "below_east",
    }


def test_zodiacal_releasing_loosing_of_bond_jumps_after_full_cycle() -> None:
    start = utc_calendar(datetime(2000, 1, 1, tzinfo=timezone.utc))
    periods = build_releasing_level_within_interval(
        start_sign="Aquarius",
        period_start=start,
        period_end=start.shifted(timedelta(days=30 * 360)),
        fortune_sign="Aquarius",
        parent_sign="Aquarius",
        level=2,
        analysis_utc=start,
        max_periods=20,
    )

    signs = [period["sign"] for period in periods[:14]]
    loosing_flags = [period["loosing_of_bond"] for period in periods[:14]]

    assert signs[:12] == [
        "Aquarius",
        "Pisces",
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
    ]
    assert signs[12:14] == ["Leo", "Virgo"]
    assert loosing_flags[6] is False
    assert loosing_flags[12] is True


def test_zodiacal_releasing_shifts_spirit_when_lots_coincide() -> None:
    # Brennan/Schaim episode192: same-sign lots shift Spirit forward one sign;
    # Fortune remains the angular reference and natal lots are not relocated.
    from fatebridge.core.predictive._common import (
        build_lot_payloads,
        build_natal_subject,
    )
    from fatebridge.core.predictive.zodiacal_releasing import (
        build_zodiacal_releasing_payload,
    )

    birth_info = build_predictive_birth_info(
        birth_year=1995,
        birth_month=7,
        birth_day=27,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4,
        birth_latitude=39.9,
        name="A",
        birth_place="x",
    )
    subject = build_natal_subject(birth_info)
    lots = build_lot_payloads(subject)
    # Fixture precondition: this birth has both lots in the same sign.
    assert lots["lot_of_spirit"]["sign"] == lots["lot_of_fortune"]["sign"]

    payload = build_zodiacal_releasing_payload(
        birth_info,
        subject,
        analysis_datetime=datetime(
            2030, 1, 1, 12, tzinfo=parse_timezone_name("Asia/Shanghai")
        ),
    )
    # Independent Kerykeion6.0.5 natal factory confirms both natal lots in Libra.
    assert lots["lot_of_spirit"]["sign"] == "Libra"
    assert payload["spirit"]["lot"]["sign"] == "Libra"
    assert payload["spirit"]["release_start_sign"] == "Scorpio"
    assert payload["fortune"]["release_start_sign"] == "Libra"
    assert payload["spirit"]["angular_reference_sign"] == "Libra"
    assert payload["spirit"]["start_sign_adjusted"] is True
    assert payload["fortune"]["start_sign_adjusted"] is False
    # Brennan2019 handout: Gemini L3 is1 month20days=50days, Cancer62.5days.
    # duration_value names a full nominal sign period; a parent may clip its end.
    periods = {row["sign"]: row for row in payload["spirit"]["level_3_timeline"]}
    assert periods["Gemini"]["duration_value"] == 50
    assert periods["Cancer"]["duration_value"] == 62.5


def test_zodiacal_releasing_active_boundary_uses_elapsed_days_across_dst() -> None:
    from datetime import timezone

    from fatebridge.core.predictive._common import build_natal_subject
    from fatebridge.core.predictive.zodiacal_releasing import (
        build_zodiacal_releasing_payload,
    )

    birth = build_predictive_birth_info(
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_latitude=31.2304,
    )
    subject = build_natal_subject(birth)
    # Independent UTC arithmetic: birth06:30UTC +20x360 days = this boundary.
    # Natal China DST is +09:00; the boundary is +08:00, hence14:30 civil.
    boundary = datetime(2010, 2, 1, 6, 30, tzinfo=timezone.utc)
    for moment, expected_sign in [
        (boundary - timedelta(microseconds=1), "Gemini"),
        (boundary, "Cancer"),
    ]:
        track = build_zodiacal_releasing_payload(
            birth, subject, analysis_datetime=moment
        )["fortune"]
        assert track["level_1_timeline"][0]["end"] == "2010-02-01T14:30:00+08:00"
        assert track["current_level_1"]["sign"] == expected_sign
        for level in (1, 2, 3):
            current = track[f"current_level_{level}"]
            assert datetime.fromisoformat(current["start"]) <= moment
            assert moment < datetime.fromisoformat(current["end"])


def test_zodiacal_releasing_rejects_a_period_end_outside_the_birth_zone_calendar(
    predictive_clock_operands,
) -> None:
    from fatebridge.core.predictive.zodiacal_releasing import (
        build_zodiacal_releasing_payload,
    )

    zone_name = "Etc/GMT+5"
    birth = build_predictive_birth_info(
        birth_year=9995,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_timezone=zone_name,
        birth_longitude=-75,
        birth_latitude=40,
    )
    target = datetime(9995, 1, 1, tzinfo=parse_timezone_name(zone_name))
    with pytest.raises(ValueError, match="Civil calendar label is outside"):
        build_zodiacal_releasing_payload(
            birth, predictive_clock_operands, analysis_datetime=target
        )
