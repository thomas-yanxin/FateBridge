"""Keep an auxiliary derivative on the actual center's compressed file fits.

Overlapping Swiss files can describe one epoch with slightly different fits.
Switching between them while differentiating does not sample one function.
This probe replays the observed center file context before each auxiliary
state and excludes directions leaving it. It never selects a context by a
rate, a residual, a date-specific rule or an external expected answer.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.retarded_epoch import stabilized_longitude_sample
from fatebridge.core.astro.solar_motion_branch import solar_interpolation_branch
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "compressed_center_file_window_replay_v1"


def observed_windows() -> Optional[Tuple[tuple, ...]]:
    getter = getattr(runtime.swe, "get_current_file_data", None)
    if not callable(getter):
        return None
    values = tuple(tuple(getter(slot)) for slot in (0, 1))
    if any(
        not name or not math.isfinite(start) or not math.isfinite(end) or start >= end
        for name, start, end, _ in values
    ):
        return None
    return values


class CenterWindowProbe:
    """Call only under the calculation's managed native runtime lock."""

    def __init__(
        self,
        planet: str,
        epoch: float,
        coordinates: Sequence[float],
        windows: Tuple[tuple, ...],
        source: Dict[str, Any],
        trace: PhysicalEphemerisTrace,
        *,
        sidereal: bool,
    ) -> None:
        self.planet = planet
        self.epoch = epoch
        self.center = tuple(coordinates)
        self.windows = windows
        self.source = source
        self.trace = trace
        self.sidereal = sidereal
        self.selected = configured_ephemeris_path()
        self.flags = (
            runtime.swe.FLG_SWIEPH
            | runtime.swe.FLG_SPEED
            | (runtime.swe.FLG_SIDEREAL if sidereal else 0)
        )
        self.lower = max(v[1] for v in windows)
        self.upper = min(v[2] for v in windows)
        self.cache: Dict[float, Dict[str, Any]] = {}
        self.anchors: set[float] = set()
        self.contexts: Dict[str, Any] = {}
        self.center_verified = False

    def _raw(self, at: float) -> Sequence[float]:
        values, returned = runtime.ephemeris_call(
            "calc", at, PLANET_SWISSEPH_IDS[self.planet], self.flags
        )
        if configured_ephemeris_path() != self.selected:
            raise EphemerisSourceError("physical_configuration_changed")
        if runtime.ephemeris_model_from_retflag(returned) != "swieph":
            raise EphemerisSourceError("model_changed")
        require_spherical_coordinates(
            values, returned, native=runtime.swe, sidereal=self.sidereal
        )
        if len(values) != 6 or not all(math.isfinite(x) for x in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        return tuple(float(value) for value in values)

    def _replay_center_files(self) -> None:
        # Nested native helpers restore the path and clear file caches. Replay
        # file identity, rather than relying on their historical open state.
        runtime.swe.set_ephe_path(self.selected or "")
        if self.sidereal:
            runtime.ephemeris_call("set_sid_mode", runtime.swe.SIDM_LAHIRI, 0, 0)
        anchor = self.epoch
        tried = set()
        for _ in range(5):
            tried.add(anchor)
            self.anchors.add(anchor)
            self._raw(anchor)
            actual = observed_windows()
            if actual == self.windows:
                return
            if actual is None:
                break
            candidates = []
            for observed, wanted in zip(actual, self.windows):
                if observed == wanted:
                    continue
                # An anchor outside an unwanted fit's range, but inside the
                # intersection of all wanted fits, forces a source transition.
                # Midpoints depend only on file headers, never on residuals.
                if self.lower < observed[1]:
                    candidates.append((self.lower + min(self.upper, observed[1])) / 2)
                if self.upper > observed[2]:
                    candidates.append((max(self.lower, observed[2]) + self.upper) / 2)
            candidates = [
                x for x in candidates if self.lower < x < self.upper and x not in tried
            ]
            if not candidates:
                break
            anchor = min(candidates, key=lambda x: (abs(x - self.epoch), x))
        raise EphemerisSourceError("position_motion_not_converged")

    def _probe(self, delta: float) -> Dict[str, Any]:
        if delta in self.cache:
            return self.cache[delta]
        at = self.epoch + delta
        if at - self.epoch != delta:
            raise EphemerisSourceError("coordinate_motion_unavailable")
        pad = 64 * math.ulp(at)
        result: Dict[str, Any] = {"cell": None}
        if not self.lower + pad < at < self.upper - pad:
            result["reason"] = "outside_interior_center_file_window"
            self.cache[delta] = result
            return result
        self._replay_center_files()
        raw = self._raw(at)
        context = self.trace.observe(
            "motion_center_window", "swieph", record_factor=False
        )
        if observed_windows() != self.windows or context != self.source:
            result["reason"] = "center_file_context_changed"
            self.cache[delta] = result
            return result
        if delta == 0:
            if tuple(raw) != self.center:
                raise EphemerisSourceError("position_motion_not_converged")
            self.center_verified = True
        value = float(raw[0])
        local_contexts: Dict[str, Any] = {}
        if self.planet != "Sun":
            value, _ = stabilized_longitude_sample(
                self.planet,
                at,
                raw,
                "swieph",
                sidereal=self.sidereal,
                source_trace=self.trace,
                contexts=local_contexts,
                factor_prefix="center_window_retarded",
            )
            self._replay_center_files()
            geometry = solar_interpolation_branch(
                self.planet,
                at,
                "swieph",
                self.trace,
                local_contexts,
                "center_window_solar",
            )
            if geometry.get("cell") is None:
                result["reason"] = "solar_interpolation_boundary_ambiguous"
                self.cache[delta] = result
                return result
            cell = f"center_files_solar_cell_{geometry['cell']}"
        else:
            cell = "center_files_solar_direction"
        if any(context != self.source for context in local_contexts.values()):
            result["reason"] = "auxiliary_file_context_changed"
        else:
            result.update(cell=cell, value=value)
        self.contexts.update(local_contexts)
        self.cache[delta] = result
        return result

    def branch(self, delta: float) -> Dict[str, Any]:
        return {
            key: value for key, value in self._probe(delta).items() if key != "value"
        }

    def value(self, delta: float) -> float:
        value = self._probe(delta)
        if value.get("cell") is None:
            raise EphemerisSourceError("position_motion_not_converged")
        return float(value["value"])

    def receipt(self) -> Dict[str, Any]:
        return {
            "method_id": METHOD_ID,
            "center_native_state_reproduced_exactly": self.center_verified,
            "source_context": self.source,
            "center_windows": [
                dict(
                    slot=slot,
                    filename=Path(v[0]).name,
                    start_jd_tt=v[1],
                    end_jd_tt=v[2],
                )
                for slot, v in enumerate(self.windows)
            ],
            "replay_anchor_jd_tt": sorted(self.anchors),
            "sample_count": len(self.cache),
            "ineligible_sample_count": sum(
                v.get("cell") is None for v in self.cache.values()
            ),
            "displayed_native_position_changed": False,
            "scope": "Observed center file contexts and auxiliary sampled solar interpolation cells. Not an atomic read-set, continuous-domain completeness or independent physical accuracy proof.",
        }
