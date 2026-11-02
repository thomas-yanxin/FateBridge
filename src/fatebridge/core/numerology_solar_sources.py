"""Describe the sources in consumed solar receipts without selecting a model."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from fatebridge.utils.errors import NumerologySourceError

TRACE_ID = "numerology_consumed_solar_sources_v1"
NATIVE_DOCUMENTATION_URL = "https://www.astro.com/swisseph/swephprg.htm"
_MODEL_KEYS = frozenset(
    {
        "model_id",
        "version",
        "sources",
        "binary_sha256",
        "loaded_image_sha256",
        "binary_filename",
        "build_manifest_sha256",
        "calculation_source_sha256",
        "native_core_version",
        "native_source_context",
        "system",
        "machine",
        "abi_version",
        "time_argument",
        "position_frame",
        "working_jd_tt",
        "software_input_years",
        "qualified_solar_term_years",
        "native_moshier_relabelled",
        "accuracy_certified",
        "internal_observed_retflags",
        "calculation_flags_requested",
        "author_validation_range",
        "outside_author_validation_range",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def solar_source_profiles(boundaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Deduplicate recorded identities; a documentation URL is not a file hash."""
    profiles: dict[str, dict[str, Any]] = {}
    try:
        for boundary in boundaries:
            record = boundary["record"]
            provider, model = record["resolution_provider"], record["ephemeris_model"]
            if any(not isinstance(v, str) or not v for v in (provider, model)):
                raise ValueError("A consumed boundary needs its actual provider/model")
            details = record.get("solar_model_details")
            if details is None:
                details = {}
            if not isinstance(details, dict):
                raise ValueError("A model receipt must be an object")
            url = details.get("source_url")
            if url is not None:
                if not isinstance(url, str) or not url.startswith(
                    ("https://", "http://")
                ):
                    raise ValueError("A recorded source URL must be HTTP(S)")
                basis = "consumed_model_receipt"
            elif provider == "swisseph" and model in {"moshier", "swieph", "jpl"}:
                url, basis = NATIVE_DOCUMENTATION_URL, "provider_documentation"
            else:
                basis = "not_recorded"
            metadata = {
                k: deepcopy(v)
                for k, v in details.items()
                if k in _MODEL_KEYS
                or k.startswith(
                    (
                        "source_",
                        "coefficient_",
                        "compressed_coefficient_",
                        "frame_coefficient_",
                        "tdb_coefficient_",
                    )
                )
            }
            profile = dict(
                resolution_provider=provider,
                ephemeris_model=model,
                ephemeris_library_version=boundary.get("ephemeris_library_version"),
                ephemeris_retflags=deepcopy(boundary.get("ephemeris_retflags", [])),
                source_url=url,
                source_url_basis=basis,
                model_metadata=metadata,
            )
            key = _canonical(profile)
            if key not in profiles:
                profiles[key] = {**profile, "boundary_count": 0}
            profiles[key]["boundary_count"] += 1
        values = list(profiles.values())
        available = bool(values) and all(p["source_url"] is not None for p in values)
        urls = {p["source_url"] for p in values}
        return dict(
            boundary_count=sum(p["boundary_count"] for p in values),
            source_profiles=values,
            source_profiles_sha256=hashlib.sha256(
                _canonical(values).encode()
            ).hexdigest(),
            source_url=next(iter(urls)) if available and len(urls) == 1 else None,
            mixed_source_urls=len(urls) > 1,
            all_source_urls_available=available,
            accuracy_certified=False,
            scope="Observed boundary provider/model and recorded source metadata only. Provider documentation does not identify exact coefficient or binary bytes. Unknown/mixed URLs remain explicit; no global configuration is substituted and no physical, classical or predictive certification follows.",
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise NumerologySourceError(
            "runtime_numerology_solar_source_conflict"
        ) from error


def attach_solar_sources(
    evidence: dict[str, Any], policy_id: str, boundaries: Iterable[dict[str, Any]]
) -> None:
    profiles = solar_source_profiles(boundaries)
    rules = [r for r in evidence["rulesets"] if r["ruleset_id"] == policy_id]
    if len(rules) != 1 or any(r["rule_id"] == TRACE_ID for r in evidence["rule_trace"]):
        raise NumerologySourceError("runtime_numerology_solar_source_conflict")
    rules[0]["source_url"] = profiles["source_url"]
    evidence["rule_trace"].append(
        dict(
            rule_id=TRACE_ID,
            source_section="Actual consumed solar boundary receipts",
            facts=profiles,
        )
    )
