"""Independent lunation times and temporal-hour boundary counterexamples."""

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import classical
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.time_scales import (
    datetime_from_ut1,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.classical_western import planetary_hour_sequence
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.utils.civil_time import ZonedCalendar

FIXTURES = Path(__file__).parents[1] / "fixtures"
LUNATIONS = json.loads((FIXTURES / "western-usno-lunations-2026.json").read_text())
SEQUENCE = json.loads(
    (FIXTURES / "western-planetary-hour-sequence-dio-1914.json").read_text()
)
pytestmark = pytest.mark.skipif(swe is None, reason="Swiss Ephemeris unavailable")


@pytest.fixture(autouse=True)
def empty_ephemeris_directory(tmp_path):
    previous = configured_ephemeris_path()
    configure_ephemeris_path(str(tmp_path))
    yield
    configure_ephemeris_path(previous)


@pytest.mark.parametrize("case", LUNATIONS["cases"])
def test_all_2026_new_and_full_moons_against_independent_usno_times(case) -> None:
    # USNO publishes UT1, not TT or civil UTC. The tzinfo here is a Gregorian
    # calendar-to-JD container; its components are explicitly nominal UT1.
    reference = datetime.fromisoformat(case["nominal_ut1"]).replace(tzinfo=timezone.utc)
    expected_ut1 = _julian_day(reference)
    result = classical._prenatal_syzygy(expected_ut1 + 0.5)
    assert result is not None
    assert result["type"] == case["type"]
    assert (
        abs(result["julian_day_ut1"] - expected_ut1) * 86400
        <= LUNATIONS["tolerance_seconds"]
    )
    assert result["solver"]["strictly_before_birth"] is True
    assert 0 <= result["solver"]["residual_degrees"] < 1e-6


@pytest.mark.parametrize("case", LUNATIONS["cases"])
def test_prenatal_selection_changes_only_after_representable_lunation(case) -> None:
    expected_ut1 = _julian_day(
        datetime.fromisoformat(case["nominal_ut1"]).replace(tzinfo=timezone.utc)
    )
    event = classical._prenatal_syzygy(expected_ut1 + 0.5)
    event_tt = event["julian_day_tt"]
    for at in (math.nextafter(event_tt, -math.inf), event_tt):
        previous = classical._prenatal_syzygy(ut1_from_tt(at), julian_day_tt=at)
        assert previous["type"] != event["type"]
        assert previous["julian_day_tt"] < at
        assert 10 < event_tt - previous["julian_day_tt"] < 18
    at = math.nextafter(event_tt, math.inf)
    after = classical._prenatal_syzygy(ut1_from_tt(at), julian_day_tt=at)
    assert after["julian_day_tt"] == event_tt


def test_prenatal_opposition_tie_uses_exact_source_longitude_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.tt_epoch import TTInstant

    origin = Fraction(2461045.125)
    birth = TTInstant(origin + Fraction(math.ulp(float(origin))) / 4)
    original = runtime.ephemeris_call

    def native(operation, *args, **kwargs):
        if operation != "calc":
            return original(operation, *args, **kwargs)
        else:
            pass
        at, body, flags = args
        assert flags == swe.FLG_SWIEPH | swe.FLG_SPEED
        if body == swe.MOON:
            longitude = float((180 + 12 * (Fraction(at) - origin)) % 360)
            speed = 12.0
        else:
            assert body == swe.SUN
            longitude, speed = 2.0**-47, 0.0
        return (longitude, 0.0, 1.0, speed, 0.0, 0.0), swe.FLG_MOSEPH | swe.FLG_SPEED

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    result = classical._prenatal_syzygy(2461044.875, julian_day_tt=birth)
    assert result is not None
    assert result["type"] == "new"
    assert result["julian_day_tt"] == math.nextafter(float(origin - 15), math.inf)
    assert result["solver"]["strictly_before_birth"] is True


def test_sidereal_syzygy_keeps_event_and_uses_event_epoch_native_lahiri() -> None:
    times = ephemeris_time(datetime(2026, 1, 30, tzinfo=timezone.utc))
    tropical = classical._prenatal_syzygy(times.jd_ut1, julian_day_tt=times.jd_tt)
    sidereal = classical._prenatal_syzygy(
        times.jd_ut1, julian_day_tt=times.jd_tt, sidereal=True
    )
    assert sidereal["julian_day_tt"] == tropical["julian_day_tt"]
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    coordinates, _ = swe.calc(
        sidereal["julian_day_tt"], swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )
    assert sidereal["longitude"] == coordinates[0]
    assert sidereal["tropical_longitude"] == tropical["longitude"]
    assert 23 < tropical["longitude"] - sidereal["longitude"] < 26
    info = build_astro_birth_info(
        birth_year=2026,
        birth_month=1,
        birth_day=30,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
    )
    chart = build_core_chart_payload(info, "chart", zodiacal=1)
    assert chart["classical"]["syzygy"]["zodiac"] == "sidereal_lahiri"


def test_full_moon_figuris_point_is_not_labeled_as_new_moon() -> None:
    from fatebridge.services.astrology_classical_snapshot import (
        _build_almuten_figuris_line,
    )

    info = build_astro_birth_info(
        birth_year=2026,
        birth_month=1,
        birth_day=4,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
    )
    chart = build_core_chart_payload(info, "chart")
    assert chart["classical"]["syzygy"]["type"] == "full"
    text = _build_almuten_figuris_line(chart)
    assert "朔望：满月" in text and "朔望→" in text
    assert "朔→" not in text


@pytest.mark.parametrize(
    "date,ruler",
    [
        ("2026-04-15", "Mercury"),
        ("2026-06-01", "Moon"),
        ("2026-09-01", "Mars"),
        ("2026-12-01", "Mars"),
    ],
)
def test_real_sunrise_one_second_later_is_first_hour_of_current_day(
    date: str, ruler: str
) -> None:
    jd = ephemeris_time(
        datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    ).jd_ut1
    from fatebridge.core.astro.solar_events import next_solar_event

    rise = next_solar_event(
        jd,
        longitude=0,
        latitude=51.5,
        rising=True,
        definition="apparent_topocentric_center",
    ).julian_day_ut1
    result = classical._planetary_hours(rise + 1 / 86400, 0, 51.5, "UTC")
    assert result["hour_number"] == 1
    assert result["is_day"] is True
    assert result["day_ruler"] == result["hour_ruler"] == ruler
    before = classical._planetary_hours(rise - 1 / 86400, 0, 51.5, "UTC")
    assert before["is_day"] is False
    assert before["hour_number"] == 12
    assert before["day_ruler"] != ruler


@pytest.mark.parametrize("ruler,next_day", SEQUENCE["weekday_successors"].items())
def test_hour_cycle_matches_bounded_dio_primary_text(ruler, next_day) -> None:
    start = SEQUENCE["order"].index(ruler)
    expected = [SEQUENCE["order"][(start + hour) % 7] for hour in range(24)]
    assert planetary_hour_sequence(ruler) == expected
    assert SEQUENCE["order"][(start + 24) % 7] == next_day


@pytest.mark.parametrize("is_day", [True, False])
@pytest.mark.parametrize("hour", range(1, 12))
def test_unequal_hour_internal_boundaries_are_half_open(
    monkeypatch: pytest.MonkeyPatch, is_day: bool, hour
) -> None:
    dawn = _julian_day(datetime(2026, 4, 15, 6, tzinfo=timezone.utc))
    # Synthetic consecutive events isolate the definition of a temporal hour
    # from the physical solar root solver, including one floating-point step.
    dusk = dawn + 0.6
    from tests.support.solar_events import fixed_crossings

    rises = (dawn, dawn + 1)
    sets = (dawn - 0.4, dusk, dusk + 1)
    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings(rises, sets),
    )
    start, end = (dawn, dusk) if is_day else (dusk, dawn + 1)
    boundary = Fraction(start) + (Fraction(end) - Fraction(start)) * hour / 12
    projected = float(boundary)
    strict_lower = (
        projected
        if Fraction(projected) < boundary
        else math.nextafter(projected, -math.inf)
    )
    at_or_after = (
        projected
        if Fraction(projected) >= boundary
        else math.nextafter(projected, math.inf)
    )
    assert Fraction(strict_lower) < boundary <= Fraction(at_or_after)
    before = classical._planetary_hours(strict_lower, 0, 51.5, "UTC")
    current = classical._planetary_hours(at_or_after, 0, 51.5, "UTC")
    after = classical._planetary_hours(
        math.nextafter(at_or_after, math.inf), 0, 51.5, "UTC"
    )
    assert before["hour_number"] == hour
    assert current["hour_number"] == after["hour_number"] == hour + 1
    assert before["is_day"] is current["is_day"] is after["is_day"] is is_day


