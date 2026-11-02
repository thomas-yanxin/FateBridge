"""Integrity and negative controls, not a claim of numerical acceptance.

The explicit external audit still returns1 for apparent-rate disagreements.
These tests must not turn reference integrity into an accuracy score.
"""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts.audit_astrodice_apparent import (
    unit_and_rate,
    validate_derivative_reference,
    validate_reference,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
PROTOCOL = json.loads(
    (FIXTURES / "astrodice-apparent-motion-protocol.json").read_text()
)
REFERENCE = json.loads((FIXTURES / "astrodice-apparent-horizons.json").read_text())
DERIVATIVE_PROTOCOL = json.loads(
    (FIXTURES / "astrodice-apparent-derivative-protocol.json").read_text()
)
DERIVATIVE = json.loads(
    (FIXTURES / "astrodice-apparent-position-derivative.json").read_text()
)


@pytest.mark.parametrize(
    "name,expected",
    [
        (
            "astrodice-apparent-motion-protocol.json",
            "7e0dd4d4b3f1e26d48650edac23fe551162a3ed733c612515c702eb82b7f6504",
        ),
        (
            "astrodice-apparent-derivative-protocol.json",
            "2eb190bf90ab03daff59d4ad21d227f9300cafadc4daab648e0dfd18b474071e",
        ),
        (
            "astrodice-apparent-horizons.json",
            "fa94b712f6390dd117b9e8a00916ab7ff0cda90f3779afb255e9889e594042db",
        ),
        (
            "astrodice-apparent-position-derivative.json",
            "434c99c5836d2f9fdf1673b7cbd0d905b8a4346c0e10d38e53d95e2b8c6824fb",
        ),
    ],
)
def test_frozen_inputs_and_raw_responses_have_not_changed(name, expected):
    assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected


def test_all_references_match_raw_time_target_angles_rates_and_five_point_stencils():
    validate_reference(PROTOCOL, REFERENCE)
    validate_derivative_reference(DERIVATIVE_PROTOCOL, DERIVATIVE, REFERENCE)
    assert sum(len(r["rows"]) for r in REFERENCE["references"]) == 570
    assert sum(len(r["rows"]) for r in DERIVATIVE["references"]) == 570
    assert (
        sum(len(r["unavailable_requested_epochs"]) for r in REFERENCE["references"])
        == 10
    )
    assert (
        sum(
            "erfa_display_frame" in row
            for r in REFERENCE["references"]
            for row in r["rows"]
        )
        == 300
    )
    for fixture, generator in [
        (REFERENCE, "gen_astrodice_apparent_reference.py"),
        (DERIVATIVE, "gen_astrodice_apparent_derivative.py"),
    ]:
        assert (
            fixture["generator_sha256"]
            == hashlib.sha256((ROOT / "scripts" / generator).read_bytes()).hexdigest()
        )
        assert fixture["forbidden_implementation_imports"] == []
        assert fixture["versions"] == {"pyerfa": "2.0.1.5", "numpy": "2.5.4"}


def test_ra_rate_already_contains_cosdeclination_and_hours_are_converted_to_days():
    unit, rate = unit_and_rate(0.0, 60.0, 1.0, 0.0)
    assert unit == pytest.approx([0.5, 0, math.sqrt(3) / 2], abs=1e-15)
    assert rate == pytest.approx([0, math.radians(24 / 3600), 0], abs=1e-15)
    assert abs(rate[1] - math.radians(24 / 3600) * 0.5) > 1e-5


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_body",
        "drop_row",
        "wrong_rate",
        "wrong_frame",
        "invent_missing",
        "raw_tamper",
    ],
)
def test_apparent_validator_rejects_data_and_coverage_reward_hacking(mutation):
    bad = copy.deepcopy(REFERENCE)
    if mutation == "drop_body":
        bad["references"].pop()
    elif mutation == "drop_row":
        bad["references"][0]["rows"].pop()
    elif mutation == "wrong_rate":
        bad["references"][0]["rows"][0]["ra_cosdec_arcsec_per_hour"] += 1
    elif mutation == "wrong_frame":
        bad["references"][0]["parameters"]["REF_SYSTEM"] = "'FK4'"
    elif mutation == "invent_missing":
        bad["references"][0]["unavailable_requested_epochs"][0]["reason"] = "passed"
    else:
        bad["references"][0]["raw_response_utf8"] += " "
    with pytest.raises(ValueError):
        validate_reference(PROTOCOL, bad)


@pytest.mark.parametrize(
    "mutation",
    ["drop_body", "drop_probe", "alter_derived_rate", "switch_stencil", "wrong_frame"],
)
def test_position_derivative_validator_rejects_invented_speeds_or_dropped_probes(
    mutation,
):
    bad = copy.deepcopy(DERIVATIVE)
    if mutation == "drop_body":
        bad["references"].pop()
    elif mutation == "drop_probe":
        bad["references"][0]["batches"][0]["rows"].pop()
    elif mutation == "alter_derived_rate":
        bad["references"][0]["rows"][0]["five_point_derivatives"]["1800"][0] += 1e-6
    elif mutation == "switch_stencil":
        bad["references"][0]["rows"][0]["icrf_direction_derivative_per_day"] = bad[
            "references"
        ][0]["rows"][0]["five_point_derivatives"]["3600"]
    else:
        bad["references"][0]["batches"][0]["parameters"]["TIME_TYPE"] = "'UT'"
    with pytest.raises(ValueError):
        validate_derivative_reference(DERIVATIVE_PROTOCOL, bad, REFERENCE)
