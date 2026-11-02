"""Selected ARC clock-page readings, kept separate from calendar rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_arc_clock_collation_v1.json"
SOURCE_SHA256 = "40bec216f980c6b29508d434e8302425c6ad7be576a8366a12cc50cb5b267ceb"


def arc_clock_reference() -> dict[str, Any]:
    """Return bound working readings without choosing a clock or uncertain glyph."""
    loaded = load_source(SOURCE)
    if loaded.sha256 != SOURCE_SHA256:
        raise ValueError("ARC所选计时页来源改变，须重新核验")
    return {**loaded.data, "source_bundle_sha256": loaded.sha256}