def test_planetary_hour_boundary_during_inserted_utc_second() -> None:
    from fatebridge.core.astro.iers_ut1 import use_ut1_source

    # Original CALCEPH DE440 + SOFA + IERS C04 at 0°, 0.85986328125° E.
    # The sixth night boundary is in 2016-12-31 23:59:60, with the
    # reference fraction in [0.528926821, 0.528980466] seconds.
    clocks = (
        datetime(2016, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2017, 1, 1, tzinfo=timezone.utc),
    )
    with use_ut1_source("iers_c04"):
        earlier, later = (
            classical._planetary_hours(
                ephemeris_time(moment).ut1, 0.85986328125, 0, "UTC"
            )
            for moment in clocks
        )

    assert earlier is not None and later is not None
    assert (earlier["hour_number"], later["hour_number"]) == (6, 7)
    assert (earlier["hour_ruler"], later["hour_ruler"]) == ("Sun", "Venus")
    assert earlier["day_ruler"] == later["day_ruler"] == "Saturn"
    assert earlier["is_day"] is later["is_day"] is False
    assert (earlier["arc_start_jd_ut1"], earlier["arc_end_jd_ut1"]) == (
        later["arc_start_jd_ut1"],
        later["arc_end_jd_ut1"],
    )
    boundary = earlier["hour_end_utc"]
    assert boundary == later["hour_start_utc"]
    assert boundary.startswith("2016-12-31T23:59:60.")
    assert boundary.endswith("+00:00")
    fractional = Fraction(int(boundary[20:26]), 1_000_000)
    assert Fraction("0.527926821") <= fractional <= Fraction("0.529980466")


