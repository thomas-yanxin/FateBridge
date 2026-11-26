"""Identify the readable orbit-element source used for Swiss fictitious bodies.

Swiss reads seorbel.txt from the first accessible search-path entry. With no
such file it uses compiled elements; a Moshier retflag alone cannot distinguish
those two cases. Public facts omit server directory names.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core import ephemeris_runtime
from fatebridge.core.ephemeris_paths import ephemeris_search_directories


def fictitious_element_source() -> dict[str, Any]:
    search = ephemeris_runtime.effective_ephemeris_search_path()
    common = {
        "scope": "Fictitious orbit elements only; not observed bodies or a JPL validation",
    }
    if search is None:
        return {**common, "status": "unavailable", "filename": None}
    for index, directory in enumerate(ephemeris_search_directories(search)):
        candidate = directory / "seorbel.txt"
        try:
            if not candidate.is_file():
                continue
        except OSError:
            continue
        return {
            **common,
            "status": "external_file",
            "filename": "seorbel.txt",
            "search_path_index": index,
        }
    return {
        **common,
        "status": "library_builtin",
        "filename": None,
        "search_path_index": None,
    }
