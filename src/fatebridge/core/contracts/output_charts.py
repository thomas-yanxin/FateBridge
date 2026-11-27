"""Nested contracts for classical, specialized and relationship charts.

Shared value contracts describe the canonical response fields. Dynamic
planet and midpoint keys remain open; interpretation prose remains extensible.
"""

from typing import Any

from fatebridge.core.contracts.output_chart_classical import (
    AlmutenFiguris,
    Classical,
    ClassicalPatterns,
    Hellenistic,
    PtolemyLayer,
    SolarConditionPolicy,
    Syzygy,
)
from fatebridge.core.contracts.output_chart_geometry import (
    ChartAngle,
    ChartAspect,
    ChartHouse,
    ChartPlanet,
    EphemerisReferencePoints,
    FixedStar,
    FixedStarProfile,
    HouseAxisConvention,
    HousePositionProjection,
    PlanetaryHours,
)
from fatebridge.core.contracts.output_chart_motion import (
    CompletePositionMotion,
    LongitudeMotionPolicy,
    SolarBranchGeometry,
)
from fatebridge.core.contracts.output_chart_profile import ChartProfile
from fatebridge.core.contracts.output_chart_relationships import (
    BirthClockConversion,
    Chart,
    ChartPerson,
    DirectionalContacts,
    Guolao,
    India,
    InnerOuter,
    Midpoint,
    MidpointAspect,
    RelationshipProfile,
    RelativeAntiscia,
    RelativeMidpointHit,
    SynastryAspect,
    ThirteenSector,
)
from fatebridge.core.contracts.output_chart_solar_position import OpaqueSolarPositions
from fatebridge.core.contracts.output_ephemeris import (
    ApparentPositionPolicy as ApparentPositionPolicy,
)
from fatebridge.core.contracts.output_midpoints import (
    MidpointAnalysis,
    SectorProfile,
    SpecialtyTimeSensitivity,
)
from fatebridge.core.contracts.output_rotation import (
    EarthRotationPolicy as EarthRotationPolicy,
)

__all__ = [
    "AlmutenFiguris",
    "ApparentPositionPolicy",
    "BirthClockConversion",
    "CHART_FIELDS",
    "CHART_TOOL_FIELDS",
    "ChartPlanet",
    "ChartProfile",
    "CompletePositionMotion",
    "EarthRotationPolicy",
    "EphemerisReferencePoints",
    "FixedStarProfile",
    "HouseAxisConvention",
    "HousePositionProjection",
    "LongitudeMotionPolicy",
    "PlanetaryHours",
    "PtolemyLayer",
    "SolarBranchGeometry",
    "SolarConditionPolicy",
    "Syzygy",
]


CHART_FIELDS: dict[str, Any] = {
    "aspect_evidence": list[ChartAspect],
    "angles": dict[str, ChartAngle],
    "aspects": list[ChartAspect],
    "houses": list[ChartHouse],
    "planets": list[ChartPlanet],
    "fixed_stars": list[FixedStar],
    "planetary_hours": PlanetaryHours,
    "chart_profile": ChartProfile,
    "classical": Classical,
    "classical_patterns": ClassicalPatterns,
    "hellenistic": Hellenistic,
    "guolao": Guolao,
    "vedic_chart": India,
    "thirteen_sectors": list[ThirteenSector],
    "sector_profile": SectorProfile,
    "midpoint_analysis": MidpointAnalysis,
    "birth_time_sensitivity": SpecialtyTimeSensitivity,
    "midpoints": list[Midpoint],
    "midpoint_aspects": list[MidpointAspect],
    "element_balance": dict[str, float],
    "modality_balance": dict[str, float],
    "base_chart": Chart,
    "inner_chart": Chart,
    "outer_chart": Chart,
    "inner": InnerOuter,
    "outer": InnerOuter,
    "relationship_profile": RelationshipProfile,
    "marks_charts": dict[str, Chart],
    "synastry_aspects": list[SynastryAspect],
    **{
        name: list[DirectionalContacts]
        for name in (
            "in_to_out_aspects",
            "out_to_in_aspects",
        )
    },
    **{
        name: list[RelativeAntiscia]
        for name in (
            "in_to_out_antiscia",
            "out_to_in_antiscia",
            "in_to_out_contra_antiscia",
            "out_to_in_contra_antiscia",
        )
    },
    **{
        name: dict[str, list[RelativeMidpointHit]]
        for name in (
            "in_to_out_midpoint",
            "out_to_in_midpoint",
        )
    },
}


CHART_TOOL_FIELDS: dict[str, dict[str, Any]] = {
    "astrology_chart": {
        "person_info": ChartPerson,
        "apparent_model_positions": OpaqueSolarPositions,
    },
    "thirteen_sector_chart": {
        "person_info": ChartPerson,
        "birth_time_sensitivity": SpecialtyTimeSensitivity,
    },
    "hellenistic_chart": {"person_info": ChartPerson},
    "guolao_chart": {"person_info": ChartPerson},
    "vedic_chart": {"person_info": ChartPerson},
    "vimshottari_dasha": {"person_info": ChartPerson},
    "relationship_chart": {"chart": Chart},
}
