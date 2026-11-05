"""Independent full-state reference, nonunit clocks and spherical singularities."""

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

from fatebridge.core.astro import continuous_lahiri as frame

REFERENCE_PATH = (
    Path(__file__).parents[1] / "fixtures/jyotish-continuous-state-reference-v1.json"
)
assert (
    hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
    == "795db1c5613325aa39e3cec48d5b44b9d47fffcc05599bc98bc7e8702d67194d"
)
REFERENCE = json.loads(REFERENCE_PATH.read_text())


def test_published_state_is_already_a_valid_JSON_value():
    result = frame.project_state(
        2451545.0, (1, 2, 3), (0.1, 0.2, 0.3), vector_rate_scale=1
    )
    assert TypeAdapter(JsonValue).validate_python(result) == result


def test_complete_all5180_independent_state_projections_and_clock_controls():
    assert REFERENCE["candidate_or_production_imported"] is False
    assert REFERENCE["summary"]["projection_cases"] == 5180
    assert REFERENCE["summary"]["precision_crosscheck_failures"] == 0
    failures = []
    wrong_uniform_rejected = 0
    no_frame_rejected = 0
    for row in REFERENCE["rows"]:
        gamma = float(Fraction(row["vector_rate_scale_rational"]))
        result = frame.project_state(
            row["epoch_jd_tt"],
            row["inertial_position"],
            row["inertial_velocity"],
            vector_rate_scale=gamma,
        )
        expected = row["expected"]
        a, b = result["spherical"], expected["spherical"]
        error = (
            max(
                abs(
                    math.remainder(a["longitude_degrees"] - b["longitude_degrees"], 360)
                ),
                abs(a["latitude_degrees"] - b["latitude_degrees"]),
            )
            * 3600
        )
        rate_error = (
            max(
                abs(a[k] - b[k])
                for k in [
                    "longitude_rate_degrees_per_day",
                    "latitude_rate_degrees_per_day",
                ]
            )
            * 3600
        )
        if error > 1e-7 or rate_error > 1e-6:
            failures.append((row["native_case_index"], gamma, error, rate_error))
        for key in ["position", "velocity_per_TT_day"]:
            assert max(abs(x - y) for x, y in zip(result[key], expected[key])) <= 1e-12
        assert abs(a["radius"] - b["radius"]) <= 1e-12
        assert abs(a["radial_rate_per_day"] - b["radial_rate_per_day"]) <= 1e-12
        for factor, kind in [(-1, "omit"), (gamma - 1, "uniform")]:
            mutant = [
                v + factor * s
                for v, s in zip(
                    expected["velocity_per_TT_day"], expected["frame_motion_per_TT_day"]
                )
            ]
            bad = frame.spherical_state(expected["position"], mutant)
            rejected = (
                max(
                    abs(bad[k] - b[k])
                    for k in [
                        "longitude_rate_degrees_per_day",
                        "latitude_rate_degrees_per_day",
                    ]
                )
                * 3600
                > 1e-6
            )
            if kind == "omit":
                no_frame_rejected += rejected
            elif row["vector_rate_scale_rational"] in {"2", "1/2"}:
                wrong_uniform_rejected += rejected
    assert not failures, failures
    assert no_frame_rejected == 5180
    assert wrong_uniform_rejected > 0


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf"), True, 1721425.0, 5373486.0]
)
def test_invalid_epochs_are_not_replaced_by_default_values(bad):
    with pytest.raises(ValueError):
        frame.frame_state(bad)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_velocity_mapping_must_be_explicit_finite_and_positive(bad):
    with pytest.raises(ValueError):
        frame.project_state(2451545.0, (1, 0, 0), (0, 1, 0), vector_rate_scale=bad)


@pytest.mark.parametrize(
    "position", [(0, 0, 0), (float("nan"), 0, 0), (1, 2), (True, 0, 0)]
)
def test_invalid_cartesian_states_do_not_produce_spherical_claims(position):
    with pytest.raises(ValueError):
        frame.project_state(2451545.0, position, (0, 1, 0), vector_rate_scale=1)


@pytest.mark.parametrize("sign", [-1, 1])
def test_poles_retain_vectors_without_fabricating_longitude_or_derivatives(sign):
    result = frame.spherical_state((0, 0, sign), (1, 0, 2))
    assert result["longitude_degrees"] is None
    assert result["longitude_rate_degrees_per_day"] is None
    assert result["latitude_rate_degrees_per_day"] is None
    assert result["latitude_degrees"] == sign * 90
    assert result["radial_rate_per_day"] == sign * 2


def test_business_endpoints_are_in_the_declared_frame_domain():
    times = {row["epoch_jd_tt"] for row in REFERENCE["rows"]}
    assert 1721425.622066106 in times
    assert 5373484.500800741 in times
    for tt in [1721425.622066106, 5373484.500800741]:
        assert frame.frame_state(tt)["epoch_jd_tt"] == tt
