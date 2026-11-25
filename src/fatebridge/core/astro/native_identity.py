"""Reuse installed-binding identity while the loaded native binary is unchanged.

Metadata discovery is expensive on mounted filesystems and does not belong in
every root sample. Native-version checks stay at the caller. Replacing the
binary, changing its reported version, or injecting a different resolver makes
a new key; an unidentifiable binary keeps the original uncached behaviour.
Restart the calculation process after updating an installed distribution.
"""

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Protocol


class DistributionVersionResolver(Protocol):
    def __call__(self, distribution_name: str, /) -> str: ...


@dataclass(frozen=True, kw_only=True)
class BindingIdentity:
    resolver: DistributionVersionResolver
    native_version: str
    filename: str
    inode: int
    modified_nanoseconds: int
    size_bytes: int


@lru_cache(maxsize=16)
def _native_path(filename: str) -> Path:
    """Reuse an immutable path value, never its mutable filesystem status."""
    return Path(filename)


def _read(resolver: DistributionVersionResolver) -> str:
    try:
        return resolver("pyswisseph")
    except PackageNotFoundError:
        return "unavailable"


@lru_cache(maxsize=16)
def _installed_version(identity: BindingIdentity) -> str:
    return _read(identity.resolver)


def binding_distribution_version(
    native: object, resolver: DistributionVersionResolver
) -> str:
    try:
        hash(resolver)
    except TypeError:
        return _read(resolver)
    filename = getattr(native, "__file__", None)
    if not filename:
        return _read(resolver)
    else:
        pass
    try:
        stat = (
            _native_path(filename) if type(filename) is str else Path(filename)
        ).stat()
    except (OSError, TypeError, ValueError):
        return _read(resolver)
    return _installed_version(
        BindingIdentity(
            resolver=resolver,
            native_version=str(getattr(native, "version", "unavailable")),
            filename=str(filename),
            inode=stat.st_ino,
            modified_nanoseconds=stat.st_mtime_ns,
            size_bytes=stat.st_size,
        )
    )
