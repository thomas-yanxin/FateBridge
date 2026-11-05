"""Pinned edition-specific day tokens; old omissions remain in their freezes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v33"
FREEZE_SHA256 = "993b493c3a698a9987e6c13899a74d706d0818bafa51d8a736295a9dfac47408"


def read_origin_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    def read(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"V33 source object required: {path.name}")
        return data

    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V33 pinned source correction changed")
    freeze = read(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in freeze[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V33 source or prior evidence changed: {name}")
    return read(corpus / "readings.json")


def day_token_evidence() -> dict[str, Any]:
    reading = read_origin_sources()
    return {
        "correction_freeze_sha256": FREEZE_SHA256,
        "year_token_alone_does_not_supply_a_day": True,
        "by_edition": reading["day_tokens"],
        "earlier_unqualified_absence_claim_corrected": True,
        "old_frozen_readings_or_reports_overwritten": False,
        "scope": "Explicit NCL Ming anecdote day token; selected Siku passage has no explicit day token. No whole-book absence or full calendar acceptance claim.",
    }