def test_planetary_hour_retains_an_opening_sunrise_in_utc_year_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.support.solar_events import fixed_crossings

    # Fixed modeled UT1 crossings spanning Gregorian years 0 and 1.
    query = 1721425.5
    rise, setting, next_rise = query - 0.75, query - 0.25, query + 0.25
    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((rise, next_rise), (setting,)),
    )
    result = classical._planetary_hours(query, 0, 40, "UTC")
    assert result is not None
    assert result["is_day"] is False
    assert result["day_ruler"] == "Sun"
    assert result["hour_number"] == 7
    assert result["hour_ruler"] == "Saturn"
    assert result["planetary_day_start_utc"].startswith("0000-12-31T")
    for field, expected in (
        ("planetary_day_start_utc", rise),
        ("arc_start_utc", setting),
        ("hour_start_utc", query),
    ):
        label = result[field]
        assert label.endswith("+00:00")
        encoded = ZonedCalendar.from_isoformat(label).utc.julian_day_exact()
        assert abs(encoded - Fraction(expected)) * 86400 <= Fraction(1, 10000)


def test_planetary_day_weekday_uses_civil_utc_not_ut1_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # At this future epoch the declared Delta T model places UT1 on Sunday
    # while the frozen civil UTC policy places this sunrise on Monday.
    dawn_utc = datetime(2099, 1, 5, 0, 0, 5, tzinfo=timezone.utc)
    dawn = ephemeris_time(dawn_utc).jd_ut1
    # Author Swiss Ephemeris 2.10.03 Delta T with the empty file path,
    # projected back to UTC under the frozen 37-second TAI−UTC offset.
    assert dawn == float.fromhex("0x1.2face3ff8f7a9p+21")
    assert datetime_from_ut1(dawn).weekday() == 0
    assert swe.revjul(dawn)[2] == 4
    from tests.support.solar_events import fixed_crossings

    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((dawn, dawn + 1), (dawn - 0.5, dawn + 0.5)),
    )
    result = classical._planetary_hours(dawn + 1 / 86400, 0, 0, "UTC")
    assert result["day_ruler"] == "Moon"
    assert result["planetary_day_start_utc"] == "2099-01-05T00:00:04.999987+00:00"


