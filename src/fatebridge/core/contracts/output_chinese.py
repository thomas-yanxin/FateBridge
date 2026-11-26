"""Nested facts for Chinese professional and local divination techniques.

Stable rows, palaces, lessons and calendar facts are validated. Dynamic names
(stars, transformations and verse/hexagram keys) remain dictionary keys. Raw
interpretation, plugin details and user question inputs remain extensible JSON.
"""

from typing import Any

from fatebridge.core.contracts.output_canping_rows import CanpingRow
from fatebridge.core.contracts.output_canping_timing import CanpingSeries, CanpingTiming
from fatebridge.core.contracts.output_chinese_bundles import (
    HeluoChart,
    HeluoDayun,
    LocalAngles,
    LocalChart,
    LocalChartBundle,
    LocalHouse,
    LocalObject,
    SanshiSubresults,
)
from fatebridge.core.contracts.output_chinese_calendar import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
    GuaLookupResult,
    Hexagram,
    LunarCalendar,
    Meihua,
    PersonInfo,
    SolarTerm,
)
from fatebridge.core.contracts.output_divination import (
    ClassicalTextEvidence,
    LiuyaoEvidence,
)
from fatebridge.core.contracts.output_heluo_jiehou import HeluoJiehouEvidence
from fatebridge.core.contracts.output_heluo_solar import HeluoSolarTermEvidence
from fatebridge.core.contracts.output_jinkou_board import JinkouCourse
from fatebridge.core.contracts.output_jinkou_board_facts import (
    JinkouCombinations,
    JinkouJue,
    JinkouRelations,
)
from fatebridge.core.contracts.output_jinkou_qi_models import JinkouQiEvidence
from fatebridge.core.contracts.output_jinkou_year_fate import (
    Jinkou,
    JinkouNatalCourse,
    JinkouYearFate,
)
from fatebridge.core.contracts.output_liuren_board import (
    Liuren,
    RenDiurnalEvidence,
    RenTermDependency,
    Runyear,
)
from fatebridge.core.contracts.output_liuyao_cast import (
    SixyaoCast,
    SixyaoDescription,
    SixyaoFlags,
    SixyaoHexagramInfo,
    SixyaoLine,
    Tongshefa,
)
from fatebridge.core.contracts.output_numerology import (
    HeluoJudge,
    HeluoTiming,
    NumerologyEvidence,
)
from fatebridge.core.contracts.output_qimen_board import Qimen
from fatebridge.core.contracts.output_ren_patterns import JinkouPatterns
from fatebridge.core.contracts.output_sanshi import SanshiSynthesis
from fatebridge.core.contracts.output_taiyi_board import Taiyi, TaiyiCounterCycles
from fatebridge.core.contracts.output_ziwei_calendar import (
    ZiweiDateConversionProvenance,
)
from fatebridge.core.contracts.output_ziwei_structure import (
    ZiweiBirth,
    ZiweiConditionSourceRevision,
    ZiweiStructuralConditionRecord,
)
from fatebridge.core.contracts.output_ziwei_timing import (
    ZiweiChildhoodLimit,
    ZiweiDecadeHalf,
    ZiweiFocusedRules,
    ZiweiHoroscope,
    ZiweiHoroscopeNatalPrerequisites,
    ZiweiLimitStarGroup,
    ZiweiLimitSubperiods,
    ZiweiNominalAgeCalendar,
    ZiweiRuleCatalogue,
    ZiweiSmallLimitHalf,
)

__all__ = [
    "CHINESE_FIELDS",
    "CHINESE_TOOL_FIELDS",
    "CalendarContext",
    "CanpingRow",
    "CanpingSeries",
    "CanpingTiming",
    "FourPillars",
    "Jinkou",
    "JinkouCombinations",
    "JinkouCourse",
    "JinkouJue",
    "JinkouNatalCourse",
    "JinkouPatterns",
    "JinkouQiEvidence",
    "JinkouRelations",
    "JinkouYearFate",
    "Liuren",
    "LocalAngles",
    "LocalHouse",
    "LocalObject",
    "Meihua",
    "PersonInfo",
    "RenDiurnalEvidence",
    "RenTermDependency",
    "SolarTerm",
    "Taiyi",
    "TaiyiCounterCycles",
    "ZiweiChildhoodLimit",
    "ZiweiConditionSourceRevision",
    "ZiweiDateConversionProvenance",
    "ZiweiDecadeHalf",
    "ZiweiHoroscopeNatalPrerequisites",
    "ZiweiLimitStarGroup",
    "ZiweiLimitSubperiods",
    "ZiweiNominalAgeCalendar",
    "ZiweiSmallLimitHalf",
    "ZiweiStructuralConditionRecord",
]


CHINESE_FIELDS: dict[str, Any] = {
    "four_pillars": FourPillars,
    "person_info": PersonInfo,
    "analysis_context": AnalysisContext,
    "birth_context": AnalysisContext,
    "calendar_context": CalendarContext,
    "jieqi_year": list[SolarTerm],
    "selected_jieqi": list[SolarTerm],
    "target_year_jieqi": list[SolarTerm],
    "lunar_calendar": LunarCalendar,
    "meihua": Meihua,
    "tongshefa": Tongshefa,
    "ziwei_birth": ZiweiBirth,
    "ziwei_horoscope": ZiweiHoroscope,
    "focused_rules": ZiweiFocusedRules,
    "rule_catalogue": ZiweiRuleCatalogue,
    "liureng": Liuren,
    "runyear": Runyear,
    "qimen": Qimen,
    "taiyi": Taiyi,
    "jinkou": Jinkou,
    "current_hexagram": Hexagram,
    "changed_hexagram": Hexagram,
    "hexagram_info": SixyaoHexagramInfo,
    "cast": SixyaoCast,
    "descriptions": dict[str, SixyaoDescription],
    "pattern_flags": SixyaoFlags,
    "benming": CanpingRow,
    "liunian_series": CanpingSeries,
    "subresults": SanshiSubresults,
}


CHINESE_TOOL_FIELDS: dict[str, dict[str, Any]] = {
    "sanshi_combined_chart": {"synthesis": SanshiSynthesis},
    "liuyao": {
        "lines": list[SixyaoLine],
        "moving_lines": list[int],
        "liuyao_evidence": LiuyaoEvidence,
        "classical_text_evidence": ClassicalTextEvidence,
    },
    "gua_lookup": {
        "queries": list[str],
        "results": dict[str, GuaLookupResult],
        "lookup_mode": str,
        "summary": str,
        "analysis_type": str,
    },
    "canping": {
        "dayun": list[CanpingRow],
        "numerology_evidence": NumerologyEvidence,
        "canping_timing": CanpingTiming,
    },
    "heluo": {
        "chart": HeluoChart,
        "dayun": HeluoDayun,
        "judge": HeluoJudge,
        "numerology_evidence": NumerologyEvidence,
        "heluo_timing": HeluoTiming,
        "jiehou_evidence": HeluoJiehouEvidence,
        "solar_term": HeluoSolarTermEvidence,
    },
    "suzhan": {"chart": LocalChart},
    "interpret_astrology_dice": {
        "chart": LocalChartBundle,
        "diceChart": LocalChartBundle,
    },
}
