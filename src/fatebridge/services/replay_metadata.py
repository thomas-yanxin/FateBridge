"""Portable, privacy-conscious execution receipts for the shared registrar."""

import os
import platform
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import TypedDict

from pydantic import BaseModel, JsonValue
from typing_extensions import NotRequired

from fatebridge import __version__
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core import ephemeris_runtime, solar_model_policy
from fatebridge.core.de440_solar import EXTENDED_MODEL_ID
from fatebridge.core.de440_solar import MODEL_ID as DE440_MODEL_ID
from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.core.error_budget import declared_error_budget
from fatebridge.core.execution_context import CallClock, ExecutionOptions
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.fetch_vsop2013 import MODEL_ID as VSOP2013_MODEL_ID

METADATA_SCHEMA_VERSION = "2.0"


class EffectiveTimeReceipt(TypedDict):
    as_of: str
    clock_timezones: list[str]


class DeterminismReceipt(TypedDict):
    uses_current_time: bool
    current_time_fields_defaulted: list[str]
    randomness_used: bool
    seed_generated: bool
    replayable_with_receipt: bool
    scope: str


class ReplayReceipt(TypedDict):
    as_of: str
    overrides: dict[str, JsonValue]
    requires_original_input: bool


class ExecutionReceipt(TypedDict):
    effective_time: EffectiveTimeReceipt
    warnings: list[str]
    replay: NotRequired[ReplayReceipt]
    metadata_schema_version: NotRequired[str]
    package_version: NotRequired[str]
    duration_ms: NotRequired[float]
    determinism: NotRequired[DeterminismReceipt]
    runtime: NotRequired[dict[str, JsonValue]]
    provenance: NotRequired[dict[str, list[str]]]
    calculation_evidence: NotRequired[dict[str, JsonValue]]


@lru_cache(maxsize=1)
def environment_receipt() -> dict[str, JsonValue]:
    """Snapshot immutable deployment inputs once per process, without Git calls."""
    dependencies: dict[str, JsonValue] = {}
    for package in (
        "pydantic",
        "pyswisseph",
        "lunardate",
        "python-dateutil",
        "pytz",
        "mpmath",
    ):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    return {
        "package_version": __version__,
        "python": platform.python_version(),
        "platform": platform.system() + "-" + platform.machine(),
        "dependencies": dependencies,
    }


def ephemeris_inventory() -> dict[str, JsonValue]:
    """List readable directory entries without judging source availability."""
    files: list[JsonValue] = []
    unlisted_directory_indices: list[JsonValue] = []
    for index, root in enumerate(
        ephemeris_search_directories(
            ephemeris_runtime.effective_ephemeris_search_path()
        )
    ):
        if not root.is_dir():
            continue
        try:
            paths = sorted(root.iterdir())
        except PermissionError:
            # note (ephemeris): Search permission allows opening known files without enumerating the directory.
            unlisted_directory_indices.append(index)
            continue
        for path in paths:
            if (
                path.suffix == ".se1"
                or path.name
                in {
                    "seorbel.txt",
                    "sefstars.txt",
                    "seleapsec.txt",
                    "seasnam.txt",
                    "swe_deltat.txt",
                    "sedeltat.txt",
                }
            ) and path.is_file():
                files.append(f"{index}/{path.name}")
    return {
        "scope": "configured_filenames; actual models/sources are reported separately",
        "files": files,
        **(
            {"unlisted_directory_indices": unlisted_directory_indices}
            if unlisted_directory_indices
            else {}
        ),
    }


def provenance_values(payload: ServiceResult) -> dict[str, list[str]]:
    """Small allowlist of non-personal policy facts that survive projection."""
    provenance_fields = {
        "ephemeris_model",
        "rule_version",
        "ruleset_version",
        "time_policy",
        "day_ganzhi_strategy",
        "calendar_engine",
        "school_version",
        "policy_version",
        "time_algorithm",
        "engine_precision",
        "ruleset_id",
        "bundle_version",
        "method_id",
        "resolution_policy",
    }
    found: dict[str, set[str]] = {}
    queue: list[JsonValue] = [payload]
    seen: set[int] = set()
    while queue:
        current = queue.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, dict):
            ruleset_id = current.get("ruleset_id")
            ruleset_version = current.get("version")
            if isinstance(ruleset_id, str) and isinstance(ruleset_version, str):
                found.setdefault("ruleset", set()).add(
                    f"{ruleset_id}@{ruleset_version}"
                )
            for field_name, value in current.items():
                if field_name in provenance_fields and isinstance(value, str):
                    found.setdefault(field_name, set()).add(value)
                elif isinstance(value, (dict, list, tuple)):
                    queue.append(value)
        elif isinstance(current, (list, tuple)):
            queue.extend(
                item for item in current if isinstance(item, (dict, list, tuple))
            )
    return {field_name: sorted(values) for field_name, values in sorted(found.items())}


