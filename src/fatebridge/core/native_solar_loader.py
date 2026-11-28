"""Shared manifest, signature, dladdr, and temp-copy loader for optional native solar libs."""

from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, TypeVar

from fatebridge.utils.errors import EphemerisSourceError

_T = TypeVar("_T")


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


def load_astronomy_json(filename: str, *, label: str) -> dict[str, Any]:
    raw = files("fatebridge").joinpath("data/astronomy").joinpath(filename).read_bytes()
    data = json.loads(
        raw,
        object_pairs_hook=lambda items: unique_json_pairs(items, label),
    )
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be an object")
    return data


class NativeSolarSourceBase:
    """Shared path/signature/environment tracking and temp cleanup for native solar libs."""

    _manifest_env: str
    _unavailable_reason: str
    _changed_reason: str

    def __init__(
        self,
        path: Path,
        signature: tuple[int, ...],
        *,
        manifest_env: str,
        unavailable_reason: str,
        changed_reason: str,
    ) -> None:
        self.path = path
        self.signature = signature
        self._manifest_env = manifest_env
        self._unavailable_reason = unavailable_reason
        self._changed_reason = changed_reason
        self.binary_path = path
        self.binary_signature: tuple[int, ...] = ()
        self._temporary: tempfile.TemporaryDirectory[str] | None = None

    def _cleanup_temporary(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()

    def check_unchanged(self, *, check_environment: bool = True) -> None:
        try:
            configured = (
                Path(os.environ.get(self._manifest_env, "")).expanduser().resolve()
            )
            if (
                (check_environment and configured != self.path)
                or file_signature(self.path, self._unavailable_reason) != self.signature
                or file_signature(self.binary_path, self._unavailable_reason)
                != self.binary_signature
            ):
                raise EphemerisSourceError(self._changed_reason)
        except (OSError, EphemerisSourceError) as error:
            raise EphemerisSourceError(self._changed_reason) from error

    def key(self) -> tuple[Any, ...]:
        return (
            str(self.path),
            self.signature,
            self.binary_signature,
        )


def select_env_backed_source(
    env_var: str,
    load_fn: Callable[[Path, tuple[int, ...]], _T],
    unavailable_reason: str,
    *,
    retry_changed_reason: str | None = None,
    clear_cache_fn: Callable[[], None] | None = None,
) -> _T:
    configured = os.environ.get(env_var, "").strip()
    if not configured:
        raise EphemerisSourceError(unavailable_reason)
    path = Path(configured).expanduser().resolve()
    source = load_fn(path, file_signature(path, unavailable_reason))
    if retry_changed_reason is None or not isinstance(source, NativeSolarSourceBase):
        return source
    try:
        source.check_unchanged()
    except EphemerisSourceError as error:
        if error.reason != retry_changed_reason:
            raise
        if clear_cache_fn is not None:
            clear_cache_fn()
        source = load_fn(path, file_signature(path, unavailable_reason))
        if isinstance(source, NativeSolarSourceBase):
            source.check_unchanged()
    return source


def validate_crossing_inputs(
    target: float,
    low: float,
    high: float,
    *,
    message: str,
    reject_bool: bool = True,
) -> None:
    if reject_bool:
        valid = all(is_finite_number(value) for value in (target, low, high))
    else:
        valid = all(math.isfinite(value) for value in (target, low, high))
    if not valid or low >= high:
        raise ValueError(message)


def validate_forward_bracket(
    left: float,
    right: float,
    *,
    message: str,
    max_span: float | None = 90.0,
) -> None:
    if not left < 0 <= right or (max_span is not None and right - left >= max_span):
        raise ValueError(message)


def bisect_forward_crossing(
    residual: Callable[[float], float],
    low: float,
    high: float,
    max_iterations: int,
) -> tuple[float, float, int]:
    """Binary64 midpoint bisection preserving exact `(low + high) / 2.0` termination."""
    iterations = 0
    for _ in range(max_iterations):
        middle = (low + high) / 2.0
        if middle == low or middle == high:
            break
        if residual(middle) < 0:
            low = middle
        else:
            high = middle
        iterations += 1
    return low, high, iterations
