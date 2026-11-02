"""Portable standard rotation, geographic-frame identity and event fixed points."""

import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from fatebridge.core import astro_models
from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro_models import (
    MODERN_HALF_WINDOW_DAYS,
    MODERN_REFERENCE_JD_TT,
    _correction,
    _fundamental_arguments,
    earth_rotation_policy,
    iers2010_gast,
    native_rotation_call,
    selected_sidereal_model,
)
from tests.test_western_accuracy import BIRTH
from tests.test_western_house_reference import REFERENCE, separation

KERNEL = json.loads(
    (Path(__file__).parent / "fixtures/western-rotation-kernel-erfa.json").read_text()
)


@pytest.mark.parametrize("case", KERNEL["cases"])
def test_iers_kernel_against_independent_erfa_with_fixed_common_inputs(case):
    actual = iers2010_gast(
        case["jd_ut1"],
        case["jd_tt"],
        case["nutation_longitude_degrees"],
        case["mean_obliquity_degrees"],
    )
    assert (
        separation(actual, case["gast_degrees"]) <= KERNEL["gast_tolerance_arcseconds"]
    )
    args = _fundamental_arguments((case["jd_tt"] - 2451545.0) / 36525)
    assert (
        max(
            abs((a - b + math.pi) % math.tau - math.pi)
            for a, b in zip(args, case["arguments_radians"])
        )
        < 1e-10
    )


@pytest.mark.parametrize("tt", [2378495.0, 2524595.0])
def test_standard_to_longterm_boundary_has_no_large_phase_step(tt):
    jd = tt
    for _ in range(5):
        jd = tt - runtime.swe.deltat_ex(jd, runtime.swe.FLG_SWIEPH)
    left, right = jd - 1 / 86400, jd + 1 / 86400
    a, b = [runtime.ephemeris_call("sidtime", t) * 15 for t in (left, right)]
    # A two-second interval must retain ordinary daily rotation at either edge.
    expected = (right - left) * 360.985647
    assert abs(((b - a + 180) % 360 - 180) - expected) * 3600 < 0.001


def test_future_native_houses_match_reference_and_keep_supplied_location():
    case = REFERENCE["cases"][-1]
    p = case["input"]
    original = dict(p)
    _, angles = runtime.ephemeris_call(
        "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"E"
    )
    for i, key in enumerate(("ascendant", "midheaven")):
        assert separation(angles[i], case["erfa_vector_angles"][key]) <= 1
    assert p == original


def test_frame_rotation_uses_only_public_python_interfaces_and_does_not_relocate_input():
    module = ModuleType("windows_shaped_swiss")
    module.FLG_SWIEPH = 2
    module.ECL_NUT = -1
    module.deltat_ex = lambda *args: 70 / 86400
    module.calc = lambda *args: ((23.44, 23.439, 0.001, 0.001), 2)
    module.sidtime = lambda jd: 10.0
    calls = []
    module.houses_ex = lambda *args, **kwargs: calls.append((args, kwargs)) or "result"
    inputs = (2470162.5, 20.0, 179.999, b"R")
    result = native_rotation_call(module, "houses_ex", inputs, {})
    delta = _correction(module, inputs[0])
    assert result == "result" and inputs[2] == 179.999
    assert calls[0][0][0:2] == inputs[0:2]
    assert abs((calls[0][0][2] - (inputs[2] + delta) + 180) % 360 - 180) < 1e-12
    assert not hasattr(module, "swe_set_astro_models")


@pytest.mark.parametrize("year", [1, 500, 1000, 1500, 1750, 2300, 3000, 5000, 9999])
def test_remote_epochs_retain_native_longterm_variation_with_one_constant_phase(year):
    times = ephemeris_time(datetime(year, 6, 21, 6, tzinfo=timezone.utc))
    assert selected_sidereal_model(times.jd_tt) == 4
    offsets = []
    for jd in [times.jd_ut1, times.jd_ut1 + 0.25]:
        managed = runtime.ephemeris_call("sidtime", jd) * 15
        native = runtime.swe.sidtime(jd) * 15
        offsets.append((managed - native + 180) % 360 - 180)
    assert offsets[0] == pytest.approx(offsets[1], abs=1e-10)
    policy = earth_rotation_policy(times.jd_tt, times.jd_ut1)
    assert (
        policy["sidereal_time_model"] == "Swiss_longterm_with_boundary_phase_alignment"
    )
    assert policy["longterm_phase_alignment"]["absolute_accuracy_certified"] is False


def test_model_adoption_window_has_explicit_representable_boundaries():
    lower = MODERN_REFERENCE_JD_TT - MODERN_HALF_WINDOW_DAYS
    upper = MODERN_REFERENCE_JD_TT + MODERN_HALF_WINDOW_DAYS
    assert selected_sidereal_model(lower) == selected_sidereal_model(upper) == 3
    assert selected_sidereal_model(math.nextafter(lower, -math.inf)) == 4
    assert selected_sidereal_model(math.nextafter(upper, math.inf)) == 4


def test_parallel_native_workers_agree_without_private_model_exports():
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(
            pool.map(lambda _: runtime.ephemeris_call("sidtime", 2487969.5), range(12))
        )
    assert max(values) == min(values)


def test_failed_event_refinement_cannot_return_unconverged_time_and_restores_observer(
    monkeypatch,
):
    module = ModuleType("nonconverging_public_backend")
    module.BIT_HINDU_RISING = 896
    module.BIT_DISC_CENTER = 256
    module.BIT_NO_REFRACTION = 512
    count = []
    restored = []
    module.set_topo = lambda *site: restored.append(site)

    def event(*args):
        count.append(args)
        return 0, (2470162.5 + len(count),)

    module.rise_trans = event
    monkeypatch.setattr(astro_models, "_correction", lambda module, jd: jd % 2)
    site = (121.4737, 31.23, 25.0)
    with pytest.raises(RuntimeError, match="did not converge"):
        native_rotation_call(module, "rise_trans", (2470162.5, 0, 1, site), {})
    assert len(count) == 6 and restored == [site]


def test_approximate_angles_do_not_claim_the_native_rotation_policy(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("deliberate native failure")

    monkeypatch.setattr(runtime.swe, "houses_ex", fail)
    result = build_core_chart_payload(
        build_astro_birth_info(**BIRTH), "chart", hsys=0, zodiacal=0
    )
    assert result["chart_profile"]["angle_method"] == "approximate_angles"
    assert result["chart_profile"]["earth_rotation"] is None


@pytest.mark.parametrize(
    "date",
    [
        "2050-01-01T00:00:00+00:00",
        "2050-12-21T00:00:00+00:00",
        "2099-09-23T00:00:00+00:00",
    ],
)
def test_refracted_sunrise_is_a_fixed_point_of_the_public_geometry(date):
    time = ephemeris_time(datetime.fromisoformat(date))
    site = (0.0, 51.5, 0.0)
    args = (
        time.jd_ut1,
        runtime.swe.SUN,
        runtime.swe.CALC_RISE | runtime.swe.BIT_DISC_CENTER,
        site,
        1013.25,
        0.0,
        runtime.swe.FLG_SWIEPH,
    )
    code, events = runtime.ephemeris_call("rise_trans", *args)
    assert code == 0
    event = events[0]
    correction = _correction(runtime.swe, event)
    native_site = ((site[0] + correction + 180) % 360 - 180, *site[1:])
    try:
        native_code, check = runtime.swe.rise_trans(*args[:3], native_site, *args[4:])
        assert native_code == 0 and abs(check[0] - event) * 86400 <= 0.001
    finally:
        runtime.swe.set_topo(*site)
