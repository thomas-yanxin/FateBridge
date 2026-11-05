"""Named-source row predicates, counterexamples and retained source conflicts."""

import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.lilly_fortitude_inputs import collect_fortitude_inputs
from fatebridge.core.lilly_fortitudes import ORDER, bodily_between, evaluate_fortitudes
from fatebridge.core.output_western import LillyFortitudes
from fatebridge.utils.errors import EphemerisSourceError
from scripts.western.audit_western_lilly_fortitudes import audit, worked_inputs

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-lilly-fortitudes-1647.json"
    ).read_text()
)


def inputs():
    states, data = worked_inputs(REFERENCE)
    return copy.deepcopy(states), copy.deepcopy(data)


def result(states, data):
    return evaluate_fortitudes(
        states, "day", data, house_system="R", zodiac_type="Tropic"
    )


def row(value, planet, code):
    return next(r for r in value["planets"][planet]["rows"] if r["code"] == code)


def test_all_original_rows_and_mean_motion_units_are_frozen_before_candidate():
    base = Path(__file__).parents[1] / "fixtures"
    assert (
        hashlib.sha256(
            (base / "western-lilly-fortitudes-1647.json").read_bytes()
        ).hexdigest()
        == "31a64976c3ca8650de975cf53cf76972741788dc81f51021278087f8ef962f6e"
    )
    assert (
        hashlib.sha256(
            (base / "western-lilly-fortitudes-sources.zip").read_bytes()
        ).hexdigest()
        == "0cea6669b1d9f96e9583772da8002813149282e189be2029165c45c1e153d2cc"
    )
    assert REFERENCE["production_imports"] is False
    assert len(REFERENCE["rows"]) == 41
    assert REFERENCE["mean_daily_motion_arcseconds"]["Mars"] == 31 * 60 + 27


def test_the_entire_printed_example_keeps_its_failed_acceptance_and_row_differences():
    evidence = audit()
    assert evidence["source_assets_checked"] == 46
    assert evidence["row_table_matches"] and evidence["mean_motion_table_matches"]
    assert evidence["planetary_applications_compared"] == 7
    assert evidence["planetary_applications_reproduced"] == 3
    assert evidence["worked_example_reproduction_passed"] is False
    assert {r["planet"] for r in evidence["comparisons"] if not r["reproduced"]} == {
        "Sun",
        "Jupiter",
        "Mercury",
        "Moon",
    }
    assert evidence["full_original_text_acceptance"] is False
    LillyFortitudes.model_validate(evidence["candidate"])


@pytest.mark.parametrize("planet", ["Sun", "Moon"])
def test_always_direct_luminaries_receive_no_direct_motion_bonus(planet):
    states, data = inputs()
    r = row(result(states, data), planet, "F06")
    assert r["applicable"] is False and r["contribution"] == 0
    assert r["satisfied"] is None and r["status"] == "not_applicable"


@pytest.mark.parametrize("planet", ORDER)
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_exact_daily_comparison_never_rounds_both_sides_into_the_same_outcome(
    planet, side
):
    states, data = inputs()
    mean = Fraction(REFERENCE["mean_daily_motion_arcseconds"][planet], 3600)
    # Distinct dyadic values either side of the threshold can round to one
    # displayed float. Their supplied-value fractions remain distinguishable.
    scale = 2**90
    floor = (mean.numerator * scale) // mean.denominator
    exact = mean if side == 0 else Fraction(floor + (1 if side > 0 else 0), scale)
    data["motion"][planet]["daily_motion_degrees"] = float(exact)
    data["motion"][planet]["daily_motion_exact_degrees"] = str(exact)
    value = result(states, data)
    assert row(value, planet, "F07")["satisfied"] is (side > 0)
    assert row(value, planet, "D04")["satisfied"] is (side < 0)


