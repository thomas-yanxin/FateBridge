"""Nested facts for Chinese professional and local divination techniques.

Stable rows, palaces, lessons and calendar facts are validated. Dynamic names
(stars, transformations and verse/hexagram keys) remain dictionary keys. Raw
interpretation, plugin details and user question inputs remain extensible JSON.
"""

from datetime import datetime as _datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import Field, JsonValue, field_validator, model_validator

from fatebridge.core.output_base import FullFact, PartialOutput
from fatebridge.core.output_canping_schedule import CanpingScheduleBasis
from fatebridge.core.output_canping_solar import (
    CanpingSolarBoundary,
    CanpingSolarContext,
)
from fatebridge.core.output_divination import (
    ClassicalHexagram,
    ClassicalTextEvidence,
    LiuyaoEvidence,
)
from fatebridge.core.output_heluo_jiehou import HeluoJiehouEvidence
from fatebridge.core.output_heluo_solar import HeluoSolarTermEvidence
from fatebridge.core.output_jinkou_branch_stars import JinkouBranchStars
from fatebridge.core.output_jinkou_breaks import JinkouBranchBreaks, align_branch_breaks
from fatebridge.core.output_jinkou_definitions import (
    JinkouDefinitionEvidence,
    compare_present_definition_facts,
)
from fatebridge.core.output_jinkou_interactions import JinkouPositionInteractions
from fatebridge.core.output_jinkou_natal import JinkouNatalAbsolute
from fatebridge.core.output_jinkou_qi_models import (
    JinkouInternalRelation,
    JinkouQiEvidence,
)
from fatebridge.core.output_jinkou_sources import JinkouStrengthSource, JinkouUseSource
from fatebridge.core.output_jinkou_stems import JinkouStemRelations
from fatebridge.core.output_liuren_auxiliary import LiurenAuxiliaryStars
from fatebridge.core.output_liuren_branches import (
    LiurenBranchRelations,
    align_branch_relations,
)
from fatebridge.core.output_liuren_cross_harmony import (
    LiurenCrossHarmony,
    align_cross_harmony,
)
from fatebridge.core.output_liuren_day_placements import (
    LiurenDayPlacements,
    align_day_placements,
)
from fatebridge.core.output_liuren_emptiness import LiurenEmptinessEvidence
from fatebridge.core.output_liuren_god_yin import LiurenGodYin, align_god_yin
from fatebridge.core.output_liuren_life import LiurenLifeStage, LiurenLifeStages
from fatebridge.core.output_liuren_progression import (
    LiurenProgression,
    align_progression,
)
from fatebridge.core.output_liuren_seasonal import (
    LiurenSeasonalEvidence,
    align_seasonal,
)
from fatebridge.core.output_liuren_transmission_relations import (
    LiurenTransmissionRelations,
    compare_present_relations,
)
from fatebridge.core.output_liuren_year_fate import LiurenYearFate
from fatebridge.core.output_meihua import (
    MeihuaCalendarPolicy,
    MeihuaCountingVariant,
    MeihuaEvidenceScope,
    MeihuaRuleset,
    MeihuaSeasonalStrength,
    MeihuaStageRelation,
    MeihuaTraceStep,
)
from fatebridge.core.output_numerology import (
    CanpingPairResolution,
    CanpingTextSelection,
    HeluoJudge,
    HeluoTiming,
    HeluoYuantangDerivation,
    NumerologyEvidence,
)
from fatebridge.core.output_qimen import (
    QimenAssessment,
    QimenCalendarPolicy,
    QimenPalaceEvidence,
    QimenPattern,
    QimenRuleset,
    QimenRuleTrace,
    QimenStructure,
)
from fatebridge.core.output_ren_clock import (
    RenCivilClockResolution,
    RenRunyearAgeCalendar,
)
from fatebridge.core.output_ren_patterns import (
    JinkouPatternCounts as JinkouPatternCounts,
)
from fatebridge.core.output_ren_patterns import (
    JinkouPatternEvaluation as JinkouPatternEvaluation,
)
from fatebridge.core.output_ren_patterns import JinkouPatternMatch as JinkouPatternMatch
from fatebridge.core.output_ren_patterns import JinkouPatterns
from fatebridge.core.output_ren_patterns import (
    JinkouUnresolvedPattern as JinkouUnresolvedPattern,
)
from fatebridge.core.output_ren_term_dates import (
    RenPublishedDateReference,
    align_published_date,
)
from fatebridge.core.output_sanshi import SanshiSynthesis
from fatebridge.core.output_taiyi_calendar import (
    TaiyiCivilClockResolution,
    TaiyiCivilLunarCalendar,
)
from fatebridge.core.output_taiyi_conditions import TaiyiConditionAssessment
from fatebridge.core.output_taiyi_counts import TaiyiCountAssessment
from fatebridge.core.output_taiyi_day import (
    TaiyiDayOrigin,
    TaiyiSourceComparison,
    TaiyiTenJing,
)
from fatebridge.core.output_taiyi_elemental import TaiyiElementalAssessment
from fatebridge.core.output_taiyi_enclosures import TaiyiEnclosureAssessment
from fatebridge.core.output_taiyi_gates import TaiyiDeterminate, TaiyiGates
from fatebridge.core.output_taiyi_historical import TaiyiHistoricalReference
from fatebridge.core.output_taiyi_hour import TaiyiHourOrigin
from fatebridge.core.output_taiyi_long_cycles import TaiyiLongCycles, TaiyiLongSummary
from fatebridge.core.output_taiyi_matrix import TaiyiVictoryMatrixAssessment
from fatebridge.core.output_taiyi_month import TaiyiMonthOrigin
from fatebridge.core.output_taiyi_oppositions import TaiyiOppositionAssessment
from fatebridge.core.output_taiyi_shiji import TaiyiShijiDerivation
from fatebridge.core.output_taiyi_source_alignment import TaiyiSourceAlignment
from fatebridge.core.output_taiyi_year_calendar import TaiyiHistoricalYearCalendar
from fatebridge.utils.civil_clock import parse_iso_datetime

Object = Dict[str, JsonValue]


class Pillar(PartialOutput):
    stem: Optional[str] = None
    branch: Optional[str] = None


class FourPillars(PartialOutput):
    year: Optional[Pillar] = None
    month: Optional[Pillar] = None
    day: Optional[Pillar] = None
    hour: Optional[Pillar] = None


class PersonInfo(PartialOutput):
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_datetime: Optional[str] = None
    birth_place: Optional[str] = None
    birth_timezone: Optional[str] = None
    birth_longitude: Optional[float] = None
    birth_latitude: Optional[float] = None
    normalized_birth_datetime: Optional[str] = None
    time_algorithm: Optional[str] = None


class AnalysisContext(PartialOutput):
    context_role: Optional[str] = None
    analysis_year: Optional[int] = None
    analysis_month: Optional[int] = None
    analysis_day: Optional[int] = None
    analysis_hour: Optional[int] = None
    analysis_minute: Optional[int] = None
    input_datetime: Optional[str] = None
    corrected_datetime: Optional[str] = None
    timezone: Optional[str] = None
    longitude: Optional[float] = None
    applied_true_solar: Optional[bool] = None
    time_algorithm: Optional[str] = None
    total_correction_minutes: Optional[float] = None
    current_jieqi: Optional[str] = None
    next_jieqi: Optional[str] = None
    lunar_display: Optional[str] = None
    lunar_date_basis: Optional[str] = None
    lunar_date_provider: Optional[str] = None
    lunar_date_reference: Optional[str] = None
    calendar_date_shift_days: Optional[int] = None
    time_input_status: Optional[str] = None
    time_input_minute_sensitive: Optional[bool] = None
    civil_utc_offset: Optional[str] = None
    civil_instant_utc: Optional[str] = None
    birth_datetime: Optional[str] = None
    analysis_datetime: Optional[str] = None
    age_years: Optional[float] = None
    house_system: Optional[str] = None
    zodiac_type: Optional[str] = None
    orb_profile: Optional[str] = None
    name: Optional[str] = None
    birth_place: Optional[str] = None


class SolarTerm(PartialOutput):
    resolution_provider: Optional[str] = None
    ephemeris_model: Optional[str] = None
    solar_model_details: Optional[Dict[str, Any]] = None
    date_key: Optional[str] = None
    datetime: Optional[str] = Field(
        None, description="兼容本地钟面标签；不含偏移，重复小时不能仅据此复原瞬间"
    )
    datetime_with_offset: Optional[str] = Field(
        None,
        description="实际民用钟时的带偏移ISO表示；沿用声明时标政策，不认证绝对UTC精度",
    )
    utc_offset_seconds: Optional[float] = Field(
        None, gt=-86400, lt=86400, allow_inf_nan=False
    )
    fold: Optional[Literal[0, 1]] = None
    timezone: Optional[str] = None
    day_ganzhi: Optional[str] = None
    name: Optional[str] = None

    @field_validator("fold", mode="before")
    @classmethod
    def fold_is_an_integer(cls, value: Any) -> Any:
        # Literal[0, 1] alone also accepts True/False as Python-equal values.
        if value is not None and type(value) is not int:
            raise ValueError("节气fold必须为整数0或1")
        return value

    @model_validator(mode="after")
    def preserve_supplied_instant(self) -> "SolarTerm":
        if self.datetime_with_offset is None:
            return self
        text = self.datetime_with_offset
        clock = parse_iso_datetime(text[:-1] + "+00:00" if text.endswith("Z") else text)
        offset = clock.utcoffset()
        if offset is None:
            raise ValueError("节气datetime_with_offset必须包含明确UTC偏移")
        if (
            self.utc_offset_seconds is not None
            and offset.total_seconds() != self.utc_offset_seconds
        ):
            raise ValueError("节气时间字符串与utc_offset_seconds不一致")
        if self.datetime is not None:
            text = self.datetime
            legacy = parse_iso_datetime(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )
            if legacy.replace(tzinfo=None) != clock.replace(tzinfo=None):
                raise ValueError("节气旧钟面标签与带偏移时间不一致")
        return self


class Trigram(PartialOutput):
    name: Optional[str] = None
    cname: Optional[str] = None
    element: Optional[str] = None
    elem: Optional[str] = None
    lines: Optional[List[int]] = None
    nature: Optional[str] = None
    symbol: Optional[str] = None
    value: Optional[List[int]] = None
    theme: Optional[str] = None
    keywords: Optional[str] = None
    image: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    guidance: Optional[str] = None


class Hexagram(PartialOutput):
    classical: Optional[ClassicalHexagram] = None
    meaning_source_kind: Optional[str] = None
    name: Optional[str] = None
    binary_code: Optional[str] = None
    code: Optional[str] = None
    lookup_type: Optional[str] = None
    matched_query: Optional[str] = None
    lines: Optional[List[int]] = None
    lower: Optional[Trigram] = None
    upper: Optional[Trigram] = None
    moving_line: Optional[int] = None
    symbol: Optional[str] = None
    theme: Optional[str] = None
    image: Optional[str] = None
    judgement: Optional[str] = None
    summary: Optional[str] = None
    guidance: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    text: Optional[str] = None
    desc: Optional[str] = None


class MeihuaSeed(PartialOutput):
    casting_method: Optional[str] = None
    parameters: Optional[Object] = None
    ignored_components: Optional[Object] = None
    raw_upper_number: Optional[int] = None
    raw_lower_number: Optional[int] = None
    line_sum: Optional[int] = None
    line_sum_basis: Optional[str] = None
    alternate_moving_line: Optional[int] = None
    count_boundary_status: Optional[str] = None
    text_count_basis: Optional[Object] = None
    text_tone_basis: Optional[Object] = None
    hour_branch: Optional[str] = None
    year_branch: Optional[str] = None
    lunar_day: Optional[int] = None
    lunar_month: Optional[int] = None
    moving_line: Optional[int] = None
    upper_number: Optional[int] = None
    lower_number: Optional[int] = None


class Meihua(PartialOutput):
    counting_variants: Optional[List[MeihuaCountingVariant]] = None
    version: Optional[str] = None
    ruleset: Optional[MeihuaRuleset] = None
    calendar_policy: Optional[MeihuaCalendarPolicy] = None
    rule_trace: Optional[List[MeihuaTraceStep]] = None
    stage_relations: Optional[List[MeihuaStageRelation]] = None
    seasonal_strength: Optional[MeihuaSeasonalStrength] = None
    evidence_scope: Optional[MeihuaEvidenceScope] = None
    ruleset_id: Optional[str] = None
    year_boundary: Optional[str] = None
    leap_month_rule: Optional[str] = None
    mutual_rule: Optional[str] = None
    source_url: Optional[str] = None
    method: Optional[str] = None
    seed: Optional[MeihuaSeed] = None
    base_hexagram: Optional[Hexagram] = None
    changed_hexagram: Optional[Hexagram] = None
    mutual_hexagram: Optional[Hexagram] = None
    cuo_hexagram: Optional[Hexagram] = None
    zong_hexagram: Optional[Hexagram] = None
    body_trigram: Optional[Trigram] = None
    use_trigram: Optional[Trigram] = None
    body_use_relation: Optional[str] = None
    body_use_summary: Optional[str] = None
    element_relation: Optional[str] = None
    moving_palace: Optional[str] = None
    summary: Optional[str] = None