def runtime_receipt(
    observed_provenance: dict[str, list[str]],
    *,
    include_astronomy: bool = True,
) -> dict[str, JsonValue]:
    if not include_astronomy and "ephemeris_model" not in observed_provenance:
        return dict(environment_receipt())

    configured_solar_mode = (
        os.environ.get(solar_model_policy.ENVIRONMENT_NAME, "auto").strip().lower()
    )
    observed_models = observed_provenance.get("ephemeris_model", [])
    has_vsop2013 = VSOP2013_MODEL_ID in observed_models
    has_spk = "fatebridge_jpl_spk_solar_v1" in observed_models
    de440_observed_models = sorted(
        {DE440_MODEL_ID, EXTENDED_MODEL_ID} & set(observed_models)
    )
    has_de440 = bool(de440_observed_models)
    if (
        (configured_solar_mode == "vsop2013" and not has_vsop2013)
        or (configured_solar_mode == "spk" and not has_spk)
        or (configured_solar_mode in {"auto", "de440"} and not has_de440)
        or configured_solar_mode not in solar_model_policy.MODES
    ):
        solar_policy_receipt = solar_model_policy.solar_model_environment_receipt(
            resolve_source=False
        )
    else:
        solar_policy_receipt = solar_model_policy.solar_model_environment_receipt(
            observed_de440_models=(
                de440_observed_models
                if EXTENDED_MODEL_ID in de440_observed_models
                else None
            )
        )

    return {
        **environment_receipt(),
        "ephemeris": ephemeris_inventory(),
        "solar_term_policy": solar_policy_receipt,
    }


def execution_receipt(
    spec: ToolSpec,
    request: BaseModel,
    result: ServiceResult,
    *,
    clock: CallClock,
    options: ExecutionOptions,
    elapsed_ms: float,
    generated_seed: bool,
    replay_overrides: dict[str, JsonValue],
    compact_receipt: bool = False,
) -> ExecutionReceipt:
    policy = spec.reproducibility or ReproducibilityPolicy()
    as_of = clock.instant.isoformat().replace("+00:00", "Z")
    time_defaults = [
        field
        for field in policy.current_time_fields
        if getattr(request, field, None) is None
    ]
    if spec.resolve_time_defaults is not None:
        time_defaults = spec.resolve_time_defaults(result, time_defaults)
    warnings = (
        ["current_time_frozen"]
        if clock.reads and (time_defaults or policy.implicit_current_time)
        else []
    ) + (["random_seed_generated"] if generated_seed else [])
    receipt: ExecutionReceipt = {
        "effective_time": {"as_of": as_of, "clock_timezones": sorted(clock.reads)},
        "warnings": warnings,
    }
    if replay_overrides:
        receipt["replay"] = {
            "as_of": as_of,
            "overrides": replay_overrides,
            "requires_original_input": True,
        }
    if compact_receipt:
        return receipt

    receipt["metadata_schema_version"] = METADATA_SCHEMA_VERSION
    receipt["package_version"] = __version__
    receipt["duration_ms"] = round(elapsed_ms, 3)
    receipt["determinism"] = {
        "uses_current_time": bool(clock.reads)
        and bool(time_defaults or policy.implicit_current_time),
        "current_time_fields_defaulted": time_defaults if clock.reads else [],
        "randomness_used": bool(replay_overrides),
        "seed_generated": generated_seed,
        "replayable_with_receipt": True,
        "scope": "business payload in identical implementation/data/runtime; metadata IDs and duration vary",
    }
    receipt["replay"] = {
        "as_of": as_of,
        "overrides": replay_overrides,
        "requires_original_input": True,
    }

    observed_provenance = provenance_values(
        {key: value for key, value in result.items() if key != "run_metadata"}
    )
    receipt["runtime"] = runtime_receipt(
        observed_provenance, include_astronomy=spec.uses_astronomy_runtime
    )
    receipt["provenance"] = observed_provenance
    if spec.methods and options.detail == "audit":
        methods = [
            method
            for method in spec.methods
            if method.requires_non_null_output is None
            or result.get(method.requires_non_null_output) is not None
        ]
        receipt["calculation_evidence"] = {
            "registered_methods": [method.as_manifest() for method in methods],
            "error_budget": declared_error_budget(
                tuple(source for method in methods for source in method.error_sources),
                {
                    "birth_time_uncertainty_minutes": getattr(
                        request, "birth_time_uncertainty_minutes", None
                    ),
                    "birth_clock_basis": getattr(request, "birth_clock_basis", "civil"),
                },
                "this_run",
            ),
        }
    return receipt
