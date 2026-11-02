"""Pinned VSOP2013 Sun provider with a checked, initialized native entry.

The named library embeds the complete EMB series and geocentric ERFA time
conversion. Its raw Swiss coordinate functions are private. This module has
no Python ERFA/JPL dependency and never silently changes orbital providers.
"""

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

from fatebridge.fetch_vsop2013 import MODEL_ID, source_profile
from fatebridge.utils.errors import EphemerisSourceError

MANIFEST_ENV = "FATEBRIDGE_VSOP2013_MANIFEST"
_LOCK = RLock()


def _finite(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate VSOP2013 manifest field")
        result[key] = value
    return result


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
        raise EphemerisSourceError("solar_vsop2013_unavailable") from error


class _ImageInfo(ctypes.Structure):
    _fields_ = [
        ("filename", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("symbol", ctypes.c_char_p),
        ("address", ctypes.c_void_p),
    ]


def _loaded_image(function: Any, expected: Path, digest: str) -> str:
    lookup = ctypes.CDLL(None).dladdr
    lookup.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ImageInfo)]
    lookup.restype = ctypes.c_int
    info = _ImageInfo()
    if (
        not lookup(ctypes.cast(function, ctypes.c_void_p), ctypes.byref(info))
        or not info.filename
    ):
        raise ValueError("Actual VSOP2013 coordinate entry could not be observed")
    actual = Path(os.fsdecode(info.filename)).resolve()
    if (
        actual != expected.resolve()
        or hashlib.sha256(actual.read_bytes()).hexdigest() != digest
    ):
        raise ValueError("Actual VSOP2013 calculation image differs")
    return digest


