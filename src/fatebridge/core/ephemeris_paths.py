"""Ordered Swiss Ephemeris search roots, without resolving or loading files."""

import os
import re
from pathlib import Path


def ephemeris_search_directories(search_path: str | None) -> tuple[Path, ...]:
    """Keep relative roots and duplicates in the configured search order.

    Swiss accepts semicolons on Unix too. Windows drive colons are part of a
    directory, not separators. Consecutive separators form one delimiter,
    as in Swiss's swi_cutstr. Swiss appends a directory separator before
    splitting, so a trailing list delimiter selects the filesystem root.
    An absent selection has no reported roots;
    callers that need a native default must supply that effective path.
    """
    if not search_path:
        return ()
    separators = r"[;:]+" if os.pathsep == ":" else r";+"
    if re.search(separators + "$", search_path):
        search_path += os.sep
    # swi_fopen passes a 20-field buffer; its final field remains unsplit.
    return tuple(
        Path(item or ".") for item in re.split(separators, search_path, maxsplit=19)
    )