class LunarCalendar(PartialOutput):
    conversion_source: Optional[Dict[str, str]] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None
    year_cn: Optional[str] = None
    month_cn: Optional[str] = None
    day_cn: Optional[str] = None
    birth: Optional[str] = None
    display: Optional[str] = None
    day_ganzhi: Optional[str] = None
    month_ganzhi: Optional[str] = None
    time_ganzhi: Optional[str] = None
    year_jieqi_ganzhi: Optional[str] = None
    solar_datetime: Optional[str] = None
    timezone: Optional[str] = None
    jieqi: Optional[str] = None
    jiedelta: Optional[str] = None
    days_until_next_jieqi: Optional[float] = None
    previous_jieqi: Optional[SolarTerm] = None
    next_jieqi: Optional[SolarTerm] = None
    meihua: Optional[Meihua] = None


class MonthBoundary(PartialOutput):
    branch: Optional[str] = None
    month_index: Optional[int] = None
    comparison_datetime: Optional[str] = None
    elapsed_basis: Optional[Literal["utc_instant_seconds"]] = None
    elapsed_seconds_since_start: Optional[float] = Field(default=None, ge=0)
    elapsed_seconds_until_next: Optional[float] = Field(default=None, ge=0)
    days_since_start: Optional[float] = None
    days_until_next: Optional[float] = None
    start_term: Optional[SolarTerm] = None
    next_term: Optional[SolarTerm] = None


class SolarTermDelta(PartialOutput):
    days_since_current: Optional[float] = None
    days_until_next: Optional[float] = None
    description: Optional[str] = None


class LunarSupport(PartialOutput):
    supported: Optional[bool] = None
    supported_range: Optional[Dict[str, str]] = None


class BirthTimeInput(PartialOutput):
    method_id: Optional[Literal["birth_clock_components_v1"]] = None
    supplied_components: Optional[List[str]] = None
    omitted_components: Optional[List[str]] = None
    calculation_defaults: Optional[Dict[str, int]] = None
    nominal_civil_datetime: Optional[str] = None
    corrected_clock_datetime: Optional[str] = None
    timezone: Optional[str] = None
    requested_utc_offset: Optional[str] = None
    civil_utc_offset: Optional[str] = None
    civil_instant_utc: Optional[str] = None
    civil_fold: Optional[Literal[0, 1]] = None
    civil_time_ambiguous: Optional[bool] = None
    timezone_source: Optional[str] = None
    timezone_rules: Optional[Dict[str, str]] = None
    offset_selection_scope: Optional[str] = None
    uncertainty_interval: Optional[Dict[str, str]] = None
    observed_precision_certified: Optional[Literal[False]] = None
    scope: Optional[str] = None


class CalendarContext(PartialOutput):
    solar_datetime: Optional[str] = None
    timezone: Optional[str] = None
    lunar_calendar: Optional[LunarCalendar] = None
    current_solar_term: Optional[SolarTerm] = None
    next_solar_term: Optional[SolarTerm] = None
    bazi_month_boundary: Optional[MonthBoundary] = None
    solar_term_delta: Optional[SolarTermDelta] = None
    lunar_calendar_support: Optional[LunarSupport] = None
    birth_time_input: Optional[BirthTimeInput] = None


class BranchName(PartialOutput):
    branch: Optional[str] = None
    name: Optional[str] = None


class LunarDate(PartialOutput):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None


class ZiweiMinuteSensitivity(PartialOutput):
    method_id: Optional[str] = None
    assumption: Optional[str] = None
    birth_seconds_supplied: Optional[bool] = None
    base_second: Optional[int] = None
    endpoint_seconds: Optional[List[float]] = None
    endpoint_placement_datetimes: Optional[List[str]] = None
    endpoint_hour_branches: Optional[List[str]] = None
    crosses_hour_branch: Optional[bool] = None
    crosses_placement_date: Optional[bool] = None
    endpoints_are_alternative_birth_facts: Optional[bool] = None
    observed_birth_precision_certified: Optional[bool] = None
    scope: Optional[str] = None


class ZiweiTimeInput(PartialOutput):
    method_id: Optional[str] = None
    status: Optional[str] = None
    requested: Optional[bool] = None
    explicitly_requested: Optional[bool] = None
    applied: Optional[bool] = None
    components_computed: Optional[bool] = None
    timezone: Optional[str] = None
    timezone_source: Optional[str] = None
    timezone_resolved_place: Optional[str] = None
    timezone_assumed: Optional[bool] = None
    timezone_rules: Optional[Dict[str, str]] = None
    longitude: Optional[float] = None
    longitude_source: Optional[str] = None
    resolved_place: Optional[str] = None
    resolution_level: Optional[str] = None
    resolution_advisory: Optional[str] = None
    longitude_correction_minutes: Optional[float] = None
    equation_of_time_minutes: Optional[float] = None
    daylight_saving_minutes: Optional[float] = None
    total_correction_minutes: Optional[float] = None
    applied_delta_seconds: Optional[float] = None
    solar_time_strategy: Optional[str] = None
    equation_of_time_method: Optional[str] = None
    equation_of_time_time_scale: Optional[str] = None
    seconds_are_derived_not_birth_accuracy: Optional[bool] = None
    minute_sensitivity: Optional[ZiweiMinuteSensitivity] = None
    advisories: Optional[List[str]] = None
    precision_scope: Optional[str] = None
    source_basis: Optional[Dict[str, str]] = None


class ZiweiCivilClock(PartialOutput):
    method_id: Optional[str] = None
    selection: Optional[str] = None
    timezone: Optional[str] = None
    resolved_utc_offset: Optional[str] = None
    wall_datetime: Optional[str] = None
    was_ambiguous: Optional[bool] = None
    fold: Optional[int] = Field(default=None, ge=0, le=1)
    instant_utc: Optional[str] = None
    timezone_rules: Optional[Dict[str, str]] = None


class ZiweiDateReference(PartialOutput):
    publisher: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    raw_sha256: Optional[str] = None
    date_scope: Optional[List[str]] = None
    role: Optional[str] = None


class ZiweiDateLookupProvenance(PartialOutput):
    solar_date: Optional[str] = None
    status: Optional[Literal["available", "unavailable"]] = None
    implementation_provider: Optional[str] = None
    printed_date_reference: Optional[str] = None
    applied_year_info_correction: Optional[str] = None


class ZiweiDateConversionProvenance(PartialOutput):
    method_id: Optional[str] = None
    lookups: Optional[Dict[str, ZiweiDateLookupProvenance]] = None
    implementation_sources: Optional[Dict[str, Dict[str, str]]] = None
    printed_date_references: Optional[Dict[str, ZiweiDateReference]] = None
    implementation_data_is_independent_validation: Optional[Literal[False]] = None
    historical_clock_policy_verified: Optional[Literal[False]] = None


class ZiweiCalendarBasis(PartialOutput):
    method_id: Optional[str] = None
    placement_clock: Optional[str] = None
    placement_datetime: Optional[str] = None
    civil_datetime: Optional[str] = None
    timezone: Optional[str] = None
    date_shift_days: Optional[int] = None
    placement_lunar_date: Optional[LunarDate] = None
    civil_date_lunar_date: Optional[LunarDate] = None
    reference_datetime_utc_plus_08: Optional[str] = None
    reference_lunar_date: Optional[LunarDate] = None
    date_lookup_convention: Optional[str] = None
    day_boundary: Optional[str] = None
    solar_terms_basis: Optional[str] = None
    classical_clock_rule_verified: Optional[bool] = None
    source_scope: Optional[str] = None
    reference_source: Optional[str] = None
    date_conversion_provenance: Optional[ZiweiDateConversionProvenance] = None
    time_input: Optional[ZiweiTimeInput] = None
    civil_clock: Optional[ZiweiCivilClock] = None


class ZiweiHoroscopeCalendarBasis(PartialOutput):
    birth: Optional[ZiweiCalendarBasis] = None
    target: Optional[ZiweiCalendarBasis] = None
    nominal_age_rule: Optional[str] = None
    age_boundary_classically_verified: Optional[bool] = None


class ZiweiPosition(BranchName):
    ganzhi: Optional[str] = None


class ZiweiStar(PartialOutput):
    name: Optional[str] = None
    label: Optional[str] = None
    brightness: Optional[str] = None
    mutagen: Optional[str] = None


class ZiweiRelatedPalace(PartialOutput):
    relation: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_palace_ganzhi: Optional[str] = None
    branch: Optional[str] = None
    stars_detail: Optional[List[ZiweiStar]] = None


class ZiweiStructuralEvidence(PartialOutput):
    major_stars: Optional[List[str]] = None
    is_empty_main_palace: Optional[bool] = None
    sanfang_sizheng: Optional[List[ZiweiRelatedPalace]] = None
    opposite_stars_relocated: Optional[bool] = None


class ZiweiSihuaSourcePosition(PartialOutput):
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_mutagen: Optional[str] = None
    calculation_path: Optional[str] = None


class ZiweiSihuaSourceDifference(PartialOutput):
    year_stem: Optional[str] = None
    transformation: Optional[str] = None
    selected_star: Optional[str] = None
    compared_star: Optional[str] = None
    selected_position: Optional[ZiweiSihuaSourcePosition] = None
    compared_position: Optional[ZiweiSihuaSourcePosition] = None


class ZiweiSihuaSourceComparison(PartialOutput):
    dynamic_reuse_classically_verified: Optional[bool] = None
    method_id: Optional[str] = None
    version: Optional[str] = None
    compared_source: Optional[str] = None
    source_title: Optional[str] = None
    source_section: Optional[str] = None
    printed_volume: Optional[str] = None
    source_cell_count: Optional[int] = None
    manual_reader_count: Optional[int] = None
    scope: Optional[str] = None
    source_frame: Optional[int] = None
    source_reading: Optional[str] = None
    year_stem: Optional[str] = None
    source_agrees_on_this_stem: Optional[bool] = None
    compared_assignments_applied: Optional[bool] = None
    whole_book_conformance_claimed: Optional[bool] = None
    differences: Optional[List[ZiweiSihuaSourceDifference]] = None


class ZiweiRuleset(PartialOutput):
    sihua_source: Optional[str] = None
    sihua_source_url: Optional[str] = None
    id: Optional[str] = None
    version: Optional[str] = None
    baseline_source: Optional[str] = None
    classical_source: Optional[str] = None
    source_kind: Optional[str] = None
    overrides: Optional[List[str]] = None
    leap_month_rule: Optional[str] = None
    sihua_rule: Optional[str] = None
    target_leap_month_rule: Optional[str] = None
    dynamic_sihua_rule: Optional[str] = None
    brightness_rule: Optional[str] = None
    classical_conformance: Optional[str] = None
    unresolved: Optional[List[str]] = None
    real_world_efficacy: Optional[str] = None


class ZiweiRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None


class ZiweiCycleRules(PartialOutput):
    status: Optional[str] = None
    changsheng_start: Optional[str] = None
    changsheng_direction: Optional[str] = None
    changsheng_rule: Optional[str] = None
    changsheng_source: Optional[str] = None
    boshi_start: Optional[str] = None
    boshi_direction: Optional[str] = None
    boshi_rule: Optional[str] = None
    boshi_source: Optional[str] = None
    label_scope: Optional[str] = None
    naming_note: Optional[str] = None
    missing_gender_resolution: Optional[str] = None
    gender_invariant_positions: Optional[Dict[str, Dict[str, str]]] = None


class ZiweiCycleSourceHeader(PartialOutput):
    source_start: Optional[str] = None
    actual_start_branches: Optional[List[str]] = None
    reported_start: Optional[str] = None
    start_match: Optional[bool] = None
    source_direction: Optional[str] = None
    actual_direction: Optional[str] = None
    direction_match: Optional[bool] = None


class ZiweiCycleSourcePosition(PartialOutput):
    actual: Optional[str] = None
    candidates: Optional[List[str]] = None
    match: Optional[bool] = None


