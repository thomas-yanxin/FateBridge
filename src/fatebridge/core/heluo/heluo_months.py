"""Compatibility re-export for untouched divination callers; consolidated in judgment.py."""

from fatebridge.core.heluo.judgment import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
    month_affinity,
)

__all__ = ["DEFAULT_MONTH_ASSIGNMENT", "MonthAssignmentMethod", "month_affinity"]
