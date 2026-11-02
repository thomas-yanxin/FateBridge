"""Independent mathematical and NASA references, rather than golden outputs.

Reference arithmetic uses exact rational angles and elapsed microseconds; it
does not import the production rules/constants to construct expected answers.
PVR source: chapters 2/3/6/10/16, examples 16/17/34/50 and table 38.
"""

import hashlib
import json
import math
import random
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from threading import local

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import (
    divisional_chart,
    nakshatra,
    positions,
    varga_longitude,
    vimshottari,
)

UTC = timezone.utc
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/jyotish-horizons.json").read_text()
)
# Transcribed from PVR table 38, starting at Ashwini's lord.
PERIODS = [
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
]
BASES = ["sidereal_365_25636", "tropical_365_2425", "savana_360"]
DAYS = [Fraction("365.25636"), Fraction("365.2425"), Fraction(360)]


def probe_angles(division):
    # Every cusp and its two immediately adjacent representable doubles,
    # plus 2,000 reproducible random points, including wrapped longitudes.
    values = []
    for number in range(12 * division + 1):
        cusp = float(Fraction(30 * number, division))
        values.extend(
            [math.nextafter(cusp, -math.inf), cusp, math.nextafter(cusp, math.inf)]
        )
    rng = random.Random(872301)
    values.extend(rng.uniform(-720, 720) for _ in range(2000))
    return values


def test_all_mansion_and_pada_cusps_against_exact_rational_partition():
    # Independent interval search, including the 108 pada boundaries.
    edges = [Fraction(10 * n, 3) for n in range(109)]
    for value in probe_angles(9):
        angle = Fraction(value) % 360
        pada = bisect_right(edges, angle) - 1
        star = pada // 4
        actual = nakshatra(value)
        assert (actual["index"], actual["pada"], actual["lord"]) == (
            star + 1,
            pada % 4 + 1,
            PERIODS[star % 9][0],
        ), value
        expected = (angle - edges[star * 4]) / Fraction(40, 3)
        assert actual["fraction_elapsed"] == pytest.approx(
            float(expected), abs=2e-16, rel=0
        )
        assert 0 <= actual["fraction_elapsed"] < 1


