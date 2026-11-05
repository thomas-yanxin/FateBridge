"""Finite ray, unknown-source and source-contract solar-position controls."""

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro import solar_position as solar
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.output_charts import ApparentPositionPolicy
from fatebridge.utils.errors import EphemerisSourceError
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


def ray(distance, fraction):
    angle = math.asin(fraction * solar.SOLAR_RADIUS_AU)
    return (distance * math.cos(angle), distance * math.sin(angle), 0.0)


@pytest.mark.parametrize("fraction", [0.0, 0.2, 0.5, 0.999])
@pytest.mark.parametrize(
    "distance,domain", [(0.5, "foreground_of_solar_disc"), (2, "behind_solar_disc")]
)
def test_finite_target_range_separates_transits_from_background_extensions(
    fraction, distance, domain
):
    result = solar.finite_solar_ray(ray(distance, fraction), (-1, 0, 0))
    assert result["unbent_ray_domain"] == domain
    assert result["impact_solar_radius_fraction"] == pytest.approx(fraction)
    assert result["observational_accuracy_certified"] is False
    assert result["maximum_physical_error_arcseconds"] is None
    assert (
        result["position_interpretation"] == "virtual_native_solar_disc_extension"
    ) == (distance == 2)


@pytest.mark.parametrize("fraction", [1.0001, 2, 20])
def test_a_ray_outside_the_sphere_has_no_virtual_extension(fraction):
    assert (
        solar.finite_solar_ray(ray(2, fraction), (-1, 0, 0))["unbent_ray_domain"]
        == "outside_solar_disc"
    )


def test_tangent_and_target_on_sphere_remain_ambiguous():
    assert (
        solar.finite_solar_ray(ray(2, 1), (-1, 0, 0))["unbent_ray_domain"]
        == "solar_limb_ambiguous"
    )
    assert (
        solar.finite_solar_ray((1 - solar.SOLAR_RADIUS_AU, 0, 0), (-1, 0, 0))[
            "unbent_ray_domain"
        ]
        == "target_on_model_sphere_ambiguous"
    )


def test_sun_behind_the_observer_does_not_occult_an_anti_solar_body():
    assert (
        solar.finite_solar_ray((-2, 0, 0), (-1, 0, 0))["unbent_ray_domain"]
        == "sun_behind_observer"
    )


@pytest.mark.parametrize(
    "bad",
    [
        (0, 0, 0),
        (float("nan"), 1, 0),
        (float("inf"), 1, 0),
        (1,),
        (1.7e308, 1.7e308, 0),
    ],
)
def test_invalid_and_overflowing_geometry_is_never_certified(bad):
    with pytest.raises(EphemerisSourceError) as caught:
        solar.finite_solar_ray(bad, (-1, 0, 0))
    assert caught.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize("reason", ["version", "backend"])
def test_unverified_source_is_explicitly_unknown_without_barycentric_fallback(
    reason, monkeypatch
):
    if reason == "version":
        monkeypatch.setattr(
            solar, "binding_distribution_version", lambda *_: "unverified"
        )
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *_: pytest.fail("Unverified geometry must not be computed"),
    )
    p = solar.apparent_position_policy(
        2459892.375,
        {
            "Mercury": "moshier" if reason == "backend" else "swieph",
            "North Node": "analytical_node",
        },
        PhysicalEphemerisTrace(),
    )
    assert p["bodies"]["Mercury"]["status"] == "not_evaluated"
    assert p["bodies"]["Mercury"]["unbent_ray_domain"] is None
    assert "North Node" in p["excluded_factors"]
    assert p["displayed_native_positions_changed"] is False
    if reason == "version":
        assert p["source_model_regularity"] is None
    else:
        assert p["source_model_regularity"]["axis_continuity_certified"] is False
    ApparentPositionPolicy.model_validate(p)


@pytest.mark.parametrize("problem", ["frame", "model", "values", "configuration"])
def test_solar_metadata_cannot_hide_a_changed_source_contract(problem, monkeypatch):
    original = runtime.ephemeris_call
    calls = 0

    def broken(*args, **kwargs):
        nonlocal calls
        values, flags = original(*args, **kwargs)
        calls += 1
        if problem == "frame":
            flags ^= runtime.swe.FLG_EQUATORIAL
        elif problem == "model":
            flags = (flags & ~runtime.swe.FLG_SWIEPH) | runtime.swe.FLG_MOSEPH
        elif problem == "values":
            values = (float("nan"), *values[1:])
        elif problem == "configuration":
            monkeypatch.setenv("SE_EPHE_PATH", "/changed-after-solar-sample")
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", broken)
    with pytest.raises(EphemerisSourceError):
        solar.apparent_position_policy(
            2459892.375, {"Mercury": "swieph"}, PhysicalEphemerisTrace()
        )
    assert calls > 0


@pytest.mark.parametrize(
    "epoch,planet,domain",
    [
        (2459892.375, "Mercury", "behind_solar_disc"),
        (2460465.875, "Venus", "behind_solar_disc"),
        (2457518.125, "Mercury", "foreground_of_solar_disc"),
    ],
)
def test_real_source_geometry_is_typed_and_leaves_the_native_tuple_unchanged(
    epoch, planet, domain
):
    flags = runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    body = getattr(runtime.swe, planet.upper())
    raw, returned = runtime.ephemeris_call("calc", epoch, body, flags)
    model = runtime.ephemeris_model_from_retflag(returned)
    assert model == "swieph", "This numerical control requires the packaged Swiss files"
    policy = solar.apparent_position_policy(
        epoch, {planet: model}, PhysicalEphemerisTrace()
    )
    ApparentPositionPolicy.model_validate(policy)
    assert policy["method_id"] == "native_apparent_solar_disc_conventions_v2"
    regularity = policy["source_model_regularity"]
    assert regularity["axis_continuity_certified"] is False
    assert regularity["unique_rate_at_mass_knots_certified"] is False
    assert regularity["profile"] == "native_eff_arr_linear_interpolation_v1"
    assert "virtual continuous" not in policy["scope"]
    assert policy["bodies"][planet]["unbent_ray_domain"] == domain
    assert runtime.ephemeris_call("calc", epoch, body, flags)[0] == raw


def test_independent_solar_position_reference_bytes_are_preserved():
    root = Path(__file__).parents[1]
    wanted = {
        "tests/fixtures/western-solar-position-protocol.json": "064ebd6f554cd94b2a3c3471a1f82d7afc4edf4abeabf1e76d2aac180e516973",
        "tests/fixtures/western-solar-position-horizons.json": "de2a112a588aad555916969edd49849a31ba7e8ae829926ef86861bd54e2ea6f",
    }
    for name, digest in wanted.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_event_history_receipt_is_explicitly_only_at_the_question_epoch(monkeypatch):
    from fatebridge.core import horary_events

    epoch = 2459892.375

    def finite_history(at, sample):
        return {
            "question_states": {p: sample(p, at) for p in horary_events.BODIES},
            "events": [],
            "status": "computed",
        }

    monkeypatch.setattr(horary_events, "solve_planetary_events", finite_history)
    result = horary_events.native_planetary_events(
        SimpleNamespace(julian_day_tt=epoch, zodiac_type="Tropic")
    )
    policy = result["apparent_position_policy"]
    assert policy["epoch_jd_tt"] == epoch
    assert policy["bodies"]["Mercury"]["unbent_ray_domain"] == "behind_solar_disc"
    assert "not a full event-window policy" in policy["scope"]
