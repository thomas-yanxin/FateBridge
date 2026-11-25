"""Ordered Swiss Ephemeris search roots, without resolving or loading files."""

import os
import re
from pathlib import Path

# note (Swiss path buffer): The native setter reserves a separator and file-name space.
SWISS_PATH_BUFFER_BYTES = 256
MAX_EPHEMERIS_PATH_BYTES = SWISS_PATH_BUFFER_BYTES - 14


def ephemeris_search_path_fits(search_path: str) -> bool:
    """Whether the native setter can retain a whole ordered search path."""
    return (
        "\0" not in search_path
        and len(os.fsencode(search_path)) <= MAX_EPHEMERIS_PATH_BYTES
    )


def ephemeris_search_directories(
    search_path: str | None, *, filename: str | None = None
) -> tuple[Path, ...]:
    """Mirror Swiss search order, including relative and duplicate directories.

    A known filename stops the search at its first oversized joined path.
    """
    if not search_path:
        return ()
    separators = r"[;:]+" if os.pathsep == ":" else r";+"
    if not search_path.endswith(os.sep):
        search_path += os.sep
    line = re.split(r"[\r\n]", search_path, maxsplit=1)[0]
    # note (swi_fopen): A native 20-field buffer leaves its final field unsplit.
    directories = re.split(separators, line, maxsplit=19)
    if filename is not None:
        filename_bytes = len(os.fsencode(filename))
        for index, directory in enumerate(directories):
            prefix_bytes = (
                0
                if directory in {"", "."}
                else len(os.fsencode(directory)) + (not directory.endswith(os.sep))
            )
            if prefix_bytes + filename_bytes >= SWISS_PATH_BUFFER_BYTES:
                directories = directories[:index]
                break
    return tuple(Path(directory or ".") for directory in directories)
