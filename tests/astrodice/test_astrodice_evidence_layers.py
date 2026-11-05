"""A missing rate oracle must not conceal an independently testable position."""

import math

import pytest

from scripts.astrodice.audit_astrodice_local_motion import (
    FAIL,
    PASS,
    UNRESOLVED,
    evaluate_layers,
    position_comparison,
    require_declared_derivative,
)


def forbidden():
    pytest.fail("Unavailable reference must never invoke the candidate")


def test_missing_rate_keeps_a_failed_position_and_the_whole_case_failed():
    result = evaluate_layers(
        {"samples": {"0": {}}},
        {"status": "reference_quality_unresolved"},
        lambda: {"status": FAIL, "midpoint_error_arcsec": 0.58},
        forbidden,
    )
    assert result["status"] == FAIL
    assert result["layers"]["position"]["midpoint_error_arcsec"] == 0.58
    assert result["layers"]["rate"]["status"] == UNRESOLVED


def test_a_passing_position_does_not_pass_an_unavailable_rate():
    result = evaluate_layers(
        {"samples": {"0": {}}},
        {"status": "reference_quality_unresolved"},
        lambda: {"status": PASS},
        forbidden,
    )
    assert result["status"] == UNRESOLVED
    assert len(result["layers"]) == 2


@pytest.mark.parametrize("failed_layer", ["position", "rate"])
def test_a_candidate_exception_does_not_suppress_the_other_layer(failed_layer):
    def broken():
        raise ValueError("independent layer failure")

    providers = {"position": lambda: {"status": FAIL}, "rate": lambda: {"status": FAIL}}
    providers[failed_layer] = broken
    result = evaluate_layers(
        {"samples": {"0": {}}},
        {"status": "qualified_under_declared_numerical_model"},
        providers["position"],
        providers["rate"],
    )
    other = "rate" if failed_layer == "position" else "position"
    assert result["status"] == "candidate_error"
    assert result["layers"][other]["status"] == FAIL
    assert result["layers"][failed_layer]["error_type"] == "ValueError"


def test_no_center_keeps_both_planned_layers_unavailable():
    result = evaluate_layers(
        {"samples": {"0": None}},
        {"status": "reference_quality_unresolved"},
        forbidden,
        forbidden,
    )
    assert result["status"] == UNRESOLVED
    assert len(result["layers"]) == 2


def test_an_unknown_layer_outcome_cannot_become_a_pass():
    result = evaluate_layers(
        {"samples": {"0": {}}},
        {"status": "qualified_under_declared_numerical_model"},
        lambda: {"status": "misspelled_failure"},
        lambda: {"status": PASS},
    )
    assert result["status"] == "candidate_error"
    assert result["layers"]["position"]["error_type"] == "ValueError"


@pytest.mark.parametrize(
    "offset,status", [(0.0, PASS), (0.019, PASS), (0.02, UNRESOLVED), (0.021, FAIL)]
)
def test_fixed_position_line_accounts_for_printing_uncertainty(offset, status):
    angle = math.radians(offset / 3600)
    row = {"samples": {"0": {"printed_angles": ["0.000000000", "0.000000000"]}}}
    result = position_comparison(row, [math.cos(angle), math.sin(angle), 0])
    assert result["status"] == status
    assert result["fixed_line_arcsec"] == 0.02
    assert (
        result["conditional_error_lower_arcsec"]
        <= offset
        <= result["conditional_error_upper_arcsec"]
    )


def test_current_derivative_policy_must_be_applied():
    declared = {
        "expected_derivative_method_id": "fatebridge_complete_position_derivative_v8"
    }
    require_declared_derivative(
        declared,
        {"status": "applied", "method_id": declared["expected_derivative_method_id"]},
    )
    for policy in [
        {"status": "partial", "method_id": declared["expected_derivative_method_id"]},
        {"status": "applied", "method_id": "unreviewed_method"},
    ]:
        with pytest.raises(ValueError):
            require_declared_derivative(declared, policy)
