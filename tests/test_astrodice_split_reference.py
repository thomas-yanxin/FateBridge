"""Reference identity, numerical time preservation and honest acceptance scope."""

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.audit_astrodice_split_reference import (
    GENERATOR_SHA256,
    REFERENCE_SHA256,
    validate,
)
from scripts.gen_astrodice_split_reference import shifted

FIXTURES = Path(__file__).parent / "data/astrodice/tables"


def inputs():
    return [
        json.loads((FIXTURES / f"lunar-split-tdb-{name}.json").read_text())
        for name in ["protocol", "reference"]
    ]


def test_frozen_split_reference_replays_every_source_state_and_stencil():
    assert (
        hashlib.sha256(
            (FIXTURES / "lunar-split-tdb-reference.json").read_bytes()
        ).hexdigest()
        == REFERENCE_SHA256
    )
    assert (
        hashlib.sha256(
            (FIXTURES / "split-tdb-collector-source.txt").read_bytes()
        ).hexdigest()
        == GENERATOR_SHA256
    )
    result = validate(*inputs())
    assert result["centers"] == 20 and result["fresh_holdout_centers"] == 16
    assert result["samples"] == 380
    assert result["probes_outside_AD1_through_AD9999"] == 2
    assert result["template_failures"] == []
    assert result["maximum_template_step_difference_arcsec_per_day"] < 0.002
    assert result["tt_calendar_acceptance"] is False


@pytest.mark.parametrize(
    "jd0,small,delta",
    [
        (5227387, 0.5, 1e-12),
        (1721425, 0.25, -0.75),
        (5373484, 0.75, 0.5),
        (5373484, 0.25, -1e-5),
    ],
)
def test_split_time_preserves_small_increments_across_calendar_edges(jd0, small, delta):
    a, b = shifted(jd0, small, delta)
    expected = Fraction(jd0) + Fraction(small) + Fraction(delta)
    actual = Fraction(a) + Fraction(b)
    assert abs(actual - expected) * 86400 < Fraction(1, 10**10)
    assert 0 <= b < 1
    if delta == 1e-12:
        assert (jd0 + small) + delta == jd0 + small
        assert actual != Fraction(jd0) + Fraction(small)


@pytest.mark.parametrize(
    "change",
    [
        "time_scale",
        "source_identity",
        "source_state",
        "emission",
        "recurrence",
        "coverage",
        "nonfinite",
        "direction_shape",
    ],
)
def test_split_reference_rejects_mutated_evidence(change):
    protocol, reference = copy.deepcopy(inputs())
    row = reference["rows"][0]
    sample = row["samples"]["0"]
    if change == "time_scale":
        protocol["time_scale"] = "TT"
    elif change == "source_identity":
        reference["kernel_sha256_before_and_after"] = "0" * 64
    elif change == "source_state":
        sample["reception_iterations"][-1]["moon_barycentric_pv"][0] += 0.001
    elif change == "emission":
        sample["reception_iterations"][0]["emission_fraction_tdb"] += 1e-9
    elif change == "recurrence":
        sample["reception_iterations"][0]["next_delay_days"] += 1e-8
    elif change == "coverage":
        row["samples"].pop(next(k for k in row["samples"] if k != "0"))
    elif change == "nonfinite":
        sample["selected_direction"][0] = float("nan")
    else:
        sample["without_finite_solar_deflection"].append(0)
    with pytest.raises(ValueError):
        validate(protocol, reference)


@pytest.mark.parametrize(
    "code,status",
    [
        (0, "nominal_argument_lines_satisfied_not_TT_acceptance"),
        (1, "nominal_argument_numeric_failure"),
        (2, "reference_quality_unresolved"),
    ],
)
def test_candidate_receipt_never_promotes_the_tdb_study_to_tt(
    monkeypatch, code, status
):
    from scripts import audit_astrodice_split_candidate as candidate

    monkeypatch.setattr(
        candidate,
        "audit",
        lambda *a, **kw: {"model": "jpl", "exit_code": code, "cases": []},
    )
    result = candidate.compare(*inputs(), "jpl")
    assert result["status"] == status
    assert result["reference_time_scale"] == "TDB"
    assert result["native_api_time_scale"] == "TT"
    assert result["tt_tdb_conversion_applied"] is False
    assert result["tt_calendar_acceptance"] is False
