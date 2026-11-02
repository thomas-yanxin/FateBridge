"""The source window is determined by the light path, never by residuals."""

import math

import pytest

from fatebridge.core.astro import ephemeris
from fatebridge.core.astro import lunar_source_window as window
from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize(
    "start,end,good",
    [
        (99, 101, True),
        (99.99999, 101, False),
        (99, 99.99999, False),
        (math.nan, 101, False),
    ],
)
def test_selected_context_must_cover_both_endpoints(start, end, good, monkeypatch):
    monkeypatch.setattr(
        runtime.swe,
        "get_current_file_data",
        lambda slot: ("/private/data/file.se1", start, end, 441),
    )
    if good:
        result = window.selected_windows(100, 99.99998)
        assert all(r["filename"] == "file.se1" for r in result)
    else:
        with pytest.raises(EphemerisSourceError) as error:
            window.selected_windows(100, 99.99998)
        assert error.value.reason == "lunar_source_window_incoherent"


@pytest.mark.parametrize("frame", ["tropical", "lahiri"])
def test_known_boundary_retains_both_native_states_and_auxiliary_source_scope(frame):
    jd = 5227387.5
    metadata = {}
    trace = PhysicalEphemerisTrace()
    if frame == "tropical":
        state, model = ephemeris._swisseph_planet_state(
            "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
        )
        assert set(trace.finish()["by_factor"]) == {"Moon"}
    else:
        state = native_lahiri_positions(
            ["Moon"],
            julian_day_ut1=jd,
            julian_day_tt=jd,
            source_trace=trace,
            motion_metadata=metadata,
        )["Moon"]
        trace.finish()
    policy = metadata["lunar_source_windows"][frame]
    assert policy["status"] == "recomputed_in_common_window"
    assert state["longitude"] == policy["coherent_spherical_coordinates"][0]
    assert state["latitude"] == policy["coherent_spherical_coordinates"][1]
    assert len(policy["initial_spherical_coordinates"]) == 3
    assert set(policy["source_contexts"]) == {
        "Moon_light_path_geometric",
        "Moon_light_path_retarded_barycentric",
    }
    for interval in policy["selected_windows_after_recomputation"]:
        assert (
            interval["start_jd_tt"]
            <= policy["retarded_jd_tt"]
            <= jd
            <= interval["end_jd_tt"]
        )


@pytest.mark.parametrize(
    "model", ["jpl", "moseph", "fatebridge_approximate_orbital_model"]
)
def test_other_kernels_do_not_claim_a_compressed_context_fix(model):
    policy = window.prime_lunar_source_window(
        2451545.0, model, PhysicalEphemerisTrace()
    )
    assert policy["status"] == "not_applied"


def test_unverified_native_identity_never_primes_a_state(monkeypatch):
    monkeypatch.setattr(window, "binding_distribution_version", lambda *args: "unknown")
    policy = window.prime_lunar_source_window(
        2451545.0, "swieph", PhysicalEphemerisTrace()
    )
    assert (
        policy["status"] == "not_applied"
        and policy["reason"] == "unverified_native_version"
    )


def test_equatorial_output_and_cartesian_diagnostic_use_the_same_window():
    from fatebridge.core.astro.lunar_source_window import coherent_lunar_native_state

    jd = 5227387.5
    metadata = {}
    trace = PhysicalEphemerisTrace()
    swe = runtime.swe
    state, model = ephemeris._swisseph_planet_state(
        "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
    )
    eq = metadata["lunar_source_windows"]["equatorial"]
    assert state["declination"] == eq["coherent_native_state"][1]
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_ICRS
        | swe.FLG_J2000
    )
    with runtime.preserve_ephemeris_path():
        values, returned, policy = coherent_lunar_native_state(
            "calc", jd, flags, jd, model, trace
        )
    assert policy["coordinate_kind"] == "cartesian"
    assert "coherent_spherical_coordinates" not in policy
    assert list(values) == policy["coherent_native_state"]
    assert returned & swe.FLG_SPEED
    trace.finish()


def test_a_different_overlapping_fit_is_rejected_after_recomputation(monkeypatch):
    first = [
        {
            "slot": 0,
            "filename": "first.se1",
            "start_jd_tt": 99.0,
            "end_jd_tt": 101.0,
            "de_number": 441,
        }
    ]
    changed = [{**first[0], "filename": "second.se1"}]
    monkeypatch.setattr(window, "selected_windows", lambda *args: changed)
    policy = {
        "status": "primed",
        "epoch_jd_tt": 100.0,
        "retarded_jd_tt": 99.999,
        "selected_windows": first,
    }
    with pytest.raises(EphemerisSourceError) as error:
        window.finish_lunar_source_window(
            policy, (0, 0, 1, 0, 0, 0), (0, 0, 1, 0, 0, 0)
        )
    assert error.value.reason == "lunar_source_window_incoherent"
