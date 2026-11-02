"""Bounded native paths without changing input files or process cwd."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from fatebridge.core.ephemeris_installation import MAX_EPHEMERIS_PATH_BYTES


@contextmanager
def fixed_star_search_path(
    catalogue: Path, operator_path: str, *, catalogue_bytes: bytes | None = None
) -> Iterator[str]:
    """Retain search order within Swiss's 242 encoded byte limit.

    The caller holds the shared ephemeris lock and hides SE_EPHE_PATH only
    during the native lookup. Relative spellings need no cwd changes; if those
    are still too long, temporary directory links retain all original data.
    Failure to create a bounded path is explicit, never a silent default path.

    When catalogue_bytes is supplied, the first directory contains precisely
    those bytes. The original catalogue directory remains next in the path for
    auxiliary files, followed by the operator's unchanged search order.
    """
    # Swiss accepts ';' on Unix as well as the platform path separator.
    parts = operator_path.replace(";", os.pathsep).split(os.pathsep)
    directories = [str(catalogue), *[part for part in parts if part]]
    if catalogue_bytes is None:
        with _bounded_search_path(directories) as search:
            yield search
        return
    with TemporaryDirectory(prefix="fb-star-input-") as temporary:
        captured = Path(temporary)
        (captured / "sefstars.txt").write_bytes(catalogue_bytes)
        with _bounded_search_path([str(captured), *directories]) as search:
            yield search


@contextmanager
def _bounded_search_path(directories: list[str]) -> Iterator[str]:
    if any("\0" in part for part in directories):
        raise ValueError("Fixed-star search directories cannot contain NUL")

    separators = ";" if os.name == "nt" else ";:"

    def shortest(path: str) -> str | None:
        try:
            relative = os.path.relpath(path)
        except ValueError:  # Windows paths on different drives.
            relative = path
        # A Path is one literal catalogue directory. Swiss cannot quote a
        # delimiter embedded in that name, even when the path is short.
        candidates = [
            value
            for value in (path, relative)
            if not any(char in value for char in separators)
        ]
        return min(candidates, key=lambda value: len(os.fsencode(value)), default=None)

    def fits(path: str) -> bool:
        return len(os.fsencode(path)) <= MAX_EPHEMERIS_PATH_BYTES

    spellings = [shortest(part) for part in directories]
    compact = os.pathsep.join(part for part in spellings if part is not None)
    if all(part is not None for part in spellings) and fits(compact):
        yield compact
        return
    # A third directory (captured stars + original auxiliaries + operator)
    # can exceed the native bound even after links under a long macOS TMPDIR.
    # A short POSIX temporary root keeps these aliases bounded without chdir.
    short_root = "/tmp" if os.name != "nt" and Path("/tmp").is_dir() else None
    with TemporaryDirectory(prefix="fb-star-path-", dir=short_root) as temporary:
        links = []
        try:
            for index, original in enumerate(directories):
                link = Path(temporary) / str(index)
                link.symlink_to(Path(original).absolute(), target_is_directory=True)
                spelling = shortest(str(link))
                if spelling is None:
                    raise ValueError(
                        "Temporary fixed-star directory contains a native search "
                        "separator; use a temporary directory without ';' or ':'"
                    )
                links.append(spelling)
        except OSError as exc:
            raise ValueError(
                "Cannot create compact fixed-star paths; use shorter catalogue "
                "and ephemeris directories on this platform"
            ) from exc
        compact = os.pathsep.join(links)
        if not fits(compact):
            raise ValueError(
                "Temporary fixed-star search path exceeds Swiss Ephemeris's "
                f"{MAX_EPHEMERIS_PATH_BYTES} encoded byte limit"
            )
        yield compact
