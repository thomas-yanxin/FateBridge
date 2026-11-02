"""Analytic clock/angle controls; no synthetic case is a celestial holdout."""

from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest

import scripts.astrodice_observer_radius_clock as producer
import scripts.verify_astrodice_observer_radius_clock as verifier


@pytest.mark.parametrize(
    "state,angles",
    [
        ([Q(1), Q(), Q(), Q(), Q(), Q()], ["0.000000000", "0.000000000"]),
        ([Q(1), Q(1), Q(), Q(), Q(), Q()], ["45.000000000", "0.000000000"]),
        ([Q(-1), Q(-1), Q(), Q(), Q(), Q()], ["225.000000000", "0.000000000"]),
        ([Q(1), Q(1), Q(1), Q(), Q(), Q()], ["45.000000000", "35.264389683"]),
    ],
)
def test_sufficient_angular_cones_are_independently_certified(state, angles):
    result = producer.angle_proof(state, angles, 0)
    assert result["status"] == "proved_inside"
    assert verifier.angular_proof(state, angles, 0, result)


def test_antipode_and_outside_angle_are_not_accepted():
    for state, angles in [
        ([Q(-1), Q(), Q(), Q(), Q(), Q()], ["0.000000000", "0.000000000"]),
        ([Q(1), Q(1), Q(), Q(), Q(), Q()], ["44.999999000", "0.000000000"]),
    ]:
        result = producer.angle_proof(state, angles, 0)
        assert result["status"] == "refuted" and not verifier.angular_proof(
            state, angles, 0, result
        )


@pytest.mark.parametrize("family", producer.FAMILIES)
def test_rounded_delay_can_require_receiver_outside_unrounded_support(
    monkeypatch, family
):
    # L is below the midpoint above 1; RN(L)=1. Receiver 2 gives emission 1
    # only for the two-round model, and lies below the unrounded image support.
    light = Q(1) + Q(1, 2**53) - Q(1, 2**56)
    scale = Q(1 if family == "absolute_JD_binary64" else 86400)
    radius = light / (producer.K * scale)
    state = [radius, Q(), Q(), Q(), Q(), Q()]
    monkeypatch.setattr(producer, "exact_state", lambda *args: state)
    monkeypatch.setattr(verifier, "exact_state", lambda *args: state)
    with localcontext() as context:
        context.prec = 90
        text = format(Decimal(radius.numerator) / Decimal(radius.denominator), ".16f")
        lt = radius * producer.K * 1440
        light_text = format(Decimal(lt.numerator) / Decimal(lt.denominator), ".12f")
    row = {
        "range_AU": text,
        "light_time_minutes": light_text,
        "astrometric_angles": ["0.000000000", "0.000000000"],
        "original_label_budget_pass": True,
    }
    nominal = producer.epoch_from_coordinate(2.0, family)
    case = {"nominal_JD": str(nominal), "window_index": 0}
    plan = {
        "numerical_tube_profiles": {"p": {"extra_binary64_ULPs": 0}},
        "maximum_lattice_points_per_model": 4096,
        "receiver_search_radius_seconds": "1",
    }
    result = producer.candidate(Path("."), case, row, "p", family, 1.0, plan)
    assert result["rounded_light_time_hex"] == (1.0).hex()
    target = next(r for r in result["receivers"] if r["reception_hex"] == (2.0).hex())
    assert target["rounding_hypotheses"] == {
        "one_round_source_norm": False,
        "two_round_source_norm": True,
    }
    assert result["source_observables_qualified"]
    assert verifier.check_candidate(
        Path("."), case, row, "p", family, 1.0, result, plan
    ) == len(result["receivers"])
