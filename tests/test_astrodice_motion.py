"""Instantaneous motion must retain its source frame and missing-data status.

Native comparisons here check an output contract, not independent apparent
speed accuracy. The frozen Horizons protocol separately checks geometric rates.
"""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.native_motion import context_motion, require_longitude_speed
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.utils.errors import EphemerisSourceError
from scripts.audit_astrodice_kernel import direction_derivative, velocity_diagnostics
from tests.ephemeris_case_runtime import native_ephemeris_files_module

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

ROOT = Path(__file__).resolve().parents[1]
FACES = {"planet": "Saturn", "sign": "Aries", "house": 0}
SKY = {"date": "2000-01-01", "time": "12:00", "zone": "UTC", "lat": 51.5, "lon": 0}
FRAME = "tropical_ecliptic_of_date"
PROTOCOL = json.loads(
    (ROOT / "tests/data/astrodice/tables/velocity-protocol.json").read_text()
)


@pytest.mark.parametrize(
    "rate,direction",
    [(0.0, "zero_instantaneous_rate"), (-1e-15, "retrograde"), (1e-15, "direct")],
)
def test_unrounded_rate_sign_does_not_locate_a_station_event(rate, direction):
    speed = require_longitude_speed((0, 0, 1, rate, 0, 0), 256, 256)
    motion = context_motion("Saturn", {"Saturn": speed}, {"Saturn": "swieph"}, FRAME)
    assert motion["longitude_speed"] == rate
    assert motion["direction"] == direction
    assert "station" not in motion


@pytest.mark.parametrize(
    "values,flags",
    [
        ((0, 0, 1, 0, 0, 0), 2),
        ((0, 0, 1, 0, 0, 0), -1),
        ((0, 0, 1), 256),
        ((0, 0, 1, None), 256),
        ((0, 0, 1, math.nan), 256),
        ((0, 0, 1, math.inf), 256),
    ],
)
def test_requested_native_motion_never_accepts_missing_or_nonfinite_speed(
    values, flags
):
    with pytest.raises(EphemerisSourceError) as error:
        require_longitude_speed(values, flags, 256)
    assert error.value.reason == "coordinate_motion_unavailable"


@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize("problem", ["missing_flag", "nan"])
def test_real_native_provider_failure_is_rejected_before_false_direct(
    sidereal, problem, monkeypatch
):
    original = runtime.ephemeris_call
    swe = runtime.swe
    assert swe is not None

    def inject(operation, *args, **kwargs):
        if operation == "calc" and args[1] == swe.SATURN:
            if problem == "missing_flag":
                # Actually ask Swiss not to compute speed: it returns zero,
                # which used to be accepted despite Saturn being retrograde.
                return original(operation, args[0], args[1], args[2] & ~swe.FLG_SPEED)
            values, flags = original(operation, *args, **kwargs)
            return (*values[:3], math.nan, *values[4:]), flags
        return original(operation, *args, **kwargs)

    assert (
        original("calc", 2451545.0, swe.SATURN, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][3]
        < 0
    )
    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError) as error:
        if sidereal:
            native_lahiri_positions(
                ["Saturn"], julian_day_ut1=2451545.0, julian_day_tt=2451545.0
            )
        else:
            ephemeris._swisseph_planet_state(
                "Saturn", 2451545.0, julian_day_tt=2451545.0
            )
    assert error.value.reason == "coordinate_motion_unavailable"


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_context_retains_native_rate_and_explicit_corrections_without_changing_dice(
    zodiacal,
):
    result = build_otherbu_result(**FACES, **SKY, zodiacal=zodiacal)
    plain = build_otherbu_result(**FACES)
    points = {o["id"]: o for o in result["chart"]["chart"]["objects"]}
    times = ephemeris_time(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
    swe = runtime.swe
    assert swe is not None
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        for name, body in PLANET_SWISSEPH_IDS.items():
            flags = (
                swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if zodiacal else 0)
            )
            expected = runtime.ephemeris_call("calc", times.jd_tt, body, flags)[0][3]
            actual = points[name]["motion"]
            assert actual["native_longitude_speed"] == expected
            assert actual["longitude_speed"] == (
                expected
                + actual.get("light_time_correction", 0)
                + actual.get("spatial_aberration_correction", 0)
                + actual.get("lunar_source_remainder_correction", 0)
                + actual.get("rotation_correction", 0)
                + actual.get("position_derivative_correction", 0)
                + actual.get("analytic_frame_correction", 0)
            )
            if zodiacal:
                assert "rotation_correction" not in actual
            if name == "Moon":
                assert actual["light_time_correction"] != 0
                assert "spatial_aberration_correction" in actual
                assert "lunar_source_remainder_correction" in actual
            assert actual["reference_frame"] == (
                "lahiri_sidereal_ecliptic_of_date" if zodiacal else FRAME
            )
    assert points["Saturn"]["motion"]["direction"] == "retrograde"
    assert (
        points["South Node"]["motion"]["longitude_speed"]
        == points["North Node"]["motion"]["longitude_speed"]
    )
    assert (
        points["South Node"]["motion"]["basis"]
        == "opposite_point_inherits_same_longitude_rate"
    )
    assert points["Pars Fortuna"]["motion"]["longitude_speed"] is None
    assert points["Pars Fortuna"]["motion"]["direction"] == "not_computed"
    policy = result["chart"]["params"]["motionPolicy"]
    assert policy["uncomputed_points"] == ["Pars Fortuna"]
    assert policy["status"] == "partial"
    assert "zero_is_not_a_located_station_event" in policy["sign_policy"]
    assert "天象瞬时黄经运动" in result["snapshot_text"]
    assert (
        f"Saturn / {points['Saturn']['motion']['longitude_speed']} 度/日 / 瞬时逆行"
        in result["snapshot_text"]
    )
    for key in (
        "method_id",
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ):
        assert result[key] == plain[key]


