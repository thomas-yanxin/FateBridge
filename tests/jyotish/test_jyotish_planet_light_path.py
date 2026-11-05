"""Common reception/retarded sources across requested frames and backends."""

import shutil
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import compressed_ephemeris as context
from fatebridge.core import ephemeris_runtime as e
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401


def tt(year):
    return float(
        Fraction(date(year, 1, 1).toordinal())
        + Fraction(3442849, 2)
        + Fraction(333, 86400000)
    )


def requested_epoch(epoch, operation):
    if operation == "calc":
        return epoch
    result = epoch
    for _ in range(8):
        result = epoch - e.swe.deltat_ex(result, e.swe.FLG_SWIEPH)
    return result


@pytest.mark.parametrize("year", [1800, 9600])
@pytest.mark.parametrize("body", range(2, 10))
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("frame", ["tropical", "lahiri", "equatorial", "icrf"])
def test_original_request_keeps_one_physical_light_path(year, body, operation, frame):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    flags = (
        e.swe.FLG_SWIEPH
        | {
            "tropical": e.swe.FLG_SPEED,
            "lahiri": e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL,
            "equatorial": e.swe.FLG_EQUATORIAL,
            "icrf": e.swe.FLG_SPEED
            | e.swe.FLG_XYZ
            | e.swe.FLG_EQUATORIAL
            | e.swe.FLG_J2000
            | e.swe.FLG_ICRS,
        }[frame]
    )
    e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
    instant = requested_epoch(tt(year), operation)
    with context.audit_compressed_endpoints():
        values, returned = e.ephemeris_call(operation, instant, body, flags)
        receipt = context.coordinate_context_evidence()
    assert e.ephemeris_model_from_retflag(returned) == "swieph"
    assert receipt["operation"] == operation
    assert receipt["input_julian_day"] == instant
    assert receipt["physical_instant_shifted"] is False
    assert receipt["selected_native_state"] == list(values)
    path = receipt["planet_light_path"]
    assert path["status"] == "reselected_common_window"
    assert path["requested_coordinate_flags"] == flags
    assert path["reception_jd_tt"] == receipt["physical_jd_tt"]
    assert path["selected_windows"] == receipt["selected_windows"]
    assert all(
        w["start_jd_tt"]
        <= min(path["selection_probe_jd_tt"], path["retarded_jd_tt"])
        <= path["reception_jd_tt"]
        <= w["end_jd_tt"]
        for w in path["selected_windows"]
    )
    for label in ["coherent_observer", "coherent_body"]:
        assert path["states"][label]["epoch_jd_tt"] == path["reception_jd_tt"]


@pytest.mark.parametrize("flag", [16, 16384, 8, 32768, 1048576])
def test_other_observer_and_position_definitions_do_not_claim_geocentric_fix(flag):
    def forbidden(*args):
        raise AssertionError(
            "Unsupported observer must not invoke a geometric preflight"
        )

    policy = context._planet_light_path(
        e.swe, 2451545.0, 2, e.swe.FLG_SWIEPH | flag, forbidden
    )
    assert policy["status"] == "not_applied"
    assert policy["states"] == {}


@pytest.mark.parametrize("body", range(2, 10))
def test_empty_data_directory_keeps_actual_analytical_fallback(tmp_path, body):
    e.configure_ephemeris_path(str(tmp_path))
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
    e.swe.set_ephe_path(str(tmp_path))
    e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
    original = e.swe.calc(2451545.0, body, flags)
    with context.audit_compressed_endpoints():
        actual = e.ephemeris_call("calc", 2451545.0, body, flags)
        receipt = context.coordinate_context_evidence()
    assert actual == original
    assert e.ephemeris_model_from_retflag(actual[1]) == "moshier"
    assert receipt["planet_light_path"]["status"] == "not_applied"


@pytest.mark.parametrize("body", [2, 3, 4])
def test_reception_only_files_keep_native_retarded_fallback(tmp_path, body):
    root = Path(__file__).resolve().parents[2] / "ephe"
    for name in ["sepl_18.se1", "semo_18.se1"]:
        shutil.copy2(root / name, tmp_path / name)
    e.configure_ephemeris_path(str(tmp_path))
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
    e.swe.set_ephe_path(str(tmp_path))
    e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
    original = e.swe.calc(tt(1800), body, flags)
    with context.audit_compressed_endpoints():
        actual = e.ephemeris_call("calc", tt(1800), body, flags)
        receipt = context.coordinate_context_evidence()
    assert actual == original
    assert e.ephemeris_model_from_retflag(actual[1]) == "moshier"
    assert receipt["planet_light_path"]["status"] == "not_applied"
    assert receipt["planet_light_path"]["native_fallback_restarted"] is True
