"""Explicit, file-backed JPL SPK solar longitude; optional ``jpl`` extra.

Only raw type2 barycentric vectors are read, never reference event tables.
Geocentric ERFA dtdb, source-derived annual aberration and IAU2006/2000B
date-frame conversion are separate from the native Swiss solar backend.
"""

from __future__ import annotations

import hashlib
import math
import os
import weakref
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from threading import RLock
from typing import Any

from fatebridge.core.analytic_solar import (
    C_AU_DAY,
    aberration,
    apparent_ecliptic,
    profile,
)
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "fatebridge_jpl_spk_solar_v1"
FILE_ENV = "FATEBRIDGE_SOLAR_SPK_FILE"
AU_KM = 149597870.7
_LOCK = RLock()


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
        raise EphemerisSourceError("solar_spk_unavailable") from error


class _KernelSun:
    def __init__(self, path: Path, signature: tuple[int, ...]):
        try:
            erfa = import_module("erfa")
            jplephem = import_module("jplephem")
            np = import_module("numpy")
            SPK = import_module("jplephem.spk").SPK
        except ImportError as error:
            raise ImportError(
                "JPL SPK太阳模型需要安装FateBridge的jpl可选依赖"
            ) from error
        self.path, self.signature, self.erfa = path, signature, erfa
        # Report modules actually loaded for this kernel, even if a separate
        # installer changes distribution metadata while this process runs.
        self.dependencies = {
            "jplephem": str(jplephem.__version__),
            "pyerfa": str(erfa.__version__),
            "numpy": str(np.__version__),
        }
        self.kernel: Any = None
        try:
            self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            self.kernel = SPK.open(str(path))
            self.segments = {
                pair: [s for s in self.kernel.segments if (s.center, s.target) == pair]
                for pair in [(0, 3), (3, 399), (0, 10)]
            }
            if any(
                not group or any(s.data_type != 2 or s.frame != 1 for s in group)
                for group in self.segments.values()
            ):
                raise ValueError("Required type2 Earth/EMB/Sun segments absent")
            self.coverage = {
                f"{a}->{b}": [[float(s.start_jd), float(s.end_jd)] for s in group]
                for (a, b), group in self.segments.items()
            }
            self.check_unchanged()
        except Exception as error:
            if self.kernel is not None:
                self.kernel.close()
            if isinstance(error, EphemerisSourceError):
                raise
            raise EphemerisSourceError("solar_spk_invalid") from error
        # Eviction must not close a kernel still held by another active root.
        self._finalizer = weakref.finalize(self, self.kernel.close)

    def check_unchanged(self) -> None:
        if _signature(self.path) != self.signature:
            raise EphemerisSourceError("solar_spk_changed")

    def segment(self, pair: tuple[int, int], tdb2: float) -> Any:
        # SPK priority is the last applicable segment, not simply the last
        # segment for that body across disjoint time intervals.
        epoch = 2451545.0 + tdb2
        for segment in reversed(self.segments[pair]):
            if segment.start_jd <= epoch <= segment.end_jd:
                return segment
        raise EphemerisSourceError("solar_spk_range")

    def longitude(self, jd_tt: float) -> float:
        correction = float(self.erfa.dtdb(2451545.0, jd_tt - 2451545.0, 0, 0, 0, 0))
        tdb2 = (jd_tt - 2451545.0) + correction / 86400
        emb, embv = self.segment((0, 3), tdb2).compute_and_differentiate(
            2451545.0, tdb2
        )
        earth, earthv = self.segment((3, 399), tdb2).compute_and_differentiate(
            2451545.0, tdb2
        )
        earth_bary, velocity = (emb + earth) / AU_KM, (embv + earthv) / AU_KM
        sun = self.segment((0, 10), tdb2).compute(2451545.0, tdb2) / AU_KM
        helio_distance = math.sqrt(sum((earth_bary - sun) ** 2))
        vector = sun - earth_bary
        for _ in range(3):
            delay = math.sqrt(sum(vector**2)) / C_AU_DAY
            sun = (
                self.segment((0, 10), tdb2 - delay).compute(2451545.0, tdb2 - delay)
                / AU_KM
            )
            vector = sun - earth_bary
        distance = math.sqrt(sum(vector**2))
        natural = tuple(float(v / distance) for v in vector)
        velocity_c = tuple(float(v / C_AU_DAY) for v in velocity)
        apparent = aberration(
            (natural[0], natural[1], natural[2]),
            (velocity_c[0], velocity_c[1], velocity_c[2]),
            helio_distance,
        )
        ecliptic = apparent_ecliptic(apparent, jd_tt)
        value = math.degrees(math.atan2(ecliptic[1], ecliptic[0])) % 360
        if not math.isfinite(value):
            raise EphemerisSourceError("solar_spk_invalid")
        return value

    def receipt(self) -> dict[str, Any]:
        return {
            "model_id": MODEL_ID,
            "kernel_filename": self.path.name,
            "kernel_sha256": self.sha256,
            "kernel_type": "DAF/SPK_type2",
            "spk_frame_id": 1,
            "segment_coverage_tdb_jd": {
                k: [p[:] for p in v] for k, v in self.coverage.items()
            },
            "time_argument": "TDB from TT via geocentric ERFA dtdb",
            "position_frame": "BCRS then IAU2006/P03 and IAU2000B true ecliptic of date",
            "frame_coefficient_sha256": profile()["loaded_sha256"],
            "light_time_iterations": 3,
            "dependencies": dict(self.dependencies),
            "source_url": "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html",
            "time_source_url": "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/time.html",
            "native_moshier_relabelled": False,
            "accuracy_certified": False,
            "source_identity_scope": "Actual selected file bytes; not authentication of a NASA download, atomic immutability or full physical/civil UTC accuracy",
        }


