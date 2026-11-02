"""Frozen model reference and adversarial local-source derivative controls."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import position_motion as motion
from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.solar_motion_branch import solar_interpolation_branch
from fatebridge.core.output_charts import CompletePositionMotion
from fatebridge.utils.errors import EphemerisSourceError
from tests.ephemeris_case_runtime import native_ephemeris_files

FIXTURES = Path(__file__).parent / "fixtures"


def test_reference_was_sealed_before_production_changes():
    wanted = {
        "western-solar-disc-motion-protocol.json": "1df6532ce9914a4f67380bf90896c94f4c221e445bd60db21994055b9ca92497",
        "western-solar-disc-motion-reference.json": "2679711e81a769c22dfeee8a75d327d543f0d9aa7eaad1b876d4895fe04096b1",
        "western-solar-disc-branch-policy.json": "ad1602ed3dee4e1661d3749e300ed7d428c5c5e6168742e9ab5525f1ab2aabb6",
    }
    for name, digest in wanted.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
    reference = json.loads(
        (FIXTURES / "western-solar-disc-motion-reference.json").read_text()
    )
    assert len(reference["rows"]) == 84
    assert reference["candidate_imports"] is False
    assert reference["independent_ephemeris"] is False
    assert reference["independent_model_reduction"] is True
    assert all(row["reference_converged"] for row in reference["rows"])


@pytest.mark.parametrize("count", [13, 25])
@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("power", range(7))
def test_one_sided_fit_has_degree_six_exactness_at_wrap(count, direction, power):
    nodes = motion.DIRECTIONAL_POLYNOMIALS[count][0]
    step = 0.0625
    center = 359.9 + (1 if power == 0 else 0)
    values = [(359.9 + (direction * x * step) ** power) % 360 for x in nodes]
    value = motion.one_sided_polynomial_stencil(values, center, step, direction)
    assert value == pytest.approx(1 if power == 1 else 0, abs=3e-11)


@pytest.mark.parametrize("epoch", [0.0, 2451545.0, 5373484.25])
@pytest.mark.parametrize("longitude", [0.0, 74.0, 226.0, 359.99])
def test_refinement_budget_is_derived_from_representability_not_known_dates(
    epoch, longitude
):
    steps, policy = motion.refinement_budget(epoch, longitude)
    assert steps[-1] >= policy["estimated_roundoff_floor_days"]
    assert steps[-1] / 2 < policy["estimated_roundoff_floor_days"]
    assert steps[-1] >= 64 * math.ulp(epoch)
    assert all(b == a / 2 for a, b in zip(steps, steps[1:]))
    for step in steps:
        for direction in [-1, 1]:
            for node in motion.DIRECTIONAL_POLYNOMIALS[25][0]:
                delta = direction * node * step
                assert (epoch + delta) - epoch == delta


def test_a_known_nearby_source_knot_allows_only_the_homogeneous_direction():
    def provider(delta):
        return 100 + 0.4 * delta + 2 * max(0, delta - 1e-5)

    def branch(delta):
        return {"cell": 5 if delta < 1e-5 else 6}

    result = motion.homogeneous_side_derivative(
        [2.0**-i for i in range(5, 16)], provider, branch
    )
    assert result["status"] == "converged"
    assert result["eligible_directions"] == [-1]
    assert abs(result["selected_rate"] - 0.4) * 3600 < 0.0002
    assert result["required_consecutive_levels"] == 3
    assert all(
        side["eligible"] is False
        for level in result["levels"]
        for side in level["sides"]
        if side["direction"] == 1
    )


def test_an_unknown_center_never_becomes_an_unconstrained_one_sided_escape():
    result = motion.homogeneous_side_derivative(
        [0.1, 0.05, 0.025],
        lambda _: pytest.fail("No derivative without a verified interior cell"),
        lambda _: {"cell": None},
    )
    assert result["status"] == "not_converged" and not result["levels"]


def test_all_eligible_sides_must_agree_even_if_one_would_give_a_desired_answer():
    result = motion.homogeneous_side_derivative(
        [2.0**-i for i in range(5, 17)],
        lambda x: 100 + 0.4 * x + abs(x),
        lambda _: {"cell": 5},
    )
    assert result["status"] == "not_converged"
    assert all(row["eligible_directions"] == [1, -1] for row in result["levels"])
    assert result["levels"][-1]["disagreement_arcsec_per_day"] > 0.0002


def test_direction_set_changes_reset_three_level_evidence():
    branch = lambda x: {"cell": 5 if x < 0.5 else 6}
    provider = lambda x: 100 + 0.4 * x
    result = motion.homogeneous_side_derivative(
        [0.25, 0.125, 0.0625, 0.03125], provider, branch
    )
    assert result["status"] == "not_converged"
    result = motion.homogeneous_side_derivative(
        [0.25, 0.125, 0.0625, 0.03125, 0.015625], provider, branch
    )
    assert result["status"] == "converged" and result["eligible_directions"] == [1, -1]


@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize(
    "planet,epoch", [("Venus", 2460465.8966340744), ("Mercury", 2459892.46875)]
)
def test_real_old_failure_or_false_plateau_has_a_typed_fixed_line_receipt(
    planet, epoch, sidereal, native_ephemeris_files
):
    swe = runtime.swe
    with runtime.preserve_ephemeris_path():
        runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)
        raw, returned = runtime.ephemeris_call(
            "calc", epoch, getattr(swe, planet.upper()), flags
        )
        model = runtime.ephemeris_model_from_retflag(returned)
        if model != "swieph":
            pytest.skip(
                "Source-model numerical checks require the disclosed Swiss files"
            )
        rate, policy = motion.complete_position_rate(
            planet, epoch, raw, model, sidereal=sidereal
        )
        CompletePositionMotion.model_validate(policy)
        assert (
            math.isfinite(rate) and policy["convergence_line_arcsec_per_day"] == 0.0002
        )
        assert (
            runtime.ephemeris_call("calc", epoch, getattr(swe, planet.upper()), flags)[
                0
            ]
            == raw
        )
        if planet == "Mercury":
            branch = policy["source_branch_motion"]
            assert branch["status"] == "converged"
            assert branch["levels"][-1]["disagreement_arcsec_per_day"] <= 0.0002
            assert len(branch["levels"][-1]["eligible_directions"]) >= 1
            assert (
                policy["sampling_stabilization"]["symmetric_stabilized_attempt"][
                    "status"
                ]
                == "not_converged"
            )
        else:
            check = policy["directional_checks"][-1]
            assert check["passed"] and check["disagreement_arcsec_per_day"] <= 0.0002


@pytest.mark.parametrize("problem", ["model", "frame", "values", "configuration"])
def test_solar_cell_probe_retains_physical_source_guards(
    problem, monkeypatch, native_ephemeris_files
):
    original = runtime.ephemeris_call
    raw, ret = original(
        "calc",
        2459892.46875,
        runtime.swe.MERCURY,
        runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
    )
    if runtime.ephemeris_model_from_retflag(ret) != "swieph":
        pytest.skip("Physical Swiss files required for source guard test")

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        if problem == "model":
            flags = flags & ~runtime.swe.FLG_SWIEPH | runtime.swe.FLG_MOSEPH
        elif problem == "frame":
            flags ^= runtime.swe.FLG_EQUATORIAL
        elif problem == "values":
            values = (math.nan,) * 6
        else:
            monkeypatch.setenv("SE_EPHE_PATH", "/controlled-changed-configuration")
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError):
        solar_interpolation_branch(
            "Mercury", 2459892.46875, "swieph", PhysicalEphemerisTrace(), {}, "guard"
        )


def test_a_solar_mass_knot_is_not_certified_as_an_interior_cell(monkeypatch):
    swe = runtime.swe
    radius = math.radians(959.63 / 3600)
    sine = 0.37 * radius

    def sample(operation, epoch, body, flags):
        if body == swe.EARTH:
            values = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        elif body == swe.SUN:
            values = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            values = (-math.sqrt(1 - sine * sine), sine, 0.0, 0.0, 0.0, 0.0)
        returned = flags | swe.FLG_NONUT
        if flags & swe.FLG_TRUEPOS:
            returned |= swe.FLG_NOABERR | swe.FLG_NOGDEFL
        return values, returned

    class Trace:
        def observe(self, *args, **kwargs):
            return {"model": "swieph"}

    monkeypatch.setattr(runtime, "ephemeris_call", sample)
    result = solar_interpolation_branch(
        "Mercury", 2451545.0, "swieph", Trace(), {}, "knot"
    )
    assert result["status"] == "boundary_ambiguous" and result["cell"] is None
