"""Western chart calculation profile and provenance."""

from typing import Annotated

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_chart_geometry import (
    ChartAspectPolicy,
    EphemerisReferencePoints,
    FixedStarProfile,
    GeographicPoleAngleDefinition,
    HouseAxisConvention,
    HousePositionProjection,
    OrbitalFallback,
    RelationshipDerivation,
)
from fatebridge.core.contracts.output_chart_motion import LongitudeMotionPolicy
from fatebridge.core.contracts.output_clock_labels import UTCDefinitionEvidence
from fatebridge.core.contracts.output_ephemeris import (
    ApparentPositionPolicy as ApparentPositionPolicy,
)
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_rotation import (
    EarthRotationPolicy as EarthRotationPolicy,
)


class ChartProfile(PartialOutput):
    utc_definition: UTCDefinitionEvidence | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    apparent_position_policy: ApparentPositionPolicy | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    ephemeris_model_scope: str | None = None
    nonphysical_factor_models: dict[str, str] | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    fixed_stars: FixedStarProfile | None = None
    house_axis_convention: HouseAxisConvention | None = None
    earth_rotation: EarthRotationPolicy | None = None
    planetary_models: dict[str, str] | None = None
    orbital_fallback: OrbitalFallback | None = None
    sidereal_planetary_methods: dict[str, str] | None = None
    angle_definition: GeographicPoleAngleDefinition | None = None
    house_overlay_policy: str | None = None
    derivation_policy: RelationshipDerivation | None = None
    aspect_policy: ChartAspectPolicy | None = None
    house_position_projection: HousePositionProjection | None = None
    coordinate_precision: str | None = None
    midpoint_coordinate_source: str | None = None
    midpoint_antipodal_policy: str | None = None
    calendar: str | None = None
    time_scale: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    horizon_method: str | None = None
    angle_method: str | None = None
    sect_convention: str | None = None
    ayanamsha: float | None = None
    ayanamsha_mean: float | None = None
    ayanamsha_includes_nutation: bool | None = None
    sidereal_position_method: str | None = None
    sidereal_house_method: str | None = None
    chart_type: Annotated[str | None, FULL_FACT] = None
    engine_backend: Annotated[str | None, FULL_FACT] = None
    engine_precision: str | None = None
    ephemeris_model: str | None = None
    house_system: str | None = None
    house_system_code: int | None = None
    house_system_label_zh: str | None = None
    house_system_source: str | None = None
    tradition: bool | None = None
    zodiac: str | None = None
    zodiac_label_zh: str | None = None
    zodiacal: int | None = None
    analysis_focus: str | None = None
