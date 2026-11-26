"""Compatibility re-export for external astronomy/guolao tests until merge."""

from fatebridge.core.sukuyo.astronomy import (
    METHOD,
    apply_equatorial_mansions,
    build_equatorial_mansions,
)

__all__ = ["METHOD", "apply_equatorial_mansions", "build_equatorial_mansions"]
