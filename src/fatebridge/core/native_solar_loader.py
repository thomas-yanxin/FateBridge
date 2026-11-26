"""Shared manifest, signature, dladdr, and temp-copy loader for optional native solar libs."""

from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Callable

from fatebridge.utils.errors import EphemerisSourceError


def is_finite_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def unique_json_pairs(items: list[tuple[str, Any]], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate {label} field")
        result[key] = value
    return result


def file_signature(path: Path, unavailable_reason: str) -> tuple[int, ...]:
    try:
        stat = path.stat()
        if not path.is_file():
            raise OSError("not a file")
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
    except OSError as error:
        raise EphemerisSourceError(unavailable_reason) from error


class ImageInfo(ctypes.Structure):
    _fields_ = [
        ("filename", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("symbol", ctypes.c_char_p),
        ("address", ctypes.c_void_p),
    ]


def verify_loaded_image(function: Any, expected_path: Path, label: str) -> None:
    lookup = ctypes.CDLL(None).dladdr
    lookup.argtypes = [ctypes.c_void_p, ctypes.POINTER(ImageInfo)]
    lookup.restype = ctypes.c_int
    info = ImageInfo()
    if (
        not lookup(ctypes.cast(function, ctypes.c_void_p), ctypes.byref(info))
        or not info.filename
    ):
        raise ValueError(f"Actual {label} calculation image could not be observed")
    mapped = Path(os.fsdecode(info.filename)).resolve()
    if mapped != expected_path.resolve():
        raise ValueError(f"Actual {label} calculation image differs")


def load_validated_manifest_and_library(
    path: Path,
    *,
    model_id: str,
    version: str,
    label: str,
    temp_prefix: str,
    unavailable_reason: str,
    cdll_loader: Callable[[str], Any] = ctypes.CDLL,
) -> tuple[Path, tuple[int, ...], tempfile.TemporaryDirectory[str], Path, Any]:
    raw = path.read_bytes()
    manifest = json.loads(
        raw,
        object_pairs_hook=lambda items: unique_json_pairs(items, f"{label} manifest"),
    )
    if not isinstance(manifest, dict):
        raise ValueError(f"{label} manifest must be an object")
    expected = dict(
        model_id=model_id,
        version=version,
        abi_version=1,
        system=platform.system(),
        machine=platform.machine(),
    )
    if platform.system() not in {"Darwin", "Linux"} or any(
        type(manifest.get(k)) is not type(v) or manifest.get(k) != v
        for k, v in expected.items()
    ):
        raise ValueError(f"{label} manifest does not match profile/ABI/platform")
    name = manifest["binary"]
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError(f"{label} binary must be a sibling filename")
    binary = (path.parent / name).resolve()
    if binary.parent != path.parent:
        raise ValueError(f"{label} binary escaped its manifest directory")
    binary_sig = file_signature(binary, unavailable_reason)
    data = binary.read_bytes()
    temporary = tempfile.TemporaryDirectory(prefix=temp_prefix)
    try:
        loaded = Path(temporary.name) / name
        loaded.write_bytes(data)
        library = cdll_loader(str(loaded))
    except Exception:
        temporary.cleanup()
        raise
    return binary, binary_sig, temporary, loaded, library
