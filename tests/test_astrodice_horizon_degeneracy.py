"""Horizon degeneracy from an independently specified altitude constraint.

No native or runtime angle is treated as a unique answer at a coincident plane.
Native and offline examples use their own actual angle inputs, not each other's
obliquity or a substituted sidereal longitude.
"""

import json
import math
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    ecliptic_horizon_angle_definition,
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.geometry import _angles, _gmst
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/astrodice-horizon-degeneracy.json").read_text()
)
FACES = {"planet": "Jupiter", "sign": "Aries", "house": 0}
SKY = {"date": "2024-06-21", "time": "12:00", "zone": "UTC"}


def singular_sky_inputs(
    *, native, hemisphere=1, latitude_offset=0, date_text=SKY["date"]
):
    birth, _, _ = _build_birth_info(
        date_text=date_text,
        time_text=SKY["time"],
        timezone_name="UTC",
        lat=0,
        lon=0,
    )
    jd = ephemeris_time(birth.utc_datetime).jd_ut1
    if native:
        assert runtime.swe is not None
        delta = runtime.ephemeris_call("deltat_ex", jd, 0)
        epsilon = runtime.ephemeris_call("calc", jd + delta, runtime.swe.ECL_NUT, 0)[0][
            0
        ]
        armc = runtime.ephemeris_call("houses_ex", jd, 0, 0, b"E")[1][2]
    else:
        epsilon = 23.439291 - 0.0130042 * ((jd - 2451545) / 36525)
        armc = _gmst(jd)
    target = 270 if hemisphere == 1 else 90
    return {
        **SKY,
        "date": date_text,
        "lat": hemisphere * (90 - epsilon) + latitude_offset,
        "lon": (target - armc + 180) % 360 - 180,
    }


@pytest.mark.parametrize("case", REFERENCE["coincident_cases"])
def test_all_ecliptic_longitudes_are_on_the_horizon_in_exact_analytic_cases(case):
    # Direct equatorial RA/Dec and USNO altitude equation, independent of the
    # A/B diagnostic. The fixture's exact 30/60-degree identities imply zero.
    for longitude in range(0, 360, 5):
        lam, eps, phi, theta = map(
            math.radians,
            [longitude, case["obliquity"], case["latitude"], case["armc"]],
        )
        ra = math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam))
        dec = math.asin(math.sin(lam) * math.sin(eps))
        sine_altitude = math.cos(theta - ra) * math.cos(dec) * math.cos(phi)
        sine_altitude += math.sin(dec) * math.sin(phi)
        assert abs(sine_altitude) < 5e-16
    definition = ecliptic_horizon_angle_definition(**case_inputs(case))
    assert definition["geometric_ascendant_resolved"] is False
    assert definition["retained_ascendant_role"] == "backend_numeric_convention_only"
    assert definition["midheaven_restricted_by_this_condition"] is False


def case_inputs(case):
    return {k: v for k, v in case.items() if k in ["latitude", "armc", "obliquity"]} | {
        "angle_method": "analytic_fixture"
    }


@pytest.mark.parametrize("case", REFERENCE["control_cases"])
def test_control_cases_are_not_marked_undefined_merely_for_high_latitude(case):
    assert ecliptic_horizon_angle_definition(**case_inputs(case)) is None


@pytest.mark.parametrize("offset", [-1e-7, 1e-7])
def test_nearby_resolved_intersections_are_qualified_without_calling_them_undefined(
    offset,
):
    case = {**REFERENCE["coincident_cases"][0], "latitude": 60 + offset}
    result = ecliptic_horizon_angle_definition(**case_inputs(case))
    assert result["status"] == "ecliptic_horizon_ill_conditioned"
    assert result["geometric_ascendant_resolved"] is True
    assert result["conditioning"]["plane_separation_degrees"] == pytest.approx(
        abs(offset), abs=1e-14
    )
    assert result["conditioning"]["not_an_input_or_model_error_bound"] is True


@pytest.mark.parametrize("offset", [-1e-4, 1e-4])
def test_nearby_but_well_resolved_planes_are_not_reclassified(offset):
    case = {**REFERENCE["coincident_cases"][0], "latitude": 60 + offset}
    assert ecliptic_horizon_angle_definition(**case_inputs(case)) is None


@pytest.mark.parametrize("native,hemisphere", list(product([True, False], [1, -1])))
def test_actual_backend_singular_sky_keeps_planets_and_qualifies_asc_dependents(
    monkeypatch, native, hemisphere
):
    if not native:
        monkeypatch.setattr(runtime, "swe", None)
    inputs = singular_sky_inputs(native=native, hemisphere=hemisphere)
    result = build_otherbu_result(**FACES, **inputs, hsys=0)
    profile = result["chart"]["params"]["chart_profile"]
    definition = profile["angle_definition"]
    assert definition["status"] == "ecliptic_horizon_numerically_unresolved"
    assert definition["angle_method"] == profile["angle_method"]
    assert definition["geometric_ascendant_resolved"] is False
    assert definition["note_zh"] in result["snapshot_text"]
    assert definition["conditioning"]["intersection_normal_norm"] < 1e-14
    assert len(result["chart"]["chart"]["objects"]) == 13
    assert len(result["chart"]["chart"]["houses"]) == 12
    plain = build_otherbu_result(**FACES)
    for key in ["symbolic_details", "interpretation", "rulesets", "rule_trace"]:
        assert result[key] == plain[key]
    # Away from the same critical point no plane-degeneracy claim is made.
    ordinary = build_otherbu_result(**FACES, **{**inputs, "lon": 0}, hsys=0)
    assert "angle_definition" not in ordinary["chart"]["params"]["chart_profile"]


