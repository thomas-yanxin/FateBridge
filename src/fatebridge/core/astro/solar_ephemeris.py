"""One locked, source-traced Sun batch for directions and time samples.

Equal TT epochs share an observation. Different physical epochs may legitimately
use different models; only comparable birth-time samples share a source cohort.
"""

from __future__ import annotations

import math
import sys
from types import TracebackType
from typing import Any, Dict, Literal

from fatebridge.core import ephemeris_runtime as ephemeris
from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
)
from fatebridge.utils.errors import EphemerisSourceError


def sun_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """Keep all Sun-call contexts, including the lunar Earth/EMB dependency.

    Swiss 2.10.03 sweplan can internally fall back to an analytical Moon while
    the Sun return flag still says SWIEPH. Do not drop the Moon context to make
    a source cohort look consistent. This is still not an atomic read-set proof.
    """
    row = source["by_factor"]["Sun"]
    files = [f for f in source["files"] if f["id"] in row["file_ids"]]
    return {
        "by_factor": {"Sun": {**row, "file_ids": [f["id"] for f in files]}},
        "files": files,
    }


class SolarEphemerisBatch:
    """Use as a context manager; result is available after successful exit."""

    def __init__(self) -> None:
        self.observations: list[Dict[str, Any]] = []
        self._indices: Dict[float, int] = {}
        self.result: Dict[str, Any] | None = None
        self._active = False
        self._entered = False

    def __enter__(self) -> SolarEphemerisBatch:
        if self._entered:
            raise RuntimeError("A Sun ephemeris batch cannot be reused")
        self._entered = True
        self._guard = runtime.preserve_ephemeris_path()
        self._guard.__enter__()
        try:
            self._path = ephemeris.configured_ephemeris_path()
            self._trace = PhysicalEphemerisTrace()
            if runtime.swe is not None:
                runtime.swe.set_ephe_path(self._path or "")
            self._active = True
        except BaseException:
            self._guard.__exit__(*sys.exc_info())
            raise
        return self

    def _check_configuration(self) -> None:
        if ephemeris.configured_ephemeris_path() != self._path:
            raise EphemerisSourceError("solar_configuration_changed")

    def sun(self, jd_tt: float) -> Dict[str, Any]:
        if not self._active:
            raise RuntimeError("Sun observations require an active ephemeris batch")
        if not math.isfinite(jd_tt):
            raise ValueError("Sun TT Julian day must be finite")
        self._check_configuration()
        if jd_tt in self._indices:
            return self.observations[self._indices[jd_tt]]
        swe = runtime.swe
        if swe is None:
            raise ValueError("Swiss Ephemeris is required for the tropical Sun")
        position, flag = runtime.ephemeris_call("calc", jd_tt, swe.SUN, swe.FLG_SWIEPH)
        self._check_configuration()
        longitude = float(position[0])
        if flag < 0 or not math.isfinite(longitude) or not 0 <= longitude < 360:
            raise ValueError("Cannot calculate a valid tropical Sun")
        model = runtime.ephemeris_model_from_retflag(flag)
        source = self._trace.observe("Sun", model)
        observation = {
            "index": len(self.observations),
            "julian_day_tt": jd_tt,
            "longitude": longitude,
            **source,
        }
        self._indices[jd_tt] = observation["index"]
        self.observations.append(observation)
        return observation

    def source(self, index: int) -> Dict[str, Any]:
        row = self.observations[index]
        return sun_source(
            {
                "by_factor": {"Sun": row},
                "files": self._trace.snapshot()["files"],
            }
        )

    def check_native(self, source: Dict[str, Any], natal_index: int) -> None:
        # Same TT epoch: require the same observed data identities, not
        # merely the same DE edition (adjacent files may overlap in time).
        native = sun_source(source)["by_factor"]["Sun"]
        current = self.source(natal_index)["by_factor"]["Sun"]
        if (native["model"], sorted(native["file_ids"])) != (
            current["model"],
            sorted(current["file_ids"]),
        ):
            raise EphemerisSourceError("solar_natal_source_mismatch")

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            if kind is None:
                self._check_configuration()
                source = self._trace.finish()
                self.result = {
                    "ruleset_id": "fatebridge.sun_ephemeris_batch.v1",
                    "observations": self.observations,
                    "files": source["files"],
                    "query_count": len(self.observations),
                    "configuration_locked": True,
                    "equal_tt_epochs_reused": True,
                    "has_unidentified_sources": any(
                        row["status"]
                        in {"identity_unavailable", "se1_contexts_partly_identified"}
                        for row in self.observations
                    ),
                    "scope": "Tropical Sun calls and all post-call se1 contexts for natal, progressed, target and sampled epochs, including observed lunar files used in Earth/EMB reduction. A Swiss Sun flag alone does not exclude an internal analytical Moon fallback. Distinct epochs may use different models. Managed calls share a lock; this is not a complete atomic dependency/read-set proof.",
                    "atomic_file_read_proven": False,
                    "accuracy_certified": False,
                }
        finally:
            self._active = False
            self._guard.__exit__(kind, value, traceback)
        return False