@lru_cache(maxsize=2)
def _load(path: Path, signature: tuple[int, ...]) -> _KernelSun:
    return _KernelSun(path, signature)


def _selected() -> _KernelSun:
    value = os.environ.get(FILE_ENV, "").strip()
    if not value:
        raise EphemerisSourceError("solar_spk_unavailable")
    path = Path(value).expanduser().resolve()
    return _load(path, _signature(path))


def cache_key() -> tuple[Any, ...]:
    with _LOCK:
        source = _selected()
        return (
            str(source.path),
            source.signature,
            source.sha256,
            profile()["loaded_sha256"],
        )


def source_receipt() -> dict[str, Any]:
    with _LOCK:
        return _selected().receipt()


def solar_longitudes_tt(jd_tts: list[float]) -> dict[str, Any]:
    """Observe one loaded SPK source at finite TT points, under one lock."""
    if not all(
        type(value) in (int, float) and math.isfinite(value) for value in jd_tts
    ):
        raise ValueError("SPK observations require finite numeric TT points")
    with _LOCK:
        source = _selected()
        selected_key = cache_key()
        before = source.receipt()
        values = [source.longitude(value) for value in jd_tts]
        source.check_unchanged()
        if before != source.receipt() or selected_key != cache_key():
            raise EphemerisSourceError("solar_configuration_changed")
        return {"longitudes": values, "model": before}


def longitude_crossing_tt(
    target: float,
    low: float,
    high: float,
    *,
    expected_source_key: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not all(math.isfinite(x) for x in (target, low, high)) or low >= high:
        raise ValueError("SPK crossing requires a finite increasing TT bracket")
    with _LOCK:
        source = _selected()

        actual_key = (
            str(source.path),
            source.signature,
            source.sha256,
            profile()["loaded_sha256"],
        )
        if expected_source_key is not None and actual_key != expected_source_key:
            raise EphemerisSourceError("solar_configuration_changed")

        def residual(epoch: float) -> float:
            return math.remainder(source.longitude(epoch) - target, 360)

        if not residual(low) < 0 <= residual(high):
            raise ValueError("SPK TT bracket does not contain a forward crossing")
        iterations = 0
        for _ in range(40):
            middle = (low + high) / 2
            if middle == low or middle == high:
                break
            if residual(middle) < 0:
                low = middle
            else:
                high = middle
            iterations += 1
        source.check_unchanged()
        return {
            "jd_tt": (low + high) / 2,
            "bracket_tt": [low, high],
            "bracket_seconds": (high - low) * 86400,
            "iterations": iterations,
            "numerical_resolution_is_physical_accuracy": False,
            "model": source.receipt(),
        }
