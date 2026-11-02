"""Known historical declarations remain distinct from current guard claims."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.validation.human_design_execution import verify_native_context

ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/human-design-profile-coverage/batch-001/complete-runs.jsonl.gz"
)


@pytest.fixture(scope="module")
def historical_context():
    with gzip.open(ARCHIVE, "rt") as stream:
        return json.loads(next(stream))["run"]["native_execution_context"]


def test_exact_historical_policy_is_verified_under_its_own_declared_scope(
    historical_context,
):
    result = verify_native_context({"native_execution_context": historical_context})
    assert not result["errors"]
    assert result["declared_policy_id"] == "compressed_file_endpoint_context_v2"
    current = endpoint_context_evidence()["policy_id"]
    assert result["matches_current_declared_policy"] == (
        current == result["declared_policy_id"]
    )
    assert result["historical_declared_policy_verified"] == (
        current != result["declared_policy_id"]
    )
    assert not result["native_execution_authenticated"]


def test_current_internal_declaration_remains_distinct_from_historical_policy():
    policy = endpoint_context_evidence()
    result = verify_native_context(
        {
            "native_execution_context": {
                "mechanism": "local_engine_context",
                "compressed_file_endpoint_policy": policy,
            }
        }
    )
    assert not result["errors"]
    assert result["matches_current_declared_policy"]
    assert not result["historical_declared_policy_verified"]
    assert not result["native_execution_authenticated"]


@pytest.mark.parametrize(
    "change",
    [
        "unknown_version",
        "static_scope",
        "missing_key",
        "extra_current_key",
        "boolean_counter",
        "nonfinite_record",
        "shifted_instant",
        "unknown_strategy",
        "invalid_auxiliary_count",
        "operation_scope",
    ],
)
def test_historical_policy_does_not_accept_unknown_versions_or_altered_claims(
    historical_context, change
):
    context = deepcopy(historical_context)
    policy = context["compressed_file_endpoint_policy"]
    if change == "unknown_version":
        policy["policy_id"] = "compressed_file_endpoint_context_v999"
    elif change == "static_scope":
        policy["scope"] += " all native accuracy certified"
    elif change == "missing_key":
        policy.pop("reference_preflight")
    elif change == "extra_current_key":
        policy["endpoint_guard_trigger"] = "borrowed_newer_guard"
    elif change == "boolean_counter":
        policy["native_cache_resets_so_far"] = False
    elif change == "nonfinite_record":
        policy["records"] = [{"jd_tt": float("nan")}]
    elif change == "shifted_instant":
        policy["input_instant_shifted"] = True
    elif change == "unknown_strategy":
        policy["context_strategy"] = "unrecorded_native_context"
    elif change == "invalid_auxiliary_count":
        context["auxiliary_candidates_checked"] = 0
    else:
        context["scope"] += " authenticated"
    result = verify_native_context({"native_execution_context": context})
    assert result["errors"]
    assert not result["matches_current_declared_policy"]
    assert not result["historical_declared_policy_verified"]
    assert not result["native_execution_authenticated"]
