"""Compatibility facade for taiyi year core and board."""

from fatebridge.core.metaphysics.taiyi.calendars import build_year_board, yearly_core
from fatebridge.core.metaphysics.taiyi.core import cyclic_core

__all__ = ["build_year_board", "cyclic_core", "yearly_core"]
