"""One byte-bound reference view per Human Design calculation or verification.

This preserves the identity of the packaged factual catalogues actually read.
It neither authenticates their publishers nor resolves their source conflicts.
"""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterator

from fatebridge.utils.errors import EphemerisSourceError

REFERENCE_NAMES = (
    "additional-polarities-2001.json",
    "circuit-pages-1996-reference.json",
    "circuit-group-2026-reference.json",
    "circuitry-2026-reference.json",
    "cross-coverage-2026-reference.json",
    "cycles-2026-reference.json",
    "rave-2001-depth.json",
    "rave-2001-reference.json",
    "personality-color-reference.json",
    "primary-diagrams-2008-reference.json",
    "profile-2026-reference.json",
    "source-variants-2026-reference.json",
)


def _read(name: str) -> bytes:
    if name not in REFERENCE_NAMES:
        raise ValueError("Unknown Human Design reference catalogue")
    try:
        return (
            files("fatebridge.data")
            .joinpath("human_design")
            .joinpath(name)
            .read_bytes()
        )
    except OSError as error:
        raise EphemerisSourceError("human_design_reference_unavailable") from error


@dataclass(frozen=True)
class _Reference:
    raw: bytes
    document: dict[str, Any]


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate source key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("Nonfinite source number")


@lru_cache(maxsize=len(REFERENCE_NAMES))
def _load(name: str) -> _Reference:
    raw = _read(name)
    try:
        document = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        if type(document) is not dict:
            raise ValueError("Source root must be an object")
    except (ValueError, TypeError, RecursionError) as error:
        raise EphemerisSourceError("human_design_reference_invalid") from error
    return _Reference(raw, document)


_active: ContextVar[dict[str, _Reference] | None] = ContextVar(
    "human_design_reference_view", default=None
)


def _reference(name: str) -> _Reference:
    active = _active.get()
    if active is not None:
        if name not in active:
            active[name] = _load(name)
        return active[name]
    return _load(name)


def reference_data(name: str) -> dict[str, Any]:
    """Internal read-only data pinned per operation."""
    return _reference(name).document


def reference_bytes(name: str) -> bytes:
    return _reference(name).raw


def clear_reference_cache() -> None:
    """Clear reusable source data; active calculation views remain pinned."""
    _load.cache_clear()


@contextmanager
def coherent_human_design_references() -> Iterator[None]:
    if _active.get() is not None:
        yield
        return
    used: dict[str, _Reference] = {}
    token = _active.set(used)
    try:
        yield
    finally:
        _active.reset(token)
