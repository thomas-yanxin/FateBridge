"""Recheck the full admitted DE440 year-grid range in Ren consumers.

Existing independent TT references and all prechange source refusals remain
visible. Same-kernel regression is not a civil clock or physical accuracy proof.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_extended_source_v1"
PIN = "f1578a034f9e64887e6a3602c3c881031a16b8aa1634511b15eea5917a6b9ff2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen extended-source reference identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    names = {
        "independent-tt.json",
        "independent-protocol.json",
        "boundary-cases.json",
        "protocol.json",
    }
    if set(manifest) != names or {p.name for p in folder.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Complete extended-source inventory required")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Frozen extended-source bytes changed")
    full = json.loads((folder / "independent-tt.json").read_text())
    protocol = json.loads((folder / "protocol.json").read_text())
    if full["production_imported"] is not False or full["protocol_sha256"] != sha(
        folder / "independent-protocol.json"
    ):
        raise ValueError("Independent TT provenance changed")
    rows = full["rows"]
    keys = {(r["year"], r["index"]) for r in rows}
    if len(rows) != 14904 or keys != {
        (y, i) for y in range(1684, 2305) for i in range(24)
    }:
        raise ValueError("Original independent TT denominator changed")
    boundaries = json.loads((folder / "boundary-cases.json").read_text())["cases"]
    if len(boundaries) != 21:
        raise ValueError("Original21 boundary cases required")
    return dict(protocol=protocol, rows=rows, boundaries=boundaries)
