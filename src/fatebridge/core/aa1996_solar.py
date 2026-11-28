"""Explicit AA1996 Sun provider with loaded binary and source identities."""

from __future__ import annotations

import ctypes
import math
import platform
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from fatebridge.core.native_solar_loader import (
    NativeSolarSourceBase,
    bisect_forward_crossing,
    file_signature,
    is_finite_number,
    load_astronomy_json,
    load_validated_manifest_and_library,
    select_env_backed_source,
    validate_crossing_inputs,
    validate_forward_bracket,
    verify_loaded_image,
)
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "fatebridge_moshier_aa1996_solar_v1"
MANIFEST_ENV = "FATEBRIDGE_AA1996_MANIFEST"
LOCK = RLock()

_finite = is_finite_number


def source_profile() -> dict[str, Any]:
    profile = load_astronomy_json("aa1996-solar-v1.json", label="AA1996 source profile")
    if profile.get("model_id") != MODEL_ID or profile.get("abi_version") != 1:
        raise ValueError("Invalid AA1996 source profile")
    return profile


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    return source_profile()


def _signature(path: Path) -> tuple[int, ...]:
    return file_signature(path, "solar_aa1996_unavailable")


def _loaded_image(function: Any, expected_path: Path) -> None:
    verify_loaded_image(function, expected_path, "AA1996")


class _Source(NativeSolarSourceBase):
    def __init__(self, path: Path, signature: tuple[int, ...]) -> None:
        super().__init__(
            path,
            signature,
            manifest_env=MANIFEST_ENV,
            unavailable_reason="solar_aa1996_unavailable",
            changed_reason="solar_aa1996_changed",
        )
        try:
            self.profile = _profile()
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
                label="AA1996",
                temp_prefix="fatebridge-aa1996-loaded-",
                unavailable_reason="solar_aa1996_unavailable",
                cdll_loader=ctypes.CDLL,
            )
            function = getattr(self.library, "fatebridge_aa1996_model_id")
            function.argtypes = []
            function.restype = ctypes.c_char_p
            if function() != MODEL_ID.encode("ascii"):
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
            _loaded_image(self.library.fatebridge_aa1996_solar, loaded)
            self.library.swe_version.argtypes = [ctypes.c_char_p]
            self.library.swe_version.restype = ctypes.c_char_p
            version = ctypes.create_string_buffer(256)
            self.library.swe_version(version)
            self.native_version = version.value.decode("ascii")
            if self.native_version != self.profile["sources"]["swiss"]["core_version"]:
                raise ValueError("Actual native core version differs")
            self.library.swe_set_ephe_path.argtypes = [ctypes.c_char_p]
            self.library.swe_set_ephe_path.restype = None
            assert self._temporary is not None
            self.library.swe_set_ephe_path(self._temporary.name.encode())
            self.check_unchanged(check_environment=False)
        except Exception as error:
            self._cleanup_temporary()
            if isinstance(error, EphemerisSourceError):
                raise
            raise EphemerisSourceError("solar_aa1996_invalid") from error

    def longitude(self, jd_tt: float) -> tuple[float, int]:
        """Evaluate a TT point already qualified by the calling boundary."""
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
            binary_filename=self.binary_path.name,
            native_core_version=self.native_version,
            system=platform.system(),
            machine=platform.machine(),
            abi_version=1,
            time_argument="TT via Swiss swe_calc",
            position_frame="Geocentric apparent ecliptic/equinox of date, Swiss2.10.03 default astronomy models with AA1996 EMB and full Moshier Moon",
            calculation_flags_requested=260,
            sources=deepcopy(self.profile["sources"]),
            software_input_years=list(self.profile["software_input_years"]),
            qualified_solar_term_years=list(self.profile["qualified_solar_term_years"]),
            working_jd_tt=list(self.profile["working_jd_tt"]),
            derived_lichun_scope=deepcopy(self.profile["derived_lichun_scope"]),
            native_moshier_relabelled=False,
            accuracy_certified=False,
        )


@lru_cache(maxsize=2)
def _load(path: Path, signature: tuple[int, ...]) -> _Source:
    return _Source(path, signature)


def _selected() -> _Source:
    return select_env_backed_source(
        MANIFEST_ENV,
        _load,
        "solar_aa1996_unavailable",
        retry_changed_reason="solar_aa1996_changed",
        clear_cache_fn=_load.cache_clear,
    )


def cache_key() -> tuple[Any, ...]:
    with LOCK:
        return _selected().key()


def source_receipt() -> dict[str, Any]:
    with LOCK:
        return _selected().receipt()


def solar_longitudes_tt(jd_tts: list[float]) -> dict[str, Any]:
    if not all(_finite(value) for value in jd_tts):
        raise ValueError("AA1996 observations require finite numeric TT points")
    with LOCK:
        source = _selected()
        low, high = source.profile["working_jd_tt"]
        if not all(low <= value <= high for value in jd_tts):
            raise EphemerisSourceError("solar_aa1996_range")
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
    projection_year: int | None = None,
) -> dict[str, Any]:
    validate_crossing_inputs(
        target,
        low,
        high,
        message="AA1996 crossing requires finite target and increasing TT bracket",
    )
    with LOCK:
        source = _selected()
        if expected_source_key is not None and source.key() != expected_source_key:
            raise EphemerisSourceError("solar_configuration_changed")
        scope = source.profile["derived_lichun_scope"]
        if projection_year is not None:
            if type(projection_year) is not int or target != scope["target_degrees"]:
                raise ValueError("AA1996 projection context requires a Lichun year")
            first = date(projection_year, 2, 1).toordinal() + 1721424.5
            last = date(projection_year, 2, 12).toordinal() + 1721424.5
            if not first <= low < high <= last:
                raise ValueError("AA1996 projection bracket must belong to its year")
        working_low, working_high = source.profile["working_jd_tt"]
        if not working_low <= low < high <= working_high and not (
            projection_year is not None
            and scope["years"][0] <= projection_year <= scope["years"][1]
        ):
            raise EphemerisSourceError("solar_aa1996_range")
        observed_flags = set()

        def residual(epoch: float) -> float:
            angle, flags = source.longitude(epoch)
            observed_flags.add(flags)
            return math.remainder(angle - target, 360.0)

        left, right = residual(low), residual(high)
        validate_forward_bracket(
            left,
            right,
            message="AA1996 bracket does not contain a forward solar crossing",
        )
        low, high, _ = bisect_forward_crossing(residual, low, high, 48)
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
