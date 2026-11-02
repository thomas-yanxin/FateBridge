"""Reuse installed-binding identity while the loaded native binary is unchanged.

Metadata discovery is expensive on mounted filesystems and does not belong in
every root sample. Native-version checks stay at the caller. Replacing the
binary, changing its reported version, or injecting a different resolver makes
a new key; an unidentifiable binary keeps the original uncached behaviour.
Restart the calculation process after updating an installed distribution.
"""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any, Callable


def _read(resolver: Callable[[str], str]) -> str:
    try:
        return resolver("pyswisseph")
    except PackageNotFoundError:
        return "unavailable"


@lru_cache(maxsize=16)
def _installed_version(
    resolver: Callable[[str], str],
    native_version: str,
    filename: str,
    inode: int,
    mtime_ns: int,
    size: int,
) -> str:
    return _read(resolver)


def binding_distribution_version(native: Any, resolver: Callable[[str], str]) -> str:
    try:
        hash(resolver)
    except TypeError:
        return _read(resolver)
    filename = getattr(native, "__file__", None)
    if not filename:
        return _read(resolver)
    try:
        stat = Path(filename).stat()
    except (OSError, TypeError, ValueError):
        return _read(resolver)
    return _installed_version(
        resolver,
        str(getattr(native, "version", "unavailable")),
        str(filename),
        stat.st_ino,
        stat.st_mtime_ns,
        stat.st_size,
    )
