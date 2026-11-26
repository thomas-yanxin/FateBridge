"""Compatibility facade for fatebridge.core.metaphysics.liureng."""

from fatebridge.core.metaphysics.liureng import (
    TwelveGodLayout,
    _liureng_month_general_on_hour,
    build_liureng_board,
    build_liureng_runyear,
    derive_selection,
    twelve_god_layout,
)
from fatebridge.core.metaphysics.ren_calendar import (
    month_general_for_term as _liureng_month_general_for_term,
)

__all__ = [
    "TwelveGodLayout",
    "_liureng_month_general_for_term",
    "_liureng_month_general_on_hour",
    "build_liureng_board",
    "build_liureng_runyear",
    "derive_selection",
    "twelve_god_layout",
]
