"""Compatibility re-export for untouched services/divination.py until merge."""

from fatebridge.core.sukuyo.sanjiu import (
    RELATION_PAIR,
    RELATION_TEMPLATE,
    SU27_ORDER,
    SU28_NAMES,
    assess_ryohan,
    distance_band_for_offset,
    kuyou_annual_star,
    kuyou_for_age,
    normalize_mansion,
    relation_between_su27,
)

__all__ = [
    "RELATION_PAIR",
    "RELATION_TEMPLATE",
    "SU27_ORDER",
    "SU28_NAMES",
    "assess_ryohan",
    "distance_band_for_offset",
    "kuyou_annual_star",
    "kuyou_for_age",
    "normalize_mansion",
    "relation_between_su27",
]
