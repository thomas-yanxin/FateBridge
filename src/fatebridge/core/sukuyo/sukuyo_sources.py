"""Load and cache Sukuyo reference JSON tables cleanly."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=None)
def _load_cached(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected JSON object in {path.name}")
    return loaded


def load_source(path: Path) -> dict[str, Any]:
    """Return a detached copy of a cached Sukuyo JSON reference table."""
    return deepcopy(_load_cached(path))
