"""Compatibility re-export for untouched services/divination.py until merge."""

from fatebridge.core.sukuyo.calendar import (
    calendar_mansion,
    day_evidence,
    lunar_mansion,
    rulesets,
)
from fatebridge.core.sukuyo.sanjiu import candidate_relation_analysis

__all__ = [
    "calendar_mansion",
    "candidate_relation_analysis",
    "day_evidence",
    "lunar_mansion",
    "rulesets",
]
