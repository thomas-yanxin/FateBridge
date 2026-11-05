"""Current native declarations must preserve source and operation boundaries."""

from copy import deepcopy

import pytest

from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.validation.human_design_execution import verify_native_context


def local_context():
    return {
        "mechanism": "local_engine_context",
        "compressed_file_endpoint_policy": endpoint_context_evidence(),
    }


def test_current_internal_native_definition_is_verified_without_execution_attestation():
    result = verify_native_context({"native_execution_context": local_context()})
    assert not result["errors"]
    assert result["matches_current_declared_policy"]
    assert not result["native_execution_authenticated"]


@pytest.mark.parametrize(
    "fault",
    [
        "unknown_version",
        "static_scope",
        "missing_key",
        "extra_claim",
        "boolean_counter",
        "negative_counter",
        "nonfinite_record",
        "invalid_record",
        "shifted_instant",
        "unknown_strategy",
        "extra_operation_claim",
    ],
)
def test_current_native_policy_rejects_invalid_or_false_declarations(fault):
    context = deepcopy(local_context())
    policy = context["compressed_file_endpoint_policy"]
    if fault == "unknown_version":
        policy["policy_id"] = "unrecognized_policy"
    elif fault == "static_scope":
        policy["scope"] += " all native accuracy certified"
    elif fault == "missing_key":
        policy.pop("trigger")
    elif fault == "extra_claim":
        policy["physical_accuracy_certified"] = True
    elif fault == "boolean_counter":
        policy["calls_corrected_so_far"] = False
    elif fault == "negative_counter":
        policy["calls_corrected_so_far"] = -1
    elif fault == "nonfinite_record":
        policy["records"] = [{"jd_tt": float("nan")}]
    elif fault == "invalid_record":
        policy["records"] = ["not an observed record"]
    elif fault == "shifted_instant":
        policy["input_instant_shifted"] = True
    elif fault == "unknown_strategy":
        policy["context_strategy"] = "unrecognized_strategy"
    else:
        context["scope"] = "authenticated"
    result = verify_native_context({"native_execution_context": context})
    assert result["errors"]
    assert not result["matches_current_declared_policy"]
    assert not result["native_execution_authenticated"]


@pytest.mark.parametrize(
    "strategy",
    [
        "fresh_owned_native_context_before_each_physical_coordinate",
        "external_endpoint_guard_and_geocentric_solar_dependency_rebuild",
    ],
)
def test_current_local_strategies_are_verified_with_the_same_static_policy(strategy):
    context = local_context()
    context["compressed_file_endpoint_policy"]["context_strategy"] = strategy
    assert not verify_native_context({"native_execution_context": context})["errors"]
