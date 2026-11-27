"""Offline place lookup service exposing coordinates, timezone and disambiguation candidates."""

from __future__ import annotations

from typing import Any

from fatebridge.utils.places import lookup_place


def calculate_place_lookup(*, query: str, limit: int = 5) -> dict[str, Any]:
    """Resolve an offline place query or return disambiguating candidates."""
    return lookup_place(query, limit=limit)
