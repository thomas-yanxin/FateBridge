"""Portable, privacy-conscious execution receipts for the shared registrar."""

import hashlib
import os
import platform
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from fatebridge import __version__
from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.core.execution_context import CallClock, ExecutionOptions
from fatebridge.core.reproducibility import BAZI_ANALYSIS_CLOCK_TOOLS
from fatebridge.core.schema_cache import contract_fingerprint
from fatebridge.utils.json_digest import digest

METADATA_SCHEMA_VERSION = "1.0"


def _file_digests(root: Path, pattern: str) -> Dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob(pattern))
        if path.is_file()
    }


@lru_cache(maxsize=1)
def environment_receipt() -> Dict[str, Any]:
    """Snapshot immutable deployment inputs once per process, without Git calls."""
    root = Path(__file__).resolve().parents[1]
    dependencies: Dict[str, Optional[str]] = {}
    for package in (
        "pydantic",
        "kerykeion",
        "pyswisseph",
        "lunardate",
        "python-dateutil",
        "pytz",
        "pygeomag",
    ):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    receipt = {
        "package_version": __version__,
        "python": platform.python_version(),
        "platform": platform.system() + "-" + platform.machine(),
        "dependencies": dependencies,
        "implementation_sha256": digest(_file_digests(root, "*.py")),
        "bundled_data_sha256": digest(_file_digests(root / "data", "*.json")),
    }
    return {**receipt, "environment_sha256": digest(receipt)}


def ephemeris_inventory() -> Dict[str, Any]:
    """Fingerprint configured file inventory, not a claim about files actually used."""
    from fatebridge.core import ephemeris_runtime

    directory = ephemeris_runtime.effective_ephemeris_search_path()
    return _ephemeris_inventory(directory)


@lru_cache(maxsize=64)
def _large_ephemeris_digest(filename: str, signature: tuple[int, ...]) -> str:
    path = Path(filename)
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(piece)
    if _stat_signature(path) != signature:
        raise ValueError("Ephemeris file changed while its inventory was hashed")
    return hasher.hexdigest()


def _stat_signature(path: Path) -> tuple[int, ...]:
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_dev)


def _ephemeris_inventory(directory: Optional[str]) -> Dict[str, Any]:
    files: Dict[str, str] = {}
    if directory:
        for index, root in enumerate(ephemeris_search_directories(directory)):
            for path in sorted(root.glob("*.se1")):
                if path.is_file():
                    files[f"{index}/{path.name}"] = _large_ephemeris_digest(
                        str(path.resolve()), _stat_signature(path)
                    )
            for name in (
                "seorbel.txt",
                "sefstars.txt",
                "seleapsec.txt",
                "seasnam.txt",
                "swe_deltat.txt",
                "sedeltat.txt",
            ):
                path = root / name
                if path.is_file():
                    # Small source files can immediately change a calculation
                    # at the same directory. Never cache solely by path/stat.
                    files[f"{index}/{name}"] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
    return {
        "scope": "effective_se1_and_auxiliary_inventory; actual models/sources are reported separately",
        "freshness": "Auxiliary text bytes hashed each receipt; large se1 hashes cached by size/mtime/ctime/inode/device, not a continuous immutability proof",
        "files": files,
        "sha256": digest(files),
    }