@pytest.mark.parametrize("failed", ["Saturn", "North Node"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_approximate_orbit_without_derivative_remains_unknown(
    failed, zodiacal, monkeypatch
):
    original = ephemeris._swisseph_planet_state
    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda name, *a, **kw: None if name == failed else original(name, *a, **kw),
    )
    result = build_otherbu_result(**FACES, **SKY, zodiacal=zodiacal)
    points = {o["id"]: o for o in result["chart"]["chart"]["objects"]}
    missing = {failed, "Pars Fortuna"} | (
        {"South Node"} if failed == "North Node" else set()
    )
    assert (
        set(result["chart"]["params"]["motionPolicy"]["uncomputed_points"]) == missing
    )
    for name in missing:
        assert points[name]["motion"]["longitude_speed"] is None
        assert points[name]["motion"]["direction"] == "not_computed"
    assert points["Moon"]["motion"]["direction"] == "direct"


def test_frozen_velocity_protocol_and_reference_identity():
    assert (
        hashlib.sha256(
            (ROOT / "tests/data/astrodice/tables/velocity-protocol.json").read_bytes()
        ).hexdigest()
        == "bae5666fedb9a6678784f8342ae0b1544140f3e8be5119f0529fbb5b7e7422af"
    )
    for key, relative in [
        ("position_protocol_sha256", "kernel-protocol.json"),
        ("reference_fixture_sha256", "kernel-horizons.json"),
    ]:
        assert (
            PROTOCOL[key]
            == hashlib.sha256(
                (ROOT / "tests/data/astrodice/tables" / relative).read_bytes()
            ).hexdigest()
        )
    assert PROTOCOL["require_speed_flag"] is True


def test_direction_derivative_removes_radial_velocity_and_retains_transverse_rate():
    assert direction_derivative((2.0, 0, 0), (3.0, 4.0, 0)) == [0.0, 2.0, 0.0]
    assert direction_derivative((2.0, 0, 0), (3.0, 0, 0)) == [0.0, 0.0, 0.0]
    with pytest.raises(ValueError):
        direction_derivative((0.0, 0, 0), (0.0, 0, 0))


@pytest.mark.parametrize(
    "problem",
    [
        "none",
        "missing_flag",
        "failed_flag",
        "short_state",
        "nonfinite",
        "wrong_velocity",
    ],
)
def test_velocity_audit_negative_controls_do_not_turn_absence_into_zero_error(problem):
    values = [1.0, 0.0, 0.0, 0.0, 0.01, 0.0]
    flags = 256
    row = {"position_au": values[:3], "velocity_au_per_day": values[3:].copy()}
    if problem == "missing_flag":
        flags = 2
    elif problem == "failed_flag":
        flags = -1
    elif problem == "short_state":
        values = values[:3]
    elif problem == "nonfinite":
        values[3] = math.nan
    elif problem == "wrong_velocity":
        values[4] += 1e-6
    result = velocity_diagnostics(values, flags, row, PROTOCOL, 256)
    assert result["passes_velocity_check"] is (problem == "none")
    if problem in {"missing_flag", "failed_flag"}:
        assert result["native_speed_flag_returned"] is False
    if problem not in {"none", "wrong_velocity"}:
        assert result["component_velocity_error_au_per_day"] is None
        assert result["direction_derivative_error_arcsec_per_day"] is None
