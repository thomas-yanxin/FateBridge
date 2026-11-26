"""Shared source facts for solar calculations and their output schemas."""

from typing import TypedDict


class SolarSourceReference(TypedDict):
    author: str
    source_version: str | None
    calculation_library: str
    time_argument: str
    coefficient_representation: str
    coefficient_profile: str | None
