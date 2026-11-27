"""Projection-compatible public contracts for specialized chart geometry."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_comparisons import (
    ComparativeGeometry,
    MeridianHouseAnalysis,
    SolarArcAnalysis,
)
from fatebridge.core.contracts.output_midpoint_geometry import (
    DialCounts,
    GeometryRuleset,
    GeometryRuleTrace,
    GeometrySource,
    MidpointAxis,
    MidpointDial,
    MidpointFactor,
    MidpointProfile,
    PhysicalEphemerisSource,
    PhysicalFactorSource,
    SourceInterpretation,
)
from fatebridge.core.contracts.output_midpoint_sensitivity import (
    SpecialtyTimeSensitivity,
)
from fatebridge.core.contracts.output_midpoint_source_tables import MixedPairGeometry

__all__ = [
    "MidpointAnalysis",
    "MixedPairGeometry",
    "PhysicalEphemerisSource",
    "PhysicalFactorSource",
    "SectorEvidence",
    "SectorProfile",
    "SpecialtyTimeSensitivity",
]


class MidpointAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    profile: MidpointProfile | None = None
    factors: list[MidpointFactor] | None = None
    midpoint_axes: list[MidpointAxis] | None = None
    dials: dict[str, MidpointDial] | None = None
    contact_counts: dict[str, DialCounts] | None = None
    unique_two_factor_pair_count: int | None = None
    interpretations: list[SourceInterpretation] | None = None
    time_sensitivity: SpecialtyTimeSensitivity | None = None
    solar_arc_analysis: SolarArcAnalysis | None = None
    meridian_houses: MeridianHouseAnalysis | None = None
    comparative_geometry: ComparativeGeometry | None = None
    reading_guide: dict[str, str] | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class SectorProfile(PartialOutput):
    status: str | None = None
    backend_convention_anchor_longitude: float | None = None
    backend_convention_sectors: list[dict[str, OpenJsonValue]] | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    anchor: str | None = None
    anchor_longitude: float | None = None
    sector_count: int | None = None
    width_degrees: float | None = None
    interval_convention: str | None = None
    boundary_display: str | None = None
    coordinate_system: str | None = None
    astronomical_constellations: bool | None = None
    original_text_conformance: str | None = None
    sources: list[GeometrySource] | None = None


class SectorEvidence(PartialOutput):
    assignment_status: str | None = None
    backend_convention_sector: int | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    longitude_unrounded: float | None = None
    ascendant_unrounded: float | None = None
    interval_convention: str | None = None
    rule_id: str | None = None
    birth_time_uncertainty: str | None = None
