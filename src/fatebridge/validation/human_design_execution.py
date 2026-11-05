"""Validate declared native context boundaries, not native execution authenticity."""

import math
import re
from copy import deepcopy
from typing import Any

from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.core.human_design_context import CONTEXT_LIFETIME, CONTEXT_SCOPE
from fatebridge.validation.claims import _same_value


def _json_values(value: Any) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _json_values(item)
        return
    if isinstance(value, dict) and all(type(k) is str for k in value):
        for item in value.values():
            _json_values(item)
        return
    raise ValueError("Malformed native diagnostic JSON")


def verify_native_context(payload: dict[str, Any]) -> dict[str, Any]:
    errors = []
    mechanism = None
    declared_policy = None
    current_definition = endpoint_context_evidence()
    current_policy = current_definition["policy_id"]
    try:
        context = payload["native_execution_context"]
        mechanism = context["mechanism"]
        policy = context["compressed_file_endpoint_policy"]
        declared_policy = policy["policy_id"]
        expected_policy = deepcopy(current_definition)
        # Dynamic diagnostics are preserved. This check does not authenticate
        # their native measurements or a complete internal call/read set.
        _json_values(policy["records"])
        if not isinstance(policy["records"], list) or any(
            type(r) is not dict for r in policy["records"]
        ):
            raise ValueError("Malformed native endpoint records")
        counters = [
            "native_cache_resets_so_far",
            "calls_corrected_so_far",
            "native_states_changed_so_far",
            "unrecorded_calls_at_record_limit",
        ]
        for key in counters:
            value = policy[key]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid native diagnostic count")
            expected_policy[key] = value
        expected_policy["records"] = policy["records"]
        expected_policy["context_strategy"] = policy["context_strategy"]
        allowed_strategies = {
            "fresh_owned_native_context_before_each_physical_coordinate",
        }
        if mechanism == "local_engine_context":
            allowed_strategies.add(
                "external_endpoint_guard_and_geocentric_solar_dependency_rebuild"
            )
        if policy["context_strategy"] not in allowed_strategies:
            raise ValueError("Unknown native context strategy")
        if not _same_value(policy, expected_policy):
            raise ValueError("Native endpoint policy or scope altered")
        if mechanism == "local_engine_context":
            # Internal fault tests and nested engine calls make no fresh-process
            # claim. Production boundary tests independently require fresh_exec.
            expected = {
                "mechanism": mechanism,
                "compressed_file_endpoint_policy": policy,
            }
        elif mechanism == "fresh_exec_process":
            count = context["auxiliary_candidates_checked"]
            rows = context["auxiliary_files_present"]
            if (
                type(count) is not int
                or not 3 <= count <= 60
                or count % 3
                or not isinstance(rows, list)
            ):
                raise ValueError("Invalid auxiliary candidate count")
            keys = []
            names = ("swe_deltat.txt", "sedeltat.txt", "seleapsec.txt")
            for row in rows:
                index, name, size, digest = (
                    row[k] for k in ("search_index", "filename", "bytes", "sha256")
                )
                if (
                    type(index) is not int
                    or not 0 <= index < count // 3
                    or name not in names
                    or type(size) is not int
                    or size < 0
                    or type(digest) is not str
                    or not re.fullmatch("[0-9a-f]{64}", digest)
                ):
                    raise ValueError("Malformed auxiliary file identity")
                if not _same_value(
                    row,
                    {
                        "search_index": index,
                        "filename": name,
                        "bytes": size,
                        "sha256": digest,
                    },
                ):
                    raise ValueError("Unexpected auxiliary file claims")
                keys.append((index, names.index(name)))
            if keys != sorted(set(keys)):
                raise ValueError("Duplicate or unsorted auxiliary identities")
            expected = {
                "mechanism": mechanism,
                "lifetime": CONTEXT_LIFETIME,
                "auxiliary_candidates_checked": count,
                "auxiliary_files_present": rows,
                "scope": CONTEXT_SCOPE,
                "compressed_file_endpoint_policy": policy,
            }
            if policy[
                "context_strategy"
            ] != "fresh_owned_native_context_before_each_physical_coordinate" or any(
                policy[k] is None for k in counters
            ):
                raise ValueError("Fresh execution lacks the owned coordinate context")
        else:
            raise ValueError("Unsupported native execution claim")
        if not _same_value(context, expected):
            raise ValueError("Native operation boundary or scope mismatch")
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        errors.append(
            {
                "code": "native_operation_context_mismatch",
                "path": "native_execution_context",
            }
        )
    return {
        "errors": errors,
        "declared_native_context": mechanism,
        "declared_policy_id": declared_policy,
        "matches_current_declared_policy": not errors
        and declared_policy == current_policy,
        "native_execution_authenticated": False,
        "scope": "Declared operation boundary, auxiliary candidate identities and the current endpoint policy only. Does not authenticate execution, diagnostic measurements/counts, internal native records, atomic reads or positional/predictive accuracy.",
    }