def provenance_values(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """Small allowlist of non-personal policy facts that survive projection."""
    keys = {
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
    }
    found: Dict[str, set[str]] = {}
    queue: List[Any] = [payload]
    while queue:
        current = queue.pop()
        if isinstance(current, dict):
            if isinstance(current.get("ruleset_id"), str) and isinstance(
                current.get("version"), str
            ):
                found.setdefault("ruleset", set()).add(
                    current["ruleset_id"] + "@" + current["version"]
                )
            for key, value in current.items():
                if key in keys and isinstance(value, str):
                    found.setdefault(key, set()).add(value)
                elif isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            queue.extend(current)
    return {key: sorted(values) for key, values in sorted(found.items())}


def execution_receipt(
    spec: Any,
    request: Any,
    result: Dict[str, Any],
    *,
    clock: CallClock,
    options: ExecutionOptions,
    elapsed_ms: float,
    generated_seed: bool,
) -> Dict[str, Any]:
    policy = spec.reproducibility
    as_of = clock.instant.isoformat().replace("+00:00", "Z")
    inputs = request.model_dump(mode="json")

    # These omissions affect either fail-loud solar behavior or the declared
    # birth-clock input components, even when the nominal values are equal.
    # A null/omitted second has the same unknown meaning and needs no extra bit.
    def semantic_presence(model: BaseModel, prefix: str = "") -> List[str]:
        present = []
        for field in type(model).model_fields:
            value = getattr(model, field)
            if isinstance(value, BaseModel):
                present.extend(semantic_presence(value, prefix + field + "."))
            elif (
                field.endswith(("use_true_solar_time", "birth_minute"))
                or (
                    spec.key == "meihua_analysis"
                    and not prefix
                    and field == "analysis_minute"
                    and value is not None
                )
            ) and field in model.model_fields_set:
                present.append(prefix + field)
        return present

    presence = sorted(semantic_presence(request))
    input_digest = digest(
        {"tool_key": spec.key, "inputs": inputs, "presence": presence}
    )
    body = {key: value for key, value in result.items() if key != "run_metadata"}
    observed_provenance = provenance_values(body)
    environment = environment_receipt()
    from fatebridge.core.solar_model_policy import (
        ENVIRONMENT_NAME,
        MODES,
        solar_model_environment_receipt,
    )

    configured_solar_mode = os.environ.get(ENVIRONMENT_NAME, "auto").strip().lower()
    from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_MODEL_ID

    vsop2013_observed = VSOP2013_MODEL_ID in observed_provenance.get(
        "ephemeris_model", []
    )
    spk_observed = "fatebridge_jpl_spk_solar_v1" in observed_provenance.get(
        "ephemeris_model", []
    )
    from fatebridge.core.de440_solar import (
        EXTENDED_MODEL_ID,
    )
    from fatebridge.core.de440_solar import MODEL_ID as DE440_MODEL_ID

    de440_observed_models = sorted(
        {DE440_MODEL_ID, EXTENDED_MODEL_ID}
        & set(observed_provenance.get("ephemeris_model", []))
    )
    de440_observed = bool(de440_observed_models)
    if (
        (configured_solar_mode == "vsop2013" and not vsop2013_observed)
        or (configured_solar_mode == "spk" and not spk_observed)
        or (configured_solar_mode in {"auto", "de440"} and not de440_observed)
        or configured_solar_mode not in MODES
    ):
        solar_policy_receipt = solar_model_environment_receipt(resolve_source=False)
    else:
        solar_policy_receipt = solar_model_environment_receipt(
            observed_de440_models=(
                de440_observed_models
                if EXTENDED_MODEL_ID in de440_observed_models
                else None
            )
        )

    environment = {
        **environment,
        "ephemeris": ephemeris_inventory(),
        "solar_term_policy": solar_policy_receipt,
    }
    environment["environment_sha256"] = digest(
        {
            key: value
            for key, value in environment.items()
            if key != "environment_sha256"
        }
    )
    time_defaults = [
        field for field in policy.current_time_fields if inputs.get(field) is None
    ]
    if spec.key in BAZI_ANALYSIS_CLOCK_TOOLS:
        # Read the resolver's actual decision. Missing fields may be fixed
        # constants in explicit partial queries, rather than clock-derived.
        reference = result.get("analysis_reference")
        if isinstance(reference, dict):
            time_defaults = list(reference["defaulted_from_clock"])
    random_used = False
    if spec.key == "sixyao":
        from fatebridge.core.local_techniques.sixyao import needs_random_coin_cast

        random_used = needs_random_coin_cast(inputs)
    overrides = {"seed": inputs["seed"]} if random_used else {}
    return {
        "metadata_schema_version": METADATA_SCHEMA_VERSION,
        "package_version": __version__,
        "contract_sha256": contract_fingerprint(
            spec.request_model, spec.output_model, spec.required_output_fields
        ),
        "input_sha256": input_digest,
        "business_output_sha256": digest(body),
        "duration_ms": round(elapsed_ms, 3),
        "effective_time": {"as_of": as_of, "clock_timezones": sorted(clock.reads)},
        "determinism": {
            "uses_current_time": bool(clock.reads)
            and bool(time_defaults or policy.implicit_current_time),
            "current_time_fields_defaulted": time_defaults if clock.reads else [],
            "randomness_used": random_used,
            "seed_generated": generated_seed,
            "replayable_with_receipt": True,
            "scope": "business payload in identical implementation/data/runtime; metadata IDs and duration vary",
        },
        "runtime": environment,
        "provenance": observed_provenance,
        "replay": {
            "as_of": as_of,
            "overrides": overrides,
            "requires_original_input": True,
        },
        "warnings": (
            (
                ["current_time_frozen"]
                if clock.reads and (time_defaults or policy.implicit_current_time)
                else []
            )
            + (["random_seed_generated"] if generated_seed else [])
        ),
        **(
            {"parent_run_id": options.parent_run_id}
            if options.parent_run_id is not None
            else {}
        ),
    }
