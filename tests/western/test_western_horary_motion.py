"""Frozen primary-text cases, independent JPL events and analytical controls."""

import json
import math
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.astrology_horary import (
    _applying_aspect,
    _moon_void_of_course,
    _planet_state,
)
from fatebridge.core.astro.horary_motion import (
    native_lunar_contacts,
    solve_lunar_contacts,
)
from fatebridge.core.classical_western import (
    build_classical_patterns,
    combustion_state,
    ptolemy_latitude_condition,
)
from fatebridge.services.western_horary import calculate_horary
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.lunar_sampler import sampled_motion
from tests.unit_test.fixtures.western_event_cases import QUESTION, state

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROTOCOL = json.loads((FIXTURES / "western-horary-motion-protocol.json").read_text())
REFERENCE = json.loads((FIXTURES / "western-horary-horizons.json").read_text())
SOURCE = json.loads((FIXTURES / "western-lilly-motion-1647.json").read_text())
SOLAR = json.loads((FIXTURES / "western-lilly-solar-1647.json").read_text())


def test_missing_native_motion_stays_unknown_despite_known_instantaneous_speeds() -> (
    None
):
    result = _moon_void_of_course(state("Moon", 0, 13), [state("Mercury", 0.1, 0)])
    assert result["void_of_course"] is None
    assert result["next_aspect"] is None
    assert result["motion_basis"]["status"] == "unavailable"
    assert result["motion_basis"]["constant_velocity_projection"] is False


def test_current_numerical_solver_matches_exact_dyadic_contact_and_ingress() -> None:
    result = sampled_motion(state("Moon", 0, 16), [state("Mercury", 1, 0)])
    assert result["void_of_course"] is False
    assert result["contacts"][0]["after_days"] == 1 / 16
    assert result["sign_exit_after_days"] == 30 / 16


def test_solar_definitions_follow_the_printed_seventeen_degree_and_sign_conditions() -> (
    None
):
    for row in SOLAR["cases"]:
        assert combustion_state(row["planet"], row["sun"]) == row["expected"]
    for value in (math.nextafter(17.0, 0), 17.0, math.nextafter(17.0, math.inf)):
        expected = "under_beams" if value < 17 else None
        assert combustion_state(value, 0.0) == expected
    assert combustion_state(31.0, 29.0) == "under_beams"
    assert combustion_state(31.0, 32.0) == "combust"


def test_printed_ten_degree_example_is_retained_as_unresolved_not_fitted() -> None:
    row = SOLAR["unresolved_printed_example"]
    assert combustion_state(row["planet"], row["sun"]) == row["definition_state"]
    assert row["printed_state"] != row["definition_state"]
    assert SOLAR["full_page_acceptance"] is False


def test_original_horary_overshoot_is_applying_and_exact_is_not_separating() -> None:
    assert (
        _applying_aspect(state("Moon", 0, 13), state("Sun", 0.1, 0))["phase"]
        == "applying"
    )
    for speed, other_speed, expected in (
        (13, 0, "exact"),
        (1, 1, "exact"),
        (None, 0, "unavailable"),
    ):
        result = _applying_aspect(state("Moon", 0, speed), state("Sun", 0, other_speed))
        assert result["phase"] == expected and result["applying"] is None
    stationary = _applying_aspect(state("Moon", 0, 1), state("Sun", 0.1, 1))
    assert stationary["phase"] == "stationary" and stationary["applying"] is None


def test_horary_uses_unrounded_native_state_and_never_guesses_missing_speed() -> None:
    point = SimpleNamespace(
        sign="Pisces", abs_pos=math.nextafter(360.0, 0), speed=-1e-09
    )
    result = _planet_state(SimpleNamespace(mercury=point), "Mercury")
    assert result["longitude"] < 360 and result["degree"] < 30
    assert result["speed"] == -1e-09 and result["retrograde"] is True
    del point.speed
    result = _planet_state(SimpleNamespace(mercury=point), "Mercury")
    assert result["speed"] is None and result["retrograde"] is None


