"""Verify original source inputs of historical experiments.

An original source may be retired or reorganized. Its declared hash still checks
the sealed original; it does not certify that current code is byte-identical.
Runtime behavior, reference data and actual execution receipts have separate
checks. Data files never fall back to this source archive.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import TypedDict

ARCHIVE_SHA256 = "7435f179a61e914a3ace56be61fe86d53acc1c098474acb05294871a24f6b82a"


class OriginalSource(TypedDict):
    paths: list[str]
    text: str


class SourceArchive(TypedDict):
    schema_version: int
    originals: dict[str, OriginalSource]


class HistoricalSources:
    def __init__(self, root: Path, *, archive: Path | None = None) -> None:
        self.root = root.absolute()
        path = (
            archive
            or self.root
            / "tests/fixtures/architecture_refactor_v1/source-originals.json.gz"
        )
        packed = path.read_bytes()
        if hashlib.sha256(packed).hexdigest() != ARCHIVE_SHA256:
            raise ValueError("Frozen original source archive changed")
        # The exact archive bytes above fix this authored schema as well.
        payload: SourceArchive = json.loads(gzip.decompress(packed))
        self.originals = payload["originals"]

    def matches(self, path: Path, expected_sha256: str) -> bool:
        path = path.absolute()
        if (
            path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256
        ):
            return True
        if not path.is_relative_to(self.root):
            return False
        relative = path.relative_to(self.root).as_posix()
        source = relative in {"AGENTS.md", "pyproject.toml", "uv.lock"} or (
            relative.startswith(("scripts/", "src/fatebridge/", "tests/test_"))
            and path.suffix == ".py"
        )
        if not source:
            return False
        original = self.originals.get(expected_sha256)
        return (
            original is not None
            and relative in original["paths"]
            and hashlib.sha256(original["text"].encode("utf-8")).hexdigest()
            == expected_sha256
        )
