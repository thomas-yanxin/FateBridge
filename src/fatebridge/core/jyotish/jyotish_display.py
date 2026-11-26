"""Minimal compatibility stub for untouched services/astrology.py until Wave 3 deletion."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo


def normalize_solar_display(
    birth: AstroBirthInfo, ephemeris_policy: str, *, requested: bool | None = None
) -> tuple[AstroBirthInfo, dict[str, Any] | None]:
    return birth, None