@pytest.mark.parametrize("division", [1, 9, 10])
def test_all_varga_segments_against_rational_reference(division):
    for value in probe_angles(division):
        angle = Fraction(value) % 360
        if division in (1, 9):
            # D9 has the equivalent absolute-angle mapping 9*longitude mod 360.
            expected = (angle * division) % 360
        else:
            sign = bisect_right([30 * n for n in range(13)], angle) - 1
            # PVR 6.2.10: tabulated first sign for each of the twelve rasis.
            starts = [0, 9, 2, 11, 4, 1, 6, 3, 8, 5, 10, 7]
            within = (angle - sign * 30) * 10
            part = int(within / 30)
            expected = ((starts[sign] + part) % 12) * 30 + within % 30
        actual = varga_longitude(value, division)
        assert 0 <= actual < 360
        assert int(actual // 30) == int(expected / 30), (value, actual, expected)
        assert actual == pytest.approx(float(expected), abs=6e-14, rel=0)


def reference_periods(birth, moon, days, cycle=0):
    angle = Fraction(moon) % 360
    star = int(angle / Fraction(40, 3))
    fraction = (angle - star * Fraction(40, 3)) / Fraction(40, 3)
    first = star % 9
    year_us = days * 86_400_000_000
    origin = birth - timedelta(
        microseconds=round(fraction * PERIODS[first][1] * year_us)
    )
    origin += timedelta(microseconds=round(cycle * 120 * year_us))
    elapsed = 0
    expected = []
    for i in range(9):
        lord, length = PERIODS[(first + i) % 9]
        start = origin + timedelta(microseconds=round(elapsed * year_us))
        end = origin + timedelta(microseconds=round((elapsed + length) * year_us))
        elapsed_sub = 0
        subs = []
        for j in range(9):
            sublord, subyears = PERIODS[(first + i + j) % 9]
            substart = start + timedelta(
                microseconds=round(length * elapsed_sub * year_us / 120)
            )
            elapsed_sub += subyears
            subend = start + timedelta(
                microseconds=round(length * elapsed_sub * year_us / 120)
            )
            subs.append((sublord, substart, subend))
        expected.append((lord, start, end, subs))
        elapsed += length
    return expected


@pytest.mark.parametrize("basis,days", list(zip(BASES, DAYS)))
def test_dasha_dates_against_source_formula_with_exact_microseconds(basis, days):
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    rng = random.Random(581043)
    for moon in [
        0,
        5,
        40,
        120,
        302 + 23 / 60,
        *[rng.random() * 360 for _ in range(40)],
    ]:
        result = vimshottari(birth, moon, birth, year_basis=basis)
        for actual, (lord, start, end, subs) in zip(
            result["timeline"], reference_periods(birth, moon, days)
        ):
            assert actual["lord"] == lord
            assert abs(datetime.fromisoformat(actual["start"]) - start) <= timedelta(
                microseconds=2
            )
            assert abs(datetime.fromisoformat(actual["end"]) - end) <= timedelta(
                microseconds=2
            )
            for sub, (name, left, right) in zip(actual["antardashas"], subs):
                assert sub["lord"] == name
                assert abs(datetime.fromisoformat(sub["start"]) - left) <= timedelta(
                    microseconds=2
                )
                assert abs(datetime.fromisoformat(sub["end"]) - right) <= timedelta(
                    microseconds=2
                )


@pytest.mark.parametrize("basis,days", list(zip(BASES, DAYS)))
def test_distant_cycle_and_every_subperiod_boundary_from_independent_formula(
    basis, days
):
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    # 5 degrees yields the exactly representable 3/8 mansion fraction.
    for cycle in [0, 1, 2, 10, 50]:
        expected = reference_periods(birth, 5, days, cycle)
        for lord, _, _, subs in expected:
            for sublord, start, _ in subs:
                if start < birth:
                    continue
                at = vimshottari(birth, 5, start, year_basis=basis)
                before = vimshottari(
                    birth, 5, start - timedelta(microseconds=1), year_basis=basis
                )
                assert (at["current_major"]["lord"], at["current_sub"]["lord"]) == (
                    lord,
                    sublord,
                )
                assert at["timeline_scope"]["cycle_index"] == cycle
                assert (
                    before["current_major"]["lord"],
                    before["current_sub"]["lord"],
                ) != (lord, sublord)


def test_pvr_example_34_aspects_with_nonzero_origin():
    # Example 34 explicitly gives Jupiter Gemini -> Libra/Sagittarius/Aquarius;
    # Mars Leo -> Scorpio/Aquarius/Pisces; Saturn Sagittarius -> Aquarius/Gemini/Virgo.
    planets = dict(
        Sun=0,
        Moon=0,
        Mercury=0,
        Venus=0,
        Jupiter=60,
        Mars=120,
        Saturn=240,
        Rahu=0,
        Ketu=180,
    )
    chart = divisional_chart({"ascendant": 0, "longitudes": planets}, 1)
    for planet, expected in {
        "Jupiter": {7, 9, 11},
        "Mars": {8, 11, 12},
        "Saturn": {11, 3, 6},
    }.items():
        assert {
            a["target_house"]
            for a in chart["graha_aspects"]
            if a["from_planet"] == planet
        } == expected


@pytest.mark.parametrize("reference", FIXTURE["references"], ids=lambda r: r["body"])
def test_physical_positions_against_frozen_nasa_jpl_horizons(
    reference, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    assert (
        hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
        == reference["response_sha256"]
    )
    assert "GEOCENTRIC" in reference["response"]["result"]
    for row in reference["rows"]:
        instant = datetime.fromisoformat(row["utc"])
        birth = build_astro_birth_info(
            birth_year=instant.year,
            birth_month=instant.month,
            birth_day=instant.day,
            birth_hour=instant.hour,
            birth_minute=instant.minute,
            birth_longitude=0,
            birth_latitude=0,
            birth_timezone="UTC",
        )
        actual = positions(birth)
        assert actual["ephemeris_models"] == ["moshier"]
        # Undo only the declared Lahiri offset for comparison with NASA's
        # apparent tropical ecliptic-of-date quantity 31. NASA does not define Lahiri.
        tropical = (actual["longitudes"][reference["body"]] + actual["ayanamsha"]) % 360
        error = (tropical - row["apparent_ecliptic_longitude"] + 180) % 360 - 180
        assert abs(error) * 3600 < FIXTURE["tolerance_arcseconds"]


def test_utc_conversion_does_not_treat_modern_utc_as_ut1():
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=18,
        birth_minute=15,
        birth_longitude=0,
        birth_latitude=0,
        birth_timezone="UTC",
    )
    raw = positions(birth)
    # TT-UTC = 32 TAI leap seconds + 32.184 s on this date (IERS table).
    utc_jd = 2451604.2604166665
    assert (raw["julian_day_tt"] - utc_jd) * 86400 == pytest.approx(64.184, abs=0.00005)
    # NASA measured DUT1 is 0.30387s; Swiss uses its Delta-T model. Allow 0.05s
    # for the model difference, but the former implicit zero is outside this bound.
    assert (raw["julian_day_ut"] - utc_jd) * 86400 == pytest.approx(0.30387, abs=0.05)


def test_ascendant_against_independent_horizon_intersection_geometry():
    # Ecliptic/horizon intersection, not another call to a house routine.
    # Sidereal time, obliquity and Lahiri still come from Swiss; this verifies
    # geometry/wiring, not independent Earth-orientation astronomy.
    rng = random.Random(419032)
    for _ in range(50):
        birth = build_astro_birth_info(
            birth_year=rng.randrange(1980, 2020),
            birth_month=rng.randrange(1, 13),
            birth_day=rng.randrange(1, 29),
            birth_hour=rng.randrange(24),
            birth_latitude=rng.uniform(-65, 65),
            birth_longitude=rng.uniform(-180, 180),
            birth_timezone="UTC",
        )
        actual = positions(birth)
        with runtime.preserve_ephemeris_path():
            theta = math.radians(
                runtime.swe.sidtime(actual["julian_day_ut"]) * 15 + birth.longitude
            )
            epsilon = math.radians(
                runtime.swe.calc(actual["julian_day_tt"], runtime.swe.ECL_NUT)[0][0]
            )
        ascendant = (
            math.degrees(
                math.atan2(
                    -math.cos(theta),
                    math.sin(theta) * math.cos(epsilon)
                    + math.tan(math.radians(birth.latitude)) * math.sin(epsilon),
                )
            )
            + 180
        )
        expected = (ascendant - actual["ayanamsha"]) % 360
        error = (actual["ascendant"] - expected + 180) % 360 - 180
        assert abs(error) < 1e-9


@pytest.mark.native_engine_fault
def test_each_worker_applies_configured_ephemeris_path_before_delta_t_conversion(
    monkeypatch, tmp_path
):
    thread_state = local()
    expected_path = str(tmp_path)
    real_set_path = runtime.swe.set_ephe_path
    real_delta_t = runtime.swe.deltat_ex
    converted = []

    def set_path(path):
        thread_state.path = path
        return real_set_path(path)

    def convert_clock(*args):
        assert getattr(thread_state, "path", None) == expected_path
        converted.append(True)
        return real_delta_t(*args)

    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=18,
        birth_minute=15,
        birth_longitude=0,
        birth_latitude=0,
        birth_timezone="UTC",
    )
    try:
        with monkeypatch.context() as patch:
            patch.setenv("SE_EPHE_PATH", expected_path)
            patch.setattr(runtime.swe, "set_ephe_path", set_path)
            patch.setattr(runtime.swe, "deltat_ex", convert_clock)
            with ThreadPoolExecutor(max_workers=3) as pool:
                assert len(list(pool.map(lambda _: positions(birth), range(6)))) == 6
            assert len(converted) >= 24
    finally:
        # Restore after the patched configuration has gone out of scope. Do
        # not hold the shared lock while waiting for worker futures.
        with runtime.preserve_ephemeris_path():
            pass
