"""Observed physical sources for a Jyotish calculation and comparable grids.

One trace hashes each encountered file at first observation and at the end of
the calculation. Reusing it avoids hashing a multi-gigabyte JPL kernel for every
birth-time sample. Observed file contexts are not an atomic file-read proof.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast

from fatebridge.core.astro import native_execution
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.physical_sources import PhysicalSourceCohort
from fatebridge.core.astro.source_session import (
    coherent_ephemeris_sources,
    current_source_session,
)
from fatebridge.core.jyotish_clock import check_clock_sources
from fatebridge.utils.errors import EphemerisSourceError

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
_P = ParamSpec("_P")
_R = TypeVar("_R")


_POINT: ContextVar[dict[str, Any] | None] = ContextVar(
    "jyotish_source_point", default=None
)


def coherent_sources(function: Callable[_P, _R]) -> Callable[_P, _R]:
    """One fresh native context for the complete outer India operation."""
    local = coherent_ephemeris_sources(function)

    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        if native_execution.in_native_worker():
            return local(*args, **kwargs)
        from fatebridge.core.astro.source_session import source_session

        with source_session():
            return cast(
                _R,
                native_execution.calculate(
                    function.__module__ + "." + function.__name__, args, kwargs
                ),
            )

    return wrapped


def coherent_india_call(function: Callable[_P, _R]) -> Callable[_P, _R]:
    """Enclose only the India route, including its birth-clock construction."""
    coherent = coherent_sources(function)

    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        if kwargs.get("chart_variant") == "india_chart":
            return coherent(*args, **kwargs)
        return function(*args, **kwargs)

    return wrapped


def observe_physical(factor: str, model: str) -> None:
    """Observe immediately after the physical calc(), never for analytical nodes."""
    session, point = current_source_session(), _POINT.get()
    if session is not None and point is not None:
        session.check()
        point[factor] = session.trace.observe(factor, model)


def traced_positions(
    function: Callable[_P, dict[str, Any]],
) -> Callable[_P, dict[str, Any]]:
    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> dict[str, Any]:
        session = current_source_session()
        if session is None:
            raise RuntimeError("Position tracing requires a source session")
        point: dict[str, Any] = {}
        token = _POINT.set(point)
        try:
            result = function(*args, **kwargs)
            snapshot = session.trace.snapshot()
            ids = {identity for row in point.values() for identity in row["file_ids"]}
            result["physical_ephemeris_source"] = {
                **snapshot,
                "by_factor": point,
                "files": [f for f in snapshot["files"] if f["id"] in ids],
                "has_unidentified_sources": any(
                    row["status"]
                    in {"identity_unavailable", "se1_contexts_partly_identified"}
                    for row in point.values()
                ),
                "factor_scope": "Physical bodies, keyed by ecliptic/equatorial/geometric_j2000 frame. Rahu/Ketu and Earth rotation are separate. Observed contexts are not an exclusive dependency or atomic read-set proof.",
            }
            birth = cast(AstroBirthInfo, args[0] if args else kwargs["birth"])
            clock_sources = check_clock_sources(
                birth,
                result["physical_ephemeris_source"],
                cast(
                    str,
                    (
                        args[3]
                        if len(args) > 3
                        else kwargs.get("ephemeris_policy", "auto")
                    ),
                ),
            )
            if clock_sources is not None:
                result["clock_source_comparison"] = clock_sources
            return result
        finally:
            _POINT.reset(token)

    return wrapped


class SourceComparison:
    """Keep source changes out of birth-time-only ranges and alternatives."""

    def __init__(self) -> None:
        self.cohort = PhysicalSourceCohort()
        self.motion_models: dict[str, str] = {}
        self.motion_counts: dict[str, int] = {}

    def add(self, raw: dict[str, Any]) -> int:
        source = raw["physical_ephemeris_source"]
        native = {
            key: source["by_factor"][key]
            for frame in ("ecliptic", "equatorial")
            for planet in PLANETS
            for key in (f"{frame}_{planet}",)
        }
        ids = {identity for row in native.values() for identity in row["file_ids"]}
        index = self.cohort.add(
            {
                **source,
                "by_factor": native,
                "files": [f for f in source["files"] if f["id"] in ids],
                "factor_scope": "Seven physical bodies in ecliptic/equatorial frames; optional motion-frame observations compared separately when available.",
            }
        )
        for key, row in source["by_factor"].items():
            if not key.startswith("geometric_j2000_"):
                continue
            model = row["model"]
            if key in self.motion_models and self.motion_models[key] != model:
                raise EphemerisSourceError("model_changed")
            self.motion_models[key] = model
            self.motion_counts[key] = self.motion_counts.get(key, 0) + 1
        return index

    def result(self) -> dict[str, Any]:
        return {
            "status": "comparable_observed_sources",
            "physical_ephemeris_sources": self.cohort.sources,
            "optional_motion_models": self.motion_models,
            "optional_motion_observation_counts": self.motion_counts,
            "scope": "Nominal plus actually calculated samples; the zero-offset sample reuses nominal coordinates. Models are compared per physical body/frame, observed DE editions and same-name file hashes must agree. Adjacent same-edition segments are allowed. Optional motion-window gaps retain their own missing status. File hashes are verified at the outer calculation endpoints, not proof of atomic reads or numerical accuracy; counts are coverage, not probability.",
        }
