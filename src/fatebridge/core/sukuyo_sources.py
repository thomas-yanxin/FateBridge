"""Keep a loaded source table and its byte fingerprint from the same read."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoadedSource:
    _payload: dict[str, Any]
    sha256: str

    @property
    def data(self) -> dict[str, Any]:
        """Return detached data; editing a reference must not change later runs.

        The cached payload is private and stays coupled to its original byte
        fingerprint. This is copy isolation, not a security boundary against
        code deliberately modifying private implementation state.
        """
        return deepcopy(self._payload)


@lru_cache(maxsize=None)
def load_source(path: Path) -> LoadedSource:
    """Keep package snapshots until explicit invalidation or process restart.

    A size-limited LRU silently reloaded a modified path once new witness tables
    displaced it. Internal callers use a finite set of package paths; retaining
    those snapshots keeps source identity independent of lookup order.
    """
    raw = path.read_bytes()
    return LoadedSource(json.loads(raw), hashlib.sha256(raw).hexdigest())
