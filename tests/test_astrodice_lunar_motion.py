"""Source-derived corrections, frozen independent positions and honest failures."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import ephemeris, lunar_motion, runtime
from fatebridge.core.astro.longitude_motion import (
    corrected_longitude_motion,
    display_rotation_rate_change,
    nutation_obliquity_rate,
)
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.utils.errors import EphemerisSourceError
from scripts.audit_astrodice_lunar_motion import validate_reference

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
PROTOCOL = json.loads((FIXTURES / "astrodice-lunar-chain-protocol.json").read_text())
REFERENCE = json.loads((FIXTURES / "astrodice-lunar-chain-reference.json").read_text())
DEVELOPMENT_REFERENCE = json.loads(
    (FIXTURES / "astrodice-apparent-position-derivative.json").read_text()
)
MODERN = [r for r in REFERENCE["rows"] if "erfa_display_frame" in r]
PLUTO = [
    r
    for item in DEVELOPMENT_REFERENCE["references"]
    if item["body"] == "Pluto"
    for r in item["rows"]
    if "erfa_display_frame" in r
]


def test_frozen_lunar_protocol_reference_and_generator_identity():
    for name, checksum in [
        (
            "astrodice-lunar-chain-protocol.json",
            "f6c0aea76ba0391e1806e2624fbb76c204d7ee0c10d19e95a4b285935db156bf",
        ),
        (
            "astrodice-lunar-chain-reference.json",
            "25ee1bd30afb338999db6444565928454ef165f956a5226cbe806e038a30a761",
        ),
    ]:
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == checksum
    for key, name in [
        ("generator_sha256", "gen_astrodice_lunar_chain_reference.py"),
        ("helper_sha256", "gen_astrodice_apparent_reference.py"),
    ]:
        assert (
            REFERENCE[key]
            == hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        )
    assert REFERENCE["versions"] == {"pyerfa": "2.0.1.5", "numpy": "2.5.4"}
    assert REFERENCE["forbidden_implementation_imports"] == []
    validate_reference(PROTOCOL, REFERENCE, DEVELOPMENT_REFERENCE)
    assert len(REFERENCE["rows"]) == 97
    assert sum(r["cohort"] == "holdout" for r in REFERENCE["rows"]) == 40
    assert sum(r["cohort"] == "holdout" for r in MODERN) == 16
    assert len(REFERENCE["previous_original_missing_epochs"]) == 1
    # The reference's own numerical uncertainty is evidence, never a pass.
    assert (
        sum(r["stencil_difference_arcsec_per_day"] > 0.002 for r in REFERENCE["rows"])
        == 7
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_center",
        "drop_probe",
        "invent_rate",
        "change_frame",
        "alter_raw",
        "change_step",
        "erase_original_missing",
    ],
)
def test_lunar_validator_rejects_missing_data_and_fitted_or_redefined_reference(
    mutation,
):
    bad = copy.deepcopy(REFERENCE)
    if mutation == "drop_center":
        bad["rows"].pop()
    elif mutation == "drop_probe":
        bad["batches"][0]["rows"].pop()
    elif mutation == "invent_rate":
        bad["rows"][0]["icrf_direction_derivative_per_day"][0] += 1e-6
    elif mutation == "change_frame":
        bad["batches"][0]["parameters"]["TIME_TYPE"] = "'UT'"
    elif mutation == "alter_raw":
        bad["batches"][0]["raw_response_utf8"] += " "
    elif mutation == "change_step":
        bad["rows"][0]["seven_point_derivatives"]["14400"][0] += 1e-6
    else:
        bad["previous_original_missing_epochs"] = []
    with pytest.raises(ValueError):
        validate_reference(PROTOCOL, bad, DEVELOPMENT_REFERENCE)


@pytest.mark.parametrize("row", MODERN, ids=lambda r: r["date_tt"])
def test_actual_domain_lunar_display_rate_against_independent_apparent_positions(row):
    jd = row["jd_tt"]
    state, model = ephemeris._swisseph_planet_state("Moon", jd, julian_day_tt=jd)
    assert model == "swieph"
    expected = row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
    assert (
        abs(state["longitude_speed"] - expected) * 3600
        <= PROTOCOL["display_longitude_speed_tolerance_arcsec_per_day"]
    )
    assert state["longitude_speed"] == state["longitude_speed_native"] + state[
        "longitude_speed_light_time_correction"
    ] + state["longitude_speed_spatial_aberration_correction"] + state.get(
        "longitude_speed_lunar_source_remainder_correction", 0.0
    ) + state[
        "longitude_speed_rotation_correction"
    ] + state.get(
        "longitude_speed_analytic_frame_correction", 0.0
    )


@pytest.mark.parametrize("row", PLUTO, ids=lambda r: r["date_tt"])
def test_high_latitude_planet_uses_the_same_source_derived_rotation_term(row):
    state, model = ephemeris._swisseph_planet_state(
        "Pluto", row["jd_tt"], julian_day_tt=row["jd_tt"]
    )
    assert model == "swieph"
    assert "longitude_speed_light_time_correction" not in state
    assert (
        abs(
            state["longitude_speed"]
            - row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
        )
        * 3600
        <= 0.002
    )
    assert (
        state["longitude_speed"]
        == state["longitude_speed_native"]
        + state["longitude_speed_rotation_correction"]
    )


def test_aberration_jacobian_matches_directional_position_derivative():
    position = (0.002, 0.001, -0.0005)
    delta = (0.0003, -0.0002, 0.0001)
    beta = (0.0001, -0.00003, 0.00002)
    point, change = lunar_motion.aberration_position_jvp(position, delta, beta)
    step = 1e-5
    shifted = [
        lunar_motion.aberration_position_jvp(
            tuple(x + k * step * v for x, v in zip(position, delta)), (0, 0, 0), beta
        )[0]
        for k in [-1, 1]
    ]
    numerical = [(b - a) / (2 * step) for a, b in zip(*shifted)]
    assert change == pytest.approx(numerical, rel=1e-9, abs=1e-13)
    assert math.hypot(*point) == pytest.approx(math.hypot(*position), abs=1e-18)


@pytest.mark.parametrize("angle", [0, 23.7, 90, 180, 359])
def test_longitude_chain_correction_is_invariant_under_common_origin_rotation(angle):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def rotate(v):
        return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])

    position = (0.002, 0.001, -0.0005)
    delta = (0.0003, -0.0002, 0.0001)
    assert lunar_motion.longitude_rate_change(
        rotate(position), rotate(delta)
    ) == pytest.approx(lunar_motion.longitude_rate_change(position, delta), abs=1e-14)


def test_rotation_correction_is_the_derivative_of_the_final_axis_rotation():
    lon, lat, eps_dot = 24.0, 17.0, 0.00003
    x, y, z = (
        math.cos(math.radians(lat)) * math.cos(math.radians(lon)),
        math.cos(math.radians(lat)) * math.sin(math.radians(lon)),
        math.sin(math.radians(lat)),
    )
    # Equatorial -> ecliptic has y'=cos(eps)y+sin(eps)z.
    analytic = math.degrees(x * z / (x * x + y * y) * math.radians(eps_dot))
    assert display_rotation_rate_change(lon, lat, eps_dot) == pytest.approx(
        analytic, abs=1e-18
    )
    assert display_rotation_rate_change(lon, 0, eps_dot) == 0


@pytest.mark.parametrize("sidereal", [False, True])
def test_ut1_conversion_uses_same_native_tt_for_the_correction(sidereal):
    jd = 2451545.0
    swe = runtime.swe
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    _, returned = runtime.ephemeris_call("calc_ut", jd, swe.MOON, flags)
    tt = jd + runtime.ephemeris_call("deltat_ex", jd, returned & 7)
    if sidereal:

        def get(tt):
            return native_lahiri_positions(
                ["Moon"], julian_day_ut1=jd, julian_day_tt=tt
            )["Moon"]

    else:

        def get(tt):
            return ephemeris._swisseph_planet_state("Moon", jd, julian_day_tt=tt)[0]

    assert get(None) == get(tt)


@pytest.mark.parametrize("problem", ["version", "moshier"])
def test_unsupported_lunar_algorithm_preserves_raw_value_with_explicit_status(
    problem, monkeypatch
):
    if problem == "version":
        monkeypatch.setattr(
            lunar_motion, "SOURCE_VERSION", ("unverified", "unverified")
        )
    correction, policy = lunar_motion.lunar_light_time_correction(
        2451545.0, (0, 0, 1, 2, 0, 0), "moshier" if problem == "moshier" else "swieph"
    )
    assert correction is None
    assert policy["status"] == "not_applied"
    assert policy["reason"] == (
        "unsupported_physical_model"
        if problem == "moshier"
        else "unverified_native_version"
    )


@pytest.mark.parametrize("problem", ["flags", "model", "nan", "position"])
def test_lunar_transaction_rejects_bad_source_and_restores_managed_sidereal_mode(
    problem, monkeypatch
):
    swe = runtime.swe
    original = runtime.ephemeris_call
    coordinates = original("calc", 2451545.0, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)[
        0
    ]
    sidereal_flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    original("set_sid_mode", swe.SIDM_LAHIRI, 0, 0)
    expected = original("calc", 2451545.0, swe.MOON, sidereal_flags)

    def inject(operation, *args, **kwargs):
        values = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == swe.EARTH and args[2] & swe.FLG_BARYCTR:
            data, flags = values
            if problem == "flags":
                return data, flags & ~swe.FLG_XYZ
            if problem == "model":
                return data, (flags & ~7) | swe.FLG_MOSEPH
            if problem == "nan":
                return (math.nan, *data[1:]), flags
            return (data[0] + 1e-5, *data[1:]), flags
        return values

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError):
        lunar_motion.lunar_light_time_correction(2451545.0, coordinates, "swieph")
    assert original("calc", 2451545.0, swe.MOON, sidereal_flags) == expected


def test_sidereal_skips_true_ecliptic_rotation_term_and_reuses_physical_chain():
    context = {}
    state, model = ephemeris._swisseph_planet_state(
        "Moon", 2451545.0, julian_day_tt=2451545.0, motion_metadata=context
    )
    lahiri = native_lahiri_positions(
        ["Moon"],
        julian_day_ut1=2451545.0,
        julian_day_tt=2451545.0,
        lunar_adjustments={
            "Moon": (
                state["longitude_speed_light_time_correction"],
                model,
                state["longitude_speed_spatial_aberration_correction"],
            )
        },
        motion_metadata=context,
    )["Moon"]
    assert (
        lahiri["longitude_speed_light_time_correction"]
        == state["longitude_speed_light_time_correction"]
    )
    assert (
        lahiri["longitude_speed_spatial_aberration_correction"]
        == state["longitude_speed_spatial_aberration_correction"]
    )
    assert "longitude_speed_rotation_correction" not in lahiri
    assert (
        lahiri["longitude_speed"]
        == lahiri["longitude_speed_native"]
        + lahiri["longitude_speed_light_time_correction"]
        + lahiri["longitude_speed_spatial_aberration_correction"]
    )
    with pytest.raises(EphemerisSourceError) as error:
        corrected_longitude_motion(
            "Moon",
            2451545.0,
            (0, 0, 1, 2, 0, 0),
            "swieph",
            sidereal=True,
            lunar_adjustment=(1.0, "jpl", 0.0),
        )
    assert error.value.reason == "coordinate_model_changed"


def test_nutation_policy_is_per_epoch_and_retains_unknown_version(monkeypatch):
    context = {}
    first = nutation_obliquity_rate(2451545.0, context)
    assert first is not None
    assert nutation_obliquity_rate(2451545.0, context) == first
    assert nutation_obliquity_rate(2451546.0, context) != first
    monkeypatch.setattr(
        "fatebridge.core.astro.longitude_motion.SOURCE_VERSION",
        ("unverified", "unverified"),
    )
    assert nutation_obliquity_rate(2451547.0, context) is None
    assert context["tropical_rotation"]["status"] == "not_applied"
