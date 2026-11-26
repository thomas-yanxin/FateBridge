"""Projection-compatible evidence contracts for Heluo and Canping."""

from fatebridge.core.contracts.output_canping_reading import (
    CanpingPairResolution,
    CanpingReadingRevision,
    CanpingTextSelection,
    CanpingTextWitness,
)
from fatebridge.core.contracts.output_heluo_month import (
    HeluoMonthAffinity,
    HeluoNajiaLine,
    HeluoNatalNajiaClause,
    HeluoSeasonalNumbers,
)
from fatebridge.core.contracts.output_heluo_qi import (
    HeluoYuanqiOpposition,
    HeluoYuanqiOppositionCondition,
    HeluoYuantangDerivation,
)
from fatebridge.core.contracts.output_heluo_structure import (
    HeluoBodyStructure,
    HeluoJudge,
    HeluoLineConditionRow,
    HeluoSourceYouyuan,
    HeluoStructurePhase,
    HeluoStructureRecord,
)
from fatebridge.core.contracts.output_heluo_timing import (
    HeluoSourceClock,
    HeluoTiming,
    HeluoTimingYearContext,
)
from fatebridge.core.contracts.output_numerology_clock import (
    HeluoNajiaCollation,
    NumerologyBirthClock,
    NumerologyClockInput,
    NumerologyEvidence,
    NumerologyPillarLink,
    NumerologyPillarLinks,
)

__all__ = [
    "CanpingPairResolution",
    "CanpingReadingRevision",
    "CanpingTextSelection",
    "CanpingTextWitness",
    "HeluoBodyStructure",
    "HeluoJudge",
    "HeluoLineConditionRow",
    "HeluoMonthAffinity",
    "HeluoNajiaCollation",
    "HeluoNajiaLine",
    "HeluoNatalNajiaClause",
    "HeluoSeasonalNumbers",
    "HeluoSourceClock",
    "HeluoSourceYouyuan",
    "HeluoStructurePhase",
    "HeluoStructureRecord",
    "HeluoTiming",
    "HeluoTimingYearContext",
    "HeluoYuanqiOpposition",
    "HeluoYuanqiOppositionCondition",
    "HeluoYuantangDerivation",
    "NumerologyBirthClock",
    "NumerologyClockInput",
    "NumerologyEvidence",
    "NumerologyPillarLink",
    "NumerologyPillarLinks",
]