def test_moving_target_and_outside_current_orb_counterexamples() -> None:
    result = _moon_void_of_course(
        state("Moon", 29, 13),
        [state("Mars", 29.9, 2)],
        physical_motion=sampled_motion(state("Moon", 29, 13), [state("Mars", 29.9, 2)]),
    )
    assert result["void_of_course"] is True
    result = _moon_void_of_course(
        state("Moon", 0, 13),
        [state("Mercury", 25, 0)],
        physical_motion=sampled_motion(state("Moon", 0, 13), [state("Mercury", 25, 0)]),
    )
    assert result["void_of_course"] is False
    assert result["next_aspect"]["inside_current_orb"] is False
    assert result["next_aspect"]["after_days"] == 25 / 13
    assert result["motion_basis"]["constant_velocity_projection"] is False


def test_time_order_is_not_orb_order() -> None:
    result = _moon_void_of_course(
        state("Moon", 0, 13),
        [state("Venus", 2.8, 1.2), state("Mercury", 3, -1)],
        physical_motion=sampled_motion(
            state("Moon", 0, 13), [state("Venus", 2.8, 1.2), state("Mercury", 3, -1)]
        ),
    )
    assert result["next_aspect"]["other"] == "Mercury"
    assert result["next_aspect"]["after_days"] == 3 / 14


def test_overlapping_lunar_contact_brackets_keep_existence_without_a_first_role() -> (
    None
):
    epoch = 2451545.0
    resolution = math.ulp(epoch)
    moon = state("Moon", 0, 16)
    targets = [
        state("Venus", 1 - 12 * resolution, 0),
        state("Mercury", 1 - 4 * resolution, 0),
    ]
    by_name = {row["planet"]: row for row in targets}

    def sample(planet, at):
        if planet == "Moon":
            return {"longitude": 16 * (at - epoch), "speed": 16.0, "latitude": 0.0}
        else:
            pass
        return {**by_name[planet], "latitude": 0.0}

    motion = solve_lunar_contacts(epoch, sample, bodies=("Venus", "Mercury"))
    shown = _moon_void_of_course(moon, targets, physical_motion=motion)
    upper = epoch + 1 / 16
    contacts = shown["motion_basis"]["contacts"]
    assert {row["other"] for row in contacts} == {"Venus", "Mercury"}
    assert all(
        row["root_bracket_tt"] == [upper - resolution, upper] for row in contacts
    )
    assert shown["void_of_course"] is False
    assert shown["next_aspect"] is None


@pytest.mark.parametrize(
    "profile,sun_longitude,limit",
    [("lilly_1647_p107_second", 14.0, 13.5), ("lilly_1647_p107_first", 15.25, 14.75)],
)
def test_future_contact_inside_current_orb_flag_is_classified_before_rounding(
    profile: str, sun_longitude: float, limit: float
) -> None:
    moon = state("Moon", math.nextafter(0.5, 0), 13.0)
    sun = state("Sun", sun_longitude, 0.0)
    assert _applying_aspect(moon, sun, orb_profile=profile) is None
    result = _moon_void_of_course(
        moon, [sun], orb_profile=profile, physical_motion=sampled_motion(moon, [sun])
    )
    assert result["void_of_course"] is False
    assert result["next_aspect"]["orb_limit"] == limit
    assert result["next_aspect"]["inside_current_orb"] is False


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda row: row["case_id"])
def test_native_ingress_and_all_contacts_match_independent_jpl(case) -> None:
    assert PROTOCOL["comparison_tolerance_event_seconds"] == 30
    result = native_lunar_contacts(
        SimpleNamespace(julian_day_tt=case["start_julian_day_tt"], zodiac_type="Tropic")
    )
    assert result["status"] == "computed", result
    assert result["constant_velocity_projection"] is False
    assert result["void_of_course"] == case["expected"]["void_of_course"]
    assert (
        abs(
            result["sign_exit_julian_day_tt"]
            - case["expected"]["sign_exit_julian_day_tt"]
        )
        * 86400
        <= PROTOCOL["comparison_tolerance_event_seconds"]
    )
    actual, expected = (result["contacts"], case["expected"]["contacts"])
    assert [(r["other"], r["ray_degrees"]) for r in actual] == [
        (r["other"], r["ray_degrees"]) for r in expected
    ]
    for row, reference in zip(actual, expected):
        assert (
            abs(row["julian_day_tt"] - reference["julian_day_tt"]) * 86400
            <= PROTOCOL["comparison_tolerance_event_seconds"]
        )
        assert row["root_bracket_tt"][1] <= result["sign_exit_root_bracket_tt"][0]
        assert math.nextafter(*row["root_bracket_tt"]) == row["root_bracket_tt"][1]


