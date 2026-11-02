"""Explicit AA1996 Sun provider with loaded binary and source identities."""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import platform
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from fatebridge.fetch_aa1996 import MODEL_ID, source_profile
from fatebridge.utils.errors import EphemerisSourceError

MANIFEST_ENV = "FATEBRIDGE_AA1996_MANIFEST"
_LOCK = RLock()


@lru_cache(maxsize=1)
def _profile() -> tuple[dict[str, Any], str]:
    return source_profile()


def _signature(path: Path) -> tuple[int, ...]:
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
        raise EphemerisSourceError("solar_aa1996_unavailable") from error


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate model manifest field")
        result[key] = value
    return result


def _finite(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


class _ImageInfo(ctypes.Structure):
    _fields_ = [
        ("filename", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("symbol", ctypes.c_char_p),
        ("address", ctypes.c_void_p),
    ]


def _loaded_image(function: Any, expected_path: Path, expected_hash: str) -> str:
    """Observe the image containing the actual calculation entry address."""
    lookup = ctypes.CDLL(None).dladdr
    lookup.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ImageInfo)]
    lookup.restype = ctypes.c_int
    info = _ImageInfo()
    if (
        not lookup(ctypes.cast(function, ctypes.c_void_p), ctypes.byref(info))
        or not info.filename
    ):
        raise ValueError("Actual calculation image could not be resolved")
    mapped = Path(os.fsdecode(info.filename)).resolve()
    if mapped != expected_path.resolve():
        raise ValueError("Calculation entry was resolved from another image")
    digest = hashlib.sha256(mapped.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise ValueError("Actual calculation image bytes differ")
    return digest


class _Source:
    def __init__(self, path: Path, signature: tuple[int, ...]):
        self.path, self.signature = path, signature
        self.profile, self.profile_sha256 = _profile()
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            raw = path.read_bytes()
            manifest = json.loads(raw, object_pairs_hook=_pairs)
            if not isinstance(manifest, dict):
                raise ValueError("Model manifest must be an object")
            expected = dict(
                model_id=MODEL_ID,
                version=self.profile["version"],
                abi_version=1,
                source_profile_sha256=self.profile_sha256,
                calculation_source_sha256=self.profile["calculation_source_sha256"],
                system=platform.system(),
                machine=platform.machine(),
            )
            if platform.system() not in {"Darwin", "Linux"} or any(
                type(manifest.get(k)) is not type(value) or manifest.get(k) != value
                for k, value in expected.items()
            ):
                raise ValueError(
                    "Manifest does not describe the loaded model/profile/platform"
                )
            name = manifest["binary"]
            if not isinstance(name, str) or not name or Path(name).name != name:
                raise ValueError("Model binary must be a sibling filename")
            binary = (path.parent / name).resolve()
            if binary.parent != path.parent:
                raise ValueError("Model binary must remain in its manifest directory")
            self.binary_path = binary
            self.binary_signature = _signature(binary)
            data = binary.read_bytes()
            self.binary_sha256 = hashlib.sha256(data).hexdigest()
            if self.binary_sha256 != manifest.get("binary_sha256"):
                raise ValueError("Binary differs from build manifest")
            self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
            # A unique private copy avoids dlopen returning an old image for a
            # replaced configured filename. Hash that copy before loading it.
            self._temporary = tempfile.TemporaryDirectory(
                prefix="fatebridge-aa1996-loaded-"
            )
            loaded = Path(self._temporary.name) / name
            loaded.write_bytes(data)
            if hashlib.sha256(loaded.read_bytes()).hexdigest() != self.binary_sha256:
                raise ValueError("Private loaded bytes differ")
            self.library = ctypes.CDLL(str(loaded))
            for symbol, wanted in [
                ("fatebridge_aa1996_model_id", MODEL_ID),
                ("fatebridge_aa1996_profile_sha256", self.profile_sha256),
            ]:
                function = getattr(self.library, symbol)
                function.argtypes = []
                function.restype = ctypes.c_char_p
                if function() != wanted.encode("ascii"):
                    raise ValueError("Actual binary model marker differs")
            self.library.fatebridge_aa1996_abi_version.argtypes = []
            self.library.fatebridge_aa1996_abi_version.restype = ctypes.c_int
            if self.library.fatebridge_aa1996_abi_version() != 1:
                raise ValueError("Unsupported model ABI")
            self.library.fatebridge_aa1996_solar.argtypes = [
                ctypes.c_double,
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_char_p,
            ]
            self.library.fatebridge_aa1996_solar.restype = ctypes.c_int
            self.loaded_image_sha256 = _loaded_image(
                self.library.fatebridge_aa1996_solar, loaded, self.binary_sha256
            )
            self.library.swe_version.argtypes = [ctypes.c_char_p]
            self.library.swe_version.restype = ctypes.c_char_p
            version = ctypes.create_string_buffer(256)
            self.library.swe_version(version)
            self.native_version = version.value.decode("ascii")
            if self.native_version != self.profile["sources"]["swiss"]["core_version"]:
                raise ValueError("Actual native core version differs")
            self.library.swe_set_ephe_path.argtypes = [ctypes.c_char_p]
            self.library.swe_set_ephe_path.restype = None
            self.library.swe_set_ephe_path(self._temporary.name.encode())
            self.check_unchanged(check_environment=False)
        except Exception as error:
            if self._temporary is not None:
                self._temporary.cleanup()
            if isinstance(error, EphemerisSourceError):
                raise
            raise EphemerisSourceError("solar_aa1996_invalid") from error

    def check_unchanged(self, *, check_environment: bool = True) -> None:
        try:
            configured = Path(os.environ.get(MANIFEST_ENV, "")).expanduser().resolve()
            if (
                (check_environment and configured != self.path)
                or _signature(self.path) != self.signature
                or _signature(self.binary_path) != self.binary_signature
            ):
                raise EphemerisSourceError("solar_aa1996_changed")
        except (OSError, EphemerisSourceError) as error:
            raise EphemerisSourceError("solar_aa1996_changed") from error

    def longitude(self, jd_tt: float) -> tuple[float, int]:
        low, high = self.profile["working_jd_tt"]
        if not low <= jd_tt <= high:
            raise EphemerisSourceError("solar_aa1996_range")
        values = (ctypes.c_double * 6)()
        error = ctypes.create_string_buffer(1024)
        flags = self.library.fatebridge_aa1996_solar(jd_tt, values, error)
        # Exact options: apparent/geocentric/date ecliptic, Moshier category,
        # speed. This category flag does not identify the custom orbital model.
        if flags != 260 or not all(math.isfinite(x) for x in values):
            raise EphemerisSourceError("solar_aa1996_calculation")
        return float(values[0]) % 360.0, int(flags)

    def receipt(self) -> dict[str, Any]:
        return dict(
            model_id=MODEL_ID,
            version=self.profile["version"],
            source_profile_sha256=self.profile_sha256,
            calculation_source_sha256=self.profile["calculation_source_sha256"],
            build_manifest_sha256=self.manifest_sha256,
            binary_sha256=self.binary_sha256,
            loaded_image_sha256=self.loaded_image_sha256,
            binary_filename=self.binary_path.name,
            native_core_version=self.native_version,
            system=platform.system(),
            machine=platform.machine(),
            abi_version=1,
            time_argument="TT via Swiss swe_calc",
            position_frame="Geocentric apparent ecliptic/equinox of date, Swiss2.10.03 default astronomy models with AA1996 EMB and full Moshier Moon",
            calculation_flags_requested=260,
            source_url=self.profile["reference"],
            sources=deepcopy(self.profile["sources"]),
            software_input_years=list(self.profile["software_input_years"]),
            qualified_solar_term_years=list(self.profile["qualified_solar_term_years"]),
            working_jd_tt=list(self.profile["working_jd_tt"]),
            native_moshier_relabelled=False,
            accuracy_certified=False,
            source_identity_scope="Locally built and actually loaded binary/profile identity; not upstream signature, atomic external-file immutability or all-epoch physical/civil accuracy",
        )

    def key(self) -> tuple[Any, ...]:
        return (
            str(self.path),
            self.signature,
            self.manifest_sha256,
            self.binary_signature,
            self.binary_sha256,
            self.profile_sha256,
        )


@lru_cache(maxsize=2)
def _load(path: Path, signature: tuple[int, ...]) -> _Source:
    return _Source(path, signature)


def _selected() -> _Source:
    configured = os.environ.get(MANIFEST_ENV, "").strip()
    if not configured:
        raise EphemerisSourceError("solar_aa1996_unavailable")
    path = Path(configured).expanduser().resolve()
    source = _load(path, _signature(path))
    try:
        source.check_unchanged()
    except EphemerisSourceError as error:
        if error.reason != "solar_aa1996_changed":
            raise
        # A new request may resolve a fresh build after an installation. A
        # source already held by an active batch still fails on any drift.
        _load.cache_clear()
        source = _load(path, _signature(path))
        source.check_unchanged()
    return source


def cache_key() -> tuple[Any, ...]:
    with _LOCK:
        return _selected().key()


def source_receipt() -> dict[str, Any]:
    with _LOCK:
        return _selected().receipt()


def solar_longitudes_tt(jd_tts: list[float]) -> dict[str, Any]:
    if not all(_finite(value) for value in jd_tts):
        raise ValueError("AA1996 observations require finite numeric TT points")
    with _LOCK:
        source = _selected()
        observed = [source.longitude(float(value)) for value in jd_tts]
        source.check_unchanged()
        return dict(
            longitudes=[x[0] for x in observed],
            retflags=[x[1] for x in observed],
            model=source.receipt(),
        )


def longitude_crossing_tt(
    target: float,
    low: float,
    high: float,
    *,
    expected_source_key: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not all(_finite(value) for value in [target, low, high]) or low >= high:
        raise ValueError(
            "AA1996 crossing requires finite target and increasing TT bracket"
        )
    with _LOCK:
        source = _selected()
        if expected_source_key is not None and source.key() != expected_source_key:
            raise EphemerisSourceError("solar_configuration_changed")
        observed_flags = set()

        def residual(epoch: float) -> float:
            angle, flags = source.longitude(epoch)
            observed_flags.add(flags)
            return math.remainder(angle - target, 360.0)

        left, right = residual(low), residual(high)
        if not left < 0 <= right or right - left >= 90:
            raise ValueError("AA1996 bracket does not contain a forward solar crossing")
        for _ in range(48):
            middle = (low + high) / 2.0
            if middle == low or middle == high:
                break
            if residual(middle) < 0:
                low = middle
            else:
                high = middle
        source.check_unchanged()
        return dict(
            jd_tt=(low + high) / 2.0,
            bracket_tt=[low, high],
            bracket_seconds=(high - low) * 86400.0,
            model={
                **source.receipt(),
                "internal_observed_retflags": sorted(observed_flags),
            },
        )