@pytest.mark.parametrize("zodiacal,hsys", list(product([0, 1], [0, 1, 8])))
def test_native_whole_equal_and_mc_equal_keep_the_same_physical_diagnostic(
    zodiacal, hsys
):
    result = build_otherbu_result(
        **FACES, **singular_sky_inputs(native=True), hsys=hsys, zodiacal=zodiacal
    )
    definition = result["chart"]["params"]["chart_profile"]["angle_definition"]
    assert definition["status"] == "ecliptic_horizon_numerically_unresolved"
    assert definition["geometry_inputs"]["armc"] == 270
    # Neither the sidereal ASC nor ayanamsha is an equatorial meridian angle.
    assert 23 < definition["geometry_inputs"]["obliquity"] < 24


@pytest.mark.parametrize(
    "date_text", ["0001-06-21", "0600-06-21", "1200-06-21", "9999-06-21"]
)
def test_distant_epoch_uses_house_obliquity_instead_of_calc_ut_default(date_text):
    result = build_otherbu_result(
        **FACES, **singular_sky_inputs(native=True, date_text=date_text), hsys=0
    )
    definition = result["chart"]["params"]["chart_profile"]["angle_definition"]
    assert definition["status"] == "ecliptic_horizon_numerically_unresolved"
    assert definition["conditioning"]["intersection_normal_norm"] < 1e-14


def test_singular_limit_depends_on_approach_direction():
    swe = pytest.importorskip("swisseph")
    # At the analytic critical latitude, approaching along longitude and along
    # latitude yields different ASC limits. No single finite backend number
    # repairs the missing unique geometry.
    along_meridian = swe.houses_armc(270, 60 - 1e-5, 30, b"E")[1][0]
    along_rotation = swe.houses_armc(270 - 1e-5, 60, 30, b"E")[1][0]
    distance = abs((along_rotation - along_meridian + 180) % 360 - 180)
    assert distance > 89


def test_offline_singular_numeric_artifact_is_not_presented_as_resolved_ascendant():
    jd = 2460483.0
    epsilon = 23.439291 - 0.0130042 * ((jd - 2451545) / 36525)
    longitude = (270 - _gmst(jd) + 180) % 360 - 180
    result = _angles(jd, longitude, 90 - epsilon)
    # Its old atan2 residual gave ~301 degrees. We preserve the numeric backend
    # result without certifying it or substituting a made-up physical angle.
    assert math.isfinite(result["ascendant"])
    assert result["midheaven"] == 270
    assert result["angle_definition"]["geometric_ascendant_resolved"] is False


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_polar_house_branch_qualification_reaches_the_dice_snapshot(zodiacal):
    result = build_otherbu_result(
        **FACES, **SKY, lat=80, lon=179, hsys=2, zodiacal=zodiacal
    )
    convention = result["chart"]["params"]["chart_profile"]["house_axis_convention"]
    assert (
        convention["policy_id"] == "fatebridge_sky_axes_separate_from_house_branch_v1"
    )
    assert convention["meridian_branch_separation_degrees"] > 179
    birth, _, _ = _build_birth_info(
        date_text=SKY["date"],
        time_text=SKY["time"],
        timezone_name="UTC",
        lat=80,
        lon=179,
    )
    times = ephemeris_time(birth.utc_datetime)
    with runtime.preserve_ephemeris_path():
        if zodiacal:
            runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        native_cusps, _ = runtime.ephemeris_call(
            "houses_ex",
            times.jd_ut1,
            80,
            179,
            b"R",
            runtime.swe.FLG_SIDEREAL if zodiacal else 0,
        )
    assert [h["lon"] for h in result["chart"]["chart"]["houses"]] == pytest.approx(
        native_cusps, abs=1e-9, rel=0
    )
    assert convention["note_zh"] in result["snapshot_text"]
    assert (
        result["symbolic_details"] == build_otherbu_result(**FACES)["symbolic_details"]
    )


def test_missing_native_obliquity_cannot_certify_resolved_geometry(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda operation, *args: 0 if operation == "deltat_ex" else ((), -1),
    )
    with pytest.raises(ValueError, match="obliquity"):
        native_ecliptic_horizon_angle_definition(
            julian_day_ut1=2460483, latitude=66.56, armc=270
        )


def test_native_diagnostic_uses_house_internal_ut1_delta_t_convention(monkeypatch):
    calls = []

    def reference(operation, *args):
        calls.append((operation, *args))
        if operation == "deltat_ex":
            return 1 / 86400
        return (30, 30, 0, 0, 0, 0), 0

    monkeypatch.setattr(runtime, "ephemeris_call", reference)
    result = native_ecliptic_horizon_angle_definition(
        julian_day_ut1=2460483, latitude=60, armc=270
    )
    assert calls == [
        ("deltat_ex", 2460483, 0),
        ("calc", 2460483 + 1 / 86400, runtime.swe.ECL_NUT, 0),
    ]
    assert result["geometric_ascendant_resolved"] is False


def test_diagnostic_is_fresh_for_each_call():
    inputs = case_inputs(REFERENCE["coincident_cases"][0])
    first = ecliptic_horizon_angle_definition(**inputs)
    first["source_urls"].clear()
    assert len(ecliptic_horizon_angle_definition(**inputs)["source_urls"]) == 2


@pytest.mark.parametrize("key", ["latitude", "armc", "obliquity"])
def test_nonfinite_geometry_is_not_accepted(key):
    inputs = case_inputs(REFERENCE["coincident_cases"][0])
    inputs[key] = math.nan
    with pytest.raises(ValueError, match="finite"):
        ecliptic_horizon_angle_definition(**inputs)
