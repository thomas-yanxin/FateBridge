"""Compatibility facade for taiyi.calendars clock helpers."""

from fatebridge.core.metaphysics.taiyi.calendars import (
    SOLAR_ANCHOR_SCOPE,
    civil_clock_resolution,
    nominal_clock_label,
    validate_seed_civil_clock,
)

__all__ = [
    "SOLAR_ANCHOR_SCOPE",
    "civil_clock_resolution",
    "nominal_clock_label",
    "validate_seed_civil_clock",
]