def test_native_root_solver_handles_acceleration_not_only_linear_orb() -> None:
    epoch = 2451545.0

    def sample(planet, at):
        days = at - epoch
        if planet == "Moon":
            return {
                "longitude": (10 + 12 * days + 0.5 * days * days) % 360,
                "speed": 12 + days,
                "latitude": 1.0,
            }
        else:
            pass
        return {"longitude": 25.0, "speed": 0.0, "latitude": -1.0}

    result = solve_lunar_contacts(epoch, sample, bodies=("Mars",))
    with localcontext() as ctx:
        ctx.prec = 80
        exit_days = -12 + Decimal(144 + 40).sqrt()
        contact_days = -12 + Decimal(144 + 30).sqrt()
    assert abs(result["sign_exit_after_days"] - float(exit_days)) < 1e-08
    assert abs(result["contacts"][0]["after_days"] - float(contact_days)) < 1e-08


def test_simultaneous_contact_and_ingress_are_unknown_at_jd_resolution() -> None:
    epoch = 2451545.0

    def sample(planet, at):
        return {
            "longitude": (29 + 13 * (at - epoch)) % 360 if planet == "Moon" else 30.0,
            "speed": 13.0 if planet == "Moon" else 0.0,
            "latitude": 0.0,
        }

    result = solve_lunar_contacts(epoch, sample, bodies=("Mars",))
    assert result["status"] == "boundary_ambiguous"
    assert result["void_of_course"] is None
    assert not result["contacts"] and result["ambiguous_boundary_contacts"]


def test_failed_native_search_remains_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    import fatebridge.core.astro.horary_motion as motion

    monkeypatch.setattr(motion, "_swisseph_planet_state", lambda *a, **k: None)
    result = native_lunar_contacts(
        SimpleNamespace(julian_day_tt=2451545.0, zodiac_type="Tropic")
    )
    assert result["status"] == "unavailable" and result["void_of_course"] is None


def test_original_p111_example_is_not_excluded_by_endpoint_aspect() -> None:
    source = SOURCE["translation_p111_example"]
    planets = [
        {"id": p, "sign": "Aries", "longitude": v}
        for p, v in source["positions"].items()
    ]
    result = build_classical_patterns(
        planets,
        _build_aspects(planets),
        "day",
        speeds={"Saturn": 0.03, "Mars": 0.5, "Mercury": 1.5},
    )
    assert {
        "translator": source["expected_translator"],
        "from": source["expected_from"],
        "to": source["expected_to"],
    } in result["translation_of_light"]
    assert result["light_configuration_policy"]["translation_definition_page"] == 111
    assert (
        result["light_configuration_policy"]["full_original_text_acceptance"] is False
    )


def test_stationary_light_moon_cannot_be_lilly_heavier_collector() -> None:
    planets = [
        {"id": p, "sign": sign, "longitude": lon}
        for p, sign, lon in [
            ("Moon", "Aries", 10.0),
            ("Saturn", "Gemini", 69.0),
            ("Jupiter", "Cancer", 99.0),
        ]
    ]
    result = build_classical_patterns(
        planets,
        _build_aspects(planets),
        "day",
        speeds={"Moon": 0.0, "Saturn": 0.1, "Jupiter": 0.2},
    )
    assert not any((r["collector"] == "Moon" for r in result["collection_of_light"]))