class ZiweiCycleSourceComparison(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    printed_volume: Optional[str] = None
    source_frames: Optional[Dict[str, int]] = None
    inputs: Optional[Dict[str, str]] = None
    scope: Optional[str] = None
    changsheng: Optional[ZiweiCycleSourceHeader] = None
    boshi: Optional[ZiweiCycleSourceHeader] = None
    positions: Optional[Dict[str, Dict[str, ZiweiCycleSourcePosition]]] = None
    source_rule_applied: Optional[Dict[str, bool]] = None
    source_name_mapping: Optional[Dict[str, str]] = None
    unknown_gender_policy: Optional[str] = None
    manual_reader_count: Optional[int] = None
    whole_book_conformance_claimed: Optional[bool] = None


class ZiweiChartMaster(PartialOutput):
    star: Optional[str] = None
    selection_basis: Optional[str] = None
    basis_branch: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    source: Optional[str] = None
    source_status: Optional[str] = None


class ZiweiChartMasters(PartialOutput):
    life: Optional[ZiweiChartMaster] = None
    body: Optional[ZiweiChartMaster] = None


class ZiweiFlowingStar(PartialOutput):
    star: Optional[str] = None
    scope: Optional[str] = None
    branch: Optional[str] = None
    scope_palace_name: Optional[str] = None
    natal_palace_name: Optional[str] = None
    rule_id: Optional[str] = None
    stem: Optional[str] = None
    source: Optional[str] = None
    natal_stars_relocated: Optional[bool] = None
    system_id: Optional[str] = None
    year_branch: Optional[str] = None


class ZiweiAnnualThreeSha(PartialOutput):
    rule_id: Optional[str] = None
    scope: Optional[str] = None
    year_branch: Optional[str] = None
    names_as_written: Optional[List[str]] = None
    branches: Optional[List[str]] = None
    individual_name_positions: Optional[Dict[str, str]] = None
    individual_assignment_status: Optional[str] = None
    source: Optional[str] = None
    distinct_from_boshi_cycle: Optional[bool] = None


class ZiweiSymbolicRecord(PartialOutput):
    star: Optional[str] = None
    source_name: Optional[str] = None
    elements_as_written: Optional[List[str]] = None
    source_quote: Optional[str] = None
    source_section: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_brightness: Optional[str] = None
    natal_mutagen: Optional[str] = None
    calculation_path: Optional[str] = None


class ZiweiSymbolicProperties(PartialOutput):
    method_id: Optional[str] = None
    source: Optional[str] = None
    source_status: Optional[str] = None
    element_collation_source: Optional[str] = None
    element_collation_frames: Optional[List[int]] = None
    element_collation_scope: Optional[str] = None
    scope: Optional[str] = None
    textual_hua_terms_are_sihua: Optional[bool] = None
    multi_element_text_retained: Optional[bool] = None
    records: Optional[List[ZiweiSymbolicRecord]] = None


class ZiweiMingEntity(PartialOutput):
    kind: Optional[str] = None
    name: Optional[str] = None


class ZiweiMingDefinition(PartialOutput):
    id: Optional[str] = None
    frame: Optional[int] = None
    quote: Optional[str] = None
    elements: Optional[List[str]] = None
    entities: Optional[List[ZiweiMingEntity]] = None
    glyph_note: Optional[str] = None
    source_names: Optional[List[str]] = None
    name_mapping: Optional[str] = None
    identity_note: Optional[str] = None
    quote_scope: Optional[str] = None
    unresolved_tail_candidates: Optional[List[str]] = None
    unresolved_tail_note: Optional[str] = None
    element_status: Optional[str] = None


class ZiweiMingOccurrence(PartialOutput):
    kind: Optional[str] = None
    name: Optional[str] = None
    definition_id: Optional[str] = None
    star: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_mutagen: Optional[str] = None
    calculation_path: Optional[str] = None


class ZiweiLianzhenReading(PartialOutput):
    definition_id: Optional[str] = None
    frame: Optional[int] = None
    quote: Optional[str] = None
    calculation_path: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    at_career_palace: Optional[bool] = None
    at_ming_branch: Optional[bool] = None
    at_shen_branch: Optional[bool] = None
    selected_mingshen_reading: Optional[str] = None
    mingshen_reading_independently_adjudicated: Optional[bool] = None
    applicable_terms_given_selected_reading: Optional[List[str]] = None
    terms_are_new_palace_names: Optional[bool] = None


class ZiweiQishaReading(PartialOutput):
    definition_id: Optional[str] = None
    frame: Optional[int] = None
    quote: Optional[str] = None
    qisha_calculation_path: Optional[str] = None
    ziwei_calculation_path: Optional[str] = None
    separation_steps: Optional[int] = None
    same_palace: Optional[bool] = None
    opposite_palace: Optional[bool] = None
    trine: Optional[bool] = None
    source_encounter_geometry_defined: Optional[bool] = None
    condition_match: Optional[bool] = None
    unresolved_reason: Optional[str] = None
    actual_qisha_mutagen: Optional[str] = None
    symbolic_quan_is_new_sihua_assignment: Optional[bool] = None


class ZiweiMingConditionalReadings(PartialOutput):
    lianzhen: Optional[ZiweiLianzhenReading] = None
    qisha: Optional[ZiweiQishaReading] = None


class ZiweiMingCountNote(PartialOutput):
    printed_quote: Optional[str] = None
    printed_count: Optional[int] = None
    enumerated_modern_star_names: Optional[int] = None
    status: Optional[str] = None


class ZiweiUnresolvedRelation(PartialOutput):
    definition_id: Optional[str] = None
    source_phrase: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None


class ZiweiMingProperties(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    source_title: Optional[str] = None
    printed_volume: Optional[str] = None
    source_section: Optional[str] = None
    manual_reader_count: Optional[int] = None
    scope: Optional[str] = None
    definitions: Optional[Dict[str, ZiweiMingDefinition]] = None
    occurrences: Optional[List[ZiweiMingOccurrence]] = None
    unlocated_natal_source_stars: Optional[List[str]] = None
    unresolved_boshi_labels: Optional[List[str]] = None
    unassigned_source_labels: Optional[List[str]] = None
    conditional_readings: Optional[ZiweiMingConditionalReadings] = None
    unresolved_relational_definitions: Optional[List[ZiweiUnresolvedRelation]] = None
    name_mapping: Optional[Dict[str, str]] = None
    positive_star_count_note: Optional[ZiweiMingCountNote] = None
    source_elements_replace_bureau_or_star_brightness: Optional[bool] = None
    source_taxonomy_applied_to_modern_classification: Optional[bool] = None
    symbolic_verbs_create_sihua_assignments: Optional[bool] = None
    actual_assignments_modified: Optional[bool] = None
    full_section_transcription_certified: Optional[bool] = None
    whole_book_acceptance_passed: Optional[bool] = None


class ZiweiXunVoid(PartialOutput):
    source_branches: Optional[List[str]] = None
    displayed_star_branches: Optional[List[str]] = None
    display_rule: Optional[str] = None
    source: Optional[str] = None


class ZiweiVoidSystems(PartialOutput):
    xun: Optional[ZiweiXunVoid] = None
    source_name_mapping: Optional[Dict[str, str]] = None


class ZiweiPalace(PartialOutput):
    name: FullFact[Optional[str]] = None
    ganzhi: FullFact[Optional[str]] = None
    daxian: Optional[str] = None
    daxian_period: Optional[int] = None
    stars: Optional[List[str]] = None
    stars_detail: Optional[List[ZiweiStar]] = None
    structural_evidence: Optional[ZiweiStructuralEvidence] = None
    changsheng12: Optional[str] = None
    boshi12: Optional[str] = None


class ZiweiReadingPalace(PartialOutput):
    name: Optional[str] = None
    ganzhi: Optional[str] = None
    stars: Optional[List[ZiweiStar]] = None
    major_stars: Optional[List[str]] = None
    sanfang_sizheng_branches: Optional[List[str]] = None
    changsheng12: Optional[str] = None
    boshi12: Optional[str] = None
    daxian: Optional[str] = None


class ZiweiReadingView(PartialOutput):
    schema_version: Optional[str] = None
    null_star_fields_omitted: Optional[List[str]] = None
    sanfang_branch_order: Optional[List[str]] = None
    palaces: Optional[List[ZiweiReadingPalace]] = None
    star_occurrence_count: Optional[int] = None
    distinct_star_count: Optional[int] = None


class ZiweiCalendarRules(PartialOutput):
    late_zi: Optional[str] = None
    leap_month: Optional[str] = None
    year_boundary: Optional[str] = None
    effective_birth_month: Optional[int] = None


class WuxingJu(PartialOutput):
    element: Optional[str] = None
    label: Optional[str] = None
    nayin: Optional[str] = None
    number: Optional[int] = None


class ZiweiAuxPlacementSourceRow(PartialOutput):
    star: Optional[str] = None
    basis_id: Optional[str] = None
    actual_branch: Optional[str] = None
    expected_branch: Optional[str] = None
    matches_source_rule: Optional[bool] = None
    calculation_path: Optional[str] = None
    unresolved_reason: Optional[str] = None


class ZiweiAuxPlacementSources(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    printed_volume: Optional[str] = None
    scope: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    methods: Optional[Dict[str, Any]] = None
    placements: Optional[List[ZiweiAuxPlacementSourceRow]] = None
    source_name_mapping: Optional[Dict[str, str]] = None
    unchecked_star_names: Optional[List[str]] = None
    manual_reader_count: Optional[int] = None
    compared_rules_applied: Optional[bool] = None
    whole_book_conformance_claimed: Optional[bool] = None


class ZiweiConditionOccurrence(PartialOutput):
    star: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_mutagen: Optional[str] = None
    calculation_path: Optional[str] = None


class ZiweiConditionExample(PartialOutput):
    ming: Optional[str] = None
    positions: Optional[Dict[str, str]] = None


class ZiweiStructuralConditionIndex(PartialOutput):
    id: Optional[str] = None
    source_frame: Optional[int] = None
    source_quote: Optional[str] = None
    geometry_match: Optional[bool] = None
    evaluated_necessary_premises_match: Optional[bool] = None
    source_literal_example_matches: Optional[bool] = None
    source_qualifications_not_evaluated: Optional[List[str]] = None
    full_traditional_judgment: None = None
    source_outcome_claim_adopted: Optional[Literal[False]] = None


class ZiweiConditionAnnotationRevision(PartialOutput):
    prior_annotation: Optional[str] = None
    reader_annotations: Optional[List[str]] = None
    status: Optional[
        Literal[
            "unresolved_after_independent_rereading",
            "corrected_after_independent_rereading",
        ]
    ] = None
    reason: Optional[str] = None


class ZiweiConditionSourceRevision(PartialOutput):
    id: Optional[str] = None
    source_manifest_sha256: Optional[str] = None
    first_reading_sha256: Optional[str] = None
    primary_review_sha256: Optional[str] = None
    peer_review_sha256: Optional[str] = None
    prior_collation_sha256: Optional[str] = None
    prior_compiled_sha256: Optional[str] = None
    changed_clause_ids: Optional[List[str]] = None
    isolated_model_readers: Optional[int] = None
    external_human_experts: Optional[Literal[0]] = None
    new_witnesses: Optional[Literal[0]] = None
    numeric_or_geometric_rules_modified: Optional[Literal[False]] = None
    whole_book_acceptance_passed: Optional[Literal[False]] = None


class ZiweiStructuralConditionRecord(ZiweiStructuralConditionIndex):
    source_annotation: Optional[str] = None
    annotation_revision: Optional[ZiweiConditionAnnotationRevision] = None
    geometry_rule: Optional[str] = None
    actual_occurrences: Optional[Dict[str, List[ZiweiConditionOccurrence]]] = None
    ming_branch_requirement_met: Optional[bool] = None
    year_stem_requirement_met: Optional[bool] = None
    literal_example: Optional[ZiweiConditionExample] = None
    missing_or_duplicated_stars: Optional[List[str]] = None


class ZiweiStructuralConditions(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    source_title: Optional[str] = None
    source_section: Optional[str] = None
    source_section_is_editorial_label: Optional[bool] = None
    source_status: Optional[str] = None
    manual_reader_count: Optional[int] = None
    source_revision: Optional[ZiweiConditionSourceRevision] = None
    ming_branch: Optional[str] = None
    year_stem: Optional[str] = None
    adjacent_branches: Optional[List[str]] = None
    flanking_reading: Optional[str] = None
    index: Optional[List[ZiweiStructuralConditionIndex]] = None
    records: Optional[List[ZiweiStructuralConditionRecord]] = None
    scope: Optional[str] = None
    actual_assignments_modified: Optional[Literal[False]] = None
    whole_book_acceptance_passed: Optional[Literal[False]] = None
    real_world_efficacy: Optional[str] = None


class ZiweiBirth(PartialOutput):
    engine: FullFact[Optional[str]] = None
    calendar_basis: FullFact[Optional[ZiweiCalendarBasis]] = None
    calendar_rules: FullFact[Optional[ZiweiCalendarRules]] = None
    ruleset: FullFact[Optional[ZiweiRuleset]] = None
    rule_trace: FullFact[Optional[List[ZiweiRuleTrace]]] = None
    reading_view: Optional[ZiweiReadingView] = None
    symbolic_properties: Optional[ZiweiSymbolicProperties] = None
    ming_textual_properties: Optional[ZiweiMingProperties] = None
    ming_structural_conditions: Optional[ZiweiStructuralConditions] = None
    sihua_source_comparison: Optional[ZiweiSihuaSourceComparison] = None
    auxiliary_placement_sources: Optional[ZiweiAuxPlacementSources] = None
    void_systems: Optional[ZiweiVoidSystems] = None
    chart_masters: Optional[ZiweiChartMasters] = None
    calendar_cycles: Optional[ZiweiCycleRules] = None
    cycle_source_comparison: Optional[ZiweiCycleSourceComparison] = None
    daxian_direction: Optional[str] = None
    hour_branch: Optional[str] = None
    lunar_date: Optional[LunarDate] = None
    ming_gong: FullFact[Optional[ZiweiPosition]] = None
    shen_gong: FullFact[Optional[ZiweiPosition]] = None
    palaces: FullFact[Optional[List[ZiweiPalace]]] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "name"},
    )
    sihua: Optional[Dict[str, str]] = None
    time_algorithm: Optional[str] = None
    wuxing_ju: FullFact[Optional[WuxingJu]] = None
    year_stem: Optional[str] = None


class ZiweiMutagenNatalLink(PartialOutput):
    transformation: Optional[str] = None
    star: Optional[str] = None
    status: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_palace_ganzhi: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_star_label: Optional[str] = None
    natal_star_brightness: Optional[str] = None
    natal_mutagen: Optional[str] = None
    scope_palace_name: Optional[str] = None


class ZiweiScopePalace(PartialOutput):
    scope_palace_name: Optional[str] = None
    branch: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_palace_ganzhi: Optional[str] = None
    natal_stars_detail: Optional[List[ZiweiStar]] = None


class ZiweiScope(PartialOutput):
    scope: Optional[str] = None
    status: Optional[str] = None
    first_age: Optional[int] = None
    unavailable_reason: Optional[str] = None
    branch: Optional[str] = None
    branch_index: Optional[int] = None
    stem: Optional[str] = None
    palace_ganzhi: Optional[str] = None
    palace_name: Optional[str] = None
    scope_palace_role: Optional[str] = None
    natal_palace_name: Optional[str] = None
    mutagen: Optional[Dict[str, str]] = None
    mutagen_natal_links: Optional[List[ZiweiMutagenNatalLink]] = None
    palace_map: Optional[List[ZiweiScopePalace]] = None
    stem_origin: Optional[str] = None
    flowing_stars: Optional[List[ZiweiFlowingStar]] = None
    annual_three_sha: Optional[ZiweiAnnualThreeSha] = None


class ZiweiInterpretationScope(PartialOutput):
    contract_version: Optional[str] = None
    scope_palace_meaning: Optional[str] = None
    transformation_meaning: Optional[str] = None
    full_scope_palaces_supported: Optional[bool] = None
    scope_palace_map_supported: Optional[bool] = None
    limitations: Optional[List[str]] = None


class ZiweiChildhoodLimit(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    given_age_ordinal: Optional[int] = None
    source_palace_label: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_palace_ganzhi: Optional[str] = None
    natal_stars_detail: Optional[List[ZiweiStar]] = None
    source: Optional[str] = None
    printed_volume: Optional[str] = None
    frame: Optional[int] = None
    source_section: Optional[str] = None
    source_reading: Optional[str] = None
    source_reading_caveat: Optional[str] = None
    age_boundary_rule_verified: Optional[Literal[False]] = None
    pre_decade_substitution_verified: Optional[Literal[False]] = None
    childhood_sihua_supported: Optional[Literal[False]] = None
    natal_stars_are_not_childhood_transformations: Optional[Literal[True]] = None
    unresolved_reason: Optional[str] = None


class ZiweiDecadeHalf(PartialOutput):
    status: Optional[str] = None
    nominal_age: Optional[int] = None
    natal_branch: Optional[str] = None
    selected_decade_age_range: Optional[List[int]] = None
    year_ordinal_in_decade: Optional[int] = None
    half: Optional[Literal["upper_five_years", "lower_five_years"]] = None
    selected_half_age_range: Optional[List[int]] = None
    textual_group: Optional[Literal["north", "south"]] = None
    conditional_on_existing_age_convention: Optional[Literal[True]] = None
    calendar_boundaries_classically_verified: Optional[Literal[False]] = None
    unresolved_reason: Optional[str] = None


class ZiweiSmallLimitHalf(PartialOutput):
    status: Optional[str] = None
    half: None = None
    half_start: None = None
    half_end: None = None
    north_textual_half: Optional[str] = None
    south_textual_half: Optional[str] = None
    unresolved_reason: Optional[str] = None


class ZiweiLimitGroupOccurrence(PartialOutput):
    star: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_mutagen: Optional[str] = None
    calculation_path: Optional[str] = None


class ZiweiLimitStarGroup(PartialOutput):
    star: Optional[str] = None
    definition_id: Optional[str] = None
    source_frame: Optional[int] = None
    source_quote: Optional[str] = None
    textual_group: Optional[Literal["north", "south", "both"]] = None
    textual_daxian_half: Optional[Literal["upper_five_years", "lower_five_years"]] = (
        None
    )
    unresolved_reason: Optional[str] = None
    actual_occurrences: Optional[List[ZiweiLimitGroupOccurrence]] = None
    selected_as_relevant_star: None = None


class ZiweiLimitSubperiods(PartialOutput):
    method_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    frame: Optional[int] = None
    source_section: Optional[str] = None
    source_reading: Optional[Dict[str, str]] = None
    transcription_method: Optional[str] = None
    independent_human_reviewers: Optional[int] = None
    independent_model_reviewers: Optional[int] = None
    daxian: Optional[ZiweiDecadeHalf] = None
    xiaoxian: Optional[ZiweiSmallLimitHalf] = None
    group_definition_source: Optional[str] = None
    group_definition_section: Optional[str] = None
    natal_star_groups: Optional[List[ZiweiLimitStarGroup]] = None
    unclassified_natal_stars: Optional[List[str]] = None
    relevant_star_geometry_defined: Optional[Literal[False]] = None
    full_traditional_judgment: None = None
    source_outcome_claim_adopted: Optional[Literal[False]] = None
    actual_assignments_modified: Optional[Literal[False]] = None
    whole_section_certified: Optional[Literal[False]] = None
    whole_book_acceptance_passed: Optional[Literal[False]] = None
    limitations: Optional[List[str]] = None


class ZiweiAgeSourceCitation(PartialOutput):
    source_url: Optional[str] = None
    frame: Optional[int] = None
    section: Optional[str] = None
    quote: Optional[str] = None
    establishes: Optional[str] = None
    does_not_establish_in_this_passage: Optional[str] = None


class ZiweiAgeSourceScope(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    title: Optional[str] = None
    review_scope: Optional[str] = None
    manual_readers: Optional[int] = None
    independent_reviewers: Optional[int] = None
    citations: Optional[List[ZiweiAgeSourceCitation]] = None
    software_age_convention: Optional[str] = None
    source_does_not_certify_software_age_convention: Optional[Literal[True]] = None
    age_boundary_classically_verified: Optional[Literal[False]] = None
    whole_book_acceptance_passed: Optional[Literal[False]] = None
    correction_history: Optional[List[Dict[str, str]]] = None


class ZiweiNominalAgeCalendar(PartialOutput):
    method_id: Optional[str] = None
    basis: Optional[Literal["birth_civil_timezone"]] = None
    rule: Optional[str] = None
    timezone: Optional[str] = None
    birth_datetime: Optional[str] = None
    target_datetime: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    target_instant_utc: Optional[str] = None
    birth_lunar_date: Optional[LunarDate] = None
    target_lunar_date: Optional[LunarDate] = None
    birth_lunar_year: Optional[int] = None
    target_lunar_year: Optional[int] = None
    birth_placement_lunar_year: Optional[int] = None
    target_civil_lunar_year: Optional[int] = None
    nominal_age: Optional[int] = None
    day_boundary: Optional[str] = None
    physical_order_checked: Optional[bool] = None
    date_lookup_convention: Optional[str] = None
    age_boundary_classically_verified: Optional[Literal[False]] = None
    boundary_source_evidence: Optional[ZiweiAgeSourceScope] = None


class ZiweiHoroscopeNatalPrerequisites(PartialOutput):
    schema_version: Optional[str] = None
    origin: Optional[Literal["same_calculation_internal_natal_chart"]] = None
    ruleset: Optional[ZiweiRuleset] = None
    lunar_date: Optional[LunarDate] = None
    year_stem: Optional[str] = None
    hour_branch: Optional[str] = None
    ming_gong: Optional[ZiweiPosition] = None
    shen_gong: Optional[ZiweiPosition] = None
    wuxing_ju: Optional[WuxingJu] = None
    rule_trace: Optional[List[ZiweiRuleTrace]] = None
    separate_birth_run: Optional[Literal[False]] = None
    classical_birth_year_boundary_verified: Optional[Literal[False]] = None


class ZiweiHoroscope(PartialOutput):
    natal_prerequisites: Optional[ZiweiHoroscopeNatalPrerequisites] = None
    sihua_source_comparison: Optional[ZiweiSihuaSourceComparison] = None
    engine: Optional[str] = None
    calendar_basis: Optional[ZiweiHoroscopeCalendarBasis] = None
    calendar_rules: Optional[ZiweiCalendarRules] = None
    ruleset: Optional[ZiweiRuleset] = None
    source_comparison: Optional[Dict[str, Any]] = None
    nominal_age: Optional[int] = None
    nominal_age_calendar: Optional[ZiweiNominalAgeCalendar] = None
    childhood_limit: Optional[ZiweiChildhoodLimit] = None
    ming_limit_subperiods: Optional[ZiweiLimitSubperiods] = None
    interpretation_scope: Optional[ZiweiInterpretationScope] = None
    scopes: Optional[List[ZiweiScope]] = None


class ZiweiFocusedRules(PartialOutput):
    sihua: Optional[Dict[str, str]] = None
    year_stem: Optional[str] = None


class ZiweiRuleCatalogue(PartialOutput):
    ming_gong_method: Optional[str] = None
    shen_gong_method: Optional[str] = None
    palace_sequence: Optional[List[str]] = None
    sihua_by_year_stem: Optional[Dict[str, Dict[str, str]]] = None
    sihua_source_comparison: Optional[ZiweiSihuaSourceComparison] = None
    ruleset: Optional[ZiweiRuleset] = None
    cycle_methods: Optional[Dict[str, str]] = None


class LiurenLesson(PartialOutput):
    anchor_branch: Optional[str] = None
    index: Optional[int] = None
    lower_branch: Optional[str] = None
    upper_branch: Optional[str] = None
    upper_day_stem_life_stage: Optional[LiurenLifeStage] = None
    relation: Optional[str] = None
    relations: Optional[Dict[str, str]] = Field(
        default=None,
        description="兼容优先标签仅列同支、合、冲、害；平不表示无刑破。并存支位条件见liureng.branch_relations。",
    )
    style_basis: Optional[str] = None
    style_hint: Optional[str] = None
    text: Optional[str] = None
    upper_lower_relation: Optional[str] = None
    use_candidate: Optional[bool] = None


class LiurenTransmission(PartialOutput):
    branch: Optional[str] = None
    ganzhi: Optional[str] = None
    god: Optional[str] = None
    relation: Optional[str] = None
    dun_stem: Optional[str] = None
    xun_kong: Optional[bool] = None
    earth_branch: Optional[str] = None
    seated_kong: Optional[bool] = None
    day_stem_life_stage: Optional[LiurenLifeStage] = None
    seated_day_stem_life_stage: Optional[LiurenLifeStage] = None


class LiurenTransmissions(PartialOutput):
    initial: Optional[LiurenTransmission] = None
    middle: Optional[LiurenTransmission] = None
    final: Optional[LiurenTransmission] = None
    method: Optional[str] = None


class LiurenBoardRow(PartialOutput):
    earth_branch: Optional[str] = None
    sky_branch: Optional[str] = None
    god: Optional[str] = None


class LiurenPattern(PartialOutput):
    basis: Optional[str] = None
    name: Optional[str] = None


class RenDiurnalEvidence(PartialOutput):
    method_id: Optional[str] = None
    hour_branch: Optional[str] = None
    explicit_choice: Optional[bool] = None
    is_diurnal: Optional[bool] = None
    selection_source: Optional[str] = None
    fixed_day_branches: Optional[List[str]] = None
    stellar_visibility_observed: None = None
    astronomical_boundary_computed: Optional[bool] = None
    solar_altitude_threshold_degrees: None = None
    basis: Optional[str] = None
    scope: Optional[str] = None


class LiurenMeta(PartialOutput):
    guiren_profile: Optional[str] = None
    current_term: Optional[str] = None
    month_general_basis: Optional[str] = None
    guiren_earth_branch: Optional[str] = None
    is_diurnal: Optional[bool] = None
    lunar_display: Optional[str] = None
    questioner_gender: Optional[str] = None
    selected_lesson_index: Optional[int] = None
    selected_lesson_relation: Optional[str] = None
    diurnal_basis: Optional[str] = None
    diurnal_evidence: Optional[RenDiurnalEvidence] = None


class RenRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_urls: Optional[List[str]] = None
    source_kind: Optional[str] = None
    classical_conformance: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    real_world_efficacy: Optional[str] = None
    conventions: Optional[Dict[str, str]] = None
    unresolved: Optional[List[str]] = None


class RenRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source_section: Optional[str] = None
    source_url: Optional[str] = None
    result: Optional[Object] = None


class LiurenSourceNote(PartialOutput):
    annotation: Optional[str] = None
    original_pdf_page: Optional[int] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    kind: Optional[str] = None
    explanation: Optional[str] = None
    scope: Optional[str] = None


class LiurenClassification(PartialOutput):
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    labels: Optional[List[str]] = None
    detail: Optional[str] = None
    transmission_method: Optional[str] = None
    lower_thief_lessons: Optional[List[int]] = None
    upper_killer_lessons: Optional[List[int]] = None
    initial_self_punishment: Optional[bool] = None
    closing_punishment: Optional[bool] = None
    selected_lesson: Optional[int] = None
    basis: Optional[str] = None
    scope: Optional[str] = None
    source_note: Optional[LiurenSourceNote] = None


class RenTermDependency(PartialOutput):
    published_date_reference: Optional[RenPublishedDateReference] = None
    role: Optional[str] = None
    name: Optional[str] = None
    civil_moment: Optional[str] = None
    provider: Optional[str] = None
    ephemeris_model: Optional[str] = None
    ephemeris_retflags: Optional[List[int]] = None
    ephemeris_library_version: Optional[str] = None
    solar_model_details: Optional[Dict[str, Any]] = None
    solver_time_scale: Optional[str] = None
    civil_time_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    leap_table_expires_at: Optional[str] = None
    leap_table_source: Optional[str] = None

    @model_validator(mode="after")
    def published_date_matches_dependency(self) -> "RenTermDependency":
        from .metaphysics.ren_term_longitude import validate_term_longitude
        from .metaphysics.ren_term_point import validate_term_point

        align_published_date(self)
        validate_term_point(
            self.solar_model_details,
            (
                _datetime.fromisoformat(self.civil_moment)
                if self.civil_moment is not None
                else None
            ),
            complete=False,
        )
        validate_term_longitude(
            name=self.name,
            provider=self.provider,
            model=self.ephemeris_model,
            flags=self.ephemeris_retflags,
            library_version=self.ephemeris_library_version,
            details=self.solar_model_details,
            complete=False,
        )
        return self


class RenSolarLongitudeDefinition(PartialOutput):
    origin: Optional[Literal["geocentric"]] = None
    position: Optional[Literal["apparent"]] = None
    plane: Optional[Literal["ecliptic_of_date"]] = None
    equinox: Optional[Literal["true_of_date"]] = None
    astronomical_model: Optional[
        Literal[
            "Swiss_Ephemeris_default_IERS2010_Astronomical_Almanac",
            "fatebridge_analytic_solar_v1",
            "per_dependency_named_models",
        ]
    ] = None
    horizons_frame_equivalence_certified: Optional[Literal[False]] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    scope: Optional[str] = None


class RenCalendarPolicy(PartialOutput):
    mode: Optional[str] = None
    civil_datetime: Optional[str] = None
    civil_instant_utc: Optional[str] = None
    civil_clock_resolution: Optional[RenCivilClockResolution] = None
    day_hour_clock: Optional[str] = None
    corrected_clock: Optional[str] = None
    day_boundary: Optional[str] = None
    effective_day_date: Optional[str] = None
    effective_day_ganzhi: Optional[str] = None
    year_month_clock: Optional[str] = None
    month_general_clock: Optional[str] = None
    month_general_override: Optional[str] = None
    month_boundary: Optional[str] = None
    month_general_boundary: Optional[str] = None
    solar_term_dependencies: Optional[List[RenTermDependency]] = None
    solar_longitude_definition: Optional[RenSolarLongitudeDefinition] = None
    precision_status: Optional[str] = None
    scope: Optional[str] = None


class Liuren(PartialOutput):
    god_yin: Optional[LiurenGodYin] = None
    seasonal_evidence: Optional[LiurenSeasonalEvidence] = None
    transmission_progression: Optional[LiurenProgression] = None
    branch_relations: Optional[LiurenBranchRelations] = None
    day_placement_patterns: Optional[LiurenDayPlacements] = None
    cross_harmony: Optional[LiurenCrossHarmony] = None
    emptiness_evidence: Optional[LiurenEmptinessEvidence] = None
    transmission_relations: Optional[LiurenTransmissionRelations] = None

    @model_validator(mode="after")
    def yin_matches_its_board(self) -> "Liuren":
        align_god_yin(self)
        return self

    engine: Optional[str] = None
    board_order: Optional[str] = None
    board_style: Optional[str] = None
    board_style_detail: Optional[str] = None
    guiren_system: Optional[str] = None
    kongwang: Optional[str] = None
    meta: Optional[LiurenMeta] = None
    month_general: Optional[BranchName] = None
    overview: Optional[List[str]] = None
    patterns: Optional[List[LiurenPattern]] = None
    four_lessons: Optional[List[LiurenLesson]] = None
    three_transmissions: Optional[LiurenTransmissions] = None
    twelve_board: Optional[List[LiurenBoardRow]] = None
    month_building_element: Optional[str] = None
    life_stages: Optional[LiurenLifeStages] = None
    auxiliary_stars: Optional[LiurenAuxiliaryStars] = None
    xun_head: Optional[str] = None
    guiren_order: Optional[str] = None
    ruleset: Optional[RenRuleset] = None
    rule_trace: Optional[List[RenRuleTrace]] = None
    classification: Optional[LiurenClassification] = None
    calendar_policy: Optional[RenCalendarPolicy] = None

    @model_validator(mode="after")
    def selection_follows_present_board(self) -> "Liuren":
        from .output_liuren_selection import validate_selection

        validate_selection(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def branch_relations_match_present_board(self) -> "Liuren":
        align_seasonal(self)
        align_branch_relations(self)
        align_day_placements(self)
        align_cross_harmony(self)
        align_progression(self)
        return self

    @model_validator(mode="after")
    def empty_evidence_matches_present_board(self) -> "Liuren":
        evidence = self.emptiness_evidence
        if evidence is None or evidence.rows is None:
            return self
        by_earth = {r.earth_branch: r for r in evidence.rows}
        by_sky = {r.sky_branch: r for r in evidence.rows}
        for row in self.twelve_board or []:
            if row.earth_branch is not None and row.sky_branch is not None:
                if (
                    row.earth_branch not in by_earth
                    or by_earth[row.earth_branch].sky_branch != row.sky_branch
                ):
                    raise ValueError("六壬空亡依据与同时返回的天地盘不一致")
        if self.three_transmissions is not None:
            for position in ("initial", "middle", "final"):
                item = getattr(self.three_transmissions, position)
                if item is None or item.branch is None:
                    continue
                if item.branch not in by_sky:
                    raise ValueError("六壬空亡依据中的三传支位无效")
                empty_row = by_sky[item.branch]
                for name, expected in (
                    ("earth_branch", empty_row.earth_branch),
                    ("xun_kong", empty_row.sky_xun_kong),
                    ("seated_kong", empty_row.earth_xun_kong),
                ):
                    actual = getattr(item, name)
                    if actual is not None and actual != expected:
                        raise ValueError("六壬空亡依据与同时返回的三传不一致")
        return self

    @model_validator(mode="after")
    def transmission_relationships_match_same_board(self) -> "Liuren":
        if self.transmission_relations and self.seasonal_evidence:
            from .metaphysics.liureng_trine_seasonal import nominal_seasonal_evidence

            month = self.seasonal_evidence.month_branch
            for trine in self.transmission_relations.trines or []:
                if month and trine.nominal_element and trine.nominal_seasonal_evidence:
                    compare_present_relations(
                        trine.nominal_seasonal_evidence.model_dump(exclude_unset=True),
                        nominal_seasonal_evidence(month, trine.nominal_element),
                    )
        if (
            self.transmission_relations is None
            or self.four_lessons is None
            or self.three_transmissions is None
        ):
            return self
        day = self.transmission_relations.day_ganzhi
        if day is None or any(
            lesson.index is None or lesson.upper_branch is None
            for lesson in self.four_lessons
        ):
            return self
        transmissions = self.three_transmissions.model_dump(exclude_unset=True)
        if any(
            not isinstance(transmissions.get(p), dict)
            or any(k not in transmissions[p] for k in ("branch", "god", "earth_branch"))
            for p in ("initial", "middle", "final")
        ):
            return self
        from .metaphysics.liureng_transmission_relations import transmission_relations

        expected = transmission_relations(
            day_ganzhi=day,
            lessons=[
                lesson.model_dump(exclude_unset=True) for lesson in self.four_lessons
            ],
            transmissions=transmissions,
            month_branch=(
                self.seasonal_evidence.month_branch if self.seasonal_evidence else None
            ),
        )
        compare_present_relations(
            self.transmission_relations.model_dump(exclude_unset=True), expected
        )
        return self


class Runyear(PartialOutput):
    age: Optional[int] = None
    engine: Optional[str] = None
    ganzhi: Optional[str] = None
    gender: Optional[str] = None
    age_basis: Optional[str] = None
    rule_id: Optional[str] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    birth_lunar_year: Optional[int] = None
    birth_civil_clock: Optional[RenCivilClockResolution] = None
    year_fate: Optional[LiurenYearFate] = None
    age_calendar: Optional[RenRunyearAgeCalendar] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class QimenHexagram(PartialOutput):
    binary_code: Optional[str] = None
    name: Optional[str] = None


class QimenPalace(PartialOutput):
    god_sequence_index: Optional[int] = None
    index: FullFact[Optional[int]] = None
    direction: Optional[str] = None
    element: Optional[str] = None
    heaven_origin_trigram: Optional[str] = None
    heaven_stems: Optional[List[str]] = None
    earth_stems: Optional[List[str]] = None
    hosted_stars: Optional[List[str]] = None
    evidence: Optional[QimenPalaceEvidence] = None
    name: Optional[str] = None
    content_palace: Optional[str] = None
    content_trigram: Optional[str] = None
    trigram: Optional[str] = None
    door: Optional[str] = None
    door_hexagram: Optional[QimenHexagram] = None
    earth_stem: Optional[str] = None
    heaven_stem: Optional[str] = None
    god: Optional[str] = None
    star: Optional[str] = None


class QimenLeader(PartialOutput):
    code: Optional[str] = None
    content_palace: Optional[str] = None
    content_trigram: Optional[str] = None
    palace: Optional[str] = None
    trigram: Optional[str] = None
    star: Optional[str] = None
    door: Optional[str] = None


class QimenOptions(PartialOutput):
    ju_method: Optional[str] = None
    god_profile: Optional[str] = None
    season_profile: Optional[str] = None
    layout: Optional[str] = None
    palaceShift: Optional[int] = None
    reverse: Optional[bool] = None


class Qimen(PartialOutput):
    stem_context: Optional[Object] = None
    god_profile: Optional[str] = None
    season_profile: Optional[str] = None
    rule_profiles: Optional[Object] = None
    ju_method: Optional[str] = None
    ju_decision: Optional[Object] = None
    ju_term: Optional[str] = None
    day_ganzhi: Optional[str] = None
    time_ganzhi: Optional[str] = None
    day_xun_head: Optional[str] = None
    day_kongwang: Optional[str] = None
    rulesets: FullFact[Optional[List[QimenRuleset]]] = None
    rule_trace: FullFact[Optional[List[QimenRuleTrace]]] = None
    calendar_policy: FullFact[Optional[QimenCalendarPolicy]] = None
    structure: Optional[QimenStructure] = None
    patterns: Optional[List[QimenPattern]] = None
    assessment: Optional[QimenAssessment] = None
    source_disagreements: Optional[List[Dict[str, JsonValue]]] = None
    engine: Optional[str] = None
    dun_type: FullFact[Optional[str]] = None
    fu_tou: Optional[str] = None
    fushi_hexagram: Optional[QimenHexagram] = None
    ju_number: FullFact[Optional[int]] = None
    ju_text: Optional[str] = None
    kongwang: Optional[str] = None
    layout: Optional[str] = None
    options_applied: Optional[QimenOptions] = None
    palaces: FullFact[Optional[List[QimenPalace]]] = Field(
        default=None,
        min_length=9,
        max_length=9,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "index"},
    )
    reference: Optional[str] = None
    xun_head: Optional[str] = None
    yuan: Optional[str] = None
    yuan_order: Optional[str] = None
    zhifu: Optional[QimenLeader] = None
    zhishi: Optional[QimenLeader] = None


class TaiyiCounterGroup(PartialOutput):
    number: Optional[int] = None
    position: Optional[int] = None
    size: Optional[int] = None


class TaiyiCounterCycles(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    paths_relative_to: Optional[str] = None
    counter_path: Optional[str] = None
    actual_ju_path: Optional[str] = None
    counter: Optional[int] = None
    calculation_mode: Optional[str] = None
    counter_unit: Optional[str] = None
    completed_cycles_before_current360: Optional[int] = None
    position360: Optional[int] = None
    ji60: Optional[TaiyiCounterGroup] = None
    yuan72: Optional[TaiyiCounterGroup] = None
    actual_kook_number: Optional[int] = None
    calendar_ganzhi_alignment: Optional[str] = None
    scope: Optional[str] = None


class TaiyiCore(PartialOutput):
    yin_dun: Optional[bool] = None
    ruler_branch: Optional[str] = None
    ruler_label: Optional[str] = None
    accumulation: Optional[int] = None
    taiyi_number: Optional[int] = None
    chenji: Optional[str] = None
    dingmu: Optional[str] = None
    diyi: Optional[str] = None
    guest_count: FullFact[Optional[int]] = None
    guest_count_des: Optional[List[str]] = None
    guest_general: Optional[int] = None
    guest_vice_general: Optional[int] = None
    heshen: Optional[str] = None
    jishen: Optional[str] = None
    junji: Optional[str] = None
    kook_number: Optional[int] = None
    kook_year: Optional[str] = None
    main_calculation: Optional[str] = None
    main_count: FullFact[Optional[int]] = None
    main_count_des: Optional[List[str]] = None
    main_general: Optional[int] = None
    main_vice_general: Optional[int] = None
    minji: Optional[str] = None
    set_count: Optional[int] = None
    set_general: Optional[int] = None
    set_vice_general: Optional[int] = None
    shiji: Optional[str] = None
    sishen: Optional[str] = None
    suijun: Optional[str] = None
    taiyi_position: Optional[str] = None
    tianyi: Optional[str] = None
    wenchang_position: Optional[str] = None
    wufu: Optional[int] = None
    zhifu: Optional[str] = None


class TaiyiPalace(PartialOutput):
    markers: Optional[List[str]] = None
    palace: Optional[str] = None


class TaiyiRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source_title: Optional[str] = None
    source_kind: Optional[str] = None
    sources: Optional[Dict[str, str]] = None
    time_granularity: Optional[str] = None
    classical_conformance: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    real_world_efficacy: Optional[str] = None
    unresolved: Optional[List[str]] = None


class TaiyiCalendarRules(PartialOutput):
    anchor_ephemeris_model: Optional[str] = None
    winter_anchor_ephemeris_model: Optional[str] = None
    civil_clock_resolution: Optional[TaiyiCivilClockResolution] = None
    year_profile: Optional[str] = None
    historical_calendar: Optional[TaiyiHistoricalYearCalendar] = None
    civil_lunar_calendar: Optional[TaiyiCivilLunarCalendar] = None
    month_profile: Optional[str] = None
    month_origin: Optional[TaiyiMonthOrigin] = None
    input_calendar: Optional[str] = None
    historical_date_reference: Optional[TaiyiHistoricalReference] = None
    day_profile: Optional[str] = None
    day_origin: Optional[TaiyiDayOrigin] = None
    palace_day_number: Optional[int] = None
    hour_profile: Optional[str] = None
    hour_origin: Optional[TaiyiHourOrigin] = None
    convention: Optional[str] = None
    calculation_mode: Optional[str] = None
    anchor_name: Optional[str] = None
    anchor_utc: Optional[str] = None
    anchor_provider: Optional[str] = None
    counter: Optional[int] = None
    boundary_instant_basis: Optional[str] = None
    ruler_branch_basis: Optional[str] = None
    heshen_branch_basis: Optional[str] = None
    clock_basis: Optional[str] = None
    cycle_year: Optional[int] = None
    month_offset: Optional[int] = None
    leap_month_policy: Optional[str] = None
    anchor_clock: Optional[str] = None
    target_clock: Optional[str] = None
    double_hour_start: Optional[str] = None
    initial_interval: Optional[str] = None
    modern_conventions: Optional[str] = None
    dst_policy: Optional[str] = None
    counter_rule_source: Optional[str] = None
    counter_formula: Optional[str] = None
    anchor_precision: Optional[str] = None
    seconds_from_anchor: Optional[float] = None
    target_slot: Optional[int] = None
    anchor_slot: Optional[int] = None
    year: Optional[int] = None
    year_boundary: Optional[str] = None
    year_boundary_status: Optional[str] = None
    year_ganzhi: Optional[str] = None
    civil_datetime: Optional[str] = None
    timezone: Optional[str] = None
    solar_correction_affects_year: Optional[bool] = None
    pillars_role: Optional[str] = None


class TaiyiCountStep(PartialOutput):
    palace: Optional[str] = None
    value: Optional[int] = None
    kind: Optional[str] = None


class TaiyiCountTrace(PartialOutput):
    count: Optional[int] = None
    path: Optional[List[TaiyiCountStep]] = None
    terminal_palace: Optional[str] = None
    terminal_excluded: Optional[bool] = None
    counting_rule: Optional[str] = None
    source: Optional[str] = None


class TaiyiRuleTrace(PartialOutput):
    main: Optional[TaiyiCountTrace] = None
    guest: Optional[TaiyiCountTrace] = None


class TaiyiEvidenceFact(PartialOutput):
    field: Optional[str] = None
    value: Optional[Union[str, int]] = None


class TaiyiPattern(PartialOutput):
    name: Optional[str] = None
    subject: Optional[str] = None
    variant: Optional[str] = None
    basis: Optional[List[TaiyiEvidenceFact]] = None
    traditional_meaning: Optional[str] = None
    source: Optional[str] = None
    supplementary_sources: Optional[List[str]] = None
    relation_profile: Optional[str] = None
    scope: Optional[str] = None


class TaiyiWinterOriginSelection(PartialOutput):
    policy_id: Optional[str] = None
    selection_switch_basis: Optional[str] = None
    selected_winter_utc: Optional[str] = None
    count_origin_date: Optional[str] = None
    count_origin_clock: Optional[str] = None
    clock_basis: Optional[str] = None
    source: Optional[str] = None
    classical_source_scope: Optional[str] = None
    classical_activation_adjudicated: Optional[bool] = None
    scope: Optional[str] = None


class Taiyi(PartialOutput):
    winter_origin_selection: Optional[TaiyiWinterOriginSelection] = None
    solar_anchors: Optional[Dict[str, SolarTerm]] = None
    solar_anchor_scope: Optional[str] = None
    counter_cycles: Optional[TaiyiCounterCycles] = None
    shiji_derivation: Optional[TaiyiShijiDerivation] = None
    elemental_guan_assessment: Optional[TaiyiElementalAssessment] = None
    victory_matrix_assessment: Optional[TaiyiVictoryMatrixAssessment] = None
    count_source_assessment: Optional[TaiyiSourceAlignment] = None
    count_assessment: Optional[TaiyiCountAssessment] = None
    opposition_assessment: Optional[TaiyiOppositionAssessment] = None
    enclosure_assessment: Optional[TaiyiEnclosureAssessment] = None
    ten_jing: Optional[TaiyiTenJing] = None
    day_source_comparisons: Optional[List[TaiyiSourceComparison]] = None
    gates: Optional[TaiyiGates] = None
    determinate_calculation: Optional[TaiyiDeterminate] = None
    condition_assessment: Optional[TaiyiConditionAssessment] = None
    long_cycles: Optional[TaiyiLongCycles] = None
    long_cycle_summary: Optional[TaiyiLongSummary] = None
    extra_palace_marks: Optional[List[TaiyiPalace]] = None
    engine: FullFact[Optional[str]] = None
    accumulation_label: Optional[str] = None
    core_board: FullFact[Optional[TaiyiCore]] = None
    life_method: FullFact[Optional[str]] = None
    palace_marks: FullFact[Optional[List[TaiyiPalace]]] = Field(
        default=None, min_length=8
    )
    center_marks: Optional[TaiyiPalace] = None
    ruleset: FullFact[Optional[TaiyiRuleset]] = None
    calendar_rules: Optional[TaiyiCalendarRules] = None
    calendar_summary: Optional[TaiyiCalendarRules] = None
    pattern_summary: Optional[Object] = None
    rule_trace: Optional[TaiyiRuleTrace] = None
    patterns: Optional[List[TaiyiPattern]] = None
    interpretation_scope: Optional[Object] = None
    rotation: Optional[str] = None
    style_label: Optional[str] = None
    taiyi_palace: Optional[str] = None
    wenchang_palace: Optional[str] = None
    big_pattern: Optional[str] = None
    small_pattern: Optional[str] = None


class JinkouGuishen(BranchName):
    start_branch: Optional[str] = None
    earth_branch: Optional[str] = None
    intrinsic_ganzhi: Optional[str] = None
    direction: Optional[str] = None


class JinkouOverview(PartialOutput):
    board_style: Optional[str] = None
    board_style_detail: Optional[str] = None
    di_fen: Optional[str] = None
    gender: Optional[str] = None
    guishen: Optional[JinkouGuishen] = None
    kongwang: Optional[str] = None
    month_general: Optional[BranchName] = Field(
        default=None,
        description="依民用瞬间中气确定的月将本位，未移到地分；yuejiang另记落地分后的将神。",
    )
    si_da_kong: Optional[str] = None
    transmission_method: Optional[str] = None
    use_position: Optional[str] = None
    use_position_basis: Optional[str] = None
    yuejiang: Optional[BranchName] = Field(
        default=None,
        description="月将加时后落在地分的将神，对应将神行；与month_general月将本位分开。",
    )
    di_fen_source: Optional[str] = None
    xun_head: Optional[str] = None
    power_basis: Optional[str] = None
    diurnal_basis: Optional[str] = None
    is_diurnal: Optional[bool] = None
    diurnal_evidence: Optional[RenDiurnalEvidence] = None


class JinkouRow(PartialOutput):
    content: Optional[str] = None
    element: Optional[str] = None
    label: Optional[str] = None
    seasonal_power: Optional[str] = Field(
        default=None, description="按月建约定的四季旺衰，与位内旺衰分开。"
    )
    internal_power: Optional[str] = Field(
        default=None,
        description="按四位课内旺神所得旺衰；多个旺神候选未裁定时为 null。",
    )
    shenjiang: Optional[str] = None
    polarity: Optional[str] = None
    dun_stem: Optional[str] = None
    intrinsic_ganzhi: Optional[str] = None
    xun_kong: Optional[bool] = None
    si_da_kong: Optional[bool] = None
    month_break: Optional[bool] = None
    is_use: Optional[bool] = None


class JinkouMotion(PartialOutput):
    name: Optional[str] = None
    source_position: Optional[str] = None
    target_position: Optional[str] = None
    relation: Optional[str] = None
    source_section: Optional[str] = None
    basis: Optional[str] = None
    empty_positions: Optional[List[str]] = None


class JinkouInternalStrength(PartialOutput):
    method: Optional[str] = None
    status: Optional[str] = None
    anchor_element: Optional[str] = None
    candidate_elements: Optional[List[str]] = None
    candidate_positions: Optional[List[str]] = None
    has_control: Optional[bool] = None
    relations: Optional[List[JinkouInternalRelation]] = None
    powers: Optional[Dict[str, Optional[str]]] = None
    basis: Optional[str] = None
    source_evidence: Optional[JinkouStrengthSource] = None
    scope: Optional[str] = None


class JinkouUseEvidence(PartialOutput):
    polarity_position: Optional[str] = None
    subject_position: Optional[str] = None
    controlled_by: Optional[List[str]] = None
    xun_kong: Optional[bool] = None
    si_da_kong: Optional[bool] = None
    month_break: Optional[bool] = None
    seasonal_power: Optional[str] = None
    internal_power: Optional[str] = None
    no_control_principle_applies: Optional[bool] = None
    internal_strength_candidates: Optional[List[str]] = None
    comprehensive_position: None = None
    source_evidence: Optional[JinkouUseSource] = None
    status: Optional[str] = None
    basis: Optional[str] = None
    scope: Optional[str] = None


class JinkouJueCheck(PartialOutput):
    left_position: Optional[str] = None
    right_position: Optional[str] = None
    left_branch: Optional[str] = None
    right_branch: Optional[str] = None
    element: Optional[str] = None
    classification: Optional[str] = None
    matched: Optional[bool] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    original_pdf_page: Optional[int] = None
    basis: Optional[str] = None

    @model_validator(mode="after")
    def named_pair_matches_facts(self) -> "JinkouJueCheck":
        from .output_jinkou_relations import validate_absolute_row

        validate_absolute_row(self.model_dump(exclude_unset=True))
        return self


class JinkouJue(PartialOutput):
    checks: Optional[List[JinkouJueCheck]] = None
    natal: Optional[JinkouNatalAbsolute] = None
    unavailable: Optional[List[JinkouJueCheck]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def complete_selected_pair_catalog(self) -> "JinkouJue":
        from .output_jinkou_relations import validate_queue

        validate_queue(self.model_dump(exclude_unset=True), "si_jue")
        return self

    @model_validator(mode="after")
    def missing_natal_is_not_a_false_or_unavailable_known_branch(self) -> "JinkouJue":
        if self.natal is None or self.unavailable is None:
            return self
        if "right_branch" not in self.natal.model_fields_set:
            return self
        if self.natal.right_branch is not None:
            if self.unavailable:
                raise ValueError("明确本命支的大绝不能仍列为缺失本命支")
        elif len(self.unavailable) != 1 or any(
            r.matched is not None or r.status != "missing_birth_branch"
            for r in self.unavailable
        ):
            raise ValueError("本命支缺失时大绝必须保留未算状态")
        return self


class JinkouBaiCheck(PartialOutput):
    position: Optional[str] = None
    element: Optional[str] = None
    seat_branch: Optional[str] = None
    bai_branch: Optional[str] = None
    matched: Optional[bool] = None
    original_pdf_page: Optional[int] = None
    basis: Optional[str] = None

    @model_validator(mode="after")
    def selected_phase_matches_seat(self) -> "JinkouBaiCheck":
        from .output_jinkou_relations import validate_defeat_row

        validate_defeat_row(self.model_dump(exclude_unset=True))
        return self


class JinkouBai(PartialOutput):
    checks: Optional[List[JinkouBaiCheck]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def complete_selected_defeat_catalog(self) -> "JinkouBai":
        from .output_jinkou_relations import validate_queue

        validate_queue(self.model_dump(exclude_unset=True), "si_bai")
        return self


class JinkouCalendarCheck(PartialOutput):
    rule_id: Optional[str] = None
    name: Optional[str] = None
    position: Optional[str] = None
    branch: Optional[str] = None
    reference_branch: Optional[str] = None
    matched: Optional[bool] = None
    original_pdf_page: Optional[int] = None
    basis: Optional[str] = None

    @model_validator(mode="after")
    def year_day_rule_matches_facts(self) -> "JinkouCalendarCheck":
        from .output_jinkou_relations import validate_calendar_row

        validate_calendar_row(self.model_dump(exclude_unset=True))
        return self


class JinkouCalendarRelations(PartialOutput):
    year_branch: Optional[str] = None
    day_branch: Optional[str] = None
    checks: Optional[List[JinkouCalendarCheck]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def year_day_references_are_coherent(self) -> "JinkouCalendarRelations":
        from .output_jinkou_relations import validate_relations

        validate_relations({"calendar": self.model_dump(exclude_unset=True)})
        return self


class JinkouRelationVariant(PartialOutput):
    branches: Optional[List[str]] = None
    scan_element: Optional[str] = None
    transcription_element: Optional[str] = None
    original_pdf_page: Optional[int] = None


class JinkouRelations(PartialOutput):
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    transcription_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_section: Optional[str] = None
    si_jue: Optional[JinkouJue] = None
    si_bai: Optional[JinkouBai] = None
    calendar: Optional[JinkouCalendarRelations] = None
    transcription_variants: Optional[List[JinkouRelationVariant]] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_unearned_full_conformance(cls, value: Any) -> Any:
        if value is not False:
            raise ValueError("所选京本结构关系不能宣称完整原典认证")
        return value

    @model_validator(mode="after")
    def source_and_selected_facts_agree(self) -> "JinkouRelations":
        from .output_jinkou_relations import validate_relations

        validate_relations(self.model_dump(exclude_unset=True))
        return self


class LabelValue(PartialOutput):
    label: Optional[str] = None
    value: Optional[str] = None


class JinkouTrineMember(PartialOutput):
    position: Optional[str] = None
    branch: Optional[str] = None
    day_clash: Optional[bool] = None
    month_break: Optional[bool] = None
    xun_kong: Optional[bool] = None
    si_da_kong: Optional[bool] = None


class JinkouTrineStem(PartialOutput):
    position: Optional[str] = None
    stem: Optional[str] = None
    element: Optional[str] = None
    trine_element: Optional[str] = None
    explicit_fire_clause: Optional[bool] = None


class JinkouTrine(PartialOutput):
    name: Optional[str] = None
    partial_name: Optional[str] = None
    element: Optional[str] = None
    branches: Optional[List[str]] = None
    present_branches: Optional[List[str]] = None
    missing_branches: Optional[List[str]] = None
    structural_status: Optional[str] = None
    human_stem_relation: Optional[str] = None
    member_conditions: Optional[List[JinkouTrineMember]] = None
    controlling_dun_stems: Optional[List[JinkouTrineStem]] = None
    source_listed_disruptors: Optional[List[str]] = None
    disruptor_application: Optional[str] = None
    du_he: None = None
    transformation_confirmed: None = None
    waiting_branch: Optional[str] = None
    calendar_candidates: None = None
    original_pdf_pages: Optional[List[int]] = None
    basis: Optional[str] = None


class JinkouTrineVariant(PartialOutput):
    original_pdf_page: Optional[int] = None
    scan_reading: Optional[str] = None
    transcription_reading: Optional[str] = None


class JinkouCombinations(PartialOutput):
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_section: Optional[str] = None
    day_branch: Optional[str] = None
    month_branch: Optional[str] = None
    trines: Optional[List[JinkouTrine]] = None
    textual_variants: Optional[List[JinkouTrineVariant]] = None
    scope: Optional[str] = None


class JinkouCourse(PartialOutput):
    engine: Optional[str] = None
    overview: Optional[JinkouOverview] = None
    rows: Optional[List[JinkouRow]] = None
    shensha: Optional[List[LabelValue]] = None
    motions: Optional[List[JinkouMotion]] = None
    internal_strength: Optional[JinkouInternalStrength] = None
    qi_evidence: Optional[JinkouQiEvidence] = None
    position_interactions: Optional[JinkouPositionInteractions] = None
    stem_relations: Optional[JinkouStemRelations] = None
    definition_evidence: Optional[JinkouDefinitionEvidence] = None
    combinations: Optional[JinkouCombinations] = None
    patterns: Optional[JinkouPatterns] = None
    use_evidence: Optional[JinkouUseEvidence] = None
    relations: Optional[JinkouRelations] = None
    branch_stars: Optional[JinkouBranchStars] = None
    branch_breaks: Optional[JinkouBranchBreaks] = None
    calendar_policy: Optional[RenCalendarPolicy] = None
    ruleset: Optional[RenRuleset] = None
    rule_trace: Optional[List[RenRuleTrace]] = None

    @model_validator(mode="after")
    def breaks_follow_this_course(self) -> "JinkouCourse":
        align_branch_breaks(self)
        return self

    @model_validator(mode="after")
    def relations_follow_this_course(self) -> "JinkouCourse":
        from .output_jinkou_relations import validate_relation_anchors

        validate_relation_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def patterns_follow_this_course(self) -> "JinkouCourse":
        from .output_jinkou_patterns import validate_pattern_anchors

        validate_pattern_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def stars_follow_this_board(self) -> "JinkouCourse":
        from .output_jinkou_branch_stars import align_branch_stars

        align_branch_stars(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def strength_and_use_follow_this_board(self) -> "JinkouCourse":
        from .output_jinkou_strength import validate_strength_evidence

        validate_strength_evidence(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def natal_relation_uses_this_general(self) -> "JinkouCourse":
        primary = (
            self.relations.si_jue.natal
            if self.relations is not None and self.relations.si_jue is not None
            else None
        )
        nodes = [primary] if primary is not None else []
        for trace in self.rule_trace or []:
            if trace.rule_id != "jinkou.jingben_relations" or trace.result is None:
                continue
            block = trace.result.get("si_jue")
            if not isinstance(block, dict) or "natal" not in block:
                continue
            traced = JinkouJue.model_validate(block).natal
            if traced is None:
                raise ValueError("将命大绝规则轨迹不可伪造为空")
            nodes.append(traced)
            if primary is not None:
                a = primary.model_dump(exclude_unset=True)
                b = traced.model_dump(exclude_unset=True)
                if any(a[k] != b[k] for k in a.keys() & b.keys()):
                    raise ValueError("将命大绝正文与同次规则轨迹不一致")
        row = next((r for r in self.rows or [] if r.label == "将神"), None)
        if row is not None and row.content is not None:
            for natal in nodes:
                if (
                    "left_branch" in natal.model_fields_set
                    and natal.left_branch != row.content
                ):
                    raise ValueError("将命大绝须使用同次四位的将神支")
        return self

    @model_validator(mode="after")
    def definition_facts_agree_with_positions(self) -> "JinkouCourse":
        if (
            self.definition_evidence is None
            or self.rows is None
            or self.overview is None
        ):
            return self
        if self.stem_relations is None or self.stem_relations.day_stem is None:
            return self
        if self.overview.is_diurnal is None:
            return self
        actual = self.definition_evidence
        if actual.hour_branch is None:
            return self
        # Only rebuild when all four raw row anchors are available. Projection
        # validation must not fabricate omitted data.
        rows = [r.model_dump(exclude_unset=True) for r in self.rows]
        needed = ("label", "content", "element")
        if len(rows) != 4 or any(any(k not in r for k in needed) for r in rows):
            return self
        if not rows[1].get("intrinsic_ganzhi"):
            return self
        from .metaphysics.jinkou_definitions import definition_evidence

        expected = definition_evidence(
            day_stem=self.stem_relations.day_stem,
            hour_branch=actual.hour_branch,
            is_diurnal=self.overview.is_diurnal,
            rows=rows,
        )
        compare_present_definition_facts(
            actual.model_dump(exclude_unset=True), expected
        )
        return self

    @model_validator(mode="after")
    def stems_agree_with_four_positions(self) -> "JinkouCourse":
        if self.stem_relations is None or self.rows is None:
            return self
        by_label = {row.label: row for row in self.rows if row.label is not None}
        for label, node in (
            ("贵神", self.stem_relations.god),
            ("将神", self.stem_relations.general),
        ):
            row = by_label.get(label)
            if row is None or node is None:
                continue
            for node_field, row_field in (
                ("branch", "content"),
                ("name", "shenjiang"),
                ("dun_stem", "dun_stem"),
                ("branch_element", "element"),
                ("branch_xun_kong", "xun_kong"),
                ("branch_si_da_kong", "si_da_kong"),
            ):
                a, b = getattr(node, node_field), getattr(row, row_field)
                if a is not None and b is not None and a != b:
                    raise ValueError("遁干证据与原四位的同次事实不一致")
        god = by_label.get("贵神")
        intrinsic = self.stem_relations.guishen_intrinsic_ganzhi
        if (
            god is not None
            and god.intrinsic_ganzhi is not None
            and intrinsic is not None
            and god.intrinsic_ganzhi != intrinsic
        ):
            raise ValueError("贵神固有干支与遁干证据不一致")
        return self


class JinkouYearFate(PartialOutput):
    method_id: Optional[Literal["jingben_birth_xun_year_fate_v1"]] = None
    status: Optional[Literal["missing_inputs", "calculated"]] = None
    birth_year_ganzhi: Optional[str] = None
    birth_xun: Optional[str] = None
    gender: Optional[str] = None
    age_ordinal: Optional[int] = Field(default=None, strict=True, ge=1, le=150)
    age_basis: Optional[Literal["explicit_one_based_ordinal"]] = None
    course_basis: Optional[Literal["annual_branch_as_ground_reading"]] = None
    course_ground_is_observed: Optional[Literal[False]] = None
    start_ganzhi: Optional[str] = None
    direction: Optional[Literal["顺", "逆"]] = None
    ganzhi: Optional[str] = None
    branch: Optional[str] = None
    missing_inputs: Optional[List[str]] = None
    natal_branch: Optional[str] = None
    natal_branch_source: Optional[
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "missing"]
    ] = None
    age_boundary_classically_verified: Optional[Literal[False]] = None
    birth_year_calendar_boundary_verified: Optional[Literal[False]] = None
    comprehensive_year_fate_adjudicated: Optional[Literal[False]] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_section: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    relation_adjudication: Optional[Literal["unresolved_course_stem_reference"]] = None
    relation_note: Optional[str] = None
    scope: Optional[str] = None
    course: Optional[JinkouCourse] = None

    @field_validator(
        "age_boundary_classically_verified",
        "birth_year_calendar_boundary_verified",
        "comprehensive_year_fate_adjudicated",
        "course_ground_is_observed",
        mode="before",
    )
    @classmethod
    def no_unverified_year_fate_certification(cls, value: Any) -> Any:
        if value is not None and value is not False:
            raise ValueError("京本岁首及综合行年未裁定，不能预发认证")
        return value

    @model_validator(mode="after")
    def ordinal_and_course_agree(self) -> "JinkouYearFate":
        from .metaphysics.jinkou_year_fate import (
            confirmed_natal_branch,
            ordinal_year_fate,
        )

        if {"birth_year_ganzhi", "age_ordinal", "gender"} <= self.model_fields_set:
            expected = ordinal_year_fate(
                birth_year_ganzhi=self.birth_year_ganzhi,
                age=self.age_ordinal,
                gender=self.gender,
            )
            actual = self.model_dump(exclude_unset=True)
            if any(actual[k] != expected[k] for k in actual.keys() & expected.keys()):
                raise ValueError("京本行年事实与所给出生年干支、岁序及性别不一致")
        if (
            self.birth_year_ganzhi is not None
            and "natal_branch" in self.model_fields_set
        ):
            if (
                confirmed_natal_branch(
                    self.birth_year_ganzhi, self.natal_branch, self.age_ordinal
                )
                != self.natal_branch
            ):
                raise ValueError("行年层的本命支须来自明确出生年支")
        if "course" in self.model_fields_set and self.status is not None:
            if (self.course is not None) != (self.status == "calculated"):
                raise ValueError("资料缺失不能返回已算行年课，已算行年不能丢失课盘")
        if self.course is not None:
            if (
                self.course.overview is not None
                and self.course.overview.di_fen is not None
                and self.branch is not None
            ):
                if self.course.overview.di_fen != self.branch:
                    raise ValueError("行年课的地分必须是本次行年支")
            if (
                self.course.overview is not None
                and self.course.overview.di_fen_source is not None
                and self.course.overview.di_fen_source != "annual_branch_derived_course"
            ):
                raise ValueError("行年另课地分来自行年支，不是已观测或直接指定方位")
            if (self.course.model_extra or {}).get("year_fate") is not None:
                raise ValueError("行年另课不递归产生另一层行年")
        return self


class JinkouNatalCourse(PartialOutput):
    method_id: Optional[Literal["jingben_natal_branch_course_v1"]] = None
    status: Optional[Literal["missing_inputs", "calculated"]] = None
    birth_year_ganzhi: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_branch_source: Optional[
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "missing"]
    ] = None
    missing_inputs: Optional[List[str]] = None
    course_basis: Optional[Literal["natal_branch_as_ground_reading"]] = None
    course_ground_is_observed: Optional[Literal[False]] = None
    birth_year_calendar_boundary_verified: Optional[Literal[False]] = None
    comprehensive_judgement: None = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_section: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    basis: Optional[str] = None
    scope: Optional[str] = None
    course: Optional[JinkouCourse] = None

    @field_validator(
        "course_ground_is_observed",
        "birth_year_calendar_boundary_verified",
        mode="before",
    )
    @classmethod
    def no_unverified_natal_certification(cls, value: Any) -> Any:
        if value is not None and value is not False:
            raise ValueError("本命课地分属于派生，出生年标签换岁边界尚未认证")
        return value

    @model_validator(mode="after")
    def natal_course_follows_confirmed_input(self) -> "JinkouNatalCourse":
        from .output_jinkou_natal_course import validate_natal_course

        validate_natal_course({"natal_course": self.model_dump(exclude_unset=True)})
        return self


class Jinkou(JinkouCourse):
    year_fate: Optional[JinkouYearFate] = None
    natal_course: Optional[JinkouNatalCourse] = None

    @model_validator(mode="after")
    def natal_course_keeps_analysis_facts(self) -> "Jinkou":
        from .output_jinkou_natal_course import validate_natal_course

        validate_natal_course(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def annual_course_keeps_analysis_facts(self) -> "Jinkou":
        if self.year_fate is not None:
            boards = [self, self.year_fate.course]
            for board in boards:
                natal = (
                    board.relations.si_jue.natal
                    if board is not None
                    and board.relations is not None
                    and board.relations.si_jue is not None
                    else None
                )
                if natal is None:
                    continue
                if (
                    "natal_branch" in self.year_fate.model_fields_set
                    and "right_branch" in natal.model_fields_set
                    and self.year_fate.natal_branch != natal.right_branch
                ):
                    raise ValueError("行年与本课大绝须使用同一明确本命支")
                if (
                    "natal_branch_source" in self.year_fate.model_fields_set
                    and "input_source" in natal.model_fields_set
                ):
                    expected_source = (
                        "not_provided"
                        if self.year_fate.natal_branch_source == "missing"
                        else self.year_fate.natal_branch_source
                    )
                    if natal.input_source != expected_source:
                        raise ValueError("本命支来源须与明确输入事实一致")
        if self.year_fate is None or self.year_fate.course is None:
            return self
        child = self.year_fate.course

        def agree(a: Any, b: Any) -> bool:
            if isinstance(a, dict) and isinstance(b, dict):
                return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
            return bool(a == b)

        if self.calendar_policy is not None and child.calendar_policy is not None:
            if not agree(
                self.calendar_policy.model_dump(exclude_unset=True),
                child.calendar_policy.model_dump(exclude_unset=True),
            ):
                raise ValueError("行年另课须保留同次分析历法口径")
        if self.overview is not None and child.overview is not None:
            for key in (
                "month_general",
                "is_diurnal",
                "diurnal_basis",
                "diurnal_evidence",
            ):
                a = self.overview.model_dump(exclude_unset=True)
                b = child.overview.model_dump(exclude_unset=True)
                if key in a and key in b and not agree(a[key], b[key]):
                    raise ValueError("行年另课须保留本次月将与显式昼夜选择")
        return self


class SixyaoLine(PartialOutput):
    changed_branch: Optional[str] = None
    changed_liuqin: Optional[str] = None
    is_fuyin_line: Optional[bool] = None
    branch: Optional[str] = None
    change: Optional[bool] = None
    element: Optional[str] = None
    god: Optional[str] = None
    liuqin: Optional[str] = None
    liushen: Optional[str] = None
    name: Optional[str] = None
    position: Optional[int] = None
    shi_ying: Optional[str] = None
    value: Optional[int] = None


class SixyaoTimeRuleset(PartialOutput):
    ruleset_id: Optional[str] = None
    year_boundary: Optional[str] = None
    source_url: Optional[str] = None
    seed: Optional[MeihuaSeed] = None


class SixyaoCoinToss(PartialOutput):
    position: Optional[int] = None
    name: Optional[str] = None
    sum: Optional[int] = None
    yao: Optional[str] = None
    symbol: Optional[str] = None
    moving: Optional[bool] = None


class SixyaoCast(PartialOutput):
    method: Optional[str] = None
    source: Optional[str] = None
    seed: Optional[int] = None
    coin_source: Optional[str] = None
    tosses: Optional[List[SixyaoCoinToss]] = None
    time_ruleset: Optional[SixyaoTimeRuleset] = None


class SixyaoHexagramInfo(PartialOutput):
    changed_palace: Optional[str] = None
    changed_palace_element: Optional[str] = None
    changed_position: Optional[str] = None
    current_palace: Optional[str] = None
    current_palace_element: Optional[str] = None
    current_position: Optional[str] = None
    shi_line: Optional[int] = None
    ying_line: Optional[int] = None


class SixyaoDescription(PartialOutput):
    code: Optional[str] = None
    name: Optional[str] = None
    theme: Optional[str] = None
    summary: Optional[str] = None
    guidance: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    raw: Optional[Hexagram] = None


class SixyaoFlags(PartialOutput):
    liuchong_base: Optional[bool] = None
    liuchong_changed: Optional[bool] = None
    liuhe_base: Optional[bool] = None
    liuhe_changed: Optional[bool] = None


class Tongshefa(PartialOutput):
    baseLeft: Optional[Hexagram] = None
    baseRight: Optional[Hexagram] = None
    mutualLeft: Optional[Hexagram] = None
    mutualRight: Optional[Hexagram] = None
    relation: Optional[str] = None
    main_relation: Optional[str] = None
    left_elem: Optional[str] = None
    right_elem: Optional[str] = None


class CanpingVerses(PartialOutput):
    statusShun: Optional[str] = None
    statusNi: Optional[str] = None
    numNi: Optional[int] = None
    numShun: Optional[int] = None
    textNi: Optional[str] = None
    textShun: Optional[str] = None
    selectionShun: Optional[CanpingTextSelection] = None
    selectionNi: Optional[CanpingTextSelection] = None
    pair_resolution: Optional[CanpingPairResolution] = None


class CanpingRow(PartialOutput):
    year_start_boundary: Optional[CanpingSolarBoundary] = None
    year_end_boundary: Optional[CanpingSolarBoundary] = None
    age: Optional[int] = None
    ageEnd: Optional[int] = None
    ageStart: Optional[int] = None
    branch: Optional[str] = None
    index: Optional[int] = None
    ni: Optional[int] = None
    numNi: Optional[int] = None
    numShun: Optional[int] = None
    shun: Optional[int] = None
    ziRound: Optional[int] = None
    verses: Optional[CanpingVerses] = None
    dayunBranch: Optional[str] = None
    dayunRange: Optional[str] = None
    ganzhi: Optional[str] = None
    taisuiBranch: Optional[str] = None
    year: Optional[int] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    at: Optional[str] = None
    start_age: Optional[float] = None
    end_age: Optional[float] = None
    status: Optional[str] = None
    pillar: Optional[str] = None
    dayun_index: Optional[int] = None
    dayun_pillar: Optional[str] = None
    segments: Optional[List["CanpingRow"]] = None


class CanpingSeries(PartialOutput):
    year_boundaries: Optional[List[CanpingSolarBoundary]] = None
    solar_context: Optional[CanpingSolarContext] = None
    dayun: Optional[List[CanpingRow]] = None
    element: Optional[str] = None
    partName: Optional[str] = None
    qiyunAge: Optional[int] = None
    rows: Optional[List[CanpingRow]] = None
    year_boundary: Optional[str] = None
    birth_pillar_year: Optional[int] = None
    age_policy: Optional[str] = None


class CanpingTiming(PartialOutput):
    solar_year_context: Optional[CanpingSolarContext] = None
    profile_id: Optional[str] = None
    method_id: Optional[str] = None
    birth_at: Optional[str] = None
    timezone: Optional[str] = None
    start_at: Optional[str] = None
    start_details: Optional[Object] = None
    calendar_offset: Optional[Object] = None
    calendar_policy: Optional[str] = None
    reference_policy: Optional[str] = None
    boundary_policy: Optional[str] = None
    dst_policy: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    source_status: Optional[str] = None
    calendar_scope: Optional[str] = None
    heluo_period_distinction: Optional[str] = None
    selected: Optional[CanpingRow] = None
    schedule_basis: Optional[CanpingScheduleBasis] = None
    first_row: Optional[CanpingRow] = None
    first_period: Optional[CanpingRow] = None

    @model_validator(mode="after")
    def coherent_schedule_source_map(self) -> "CanpingTiming":
        basis = self.schedule_basis
        known_profile = self.profile_id or (basis.profile_id if basis else None)
        known_start = self.start_at or (basis.actual_start_at if basis else None)
        if self.first_row is not None:
            if known_profile == "legacy_minggong_v1" or (
                basis is not None and basis.has_actual_date_mapping is False
            ):
                for key in (
                    "start_at",
                    "end_at",
                    "start_age",
                    "end_age",
                    "at",
                    "dayun_index",
                    "year_start_boundary",
                    "year_end_boundary",
                ):
                    if getattr(self.first_row, key) is not None:
                        raise ValueError(
                            "旧法首行仅为年龄标签，不能补实际日期或查询身份。"
                        )
            if self.first_period is not None:

                def agree(a: Any, b: Any) -> bool:
                    if a is None or b is None:
                        return True
                    if isinstance(a, dict) and isinstance(b, dict):
                        return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
                    if isinstance(a, list) and isinstance(b, list):
                        return len(a) == len(b) and all(
                            agree(x, y) for x, y in zip(a, b)
                        )
                    return bool(a == b)

                if not agree(
                    self.first_row.model_dump(exclude_unset=True),
                    self.first_period.model_dump(exclude_unset=True),
                ):
                    raise ValueError("首行与首运的已返回事实不一致。")
        if basis is not None:
            if (
                self.start_at is not None
                and basis.actual_start_at is not None
                and self.start_at != basis.actual_start_at
            ):
                raise ValueError("配运来源回执与实际起运瞬间不一致。")
            if (
                self.profile_id is not None
                and basis.profile_id is not None
                and self.profile_id != basis.profile_id
            ):
                raise ValueError("配运来源回执与实际方法不一致。")
            if (
                self.calendar_offset is not None
                and basis.age_conversion_result is not None
            ):
                for key in (
                    self.calendar_offset.keys() & basis.age_conversion_result.keys()
                ):
                    actual = self.calendar_offset[key]
                    recorded = basis.age_conversion_result[key]
                    if type(actual) is not type(recorded) or actual != recorded:
                        raise ValueError("配运年龄折算回执与本次实际结果不一致。")
            if basis.calendar_mapping is not None:
                for key in (
                    "calendar_policy",
                    "reference_policy",
                    "boundary_policy",
                    "dst_policy",
                ):
                    actual = getattr(self, key)
                    recorded = basis.calendar_mapping.get(key)
                    if (
                        known_profile != "legacy_minggong_v1"
                        and actual is not None
                        and recorded is not None
                        and actual != recorded
                    ):
                        raise ValueError("配运日期映射回执与本次实际政策不一致。")
        if (
            self.first_period is not None
            and self.first_period.start_at is not None
            and known_start is not None
            and self.first_period.start_at != known_start
        ):
            raise ValueError("首运摘要与实际起运时刻不一致。")
        if self.first_period is not None and (
            known_profile == "legacy_minggong_v1"
            or basis is not None
            and basis.has_actual_date_mapping is False
        ):
            raise ValueError("旧命宫排法不能补成已核日期首运。")
        return self


class HeluoHexagram(PartialOutput):
    lines: Optional[List[int]] = None
    name: Optional[str] = None
    yuan: Optional[int] = None
    low: Optional[str] = None
    up: Optional[str] = None


class HeluoChart(PartialOutput):
    cycleYear: Optional[int] = None
    yuanCycle: Optional[str] = None
    yangLingBasis: Optional[str] = None
    yuantang_derivation: Optional[HeluoYuantangDerivation] = None
    di: Optional[int] = None
    diGua: Optional[str] = None
    diNum: Optional[int] = None
    gender: Optional[str] = None
    hourZhi: Optional[str] = None
    tian: Optional[int] = None
    tianGua: Optional[str] = None
    tianNum: Optional[int] = None
    tianTop: Optional[bool] = None
    yangGan: Optional[bool] = None
    yangLing: Optional[bool] = None
    yangMing: Optional[bool] = None
    hou: Optional[HeluoHexagram] = None
    xian: Optional[HeluoHexagram] = None


class HeluoPeriod(PartialOutput):
    ageEnd: Optional[int] = None
    ageStart: Optional[int] = None
    gua: Optional[str] = None
    lines: Optional[List[int]] = None
    pos: Optional[int] = None
    yang: Optional[bool] = None
    yearStart: Optional[int] = None
    years: Optional[int] = None


class HeluoDayun(PartialOutput):
    all: Optional[List[HeluoPeriod]] = None
    hou: Optional[List[HeluoPeriod]] = None
    xian: Optional[List[HeluoPeriod]] = None
    endAge: Optional[int] = None
    xianEndAge: Optional[int] = None


class LocalAngles(PartialOutput):
    ascendant: Optional[float] = None
    midheaven: Optional[float] = None


class LocalHouse(PartialOutput):
    id: Optional[str] = None
    lon: Optional[float] = None
    sign: Optional[str] = None
    sign_zh: Optional[str] = None


class LocalObject(PartialOutput):
    house: Optional[str] = None
    ecliptic_house_position: Optional[float] = None
    id: Optional[str] = None
    lon: Optional[float] = None
    sign: Optional[str] = None
    signlon: Optional[float] = None


class LocalChart(PartialOutput):
    angles: Optional[LocalAngles] = None
    houses: Optional[List[LocalHouse]] = None
    objects: Optional[List[LocalObject]] = None
    ok: Optional[bool] = None


class LocalChartBundle(PartialOutput):
    chart: Optional[LocalChart] = None
    params: Optional[Object] = None


class SanshiSubresult(PartialOutput):
    analysis_context: Optional[AnalysisContext] = None
    analysis_type: Optional[str] = None
    calendar_context: Optional[CalendarContext] = None
    four_pillars: Optional[FourPillars] = None
    liureng: Optional[Liuren] = None


class QimenSubresult(SanshiSubresult):
    pan: Optional[Qimen] = None


class TaiyiSubresult(SanshiSubresult):
    pan: Optional[Taiyi] = None


class SanshiSubresults(PartialOutput):
    liureng_gods: Optional[SanshiSubresult] = None
    qimen: Optional[QimenSubresult] = None
    taiyi: Optional[TaiyiSubresult] = None


CHINESE_FIELDS: Dict[str, Any] = {
    "four_pillars": FourPillars,
    "person_info": PersonInfo,
    "analysis_context": AnalysisContext,
    "birth_context": AnalysisContext,
    "calendar_context": CalendarContext,
    "jieqi_year": List[SolarTerm],
    "selected_jieqi": List[SolarTerm],
    "target_year_jieqi": List[SolarTerm],
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
    "descriptions": Dict[str, SixyaoDescription],
    "pattern_flags": SixyaoFlags,
    "benming": CanpingRow,
    "liunian_series": CanpingSeries,
    "subresults": SanshiSubresults,
}

# Root names such as chart, dayun, lines and result have different meanings in
# different families. Resolve them by tool instead of weakening them with unions.
CHINESE_TOOL_FIELDS: Dict[str, Dict[str, Any]] = {
    "sanshiunited": {"synthesis": SanshiSynthesis},
    "sixyao": {
        "lines": List[SixyaoLine],
        "moving_lines": List[int],
        "liuyao_evidence": LiuyaoEvidence,
        "classical_text_evidence": ClassicalTextEvidence,
    },
    "gua_lookup": {"result": Hexagram},
    "gua_meiyi": {"queries": List[str], "results": Dict[str, Hexagram]},
    "canping": {
        "dayun": List[CanpingRow],
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
    "otherbu": {"chart": LocalChartBundle, "diceChart": LocalChartBundle},
}
