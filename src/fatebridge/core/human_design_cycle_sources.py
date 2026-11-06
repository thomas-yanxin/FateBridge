"""Observed file contexts for a finite multi-decade Human Design cycle batch.

Slot2 is the main-asteroid orbit file even when Chiron's returned flag says
Moshier or JPL for the solar/Earth calculation. Slots are post-call contexts,
not a complete atomic read set; hashes identify bytes, not positional truth.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris_integrity import load_ephemeris_manifest
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.jpl_ephemeris import configured_jpl_file, jpl_header
from fatebridge.utils.errors import EphemerisSourceError

SOURCE_SCOPE = "逐次原生计算后观察到的文件上下文；凯龙星独立保留slot2小行星轨道，即使Earth/太阳计算旗标为Moshier或JPL。批次前后检查路径策略、文件身份、SHA-256及同天体同角色的DE版本，不是完整原子读取集合或位置准确度认证。"


def _signature(path: Path) -> tuple[int, ...]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(piece)
    return value.hexdigest()


class CycleSourceTrace:
    """One source trace, shared across all bodies in one locked calculation."""

    def __init__(self) -> None:
        self._path = configured_ephemeris_path()
        self._jpl = configured_jpl_file()
        self._paths: dict[Path, tuple[tuple[int, ...], str]] = {}
        self._files: dict[str, dict[str, Any]] = {}
        self._contexts: list[dict[str, Any]] = []
        self._context_indices: dict[tuple[Any, ...], int] = {}
        self._editions: dict[tuple[str, str, int], int] = {}
        self._names: dict[tuple[int, str], str] = {}
        self._metadata_cache: dict[
            tuple[Any, ...], tuple[Path, tuple[int, ...], str]
        ] = {}
        self._manifest = load_ephemeris_manifest()["files"]

    def check_configuration(self) -> None:
        if (
            configured_ephemeris_path() != self._path
            or configured_jpl_file() != self._jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")

    def _file(self, slot: int, metadata: tuple[Any, ...], *, jpl: bool) -> str:
        key_metadata = slot, metadata, jpl
        if key_metadata in self._metadata_cache:
            path, signature, identity = self._metadata_cache[key_metadata]
            try:
                if _signature(path) != signature:
                    raise EphemerisSourceError("changed_during")
            except OSError as error:
                raise EphemerisSourceError("unavailable_during") from error
            return identity
        filename, start, end, de_number = metadata
        path = Path(filename).absolute()
        if jpl:
            header = jpl_header(path)
            start, end, de_number = (
                header["start_julian_day_tdb"],
                header["end_julian_day_tdb"],
                header["de_number"],
            )
        if (
            type(start) not in (float, int)
            or type(end) not in (float, int)
            or not math.isfinite(start)
            or not math.isfinite(end)
            or start >= end
            or type(de_number) is not int
            or de_number <= 0
        ):
            raise EphemerisSourceError("invalid_range")
        try:
            signature = _signature(path)
            if path in self._paths:
                previous, identity = self._paths[path]
                if signature != previous:
                    raise EphemerisSourceError("changed_during")
                saved = self._files[identity]
                if saved["de_number"] != de_number:
                    raise EphemerisSourceError("edition_changed")
                if (
                    saved["slot"],
                    saved["start_julian_day_tdb" if jpl else "start_julian_day_tt"],
                    saved["end_julian_day_tdb" if jpl else "end_julian_day_tt"],
                ) != (slot, start, end):
                    raise EphemerisSourceError("slot_changed")
                self._metadata_cache[key_metadata] = path, signature, identity
                return identity
            digest = _digest(path)
            if _signature(path) != signature:
                raise EphemerisSourceError("changed_during")
        except OSError as error:
            raise EphemerisSourceError("unavailable_during") from error
        identity = f"{'jpl' if jpl else 'se1'}:{slot}:{path.name}"
        previous_digest = self._names.get((slot, path.name))
        if previous_digest is not None and previous_digest != digest:
            raise EphemerisSourceError("changed_across")
        self._names[(slot, path.name)] = digest
        expected = self._manifest.get(path.name)
        self._files[identity] = {
            "id": identity,
            "slot": slot,
            "filename": path.name,
            "sha256": digest,
            "bytes": signature[2],
            "range_time_scale": "TDB" if jpl else "TT",
            ("start_julian_day_tdb" if jpl else "start_julian_day_tt"): float(start),
            ("end_julian_day_tdb" if jpl else "end_julian_day_tt"): float(end),
            "de_number": de_number,
            "matches_packaged_manifest": bool(
                expected
                and expected["sha256"] == digest
                and expected["bytes"] == signature[2]
            ),
        }
        self._paths[path] = (signature, identity)
        self._metadata_cache[key_metadata] = path, signature, identity
        return identity

    def observe(self, body: str, model: str) -> int:
        self.check_configuration()
        if body not in {"Saturn", "Uranus", "Chiron"} or model not in {
            "swieph",
            "moshier",
            "jpl",
        }:
            raise ValueError("Unsupported cycle source context")
        getter = getattr(runtime.swe, "get_current_file_data", None)
        requires_files = body == "Chiron" or model != "moshier"
        ids = []
        if getter is None:
            status = "identity_unavailable" if requires_files else "library_builtin"
        else:
            slots = ([0, 1] if model == "swieph" else [0] if model == "jpl" else []) + (
                [2] if body == "Chiron" else []
            )
            for slot in slots:
                metadata = getter(slot)
                if not metadata[0]:
                    if slot in (0, 2):
                        raise EphemerisSourceError("unavailable_during")
                    continue
                identity = self._file(slot, metadata, jpl=model == "jpl" and slot == 0)
                de_number = self._files[identity]["de_number"]
                key = body, model, slot
                if key in self._editions and self._editions[key] != de_number:
                    raise EphemerisSourceError("edition_changed")
                self._editions[key] = de_number
                ids.append(identity)
            status = "file_contexts_observed" if ids else "library_builtin"
        key_context = body, model, status, tuple(sorted(ids))
        if key_context not in self._context_indices:
            self._context_indices[key_context] = len(self._contexts)
            self._contexts.append(
                {
                    "body": body,
                    "native_return_flag_model": model,
                    "status": status,
                    "file_ids": sorted(ids),
                }
            )
        return self._context_indices[key_context]

    def finish(self) -> dict[str, Any]:
        self.check_configuration()
        for path, (signature, identity) in self._paths.items():
            try:
                if (
                    _signature(path) != signature
                    or _digest(path) != self._files[identity]["sha256"]
                    or _signature(path) != signature
                ):
                    raise EphemerisSourceError("changed_during")
            except OSError as error:
                raise EphemerisSourceError("unavailable_during") from error
        return {
            "method_id": "human_design_cycle_file_contexts_v1",
            "status": (
                "identity_incomplete"
                if any(c["status"] == "identity_unavailable" for c in self._contexts)
                else "observed_contexts_endpoint_verified"
            ),
            "files": [self._files[key] for key in sorted(self._files)],
            "contexts": self._contexts,
            "has_unidentified_sources": any(
                c["status"] == "identity_unavailable" for c in self._contexts
            ),
            "configuration_checked": True,
            "endpoint_file_hashes_checked": True,
            "atomic_file_read_proven": False,
            "accuracy_certified": False,
            "scope": SOURCE_SCOPE,
        }


def cycle_source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": source["status"],
        "has_unidentified_sources": source["has_unidentified_sources"],
        "atomic_file_read_proven": False,
        "accuracy_certified": False,
        "files": [
            {
                key: row[key]
                for key in (
                    "filename",
                    "de_number",
                    "matches_packaged_manifest",
                )
            }
            for row in source["files"]
        ],
        "scope": SOURCE_SCOPE,
    }


class CycleBirthSources:
    """Capture served natal positions at their original native calls.

    Later same-TT evaluations can differ after native cache resets. Preserve
    the actual original activation without inventing an equality tolerance.
    """

    def __init__(self) -> None:
        self.trace = CycleSourceTrace()
        self.rows: dict[str, list[float | int]] = {}
        self.indices: dict[str, int] = {}
        self.jd_tt: float | None = None

    def observe(self, body: str, jd_tt: float, state: dict[str, Any]) -> None:
        if body not in {"Saturn", "Uranus"}:
            return
        if body in self.rows or (self.jd_tt is not None and self.jd_tt != jd_tt):
            raise EphemerisSourceError("nominal_source_mismatch")
        self.jd_tt = jd_tt
        model = position_flag_model(state["return_flags"])
        self.indices[body] = self.trace.observe(body, model)
        self.rows[body] = [
            jd_tt,
            state["longitude"],
            state["longitude_speed"],
            state["return_flags"],
        ]
