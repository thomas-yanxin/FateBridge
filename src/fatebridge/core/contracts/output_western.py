"""Stable nested facts for western professional techniques.

These contracts follow the builders in core/predictive, astrology_lifespan and
astrology_horary. Dictionary keys (planet, lot and diagnostic identifiers) stay
open; their values have contracts. Labels and method names remain extensible.
"""

from typing import Any

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_western_calendar import (
    WesternCivilCalendarConversion,
    WesternEventClockConversion,
    WesternHourOriginConversion,
)
from fatebridge.core.contracts.output_western_events import (
    PlanetaryEvent,
    PlanetaryEventHistory,
)
from fatebridge.core.contracts.output_western_geometry import (
    NatalReference,
    PrimaryDirections,
    WesternCalculationBasis,
    WesternPoint,
)
from fatebridge.core.contracts.output_western_horary import (
    Horary,
    HoraryRadicality,
    LillyFortitudes,
    LillyFortune,
)
from fatebridge.core.contracts.output_western_horary_facts import (
    HoraryMotionBasis,
    LillyDirectedSignRelationship,
    LillyHouseAssignment,
)
from fatebridge.core.contracts.output_western_lifespan import (
    AgePoint,
    Balbillus,
    Distributions,
    ExtraReturns,
    HarmonicChart,
    JaynesDeclination,
    Keypoints,
    LunationPhase,
    Mundane,
    PersianDirected,
    PlanetaryAges,
    PlanetaryArc,
    VedicProgression,
    YearSystem129,
)
from fatebridge.core.contracts.output_western_timing import (
    Decennials,
    Directions,
    Firdaria,
    Profection,
    Returns,
    SystemOutput,
    TimeLords,
    TimingChart,
    Transits,
    ZodiacalReleasing,
)


class TriplicityStage(PartialOutput):
    stage: int | None = None
    stage_label: str | None = None
    role: str | None = None
    role_label: str | None = None
    ruler: str | None = None
    ruler_label: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    planetary_period_years: float | None = None
    natal_condition: WesternPoint | None = None


class TriplicityRulers(SystemOutput):
    division: str | None = None
    element: str | None = None
    element_label: str | None = None
    lifespan_years: float | None = None
    sect: str | None = None
    sect_label: str | None = None
    sect_light: str | None = None
    sect_light_label: str | None = None
    sect_light_sign: str | None = None
    sect_light_sign_label: str | None = None
    stages: list[TriplicityStage] | None = None


__all__ = [
    "Horary",
    "HoraryMotionBasis",
    "HoraryRadicality",
    "LillyDirectedSignRelationship",
    "LillyFortitudes",
    "LillyFortune",
    "LillyHouseAssignment",
    "PlanetaryEvent",
    "PlanetaryEventHistory",
    "WESTERN_FIELDS",
    "WesternCalculationBasis",
    "WesternCivilCalendarConversion",
    "WesternEventClockConversion",
    "WesternHourOriginConversion",
]


WESTERN_FIELDS: dict[str, Any] = {
    "calendar_conversion": WesternCivilCalendarConversion,
    "clock_conversion": WesternEventClockConversion,
    "natal_reference": NatalReference,
    "solarreturn": TimingChart,
    "lunarreturn": TimingChart,
    "transit": TimingChart,
    "solararc": TimingChart,
    "givenyear": TimingChart,
    "profection": Profection,
    "pd": PrimaryDirections,
    "pdchart": PrimaryDirections,
    "zr": ZodiacalReleasing,
    "firdaria": Firdaria,
    "decennials": Decennials,
    "directions": Directions,
    "returns": Returns,
    "time_lords": TimeLords,
    "transits": Transits,
    "harmonic_chart": HarmonicChart,
    "planetary_ages": PlanetaryAges,
    "triplicity_rulers": TriplicityRulers,
    "lunation_phase": LunationPhase,
    "distributions": Distributions,
    "balbillus": Balbillus,
    "keypoints": Keypoints,
    "yearsystem129": YearSystem129,
    "planetary_arc": PlanetaryArc,
    "persian_directed": PersianDirected,
    "age_point": AgePoint,
    "vedic_progression": VedicProgression,
    "jaynes_declination": JaynesDeclination,
    "mundane": Mundane,
    "extrareturns": ExtraReturns,
    "horary": Horary,
}
