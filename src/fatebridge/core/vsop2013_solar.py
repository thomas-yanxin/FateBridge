"""Pinned VSOP2013 Sun provider with a checked, initialized native entry.

The named library embeds the complete EMB series and geocentric ERFA time
conversion. Its raw Swiss coordinate functions are private. This module has
no Python ERFA/JPL dependency and never silently changes orbital providers.
"""

from __future__ import annotations

import ctypes
import math
import os
import platform
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from fatebridge.core.native_solar_loader import (
    file_signature,
    is_finite_number,
    load_validated_manifest_and_library,
    verify_loaded_image,
)
from fatebridge.fetch_vsop2013 import MODEL_ID, source_profile
from fatebridge.utils.errors import EphemerisSourceError

MANIFEST_ENV = "FATEBRIDGE_VSOP2013_MANIFEST"
LOCK = RLock()

_finite = is_finite_number


def _signature(path: Path) -> tuple[int, ...]:
    return file_signature(path, "solar_vsop2013_unavailable")


def _loaded_image(function: Any, expected: Path) -> None:
    verify_loaded_image(function, expected, "VSOP2013")


class _Source:
    def __init__(self, path: Path, signature: tuple[int, ...]) -> None:
        self.path, self.signature = path, signature
        try:
            self.profile = source_profile()
        except (OSError, ValueError, TypeError) as profile_error:
            raise EphemerisSourceError("solar_vsop2013_invalid") from profile_error
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            (
                self.binary_path,
                self.binary_signature,
                self._temporary,
                loaded,
                self.library,
            ) = load_validated_manifest_and_library(
                path,
                model_id=MODEL_ID,
                version=self.profile["version"],
                label="VSOP2013",
                temp_prefix="fatebridge-vsop2013-loaded-",
                unavailable_reason="solar_vsop2013_unavailable",
                cdll_loader=ctypes.CDLL,
            )
            function = getattr(self.library, "fatebridge_vsop2013_model_id")
            function.argtypes = []
            function.restype = ctypes.c_char_p
            if function() != MODEL_ID.encode("ascii"):
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
            _loaded_image(self.library.fatebridge_vsop2013_solar, loaded)
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
            binary_filename=self.binary_path.name,
            native_core_version=self.native_version,
            system=platform.system(),
            machine=platform.machine(),
            abi_version=1,
            coefficients_embedded=True,
            time_argument="TT, converted internally to TDB by full geocentric ERFA dtdb",
            position_frame="Geocentric apparent ecliptic/equinox of date; VSOP2013 full EMB, full Moshier Moon, Swiss2.10.03 reduction",
            calculation_flags_requested=260,
            sources=deepcopy(self.profile["sources"]),
            software_input_years=list(self.profile["software_input_years"]),
            qualified_solar_term_years=list(self.profile["qualified_solar_term_years"]),
            working_jd_tt=list(self.profile["working_jd_tt"]),
            derived_lichun_scope=deepcopy(self.profile["derived_lichun_scope"]),
            native_moshier_relabelled=False,
            accuracy_certified=False,
        )

    def key(self) -> tuple[Any, ...]:
        return (
            str(self.path),
            self.signature,
            self.binary_signature,
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
    with LOCK:
        return _selected().key()


def source_receipt() -> dict[str, Any]:
    with LOCK:
        return _selected().receipt()


def solar_longitudes_tt(jd_tts: list[float]) -> dict[str, Any]:
    if not all(_finite(value) for value in jd_tts):
        raise ValueError("VSOP2013 observations require finite numeric TT points")
    with LOCK:
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
    with LOCK:
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
