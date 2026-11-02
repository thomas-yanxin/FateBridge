"""Identify the readable orbit-element source used for Swiss fictitious bodies.

Swiss reads seorbel.txt from the first accessible search-path entry. With no
such file it uses compiled elements; a Moshier retflag alone cannot distinguish
those two cases. Public facts omit server directory names.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict

from fatebridge.core import ephemeris_runtime


def fictitious_element_source() -> Dict[str, Any]:
    search = ephemeris_runtime.effective_ephemeris_search_path()
    common = {
        "scope": "Fictitious orbit elements only; not observed bodies or a JPL validation",
    }
    if search is None:
        return {**common, "status": "unavailable", "filename": None, "sha256": None}
    for index, directory in enumerate(search.split(os.pathsep)):
        candidate = Path(directory) / "seorbel.txt"
        try:
            data = candidate.read_bytes()
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            continue
        return {
            **common,
            "status": "external_file",
            "filename": "seorbel.txt",
            "search_path_index": index,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return {
        **common,
        "status": "library_builtin",
        "filename": None,
        "search_path_index": None,
        "sha256": None,
    }
