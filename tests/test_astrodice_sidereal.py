"""Native Lahiri geometry at the declared clock, with unchanged tight tolerances.

ERFA rotation/axis accuracy is checked independently in test_astrodice_rotation.
Raw houses_ex uses Swiss's default long-term clock after 2050; it is not a
same-model oracle for the managed standard clock. Use public houses_armc to
isolate the native house/Lahiri contract from that clock choice.
"""

from datetime import datetime
from itertools import product

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _ayanamsha
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.utils.errors import EphemerisSourceError

swe = pytest.importorskip("swisseph")
FACES = {"planet": "Moon", "sign": "Cancer", "house": 0}
DATES = ["1900-01-01", "2000-01-01", "2024-03-20", "2050-12-21"]
# Public 0..8 mapping, declared separately from production profile resolution.
HOUSE_CODES = [b"W", b"B", b"R", b"P", b"K", b"V", b"T", b"S", b"D"]
BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "North Node": swe.MEAN_NODE,
}


def angular_error(a, b):
    return abs((a - b + 180) % 360 - 180)


def native_lahiri_geometry_at_managed_clock(jd_ut1, latitude, longitude, code):
    # The clock has a separate frozen ERFA oracle. Neither the returned chart
    # angles nor its house cusps supply any expected value to this check.
    armc = (ephemeris_runtime.ephemeris_call("sidtime", jd_ut1) * 15 + longitude) % 360
    house_tt = jd_ut1 + swe.deltat_ex(jd_ut1, 0)
    epsilon = swe.calc(house_tt, swe.ECL_NUT, 0)[0][0]
    cusps, angles = swe.houses_armc(armc, latitude, epsilon, code)
    offset = swe.get_ayanamsa_ex(house_tt, 0)[1]
    zodiac_angles = [(value - offset) % 360 for value in angles[:2]]
    # Whole-sign cusps belong to the resulting sidereal signs. Rotating a
    # previously quantized tropical 0/30/... cusp is a different operation.
    zodiac_cusps = (
        [((zodiac_angles[0] // 30) * 30 + i * 30) % 360 for i in range(12)]
        if code == b"W"
        else [(value - offset) % 360 for value in cusps]
    )
    return zodiac_cusps, zodiac_angles


@pytest.mark.parametrize(
    "date,hsys,location,file_free",
    list(product(DATES, range(9), [(51.5, 0), (-33.5, 151.2)], [False, True])),
)
def test_context_matches_native_lahiri_positions_angles_and_cusps(
    date, hsys, location, file_free, monkeypatch, tmp_path
):
    if file_free:
        monkeypatch.setattr(ephemeris_runtime, "_configured_path", str(tmp_path))
    with ephemeris_runtime.preserve_ephemeris_path():
        # A previous client may have left Fagan/Bradley in this worker.
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY, 0, 0)
        result = build_otherbu_result(
            **FACES,
            date=date,
            time="12:00",
            zone="UTC",
            gps_lat=location[0],
            gps_lon=location[1],
            zodiacal=1,
            hsys=hsys,
        )
        times = ephemeris_time(datetime.fromisoformat(date + "T12:00:00+00:00"))
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        expected = {
            name: swe.calc(
                times.jd_tt, code, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
            )[0][0]
            for name, code in BODIES.items()
        }
        cusps, angles = native_lahiri_geometry_at_managed_clock(
            times.jd_ut1, location[0], location[1], HOUSE_CODES[hsys]
        )
        nutation = swe.calc(times.jd_tt, swe.ECL_NUT, swe.FLG_SWIEPH)[0][2]
    chart = result["chart"]["chart"]
    points = {p["id"]: p for p in chart["objects"]}
    for name, longitude in expected.items():
        assert angular_error(points[name]["lon"], longitude) < 1e-9
    assert angular_error(chart["angles"]["ascendant"], angles[0]) < 1e-9
    assert angular_error(chart["angles"]["midheaven"], angles[1]) < 1e-9
    for actual, expected_cusp in zip(chart["houses"], cusps):
        assert angular_error(actual["lon"], expected_cusp) < 1e-9
    profile = result["chart"]["params"]["chart_profile"]
    assert profile["sidereal_position_method"] == "swisseph_calc_sidereal_lahiri"
    assert profile["sidereal_house_method"] == "swisseph_houses_ex_sidereal_lahiri"
    assert profile["ayanamsha_includes_nutation"] is True
    assert profile["ayanamsha"] - profile["ayanamsha_mean"] == pytest.approx(
        nutation, abs=1e-10
    )
    assert result["symbolic_details"]["triplicity_condition"]["sect"] is None


def test_corrected_legacy_offset_removes_the_reproduced_nutation_error():
    times = ephemeris_time(datetime.fromisoformat("1900-01-01T12:00:00+00:00"))
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        tropical = swe.calc(times.jd_tt, swe.MOON, swe.FLG_SWIEPH)[0][0]
        sidereal = swe.calc(times.jd_tt, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[
            0
        ][0]
        mean_offset = swe.get_ayanamsa_ut(times.jd_ut1)
        offset = _ayanamsha(times.jd_ut1)
    assert angular_error(tropical - mean_offset, sidereal) * 3600 > 10
    assert angular_error(tropical - offset, sidereal) * 3600 < 1e-5


def test_mean_offset_error_can_change_the_reported_sidereal_sign():
    moment = datetime.fromisoformat("2000-01-02T09:07:28.584673+00:00")
    times = ephemeris_time(moment)
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        tropical = swe.calc(times.jd_tt, swe.MOON, swe.FLG_SWIEPH)[0][0]
        old_value = (tropical - swe.get_ayanamsa_ut(times.jd_ut1)) % 360
        native = swe.calc(times.jd_tt, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][
            0
        ]
    assert old_value < 210 < native
    result = build_otherbu_result(
        **FACES,
        date="2000-01-02",
        time="09:07:28.584673",
        zone="UTC",
        gps_lat=0,
        gps_lon=0,
        zodiacal=1,
        hsys=0,
    )
    moon = next(p for p in result["chart"]["chart"]["objects"] if p["id"] == "Moon")
    assert moon["sign"] == "Scorpio"
    assert result["sign"] == "Cancer"  # The actual roll remains an independent input.


def test_sidereal_result_cannot_be_a_tropical_position_with_a_new_label(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *args: ((123.0, 0, 1, 0, 0, 0), swe.FLG_SWIEPH | swe.FLG_SPEED),
    )
    with pytest.raises(EphemerisSourceError) as error:
        native_lahiri_positions(
            ["Moon"], julian_day_ut1=2451545.0, julian_day_tt=2451545.0007
        )
    assert error.value.reason == "coordinate_contract_changed"


def test_near_station_motion_uses_the_same_zodiac_frame_as_the_position():
    # Real calculation counterexample: these two reference-frame velocities
    # have opposite signs. It is not a forecast of a terrestrial event.
    birth, _, _ = _build_birth_info(
        date_text="2024-04-01",
        time_text="22:14:15.270121",
        timezone_name="UTC",
        lat=0,
        lon=0,
    )
    times = ephemeris_time(birth.utc_datetime)
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        tropical_speed = swe.calc(
            times.jd_tt, swe.MERCURY, swe.FLG_SWIEPH | swe.FLG_SPEED
        )[0][3]
        sidereal_speed = swe.calc(
            times.jd_tt, swe.MERCURY, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
        )[0][3]
    assert tropical_speed > 0 > sidereal_speed
    sidereal = build_core_chart_payload(birth, "chart", hsys=0, zodiacal=1)
    tropical = build_core_chart_payload(birth, "chart", hsys=0, zodiacal=0)
    assert sidereal["classical"]["planets"]["Mercury"]["retrograde"] is True
    assert tropical["classical"]["planets"]["Mercury"]["retrograde"] is False


def test_offline_sidereal_context_declares_its_approximation(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = build_otherbu_result(
        **FACES,
        date="2000-01-01",
        time="12:00",
        zone="UTC",
        gps_lat=0,
        gps_lon=0,
        hsys=0,
        zodiacal=1,
    )
    profile = result["chart"]["params"]["chart_profile"]
    assert profile["sidereal_position_method"] == "ayanamsha_offset_approximation"
    assert profile["sidereal_house_method"] == "ayanamsha_offset_approximation"
    assert profile["ayanamsha_includes_nutation"] is False
    assert profile["engine_precision"] == "approximate_orbital_model"


def test_sidereal_conversion_does_not_change_roll_or_solar_sect_and_is_offset_invariant():
    inputs = {
        **FACES,
        "date": "2024-03-20",
        "time": "06:30",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
    }
    tropical = build_otherbu_result(**inputs, zodiacal=0)
    sidereal = build_otherbu_result(**inputs, zodiacal=1)
    local = build_otherbu_result(
        **{**inputs, "time": "14:30", "zone": "+08:00"}, zodiacal=1
    )
    assert sidereal["chart"]["chart"] == local["chart"]["chart"]
    for key in (
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ):
        assert tropical[key] == sidereal[key]
    assert (
        tropical["chart"]["params"]["fortuneDefinition"]["sect_applied"]
        == sidereal["chart"]["params"]["fortuneDefinition"]["sect_applied"]
        == "day"
    )
