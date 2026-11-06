"""Observed physical ephemeris identities and comparable sample cohorts.

Swiss's returned model identifies the top-level branch, not every internal
dependency. Managed geocentric physical calls separately require the observed
planet/Moon contexts. File slots describe contexts after calc(), not a complete
atomic read set. File hashes and DE headers do not certify positional accuracy.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris_integrity import load_ephemeris_manifest
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file, jpl_header
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.physical_ephemeris_sources.v1"


def _file_digest(path: Path) -> str:
    # Raw DE441 is over 2 GiB; do not load it into process memory for tracing.
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_physical_configuration(selected: str | None) -> None:
    if configured_ephemeris_path() != selected:
        raise EphemerisSourceError("physical_configuration_changed")


class PhysicalEphemerisTrace:
    """One native calculation, with private paths kept out of results."""

    def __init__(self) -> None:
        self._paths: Dict[Path, str] = {}
        self._files: Dict[str, Dict[str, Any]] = {}
        self._factors: Dict[str, Dict[str, Any]] = {}
        self._manifest = load_ephemeris_manifest()["files"]
        self._jpl_name = configured_jpl_file()

    def observe(
        self, factor: str, model: str, *, record_factor: bool = True
    ) -> Dict[str, Any]:
        """Identify/hash a state context, optionally registering a chart factor.

        Auxiliary derivative states use the same verified file set but keep
        their context in the method's own provenance. They are not additional
        physical chart factors and must not change a body's source cohort.
        """
        from fatebridge.core.physical_source_observation import require_physical_model

        require_physical_model(model)
        if configured_jpl_file() != self._jpl_name:
            raise EphemerisSourceError("physical_configuration_changed")
        ids = []
        status = "library_builtin" if model == "moshier" else "identity_unavailable"
        unidentified = False
        getter = getattr(runtime.swe, "get_current_file_data", None)
        # Analytical fallback can leave old Swiss slots populated. Do not
        # attribute those stale contexts to a Moshier calculation.
        if model in {"swieph", "jpl"} and getter is not None:
            for slot in (0,) if model == "jpl" else (0, 1):
                filename, start, end, de_number = getter(slot)
                if not filename:
                    continue
                path = Path(filename).absolute()
                if model == "jpl":
                    header = jpl_header(path)
                    start = header["start_julian_day_tdb"]
                    end = header["end_julian_day_tdb"]
                    de_number = header["de_number"]
                if not (math.isfinite(start) and math.isfinite(end) and start < end):
                    raise EphemerisSourceError("invalid_range")
                if path not in self._paths:
                    try:
                        size = path.stat().st_size
                        digest = _file_digest(path)
                    except OSError as error:
                        if model == "jpl":
                            raise EphemerisSourceError("unavailable_during") from error
                        unidentified = True
                        continue
                    prefix = "jpl" if model == "jpl" else "se1"
                    identity = f"{prefix}:{slot}:{path.name}"
                    expected = (
                        self._manifest.get(path.name) if model == "swieph" else None
                    )
                    self._files[identity] = {
                        "id": identity,
                        "slot": slot,
                        "filename": path.name,
                        "sha256": digest,
                        "bytes": size,
                        "range_time_scale": "TDB" if model == "jpl" else "TT",
                        (
                            "start_julian_day_tdb"
                            if model == "jpl"
                            else "start_julian_day_tt"
                        ): float(start),
                        (
                            "end_julian_day_tdb"
                            if model == "jpl"
                            else "end_julian_day_tt"
                        ): float(end),
                        "de_number": int(de_number),
                        "matches_packaged_manifest": bool(
                            expected
                            and expected["sha256"] == digest
                            and expected["bytes"] == size
                        ),
                    }
                    self._paths[path] = identity
                identity = self._paths[path]
                if self._files[identity]["slot"] != slot:
                    raise EphemerisSourceError("slot_changed")
                ids.append(identity)
            if ids:
                status = (
                    "jpl_context_observed"
                    if model == "jpl"
                    else (
                        "se1_contexts_partly_identified"
                        if unidentified
                        else "se1_contexts_observed"
                    )
                )
        context = {
            "model": model,
            "status": status,
            "file_ids": sorted(set(ids)),
        }
        if record_factor:
            self._factors[factor] = context
        return context

    def finish(self) -> Dict[str, Any]:
        if configured_jpl_file() != self._jpl_name:
            raise EphemerisSourceError("physical_configuration_changed")
        for path, identity in self._paths.items():
            try:
                digest = _file_digest(path)
            except OSError as error:
                raise EphemerisSourceError("unavailable_during") from error
            if digest != self._files[identity]["sha256"]:
                raise EphemerisSourceError("changed_during")
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        """Observed contexts so far; only finish() verifies endpoint hashes."""
        result = {
            "ruleset_id": RULESET,
            "by_factor": self._factors,
            "files": [self._files[key] for key in sorted(self._files)],
            "has_unidentified_sources": any(
                row["status"]
                in {"identity_unavailable", "se1_contexts_partly_identified"}
                for row in self._factors.values()
            ),
            "scope": "Returned models and se1 contexts observed after physical-body calc calls; not a complete dependency/read-set proof. Analytical node, fictitious orbit elements and Earth-rotation inputs are separate."
            + (
                " JPL context identity uses its direct-access header because the native file slot returns zero range/edition fields."
                if any(row["model"] == "jpl" for row in self._factors.values())
                else ""
            ),
            "atomic_file_read_proven": False,
            "accuracy_certified": False,
        }
        if any(row["model"] == "jpl" for row in self._factors.values()):
            result["time_scale_policy"] = jpl_time_scale_policy()
        return result


def jpl_time_scale_policy() -> Dict[str, Any]:
    """Describe the inspected native approximation; do not change an epoch."""
    from importlib.metadata import version

    native = str(getattr(runtime.swe, "version", "unavailable"))
    binding = binding_distribution_version(runtime.swe, version)
    inspected = (native, binding) == ("2.10.03", "2.10.3.2")
    return {
        "policy_id": "swiss_native_tt_as_tdb_argument_v1",
        "status": "source_inspected" if inspected else "unverified_native_version",
        "native_version": native,
        "binding_version": binding,
        "native_api_time_scale": "TT",
        "raw_header_time_scale": "TDB",
        "tt_tdb_conversion_applied": False if inspected else None,
        "source_documented_maximum_difference_seconds": 0.002 if inspected else None,
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:jplplan",
        "source_url": "https://ssd.jpl.nasa.gov/doc/de440_de441.html",
        "native_source_url": "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c",
        "scope": "Native source documents Teph approximately TDB approximately TT. The .002 second value is its documented estimate, not a new observational bound or an implemented time conversion. Numerical positions and rates are unchanged.",
    }


class PhysicalSourceCohort:
    """Do not conflate a changing model with birth-clock sensitivity."""

    def __init__(self) -> None:
        self.sources: List[Dict[str, Any]] = []
        self._models: Dict[str, str] = {}
        self._editions: Dict[int, List[int]] = {}
        self._file_hashes: Dict[tuple[int, str], str] = {}

    def add(self, source: Dict[str, Any]) -> int:
        models = {key: row["model"] for key, row in source["by_factor"].items()}
        editions: Dict[int, List[int]] = {}
        for file in source["files"]:
            editions.setdefault(file["slot"], []).append(file["de_number"])
        editions = {key: sorted(set(value)) for key, value in editions.items()}
        if self.sources and models != self._models:
            raise EphemerisSourceError("model_changed")
        if self.sources and editions != self._editions:
            raise EphemerisSourceError("edition_changed")
        for file in source["files"]:
            key = (file["slot"], file["filename"])
            if key in self._file_hashes and self._file_hashes[key] != file["sha256"]:
                raise EphemerisSourceError("changed_across")
            self._file_hashes[key] = file["sha256"]
        self._models, self._editions = models, editions
        if source not in self.sources:
            self.sources.append(source)
        return self.sources.index(source)