@pytest.mark.parametrize(
    "date", ["1900-01-01", "1961-06-01", "1972-01-02", "2017-01-02", "2099-01-05"]
)
def test_ut1_tt_civil_round_trip_preserves_time_policy(date: str) -> None:
    civil = datetime.fromisoformat(date).replace(tzinfo=timezone.utc) + timedelta(
        hours=12
    )
    times = ephemeris_time(civil)
    assert abs(tt_from_ut1(times.jd_ut1) - times.jd_tt) * 86400 < 0.0001
    assert ut1_from_tt(times.jd_tt) == times.jd_ut1
    assert abs((datetime_from_ut1(times.jd_ut1) - civil).total_seconds()) < 0.0001


@pytest.mark.local_data
@pytest.mark.parametrize(
    "civil,root_hex,strict_after",
    [
        ("2000-01-06T18:13:38.112763+00:00", "0x1.2b42f214e9e85p+21", False),
        ("2000-01-06T18:13:38.112764+00:00", "0x1.2b42f214e9e85p+21", True),
        ("2000-01-21T04:40:26.317746+00:00", "0x1.2b4365905e112p+21", False),
        ("2000-01-21T04:40:26.317747+00:00", "0x1.2b4365905e112p+21", True),
    ],
)
def test_prenatal_receipt_keeps_actual_civil_microseconds(
    monkeypatch: pytest.MonkeyPatch, civil: str, root_hex: str, strict_after: bool
) -> None:
    # These original author-C source encodings also anchor the R36 pre-repair
    # observations. They qualify a source-point relation, not physical accuracy
    # or public acceptance of microsecond western birth inputs.
    reference = json.loads(
        (
            Path(__file__).parents[1]
            / "data/progressed_lunation_v1/expected-roots.json"
        ).read_text()
    )
    anchor = next(
        row
        for row in reference["roots"]["author_C"]
        if row["selected_tt_hex"] == root_hex
    )
    ephe = Path(__file__).resolve().parents[2] / "ephe"
    for asset in reference["source_provenance"]["source_assets"]:
        if asset["filename"] in {"sepl_18.se1", "semo_18.se1"}:
            assert hashlib.sha256(
                (ephe / asset["filename"]).read_bytes()
            ).hexdigest() == (asset["sha256"])
        else:
            pass
    moment = datetime.fromisoformat(civil)
    # Restore the environment before the native path; the module's other
    # tests deliberately use an empty directory and Moshier.
    with preserve_ephemeris_path(), monkeypatch.context() as source:
        source.setenv("SE_EPHE_PATH", str(ephe))
        source.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        info = build_astro_birth_info(
            birth_year=moment.year,
            birth_month=moment.month,
            birth_day=moment.day,
            birth_hour=moment.hour,
            birth_minute=moment.minute,
            birth_second=moment.second,
            birth_microsecond=moment.microsecond,
            birth_timezone="UTC",
            birth_longitude=0.0,
            birth_latitude=0.0,
            use_true_solar_time=False,
            preserve_instant=True,
            require_resolved_timezone=True,
        )
        times = info.time_scales
        result = classical._prenatal_syzygy(times.jd_ut1, julian_day_tt=times.tt)
    root = float.fromhex(root_hex)
    assert times.jd_tt == root
    assert (Fraction(root) < times.tt.days) is strict_after
    assert result is not None
    assert result["ephemeris_source"]["models_by_body"] == {
        "Sun": ["swieph"],
        "Moon": ["swieph"],
    }
    assert Fraction(result["julian_day_tt"]) < times.tt.days
    assert result["solver"]["strictly_before_birth"] is True
    if strict_after:
        assert result["julian_day_tt"] == root
        assert result["type"] == ("new" if anchor["target"] == 0 else "full")
    else:
        assert result["julian_day_tt"] < root
        assert result["type"] == ("full" if anchor["target"] == 0 else "new")
