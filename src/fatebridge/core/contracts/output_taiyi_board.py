"""Taiyi counters, palaces and calendar evidence."""

from typing import Annotated

from pydantic import Field

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import Object, SolarTerm
from fatebridge.core.contracts.output_taiyi_calendar import (
    TaiyiCivilClockResolution,
    TaiyiCivilLunarCalendar,
)
from fatebridge.core.contracts.output_taiyi_conditions import TaiyiConditionAssessment
from fatebridge.core.contracts.output_taiyi_counts import TaiyiCountAssessment
from fatebridge.core.contracts.output_taiyi_day import (
    TaiyiDayOrigin,
    TaiyiSourceComparison,
    TaiyiTenJing,
)
from fatebridge.core.contracts.output_taiyi_elemental import TaiyiElementalAssessment
from fatebridge.core.contracts.output_taiyi_enclosures import TaiyiEnclosureAssessment
from fatebridge.core.contracts.output_taiyi_gates import TaiyiDeterminate, TaiyiGates
from fatebridge.core.contracts.output_taiyi_historical import TaiyiHistoricalReference
from fatebridge.core.contracts.output_taiyi_hour import TaiyiHourOrigin
from fatebridge.core.contracts.output_taiyi_long_cycles import (
    TaiyiLongCycles,
    TaiyiLongSummary,
)
from fatebridge.core.contracts.output_taiyi_matrix import TaiyiVictoryMatrixAssessment
from fatebridge.core.contracts.output_taiyi_month import TaiyiMonthOrigin
from fatebridge.core.contracts.output_taiyi_oppositions import TaiyiOppositionAssessment
from fatebridge.core.contracts.output_taiyi_shiji import TaiyiShijiDerivation
from fatebridge.core.contracts.output_taiyi_source_alignment import TaiyiSourceAlignment
from fatebridge.core.contracts.output_taiyi_year_calendar import (
    TaiyiHistoricalYearCalendar,
)


class TaiyiCounterGroup(PartialOutput):
    number: int | None = None
    position: int | None = None
    size: int | None = None


