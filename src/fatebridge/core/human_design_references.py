"""One byte-bound reference view per Human Design calculation or verification.

This preserves the identity of the packaged factual catalogues actually read.
It neither authenticates their publishers nor resolves their source conflicts.
"""

import hashlib
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

# Reviewed factual catalogue bytes; a source revision requires explicit review.
REFERENCE_SHA256 = {
    "additional-polarities-2001.json": "2bdfaabbe3ab98b43eac457ad5545c4ccee8205e6d0c7fc760cf1e95029bd262",
    "circuit-pages-1996-reference.json": "fd3f5d84067a007b749a0471b67965c221446f2cb8e8aa4b189d644c9ed1c255",
    "circuit-group-2026-reference.json": "51a21e99322cea57de381a31245d12ecacc8786e85753f218566bdd5a1535b75",
    "circuitry-2026-reference.json": "37dd83d2b22ec78a13104912766cbf07b9d391931407bd4fa46f8179f9988f1a",
    "cross-coverage-2026-reference.json": "327322798db2e7e526fad6fe064118168c439c89fbe636489b9a8f637430bf1e",
    "cycles-2026-reference.json": "a037832cb2ac0a2a82ca2b8b84637abccd1cc14fc6b6a248e794671b066b687b",
    "rave-2001-depth.json": "6fd06279b49f071dabb34aa293070f51f840cd1773986304aecbbbaa6be2270b",
    "rave-2001-reference.json": "92053afe9868d5683e7463e9b1f468e4b3a16ceb60197901a38b53d5097af120",
    "personality-color-reference.json": "71005fa44011da9fa63b12a790b171ba2e562969816b9b5544e4da5532a256ec",
    "primary-diagrams-2008-reference.json": "ce711043ed448544766abf539e5178dd81a69796bb58159dc51df9a615ab73c9",
    "profile-2026-reference.json": "3d339fa324de5cada3b0f3a7b5e1813c02b4a4503aaeb7eafd958b5d9e8f156f",
    "source-variants-2026-reference.json": "4ffe29fe97b93a29173c1d36bce7aa31a259a38c122815b3c91c9ceecd502061",
}


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


def _semantic_digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            document, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class _Reference:
    raw: bytes
    document: dict[str, Any]
    sha256: str
    semantic_sha256: str


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
        semantic = _semantic_digest(document)
    except (ValueError, TypeError, RecursionError) as error:
        raise EphemerisSourceError("human_design_reference_invalid") from error
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REFERENCE_SHA256[name]:
        raise EphemerisSourceError("human_design_reference_identity_mismatch")
    return _Reference(raw, document, digest, semantic)


_active: ContextVar[dict[str, _Reference] | None] = ContextVar(
    "human_design_reference_view", default=None
)


def _validate(name: str, record: _Reference) -> None:
    try:
        same_document = _semantic_digest(record.document) == record.semantic_sha256
    except (ValueError, TypeError, RecursionError):
        same_document = False
    if hashlib.sha256(_read(name)).hexdigest() != record.sha256 or not same_document:
        raise EphemerisSourceError("human_design_reference_changed")


def _reference(name: str) -> _Reference:
    active = _active.get()
    if active is not None:
        if name not in active:
            record = _load(name)
            _validate(name, record)
            active[name] = record
        return active[name]
    return _load(name)


def reference_data(name: str) -> dict[str, Any]:
    """Internal read-only data; any in-operation mutation fails the end check."""
    return _reference(name).document


def reference_bytes(name: str) -> bytes:
    return _reference(name).raw


def reference_sha256(name: str) -> str:
    return _reference(name).sha256


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
        for name, record in used.items():
            _validate(name, record)
    finally:
        _active.reset(token)
