"""Selected ARC clock-page readings, kept separate from calendar rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[2] / "data/sukuyo_arc_clock_collation_v1.json"


def arc_clock_reference() -> dict[str, Any]:
    """Return bound working readings without choosing a clock or uncertain glyph."""
    return load_source(SOURCE)
