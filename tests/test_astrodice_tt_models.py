"""Analytic checks fixed before opening new astronomical source responses."""

import math
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_tt_models import (
    MODELS,
    coefficients,
    comparison,
    prediction,
    sine,
)
from scripts.verify_astrodice_tt_models import NativeModel

AUTHOR = (
    Path(__file__).parent
    / "data/astrodice/reference_sets/fixture-clock-budget-v1/dtdb.c"
)


@pytest.mark.parametrize("argument", [0, -4, Q(22, 7), 1000000, -1000000])
def test_sine_encloses_numerical_replay_without_using_libm_as_a_bound(argument):
    a, b = sine(I(argument)).bounds()
    assert a <= b and b - a < Q("1e-60")
    assert abs(float((a + b) / 2) - math.sin(float(argument))) < 1e-15


def test_author_native_full_series_replays_enclosed_implicit_models():
    raw = AUTHOR.read_bytes()
    native = NativeModel(raw)
    try:
        for epoch in (Q("2451545"), Q("1721425.5"), Q("5373484.49999")):
            for model in MODELS:
                p = prediction(epoch, model, raw)
                a, b = map(Q, p["predicted_TDB_minus_TT_seconds"])
                assert a - Q("1e-12") <= native.offset(epoch, model) <= b + Q("1e-12")
                assert b - a < Q("1e-40") and not p["physical_model_error_certified"]
    finally:
        native.close()


def test_extrapolation_keeps_its_documented_accuracy_scope():
    raw = AUTHOR.read_bytes()
    assert prediction(Q(2451545), MODELS[0], raw)["model_accuracy_scope"].startswith(
        "documented_1950"
    )
    assert prediction(Q(4680826), MODELS[0], raw)["model_accuracy_scope"].startswith(
        "outside_documented"
    )
    with pytest.raises(ValueError, match="source changed"):
        coefficients(raw + b"\n")


def test_disjoint_incomplete_and_unavailable_clocks_cannot_be_promoted():
    pred = {"predicted_JD_TDB": ["10", "11"]}
    inv = {
        "status": "bracketed",
        "effective_JD": ["12", "13"],
        "all_six_compatible": True,
    }
    assert comparison(pred, inv, True)["status"] == "disjoint"
    inv["effective_JD"] = ["10", "11"]
    inv["all_six_compatible"] = False
    assert not comparison(pred, inv, True)["qualified_not_refuted"]
    inv["all_six_compatible"] = True
    assert not comparison(pred, inv, False)["qualified_not_refuted"]
    assert (
        comparison(pred, {"status": "unbracketed"}, True)["status"]
        == "source_clock_unknown"
    )