class TaiyiCounterCycles(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source: str | None = None
    paths_relative_to: str | None = None
    counter_path: str | None = None
    actual_ju_path: str | None = None
    counter: int | None = None
    calculation_mode: str | None = None
    counter_unit: str | None = None
    completed_cycles_before_current360: int | None = None
    position360: int | None = None
    ji60: TaiyiCounterGroup | None = None
    yuan72: TaiyiCounterGroup | None = None
    actual_kook_number: int | None = None
    calendar_ganzhi_alignment: str | None = None
    scope: str | None = None


class TaiyiCore(PartialOutput):
    yin_dun: bool | None = None
    ruler_branch: str | None = None
    ruler_label: str | None = None
    accumulation: int | None = None
    taiyi_number: int | None = None
    chenji: str | None = None
    dingmu: str | None = None
    diyi: str | None = None
    guest_count: Annotated[int | None, FULL_FACT] = None
    guest_count_des: list[str] | None = None
    guest_general: int | None = None
    guest_vice_general: int | None = None
    heshen: str | None = None
    jishen: str | None = None
    junji: str | None = None
    kook_number: int | None = None
    kook_year: str | None = None
    main_calculation: str | None = None
    table_policy: str | None = None
    main_count: Annotated[int | None, FULL_FACT] = None
    main_count_des: list[str] | None = None
    main_general: int | None = None
    main_vice_general: int | None = None
    minji: str | None = None
    set_count: int | None = None
    set_general: int | None = None
    set_vice_general: int | None = None
    shiji: str | None = None
    shiji_profile: str | None = None
    requested_shiji_profile: str | None = None
    sishen: str | None = None
    suijun: str | None = None
    taiyi_position: str | None = None
    tianyi: str | None = None
    wenchang_position: str | None = None
    wufu: int | None = None
    zhifu: str | None = None


class TaiyiPalace(PartialOutput):
    markers: list[str] | None = None
    palace: str | None = None


class TaiyiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source_title: str | None = None
    source_kind: str | None = None
    sources: dict[str, str] | None = None
    time_granularity: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    unresolved: list[str] | None = None


class TaiyiCalendarRules(PartialOutput):
    anchor_ephemeris_model: str | None = None
    winter_anchor_ephemeris_model: str | None = None
    civil_clock_resolution: TaiyiCivilClockResolution | None = None
    year_profile: str | None = None
    shiji_profile: str | None = None
    historical_calendar: TaiyiHistoricalYearCalendar | None = None
    civil_lunar_calendar: TaiyiCivilLunarCalendar | None = None
    month_profile: str | None = None
    month_origin: TaiyiMonthOrigin | None = None
    input_calendar: str | None = None
    historical_date_reference: TaiyiHistoricalReference | None = None
    day_profile: str | None = None
    day_origin: TaiyiDayOrigin | None = None
    palace_day_number: int | None = None
    hour_profile: str | None = None
    hour_origin: TaiyiHourOrigin | None = None
    convention: str | None = None
    calculation_mode: str | None = None
    anchor_name: str | None = None
    anchor_utc: str | None = None
    anchor_provider: str | None = None
    counter: int | None = None
    boundary_instant_basis: str | None = None
    ruler_branch_basis: str | None = None
    heshen_branch_basis: str | None = None
    clock_basis: str | None = None
    cycle_year: int | None = None
    month_offset: int | None = None
    leap_month_policy: str | None = None
    anchor_clock: str | None = None
    target_clock: str | None = None
    double_hour_start: str | None = None
    initial_interval: str | None = None
    dst_policy: str | None = None
    counter_rule_source: str | None = None
    counter_formula: str | None = None
    anchor_precision: str | None = None
    seconds_from_anchor: float | None = None
    target_slot: int | None = None
    anchor_slot: int | None = None
    year: int | None = None
    year_boundary: str | None = None
    year_boundary_status: str | None = None
    year_ganzhi: str | None = None
    civil_datetime: str | None = None
    timezone: str | None = None
    solar_correction_affects_year: bool | None = None
    pillars_role: str | None = None


class TaiyiEvidenceFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiPattern(PartialOutput):
    name: str | None = None
    subject: str | None = None
    variant: str | None = None
    basis: list[TaiyiEvidenceFact] | None = None
    traditional_meaning: str | None = None
    source: str | None = None
    supplementary_sources: list[str] | None = None
    relation_profile: str | None = None
    scope: str | None = None


class TaiyiWinterOriginSelection(PartialOutput):
    policy_id: str | None = None
    selection_switch_basis: str | None = None
    selected_winter_utc: str | None = None
    count_origin_date: str | None = None
    count_origin_clock: str | None = None
    clock_basis: str | None = None
    classical_source_scope: str | None = None
    classical_activation_adjudicated: bool | None = None
    scope: str | None = None


class Taiyi(PartialOutput):
    winter_origin_selection: TaiyiWinterOriginSelection | None = None
    solar_anchors: dict[str, SolarTerm] | None = None
    solar_anchor_scope: str | None = None
    counter_cycles: TaiyiCounterCycles | None = None
    shiji_derivation: TaiyiShijiDerivation | None = None
    elemental_guan_assessment: TaiyiElementalAssessment | None = None
    victory_matrix_assessment: TaiyiVictoryMatrixAssessment | None = None
    count_source_assessment: TaiyiSourceAlignment | None = None
    count_assessment: TaiyiCountAssessment | None = None
    opposition_assessment: TaiyiOppositionAssessment | None = None
    enclosure_assessment: TaiyiEnclosureAssessment | None = None
    ten_jing: TaiyiTenJing | None = None
    fate_palaces: Object | None = None
    day_source_comparisons: list[TaiyiSourceComparison] | None = None
    gates: TaiyiGates | None = None
    determinate_calculation: TaiyiDeterminate | None = None
    condition_assessment: TaiyiConditionAssessment | None = None
    long_cycles: TaiyiLongCycles | None = None
    long_cycle_summary: TaiyiLongSummary | None = None
    extra_palace_marks: list[TaiyiPalace] | None = None
    engine: Annotated[str | None, FULL_FACT] = None
    accumulation_label: str | None = None
    core_board: Annotated[TaiyiCore | None, FULL_FACT] = None
    life_method: Annotated[str | None, FULL_FACT] = None
    palace_marks: Annotated[list[TaiyiPalace] | None, FULL_FACT] = Field(
        default=None, min_length=8
    )
    center_marks: TaiyiPalace | None = None
    ruleset: Annotated[TaiyiRuleset | None, FULL_FACT] = None
    calendar_rules: TaiyiCalendarRules | None = None
    calendar_summary: TaiyiCalendarRules | None = None
    pattern_summary: Object | None = None
    patterns: list[TaiyiPattern] | None = None
    interpretation_scope: Object | None = None
    rotation: str | None = None
    style_label: str | None = None
    taiyi_palace: str | None = None
    wenchang_palace: str | None = None
    big_pattern: str | None = None
    small_pattern: str | None = None