def test_unrelated_missing_speed_does_not_erase_known_route_geometry() -> None:
    planets = [
        {"id": p, "sign": "Aries", "longitude": lon}
        for p, lon in [
            ("Saturn", 20.0),
            ("Mars", 15.0),
            ("Mercury", 16.0),
            ("Sun", 200.0),
        ]
    ]
    result = build_classical_patterns(
        planets,
        _build_aspects(planets),
        "day",
        speeds={"Saturn": 0.03, "Mars": 0.5, "Mercury": 1.5},
    )
    assert {"translator": "Mercury", "from": "Mars", "to": "Saturn"} in result[
        "translation_of_light"
    ]


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (1.0, 2.0, "same_hemisphere"),
        (1.0, -1.0, "opposite_hemispheres"),
        (0.0, -1.0, "same_hemisphere"),
        (math.ulp(0.0), -math.ulp(0.0), "opposite_hemispheres"),
        (None, 0.0, "missing_latitude"),
    ],
)
def test_ptolemy_bodily_latitude_condition_is_not_float_product_or_default_zero(
    a, b, expected: str
) -> None:
    assert ptolemy_latitude_condition(0.0, a, b)["status"] == expected
    assert (
        ptolemy_latitude_condition(60.0, a, b)["status"]
        == "not_required_for_aspect_ray"
    )


def test_service_preserves_native_events_and_same_body_condition() -> None:
    result = calculate_horary(**QUESTION, category="general")
    assert "error" not in result, result
    horary = result["horary"]
    assert horary["rule_profile"]["full_original_text_acceptance"] is False
    assert horary["perfection"]["status"] == "source_conditions_incomplete"
    assert horary["perfection"]["lilly_conditions"]["same_body_not_bilateral"] is True
    assert horary["moon"]["motion_basis"]["status"] == "computed"
    assert (
        horary["calculation_basis"]["julian_day_tt"]
        == horary["moon"]["motion_basis"]["start_julian_day_tt"]
    )


@pytest.mark.parametrize("failure", ["native_exception", "negative_flags", "nonfinite"])
def test_native_sidereal_offset_failure_never_becomes_a_linear_success(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        else:
            pass
        if failure == "native_exception":
            raise RuntimeError("Synthetic native offset failure")
        else:
            pass
        return (-1, 23.0) if failure == "negative_flags" else (2, math.nan)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(RuntimeError, match="Native Lahiri ayanamsha unavailable"):
        geometry.native_lahiri_ayanamsha(2451545.0)
    result = native_lunar_contacts(
        SimpleNamespace(julian_day_tt=2451545.0, zodiac_type="Sidereal")
    )
    assert result["status"] == "unavailable"
    assert result["void_of_course"] is None and result["contacts"] == []
    service = calculate_horary(**QUESTION, category="general", zodiac_type="Sidereal")
    assert service["error_code"] == "internal_error"
    assert "horary" not in service


def test_native_lahiri_keeps_selected_source_consistency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def changed(*args, **kwargs):
        raise EphemerisSourceError("physical_configuration_changed")

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        geometry.native_lahiri_ayanamsha(2451545.0)


def test_valid_native_lahiri_retains_values_and_sidereal_events() -> None:
    for epoch in (2451545.0, 2460462.7708333335, 2461335.5):
        assert geometry.native_lahiri_ayanamsha(epoch) == geometry._ayanamsha(epoch)
    result = calculate_horary(**QUESTION, category="general", zodiac_type="Sidereal")
    assert "error" not in result, result
    assert (
        result["horary"]["moon"]["motion_basis"]["longitude_frame"] == "sidereal_lahiri"
    )
    assert result["horary"]["moon"]["motion_basis"]["status"] == "computed"