class _Source:
    def __init__(self, path: Path, signature: tuple[int, ...]):
        self.path, self.signature = path, signature
        try:
            self.profile, self.profile_sha256 = source_profile()
        except (OSError, ValueError, TypeError) as profile_error:
            raise EphemerisSourceError("solar_vsop2013_invalid") from profile_error
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            raw = path.read_bytes()
            manifest = json.loads(raw, object_pairs_hook=_pairs)
            if not isinstance(manifest, dict):
                raise ValueError("VSOP2013 manifest must be an object")
            expected = dict(
                model_id=MODEL_ID,
                version=self.profile["version"],
                abi_version=1,
                source_profile_sha256=self.profile_sha256,
                calculation_source_sha256=self.profile["calculation_source_sha256"],
                embedded_series_sha256=self.profile["embedded_series_sha256"],
                system=platform.system(),
                machine=platform.machine(),
            )
            if platform.system() not in {"Darwin", "Linux"} or any(
                type(manifest.get(key)) is not type(value) or manifest.get(key) != value
                for key, value in expected.items()
            ):
                raise ValueError(
                    "VSOP2013 manifest does not match profile/ABI/platform"
                )
            name = manifest["binary"]
            if not isinstance(name, str) or not name or Path(name).name != name:
                raise ValueError("VSOP2013 binary must be a sibling filename")
            binary = (path.parent / name).resolve()
            if binary.parent != path.parent:
                raise ValueError("VSOP2013 binary escaped its manifest directory")
            self.binary_path = binary
            self.binary_signature = _signature(binary)
            data = binary.read_bytes()
            self.binary_sha256 = hashlib.sha256(data).hexdigest()
            if self.binary_sha256 != manifest.get("binary_sha256"):
                raise ValueError("VSOP2013 binary does not match its receipt")
            self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
            # dlopen must not silently return an old image for a replaced name.
            self._temporary = tempfile.TemporaryDirectory(
                prefix="fatebridge-vsop2013-loaded-"
            )
            loaded = Path(self._temporary.name) / name
            loaded.write_bytes(data)
            if hashlib.sha256(loaded.read_bytes()).hexdigest() != self.binary_sha256:
                raise ValueError("VSOP2013 private loaded bytes differ")
            self.library = ctypes.CDLL(str(loaded))
            for symbol, value in (
                ("fatebridge_vsop2013_model_id", MODEL_ID),
                ("fatebridge_vsop2013_profile_sha256", self.profile_sha256),
            ):
                function = getattr(self.library, symbol)
                function.argtypes = []
                function.restype = ctypes.c_char_p
                if function() != value.encode("ascii"):
                    raise ValueError("Loaded VSOP2013 identity marker differs")
            self.library.fatebridge_vsop2013_abi_version.argtypes = []
            self.library.fatebridge_vsop2013_abi_version.restype = ctypes.c_int
            if self.library.fatebridge_vsop2013_abi_version() != 1:
                raise ValueError("Loaded VSOP2013 ABI differs")
            self.library.fatebridge_vsop2013_native_version.argtypes = [ctypes.c_char_p]
            self.library.fatebridge_vsop2013_native_version.restype = ctypes.c_char_p
            version = ctypes.create_string_buffer(256)
            self.library.fatebridge_vsop2013_native_version(version)
            self.native_version = version.value.decode("ascii")
            if self.native_version != self.profile["native_core_version"]:
                raise ValueError("Loaded VSOP2013 native reduction version differs")
            self.library.fatebridge_vsop2013_solar.argtypes = [
                ctypes.c_double,
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_char_p,
            ]
            self.library.fatebridge_vsop2013_solar.restype = ctypes.c_int
            self.loaded_image_sha256 = _loaded_image(
                self.library.fatebridge_vsop2013_solar, loaded, self.binary_sha256
            )
            # Verify the required failure before enabling any calculations.
            values = (ctypes.c_double * 6)()
            error = ctypes.create_string_buffer(1024)
            before = self.library.fatebridge_vsop2013_solar(2451545.0, values, error)
            if (
                before != -1
                or error.value != b"vsop2013_not_initialized"
                or any(math.isfinite(x) for x in values)
            ):
                raise ValueError(
                    "Loaded VSOP2013 image did not reject uninitialized use"
                )
            self.library.fatebridge_vsop2013_initialize.argtypes = []
            self.library.fatebridge_vsop2013_initialize.restype = ctypes.c_int
            if self.library.fatebridge_vsop2013_initialize() != 0:
                raise ValueError(
                    "Loaded VSOP2013 embedded series initialization failed"
                )
            self.check_unchanged()
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            OverflowError,
            AttributeError,
            UnicodeError,
            EphemerisSourceError,
        ) as error:
            if self._temporary is not None:
                self._temporary.cleanup()
            raise EphemerisSourceError("solar_vsop2013_invalid") from error

    def check_unchanged(self, *, check_environment: bool = True) -> None:
        try:
            configured = Path(os.environ.get(MANIFEST_ENV, "")).expanduser().resolve()
            if (
                (check_environment and configured != self.path)
                or _signature(self.path) != self.signature
                or _signature(self.binary_path) != self.binary_signature
            ):
                raise EphemerisSourceError("solar_vsop2013_changed")
        except (OSError, EphemerisSourceError) as error:
            raise EphemerisSourceError("solar_vsop2013_changed") from error

    def position(self, jd_tt: float) -> tuple[float, ...]:
        low, high = self.profile["working_jd_tt"]
        if not math.isfinite(jd_tt) or not low <= jd_tt <= high:
            raise EphemerisSourceError("solar_vsop2013_range")
        values = (ctypes.c_double * 6)()
        error = ctypes.create_string_buffer(1024)
        flags = self.library.fatebridge_vsop2013_solar(jd_tt, values, error)
        if (
            flags != 260
            or not all(math.isfinite(x) for x in values)
            or not 0.9 < values[3] < 1.1
        ):
            raise EphemerisSourceError("solar_vsop2013_calculation")
        return tuple(float(x) for x in values)

    def receipt(self) -> dict[str, Any]:
        return dict(
            model_id=MODEL_ID,
            version=self.profile["version"],
            source_profile_sha256=self.profile_sha256,
            calculation_source_sha256=self.profile["calculation_source_sha256"],
            embedded_series_sha256=self.profile["embedded_series_sha256"],
            build_manifest_sha256=self.manifest_sha256,
            binary_sha256=self.binary_sha256,
            loaded_image_sha256=self.loaded_image_sha256,
            binary_filename=self.binary_path.name,
            native_core_version=self.native_version,
            system=platform.system(),
            machine=platform.machine(),
            abi_version=1,
            coefficients_embedded=True,
            time_argument="TT, converted internally to TDB by full geocentric ERFA dtdb",
            position_frame="Geocentric apparent ecliptic/equinox of date; VSOP2013 full EMB, full Moshier Moon, Swiss2.10.03 reduction",
            calculation_flags_requested=260,
            source_url=self.profile["reference"],
            sources=deepcopy(self.profile["sources"]),
            software_input_years=list(self.profile["software_input_years"]),
            qualified_solar_term_years=list(self.profile["qualified_solar_term_years"]),
            working_jd_tt=list(self.profile["working_jd_tt"]),
            derived_lichun_scope=deepcopy(self.profile["derived_lichun_scope"]),
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
        raise EphemerisSourceError("solar_vsop2013_unavailable")
    path = Path(configured).expanduser().resolve()
    source = _load(path, _signature(path))
    try:
        source.check_unchanged()
    except EphemerisSourceError as error:
        if error.reason != "solar_vsop2013_changed":
            raise
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
        raise ValueError("VSOP2013 observations require finite numeric TT points")
    with _LOCK:
        source = _selected()
        observed = [source.position(float(value))[0] for value in jd_tts]
        source.check_unchanged()
        return dict(
            longitudes=observed, retflags=[260] * len(observed), model=source.receipt()
        )


def longitude_crossing_tt(
    target: float,
    low: float,
    high: float,
    *,
    expected_source_key: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not all(_finite(value) for value in (target, low, high)) or low >= high:
        raise ValueError(
            "VSOP2013 crossing requires finite target and increasing TT bracket"
        )
    target, low, high = float(target), float(low), float(high)
    with _LOCK:
        source = _selected()
        if expected_source_key is not None and source.key() != expected_source_key:
            raise EphemerisSourceError("solar_configuration_changed")

        def residual(epoch: float) -> tuple[float, float]:
            values = source.position(epoch)
            return math.remainder(values[0] - target, 360.0), values[3]

        left, right = residual(low)[0], residual(high)[0]
        if not left < 0 <= right or right - left >= 90:
            raise ValueError(
                "VSOP2013 bracket does not contain a forward solar crossing"
            )
        epoch = (low + high) / 2
        for _ in range(8):
            value, speed = residual(epoch)
            if value < 0:
                low = epoch
            else:
                high = epoch
            trial = epoch - value / speed
            if trial == epoch:
                points = {epoch}
                before = after = epoch
                for _ in range(4):
                    before = math.nextafter(before, -math.inf)
                    after = math.nextafter(after, math.inf)
                    points.update((before, after))
                evaluated = [(point, residual(point)[0]) for point in sorted(points)]
                found = False
                for (a, fa), (b, fb) in zip(evaluated, evaluated[1:]):
                    if fa < 0 <= fb:
                        low, high, found = a, b, True
                        break
                if found:
                    break
            epoch = trial if low < trial < high else (low + high) / 2
        # Preserve the exact binary64 termination, never a coarse time stop.
        for _ in range(48):
            middle = (low + high) / 2
            if middle == low or middle == high:
                break
            if residual(middle)[0] < 0:
                low = middle
            else:
                high = middle
        if not residual(low)[0] < 0 <= residual(high)[0]:
            raise EphemerisSourceError("solar_vsop2013_calculation")
        source.check_unchanged()
        return dict(
            jd_tt=(low + high) / 2,
            bracket_tt=[low, high],
            bracket_seconds=(high - low) * 86400.0,
            model={**source.receipt(), "internal_observed_retflags": [260]},
        )