def test_instantaneous_rate_is_not_substituted_for_actual_daily_displacement():
    states, data = inputs()
    p = data["motion"]["Mercury"]
    p.update(
        daily_motion_degrees=0.25,
        daily_motion_exact_degrees="1/4",
        instantaneous_speed_degrees_per_day=2.0,
    )
    value = result(states, data)
    assert row(value, "Mercury", "D04")["satisfied"] is True
    assert row(value, "Mercury", "F07")["satisfied"] is False
    p["daily_motion_exact_degrees"] = "1/2"
    with pytest.raises(ValueError, match="receipt differ"):
        result(states, data)


@pytest.mark.parametrize("direction,code", [("direct", "F06"), ("retrograde", "D03")])
def test_direction_and_retrograde_displacement_magnitude_are_separate(direction, code):
    states, data = inputs()
    data["motion"]["Saturn"].update(
        direction=direction,
        daily_motion_degrees=-0.1,
        daily_motion_exact_degrees="-1/10",
    )
    value = result(states, data)
    assert row(value, "Saturn", code)["satisfied"] is True
    assert row(value, "Saturn", "F07")["satisfied"] is True


def test_grouped_benefics_count_once_and_self_conjunction_never_awards_points():
    states, data = inputs()
    for p in ["Sun", "Jupiter", "Venus"]:
        states[p]["longitude"] = 100
    value = result(states, data)
    assert row(value, "Sun", "F13")["contribution"] == 5
    states["Venus"]["longitude"] = 110
    assert row(result(states, data), "Jupiter", "F13")["satisfied"] is False


@pytest.mark.parametrize(
    "gap,expected",
    [(Fraction(0), True), (Fraction(1, 60), False), (Fraction(1, 2), False)],
)
def test_partile_is_exact_source_ray_and_does_not_inherit_a_one_degree_orb(
    gap, expected
):
    states, data = inputs()
    states["Mars"]["longitude"] = 100
    states["Jupiter"]["longitude"] = 100 + gap
    states["Venus"]["longitude"] = 20
    assert row(result(states, data), "Mars", "F13")["satisfied"] is expected


@pytest.mark.parametrize(
    "distance,code",
    [
        (Fraction(1, 10), "F12"),
        (Fraction(5), "D08"),
        (Fraction(16), "D09"),
        (Fraction(17), "F11"),
    ],
)
def test_solar_conditions_do_not_stack_clear_combust_and_cazimi_credits(distance, code):
    states, data = inputs()
    states["Sun"]["longitude"] = 100
    states["Mercury"]["longitude"] = 100 + distance
    value = result(states, data)
    assert row(value, "Mercury", code)["satisfied"] is True
    assert (
        sum(
            row(value, "Mercury", c)["satisfied"] is True
            for c in ["F12", "D08", "D09", "F11"]
        )
        == 1
    )
    for c in ["F12", "D08", "D09", "F11"]:
        assert row(value, "Sun", c)["status"] == "not_applicable"


@pytest.mark.parametrize("sun,mercury,code", [(359, 1, "F09"), (1, 359, "D06")])
def test_orientality_crosses_zodiac_zero_without_reversing_meaning(sun, mercury, code):
    states, data = inputs()
    states["Sun"]["longitude"] = sun
    states["Mercury"]["longitude"] = mercury
    assert row(result(states, data), "Mercury", code)["satisfied"] is True


@pytest.mark.parametrize("elongation", [0, 180])
def test_exact_new_and_full_moon_boundaries_remain_unknown(elongation):
    states, data = inputs()
    states["Moon"]["longitude"] = states["Sun"]["longitude"] + elongation
    value = result(states, data)
    assert row(value, "Moon", "F10")["status"] == "unknown"
    assert row(value, "Moon", "D07")["contribution"] is None
    assert value["summary"]["Moon"]["literal_table_balance"] is None


@pytest.mark.parametrize(
    "target,first,second,expected",
    [
        (13, 15, 10, True),
        (359, 350, 10, True),
        (100, 10, 190, None),
        (10, 10, 15, False),
        (80, 10, 100, True),
    ],
)
def test_bodily_between_has_no_invented_fifteen_degree_cap(
    target, first, second, expected
):
    assert (
        bodily_between(Fraction(target), Fraction(first), Fraction(second)) is expected
    )


