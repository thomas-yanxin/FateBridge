"""Freeze the evaluator's declared native data selectors, never credentials.

These values identify requested configuration, not actual files read or sky
accuracy. Tool return flags and source witnesses remain separate evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

LEGACY_NATIVE_ENVIRONMENT_KEYS = (
    "SE_EPHE_PATH",
    "FATEBRIDGE_JPL_FILE",
    "FATEBRIDGE_SOLAR_TERM_MODEL",
    "FATEBRIDGE_SOLAR_SPK_FILE",
    "XDG_CACHE_HOME",
)
NATIVE_ENVIRONMENT_KEYS = LEGACY_NATIVE_ENVIRONMENT_KEYS + (
    "FATEBRIDGE_AA1996_MANIFEST",
    "FATEBRIDGE_VSOP2013_MANIFEST",
)
NativeSelection = dict[str, str | None]
LEGACY_METHOD = "evaluation_native_environment_v1"
LEGACY_CONTEXT_METHOD = "evaluation_native_environment_with_working_directory_v2"
METHOD = "evaluation_native_environment_with_optional_sources_v3"
CONTEXT_METHOD = (
    "evaluation_native_environment_with_optional_sources_and_working_directory_v4"
)


def validate_selection(value: object) -> NativeSelection:
    if not isinstance(value, dict) or set(value) not in (
        set(LEGACY_NATIVE_ENVIRONMENT_KEYS),
        set(NATIVE_ENVIRONMENT_KEYS),
    ):
        raise ValueError(
            "Native selection must contain exactly the declared selector keys"
        )
    result: NativeSelection = {}
    for key in NATIVE_ENVIRONMENT_KEYS:
        if key not in value:
            continue  # Preserve legacy null/unknown distinctions when reading old bytes.
        item = value[key]
        if item is not None and (type(item) is not str or "\x00" in item):
            raise ValueError("Native selector values must be strings or explicit null")
        result[key] = item
    return result


def capture_selection(environment: Mapping[str, str] | None = None) -> NativeSelection:
    source = os.environ if environment is None else environment
    return validate_selection({key: source.get(key) for key in NATIVE_ENVIRONMENT_KEYS})


def selected_environment(selection: NativeSelection | None = None) -> dict[str, str]:
    values = capture_selection() if selection is None else validate_selection(selection)
    return {key: item for key, item in values.items() if item is not None}


def process_environment(
    selection: NativeSelection, environment: Mapping[str, str] | None = None
) -> dict[str, str]:
    result = dict(os.environ if environment is None else environment)
    values = validate_selection(selection)
    for key in NATIVE_ENVIRONMENT_KEYS:
        item = values.get(key)
        # Unrecorded optional paths in legacy evidence cannot come from a later
        # ambient process. Reading historical bytes does not authenticate them.
        if item is None:
            result.pop(key, None)
        else:
            result[key] = item
    return result


def selection_bytes(selection: NativeSelection) -> bytes:
    return (
        json.dumps(
            {
                "method_id": (
                    METHOD
                    if set(selection) == set(NATIVE_ENVIRONMENT_KEYS)
                    else LEGACY_METHOD
                ),
                "values": validate_selection(selection),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def context_bytes(selection: NativeSelection, working_directory: Path) -> bytes:
    """Retain native path-list syntax and bind its original resolution directory.

    Expanding every path would change Swiss path length limits, separator
    semantics and basename-only JPL selection. Keep the strings unchanged.
    """
    return (
        json.dumps(
            {
                "method_id": (
                    CONTEXT_METHOD
                    if set(selection) == set(NATIVE_ENVIRONMENT_KEYS)
                    else LEGACY_CONTEXT_METHOD
                ),
                "values": validate_selection(selection),
                "working_directory": {
                    "flavor": "nt" if os.name == "nt" else "posix",
                    "path": str(working_directory.resolve()),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _record(raw: bytes) -> dict[str, Any]:
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError("Unknown native selection record")
    method = record.get("method_id")
    keys = {"method_id", "values"}
    if method in {CONTEXT_METHOD, LEGACY_CONTEXT_METHOD}:
        keys.add("working_directory")
        cwd = record.get("working_directory")
        if (
            not isinstance(cwd, dict)
            or set(cwd) != {"flavor", "path"}
            or type(cwd["flavor"]) is not str
            or cwd["flavor"] not in {"posix", "nt"}
            or type(cwd["path"]) is not str
            or "\x00" in cwd["path"]
            or not (PureWindowsPath if cwd["flavor"] == "nt" else PurePosixPath)(
                cwd["path"]
            ).is_absolute()
        ):
            raise ValueError("Native working directory must be an absolute path")
    elif method not in {METHOD, LEGACY_METHOD}:
        raise ValueError("Unknown native selection record")
    if set(record) != keys:
        raise ValueError("Unknown native selection record")
    expected_keys = (
        NATIVE_ENVIRONMENT_KEYS
        if method in {METHOD, CONTEXT_METHOD}
        else LEGACY_NATIVE_ENVIRONMENT_KEYS
    )
    values = validate_selection(record["values"])
    if set(values) != set(expected_keys):
        raise ValueError("Native selector keys do not match their versioned schema")
    return record


def frozen_working_directory(raw: bytes) -> dict[str, str] | None:
    """Validate historical context without accessing its original host paths."""
    value = _record(raw).get("working_directory")
    return None if value is None else {"flavor": value["flavor"], "path": value["path"]}


def execution_directory(raw: bytes) -> Path | None:
    """Reject lost or foreign path contexts before a new execution starts."""
    cwd = frozen_working_directory(raw)
    if cwd is None:
        return None  # Legacy bytes contain no working-directory evidence.
    if cwd["flavor"] != ("nt" if os.name == "nt" else "posix"):
        raise ValueError("Native working directory belongs to another path platform")
    path = Path(cwd["path"])
    if not path.is_dir():
        raise ValueError("Frozen native working directory is unavailable")
    return path


def load_selection(path: Path, expected_sha256: str) -> tuple[NativeSelection, bytes]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Frozen native selection bytes changed")
    record = _record(raw)
    return validate_selection(record["values"]), raw


def verify_stage_selection(preparation: Path, run: Path) -> dict[str, object]:
    """Compare separately preserved stage files, never infer lost selections."""
    prepared = json.loads((preparation / "preparation.json").read_text())
    executed = json.loads((run / "report.json").read_text())
    if not isinstance(prepared, dict) or not isinstance(executed, dict):
        raise ValueError("Native stage reports must be objects")
    first = prepared.get("native_environment_sha256")
    second = executed.get("native_environment_sha256")
    if first is None and second is None:
        return {
            "status": "not_recorded_in_legacy_run",
            "stage_equivalence_verified": False,
        }
    if not isinstance(first, str) or not isinstance(second, str):
        raise ValueError("Native selection missing from one execution stage")
    _, raw = load_selection(preparation / "native-environment.json", first)
    load_selection(run / "native-environment.json", second)
    if first != second:
        raise ValueError("Prepared and executed native selections differ")
    result: dict[str, object] = {
        "status": "verified_exact_declared_native_selection",
        "native_environment_sha256": first,
        "stage_equivalence_verified": True,
        "actual_file_read_set_authenticated": False,
        "scope": "Same declared selector bytes only; returned backend flags and file witnesses remain separate evidence.",
    }
    cwd = frozen_working_directory(raw)
    if cwd is not None:
        result["native_working_directory"] = cwd
        result["scope"] = (
            "Same declared selector and native working-directory bytes only; "
            "returned backend flags and file witnesses remain separate evidence."
        )
    return result
