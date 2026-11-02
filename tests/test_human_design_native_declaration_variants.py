"""A reused v5 label cannot erase the identity of its full declaration."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.validation.human_design_execution import verify_native_context
from tests.human_design_policy_expectation import VARIANTS, static_policy

A = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/human-design-cycle-reference-brackets-v1"
)
ORIGINAL = json.loads(
    gzip.decompress((A / "evidence/original-cycle142-run.json.gz").read_bytes())
)["run"]


def test_full_static_definitions_are_frozen_and_both_report_correct_identity():
    fixture = (
        Path(__file__).parent
        / "fixtures/human-design-native-declaration-v5-variants.json"
    )
    assert (
        hashlib.sha256(fixture.read_bytes()).hexdigest()
        == "7085e84575f95270f4db7b65c98cd2a24e202a9a8c7ba78094ebe630b07ec7a9"
    )
    assert static_policy(endpoint_context_evidence()) == VARIANTS["current_static"]
    policy = ORIGINAL["native_execution_context"]["compressed_file_endpoint_policy"]
    assert static_policy(policy) == VARIANTS["old_static"]
    result = verify_native_context(ORIGINAL)
    assert not result["errors"]
    assert result["matches_current_declared_policy"] is False
    assert result["historical_declared_policy_verified"] is True
    current = deepcopy(ORIGINAL)
    current["native_execution_context"]["compressed_file_endpoint_policy"].update(
        VARIANTS["current_static"]
    )
    result = verify_native_context(current)
    assert not result["errors"]
    assert result["matches_current_declared_policy"] is True
    assert result["historical_declared_policy_verified"] is False


@pytest.mark.parametrize("variant", ["old_static", "current_static"])
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_scope",
        "wrong_version",
        "false_shift",
        "extra_claim",
        "missing_trigger",
        "negative_count",
        "boolean_count",
        "invalid_record",
        "external_strategy_for_fresh_process",
    ],
)
def test_known_version_label_never_whitelists_an_unknown_declaration(variant, mutation):
    value = deepcopy(ORIGINAL)
    policy = value["native_execution_context"]["compressed_file_endpoint_policy"]
    policy.update(VARIANTS[variant])
    if mutation == "unknown_scope":
        policy["scope"] += " All source reads are authenticated."
    elif mutation == "wrong_version":
        policy["policy_id"] = "compressed_file_endpoint_context_v999"
    elif mutation == "false_shift":
        policy["input_instant_shifted"] = True
    elif mutation == "extra_claim":
        policy["physical_accuracy_certified"] = True
    elif mutation == "missing_trigger":
        del policy["trigger"]
    elif mutation == "negative_count":
        policy["calls_corrected_so_far"] = -1
    elif mutation == "boolean_count":
        policy["calls_corrected_so_far"] = False
    elif mutation == "invalid_record":
        policy["records"] = ["not an observed record"]
    else:
        policy["context_strategy"] = (
            "external_endpoint_guard_and_geocentric_solar_dependency_rebuild"
        )
    result = verify_native_context(value)
    assert result["errors"]
    assert result["native_execution_authenticated"] is False


@pytest.mark.parametrize("variant", ["old_static", "current_static"])
@pytest.mark.parametrize(
    "strategy",
    [
        "fresh_owned_native_context_before_each_physical_coordinate",
        "external_caller_post_call_endpoint_guard_only",
        "external_endpoint_guard_and_geocentric_solar_dependency_rebuild",
    ],
)
def test_local_strategy_must_belong_to_the_exact_static_definition(variant, strategy):
    policy = deepcopy(
        ORIGINAL["native_execution_context"]["compressed_file_endpoint_policy"]
    )
    policy.update(VARIANTS[variant])
    policy["context_strategy"] = strategy
    current_external = "external_endpoint_guard_and_geocentric_solar_dependency_rebuild"
    old_external = "external_caller_post_call_endpoint_guard_only"
    expected = strategy not in (
        {current_external} if variant == "old_static" else {old_external}
    )
    result = verify_native_context(
        {
            "native_execution_context": {
                "mechanism": "local_engine_context",
                "compressed_file_endpoint_policy": policy,
            }
        }
    )
    assert (not result["errors"]) is expected
    assert result["native_execution_authenticated"] is False