@pytest.mark.parametrize(
    "star,code,orb", [("Regulus", "F17", 6), ("Spica", "F18", 5), ("Algol", "D15", 5)]
)
def test_distinct_stellar_ranges_use_corrected_source_and_exact_boundary(
    star, code, orb
):
    states, data = inputs()
    lon = data["star_longitudes"][star]
    states["Mercury"]["longitude"] = lon + orb
    assert row(result(states, data), "Mercury", code)["satisfied"] is True
    states["Mercury"]["longitude"] = math.nextafter(lon + orb, math.inf)
    assert row(result(states, data), "Mercury", code)["satisfied"] is False


def test_missing_physical_facts_remain_unknown_and_do_not_create_a_full_balance():
    states, _ = inputs()
    value = result(states, {})
    for p in ORDER:
        assert len(value["planets"][p]["rows"]) == 41
        assert value["summary"][p]["literal_table_balance"] is None
        assert row(value, p, "F07")["contribution"] is None
        assert row(value, p, "F14")["satisfied"] is None
    assert value["full_original_text_acceptance"] is False


def test_absent_epoch_does_not_fabricate_daily_motion_or_fixed_star_positions():
    data = collect_fortitude_inputs(SimpleNamespace())
    assert data["status"] == "not_computed" and data["motion"] == {}
    assert data["north_node_longitude"] is None and data["star_longitudes"] == {}


def subject():
    from datetime import datetime

    from fatebridge.core.predictive.native_chart import build_native_subject

    return build_native_subject(
        name="daily motion control",
        local_datetime=datetime.fromisoformat("2024-06-01T06:30:00+00:00"),
        longitude=116.4,
        latitude=39.9,
        timezone_name="UTC",
        house_system="R",
    )


def test_native_daily_samples_and_dated_stars_preserve_the_native_coordinates():
    s = subject()
    swe = runtime.swe
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    before = runtime.ephemeris_call("calc", s.julian_day_tt, swe.MERCURY, flags)
    data = collect_fortitude_inputs(s)
    assert data["status"] == "computed" and set(data["star_longitudes"]) == {
        "Regulus",
        "Spica",
        "Algol",
    }
    assert data["star_position_policy"] == "dated_native_apparent_positions"
    for p, r in data["motion"].items():
        assert len(r["samples"]) == 5
        assert (
            float(Fraction(r["daily_motion_exact_degrees"]))
            == r["daily_motion_degrees"]
        )
        assert r["samples"][0]["longitude"] == pytest.approx(
            s.points[p.lower()].abs_pos, abs=2e-12
        )
    assert runtime.ephemeris_call("calc", s.julian_day_tt, swe.MERCURY, flags) == before


@pytest.mark.parametrize(
    "problem", ["backend", "configuration", "star_observer_model", "nominal_position"]
)
def test_daily_input_sampling_cannot_hide_a_source_change(problem, monkeypatch):
    import fatebridge.core.lilly_fortitude_inputs as module

    s = subject()
    if problem == "nominal_position":
        from dataclasses import replace

        s = replace(
            s,
            points={
                **s.points,
                "mercury": replace(s.mercury, abs_pos=s.mercury.abs_pos + 1),
            },
        )
    if problem == "star_observer_model":
        original = module.apparent_positions

        def changed(*a, **k):
            p, r = original(*a, **k)
            r["earth_ephemeris_model"] = "incompatible"
            return p, r

        monkeypatch.setattr(module, "apparent_positions", changed)
    elif problem != "nominal_position":
        original = module._swisseph_planet_state

        def changed(*a, **k):
            v, m = original(*a, **k)
            if problem == "configuration":
                monkeypatch.setenv("SE_EPHE_PATH", "/changed-during-daily-sampling")
            return v, "incompatible" if problem == "backend" else m

        monkeypatch.setattr(module, "_swisseph_planet_state", changed)
    with pytest.raises(EphemerisSourceError):
        collect_fortitude_inputs(s)
