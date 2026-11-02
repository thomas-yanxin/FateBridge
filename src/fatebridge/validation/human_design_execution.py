"""Validate declared native context boundaries, not native execution authenticity."""

import math
import re
from copy import deepcopy
from typing import Any

from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.core.human_design_context import CONTEXT_LIFETIME, CONTEXT_SCOPE
from fatebridge.validation.claims import _same_value

# Exact historical declaration, recovered from the unchanged frozen v2
# implementation. It certifies neither execution nor later light-path guards.
# Unknown versions are not inferred from this schema or accepted by prefix.
_LEGACY_V2_POLICY = {
    "policy_id": "compressed_file_endpoint_context_v2",
    "trigger": "actual_SWIEPH_physical_calc_at_observed_file_end_within_64_TT_ULPs",
    "input_instant_shifted": False,
    "native_coordinates_may_be_corrected": True,
    "context_strategy": "external_caller_post_call_endpoint_guard_only",
    "native_cache_resets_so_far": None,
    "reference_preflight": "same_reception_epoch_geometric_Sun",
    "calls_corrected_so_far": None,
    "native_states_changed_so_far": None,
    "records": [],
    "unrecorded_calls_at_record_limit": 0,
    "source_url": "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L2163-L2179",
    "scope": "Within the owned private operation, reset computed native state using the same path, preselect its source with a same-reception-epoch geometric Sun, then execute the exact requested coordinate call. Native owned default model/tidal settings are reapplied; sidereal/topocentric parameters and fixed Delta-T survive set_ephe_path. External callers retain only the original post-call endpoint guard. Correction counts describe preflight or requested native subcalls, not independent samples or proof that an unevaluated original target changed. No atomic read-set or physical accuracy certificate.",
}

# Recovered byte-for-byte from the sealed runtime source whose SHA-256 is
# 5acf889adc74bcee238f35c73a8b6769dc58e492ed5b90412da05f975ab21a17.
# A later shared-runtime edit retained the v5 ID but changed its external-call
# strategy and scope. Recognize this exact older definition, not any v5 text.
_LEGACY_V5_POLICY = {
    **_LEGACY_V2_POLICY,
    "policy_id": "compressed_file_endpoint_context_v5",
    "trigger": "owned_physical_light_path_or_observed_compressed_endpoint",
    "endpoint_guard_trigger": "actual_SWIEPH_physical_calc_at_observed_file_end_within_64_TT_ULPs",
    "scope": "Within the owned private operation, reset computed native state using the same path and preselect with a same-reception-epoch geometric Sun. For supported geocentric apparent Sun/Moon/planet requests, establish the checked reception/retarded light-path context before the exact original coordinate call. Native owned default model/tidal settings are reapplied; sidereal/topocentric parameters and fixed Delta-T survive set_ephe_path. External callers retain only the original post-call endpoint guard. Correction counts describe preflight or requested native subcalls, not independent samples or proof that an unevaluated original target changed. No atomic read-set or physical accuracy certificate.",
}
_DYNAMIC_POLICY_FIELDS = frozenset(
    {
        "context_strategy",
        "records",
        "native_cache_resets_so_far",
        "calls_corrected_so_far",
        "native_states_changed_so_far",
        "unrecorded_calls_at_record_limit",
    }
)


def _static_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in policy.items() if k not in _DYNAMIC_POLICY_FIELDS}


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
    historical_definition = False
    try:
        context = payload["native_execution_context"]
        mechanism = context["mechanism"]
        policy = context["compressed_file_endpoint_policy"]
        declared_policy = policy["policy_id"]
        expected_policy = deepcopy(current_definition)
        static = _static_policy(policy)
        if not _same_value(static, _static_policy(current_definition)):
            for previous in (_LEGACY_V2_POLICY, _LEGACY_V5_POLICY):
                if _same_value(static, _static_policy(previous)):
                    expected_policy = deepcopy(previous)
                    historical_definition = True
                    break
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
        if historical_definition:
            allowed_strategies.add("external_caller_post_call_endpoint_guard_only")
        elif mechanism == "local_engine_context":
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
        and declared_policy == current_policy
        and not historical_definition,
        "historical_declared_policy_verified": not errors and historical_definition,
        "native_execution_authenticated": False,
        "scope": "Declared operation boundary, auxiliary candidate identities and the exact current or explicitly supported historical endpoint policy only. Historical declarations do not verify newer safeguards. Does not authenticate execution, diagnostic measurements/counts, internal native records, atomic reads or positional/predictive accuracy.",
    }
