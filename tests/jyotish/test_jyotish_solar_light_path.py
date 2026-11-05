"""Solar exact light-time nodes, original requests and auxiliary fallback."""

import shutil
from pathlib import Path

import pytest

from fatebridge.core import compressed_ephemeris as context
from fatebridge.core import ephemeris_runtime as e
from tests.jyotish.test_jyotish_planet_light_path import requested_epoch, tt
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401


@pytest.mark.parametrize("year", range(600, 9601, 600))
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("frame", ["tropical", "lahiri", "equatorial", "icrf"])
def test_two_exact_solar_nodes_and_rebuilt_observer_keep_original_request(
    year, operation, frame
):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
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
    instant = requested_epoch(tt(year), operation)
    with context.audit_compressed_endpoints():
        result = e.ephemeris_call(operation, instant, e.swe.SUN, flags)
        receipt = context.coordinate_context_evidence()
        repeated = e.ephemeris_call(operation, instant, e.swe.SUN, flags)
    assert result == repeated
    assert receipt["selected_native_state"] == list(result[0])
    assert receipt["input_julian_day"] == instant
    assert receipt["operation"] == operation
    assert receipt["physical_instant_shifted"] is False
    path = receipt["solar_light_path"]
    assert path["status"] in {"already_covered", "reselected_common_window"}
    assert path["requested_coordinate_flags"] == flags
    assert (
        len(path["selection_retarded_epochs_jd_tt"])
        == len(path["retarded_epochs_jd_tt"])
        == 2
    )
    assert all(
        w["start_jd_tt"]
        <= min(path["selection_retarded_epochs_jd_tt"] + path["retarded_epochs_jd_tt"])
        <= path["reception_jd_tt"]
        <= w["end_jd_tt"]
        for w in path["selected_windows"]
    )
    prefix = "final" if path["status"] == "reselected_common_window" else "coherent"
    for label in [prefix + "_observer", prefix + "_sun"]:
        state = path["states"][label]
        assert state["epoch_jd_tt"] == path["reception_jd_tt"]
        assert state["observed_file_windows"] == path["selected_windows"]


@pytest.mark.parametrize("flag", [16, 16384, 8, 32768, 128, 1048576])
def test_solar_other_definitions_do_not_claim_two_node_coherence(flag):
    def forbidden(*args):
        raise AssertionError("Unsupported solar definition invoked a preflight")

    policy = context._solar_light_path(
        e.swe, 2451545.0, e.swe.FLG_SWIEPH | flag, forbidden
    )
    assert policy["status"] == "not_applied"
    assert policy["states"] == {}


@pytest.mark.parametrize(
    "files",
    [[], ["sepl_18.se1", "semo_18.se1"]],
)
def test_solar_actual_native_backend_survives_unavailable_auxiliary_files(
    tmp_path, files
):
    root = Path(__file__).resolve().parents[2] / "ephe"
    for name in files:
        shutil.copy2(root / name, tmp_path / name)
    e.configure_ephemeris_path(str(tmp_path))
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
    e.swe.set_ephe_path(str(tmp_path))
    e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
    expected = e.swe.calc(tt(1800), e.swe.SUN, flags)
    with context.audit_compressed_endpoints():
        actual = e.ephemeris_call("calc", tt(1800), e.swe.SUN, flags)
        receipt = context.coordinate_context_evidence()
    assert actual == expected
    assert receipt["solar_light_path"]["status"] == "not_applied"
    if files:
        assert receipt["solar_light_path"]["native_context_restarted"] is True


def test_partial_files_with_actual_covering_headers_still_repair_sun(tmp_path):
    root = Path(__file__).resolve().parents[2] / "ephe"
    for name in ["sepl_12.se1", "sepl_18.se1", "semo_18.se1"]:
        shutil.copy2(root / name, tmp_path / name)
    e.configure_ephemeris_path(str(tmp_path))
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
    e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
    with context.audit_compressed_endpoints():
        result = e.ephemeris_call("calc", tt(1800), e.swe.SUN, flags)
        receipt = context.coordinate_context_evidence()
        repeated = e.ephemeris_call("calc", tt(1800), e.swe.SUN, flags)
    assert result == repeated
    assert e.ephemeris_model_from_retflag(result[1]) == "swieph"
    path = receipt["solar_light_path"]
    assert path["status"] == "reselected_common_window"
    assert [w["filename"] for w in path["selected_windows"]] == [
        "sepl_12.se1",
        "semo_18.se1",
    ]
    assert all(
        w["start_jd_tt"]
        <= min(path["selection_retarded_epochs_jd_tt"] + path["retarded_epochs_jd_tt"])
        <= path["reception_jd_tt"]
        <= w["end_jd_tt"]
        for w in path["selected_windows"]
    )


def test_solar_endpoint_and_light_path_triggers_are_separate_evidence():
    with context.audit_compressed_endpoints():
        evidence = context.endpoint_context_evidence()
    assert (
        evidence["trigger"]
        == "owned_physical_light_path_or_observed_compressed_endpoint"
    )
    assert "64_TT_ULPs" in evidence["endpoint_guard_trigger"]
