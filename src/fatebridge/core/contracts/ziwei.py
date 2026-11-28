"""Output contracts for Ziwei Doushu birth chart, timing, and rules."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
    ProjectedOutput,
)
from fatebridge.core.contracts.common import (
    AnalysisContext,
    BranchName,
    LunarDate,
    PersonInfo,
)
from fatebridge.core.receipt_models import RunMetadata


class ZiweiMinuteSensitivity(PartialOutput):
    method_id: str | None = None
    clock_stage: Literal["after_normalization_before_day_divide"] | None = None
    birth_seconds_supplied: bool | None = None
    base_second: int | None = None
    endpoint_seconds: list[float] | None = None
    endpoint_placement_datetimes: list[str] | None = None
    endpoint_hour_branches: list[str] | None = None
    crosses_hour_branch: bool | None = None
    crosses_placement_date: bool | None = None


class ZiweiTimeInput(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    requested: bool | None = None
    explicitly_requested: bool | None = None
    applied: bool | None = None
    components_computed: bool | None = None
    timezone: str | None = None
    timezone_source: str | None = None
    timezone_resolved_place: str | None = None
    timezone_assumed: bool | None = None
    longitude: float | None = None
    longitude_source: str | None = None
    resolved_place: str | None = None
    resolution_level: str | None = None
    resolution_advisory: str | None = None
    longitude_correction_minutes: float | None = None
    equation_of_time_minutes: float | None = None
    daylight_saving_minutes: float | None = None
    total_correction_minutes: float | None = None
    applied_delta_seconds: float | None = None
    solar_time_strategy: str | None = None
    equation_of_time_method: str | None = None
    equation_of_time_time_scale: str | None = None
    minute_sensitivity: ZiweiMinuteSensitivity | None = None


class ZiweiCivilClock(PartialOutput):
    method_id: str | None = None
    selection: str | None = None
    timezone: str | None = None
    resolved_utc_offset: str | None = None
    wall_datetime: str | None = None
    was_ambiguous: bool | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None


class ZiweiCalendarBasis(PartialOutput):
    method_id: str | None = None
    placement_clock: str | None = None
    placement_datetime: str | None = None
    civil_datetime: str | None = None
    civil_instant_utc: str | None = None
    apparent_solar_datetime: str | None = None
    timezone: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    late_zi_rollover_applied: bool | None = None
    date_shift_days: int | None = None
    placement_lunar_date: LunarDate | None = None
    civil_date_lunar_date: LunarDate | None = None
    reference_datetime_utc_plus_08: str | None = None
    reference_lunar_date: LunarDate | None = None
    day_boundary: str | None = None
    time_input: ZiweiTimeInput | None = None
    civil_clock: ZiweiCivilClock | None = None


class ZiweiHoroscopeCalendarBasis(PartialOutput):
    birth: ZiweiCalendarBasis | None = None
    target: ZiweiCalendarBasis | None = None
    nominal_age_rule: str | None = None


class ZiweiPosition(BranchName):
    ganzhi: str | None = None


class ZiweiStar(PartialOutput):
    name: str | None = None
    label: str | None = None
    brightness: str | None = Field(
        default=None, description="庙旺表档位；null 表示所选表未给该星该支定档。"
    )
    brightness_source: str | None = None
    mutagen: str | None = None


class ZiweiStructuralEvidence(PartialOutput):
    major_stars: list[str] | None = None
    is_empty_main_palace: bool | None = None
    sanfang_sizheng_branches: list[str] | None = None
    opposite_stars_relocated: bool | None = None


class ZiweiBrightnessTableReceipt(PartialOutput):
    id: str | None = None
    source_kind: str | None = None
    source_url: str | None = None
    version: str | None = None
    branch_order: list[str] | None = None
    grade_scale: list[str] | None = None
    aliases: dict[str, str] | None = None
    blank_meaning: str | None = None


class ZiweiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    school: str | None = None
    astro_type: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    year_divide: Literal["normal", "exact"] | None = None
    horoscope_divide: Literal["normal", "exact"] | None = None
    age_divide: Literal["normal", "birthday"] | None = None
    leap_month_rule: (
        Literal["split_at_day_15", "all_current_month", "all_next_month"] | None
    ) = None
    target_leap_month_rule: str | None = None
    sihua_source: str | None = None
    sihua_rule: str | None = None
    brightness_rule: str | None = None
    brightness_table: ZiweiBrightnessTableReceipt | None = None
    overrides: list[str] | None = None


class ZiweiYearCyclePosition(PartialOutput):
    name: str
    branch: str


class ZiweiYearCycle(PartialOutput):
    system_id: Annotated[str | None, FULL_FACT] = None
    start_branch: Annotated[str | None, FULL_FACT] = None
    positions: Annotated[list[ZiweiYearCyclePosition] | None, FULL_FACT] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "branch"},
    )


class ZiweiYearBranchCycles(PartialOutput):
    anchor_basis: Annotated[
        Literal["natal_lunar_year_branch", "target_lunar_year_branch"] | None, FULL_FACT
    ] = None
    year_branch: Annotated[str | None, FULL_FACT] = None
    direction: Annotated[Literal["forward"] | None, FULL_FACT] = None
    source: Annotated[str | None, FULL_FACT] = None
    suiqian: Annotated[ZiweiYearCycle | None, FULL_FACT] = None
    jiangqian: Annotated[ZiweiYearCycle | None, FULL_FACT] = None


class ZiweiCycleRules(PartialOutput):
    status: str | None = None
    changsheng_start: str | None = None
    changsheng_direction: str | None = None
    changsheng_rule: str | None = None
    boshi_start: str | None = None
    boshi_direction: str | None = None
    boshi_rule: str | None = None
    missing_gender_resolution: str | None = None
    gender_invariant_positions: dict[str, dict[str, str]] | None = None
    year_branch_cycles: Annotated[ZiweiYearBranchCycles | None, FULL_FACT] = None


class ZiweiChartMaster(PartialOutput):
    star: str | None = None
    selection_basis: str | None = None
    basis_branch: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None


class ZiweiChartMasters(PartialOutput):
    life: ZiweiChartMaster | None = None
    body: ZiweiChartMaster | None = None


class ZiweiFlowingStar(PartialOutput):
    star: str | None = None
    scope: str | None = None
    branch: str | None = None
    scope_palace_name: str | None = None
    natal_palace_name: str | None = None
    rule_id: str | None = None
    stem: str | None = None
    basis_branch: str | None = None
    system_id: str | None = None
    year_branch: str | None = None
    source: str | None = None


class ZiweiAnnualThreeSha(PartialOutput):
    rule_id: str | None = None
    scope: str | None = None
    year_branch: str | None = None
    names_as_written: list[str] | None = None
    branches: list[str] | None = None
    source: str | None = None


class ZiweiXunVoid(PartialOutput):
    source_branches: list[str] | None = None
    displayed_star_branches: list[str] | None = None
    display_rule: str | None = None


class ZiweiVoidSystems(PartialOutput):
    xun: ZiweiXunVoid | None = None


class ZiweiPalace(PartialOutput):
    name: Annotated[str | None, FULL_FACT] = None
    ganzhi: Annotated[str | None, FULL_FACT] = None
    is_original_palace: bool | None = None
    daxian: str | None = None
    daxian_period: int | None = None
    stars: list[str] | None = None
    stars_detail: list[ZiweiStar] | None = None
    structural_evidence: ZiweiStructuralEvidence | None = None
    changsheng12: str | None = None
    boshi12: str | None = None


class ZiweiReadingPalace(PartialOutput):
    name: str | None = None
    ganzhi: str | None = None
    stars: list[ZiweiStar] | None = None
    major_stars: list[str] | None = None
    sanfang_sizheng_branches: list[str] | None = None
    changsheng12: str | None = None
    boshi12: str | None = None
    daxian: str | None = None


class ZiweiReadingView(PartialOutput):
    schema_version: str | None = None
    null_star_fields_omitted: list[str] | None = None
    sanfang_branch_order: list[str] | None = None
    palaces: list[ZiweiReadingPalace] | None = None
    star_occurrence_count: int | None = None
    distinct_star_count: int | None = None


class ZiweiCalendarRules(PartialOutput):
    late_zi: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    year_divide: Literal["normal", "exact"] | None = None
    leap_month: str | None = None
    year_boundary: str | None = None
    effective_birth_month: int | None = None


class WuxingJu(PartialOutput):
    element: str | None = None
    label: str | None = None
    nayin: str | None = None
    number: int | None = None


class ZiweiPalaceSihuaOccurrence(PartialOutput):
    palace_name: str
    branch: str
    calculation_path: str


class ZiweiPalaceSihuaOrigin(PartialOutput):
    source_palace: str
    source_stem: str
    source_branch: str
    self_transformation: bool | None = None


class ZiweiPalaceSihuaGroup(PartialOutput):
    transformation: Literal["化禄", "化权", "化科", "化忌"]
    target_star: str
    target_occurrences: list[ZiweiPalaceSihuaOccurrence]
    origins: list[ZiweiPalaceSihuaOrigin] = Field(min_length=1)


class ZiweiPalaceSihuaRelations(PartialOutput):
    policy: Literal["selected_natal_table_reused_for_palace_stems"] | None = None
    sihua_rule: str | None = None
    groups: list[ZiweiPalaceSihuaGroup] | None = None


class ZiweiFlyingMatrixRow(PartialOutput):
    palace: str | None = None
    ganzhi: str | None = None
    is_original_palace: bool | None = None
    transforms: dict[str, str] | None = None
    outward_self: list[str] | None = None
    inward_self: list[str] | None = None
    ji_clash: str | None = None
    lu_to_ji: str | None = None
    ji_to_ji: str | None = None


class ZiweiFlyingSihua(PartialOutput):
    sihua_rule: str | None = None
    laiyin_gong: ZiweiPosition | None = None
    matrix: list[ZiweiFlyingMatrixRow] | None = None


class ZiweiPatternRecord(PartialOutput):
    id: str | None = None
    name: str | None = None
    category: str | None = None
    matched: bool | None = None
    conditions: dict[str, bool] | None = None
    borrowed_opposite_palace: str | None = None
    borrowed_opposite_branch: str | None = None
    borrowed_opposite_major_stars: list[str] | None = None


class ZiweiNamedPatternEvidence(PartialOutput):
    method_id: str | None = None
    total_checked: int | None = None
    matched_count: int | None = None
    matched: list[ZiweiPatternRecord] | None = None
    unmatched_ids: list[str] | None = None


class ZiweiBirth(PartialOutput):
    engine: Annotated[str | None, FULL_FACT] = None
    school: str | None = None
    astro_type: str | None = None
    calendar_basis: Annotated[ZiweiCalendarBasis | None, FULL_FACT] = None
    calendar_rules: Annotated[ZiweiCalendarRules | None, FULL_FACT] = None
    ruleset: Annotated[ZiweiRuleset | None, FULL_FACT] = None
    reading_view: ZiweiReadingView | None = None
    named_patterns: ZiweiNamedPatternEvidence | None = None
    flying_sihua: ZiweiFlyingSihua | None = None
    palace_sihua_relations: ZiweiPalaceSihuaRelations | None = None
    void_systems: ZiweiVoidSystems | None = None
    chart_masters: ZiweiChartMasters | None = None
    calendar_cycles: Annotated[ZiweiCycleRules | None, FULL_FACT] = None
    daxian_direction: str | None = None
    hour_branch: str | None = None
    zidou_branch: str | None = None
    laiyin_gong: ZiweiPosition | None = None
    lunar_date: LunarDate | None = None
    ming_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    shen_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    palaces: Annotated[list[ZiweiPalace] | None, FULL_FACT] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "name"},
    )
    sihua: dict[str, str] | None = None
    time_algorithm: str | None = None
    wuxing_ju: Annotated[WuxingJu | None, FULL_FACT] = None
    year_stem: str | None = None


class ZiweiMutagenNatalLink(PartialOutput):
    transformation: str | None = None
    star: str | None = None
    status: str | None = None
    natal_palace_name: str | None = None
    natal_palace_ganzhi: str | None = None
    natal_branch: str | None = None
    natal_star_label: str | None = None
    natal_star_brightness: str | None = None
    natal_mutagen: str | None = None
    scope_palace_name: str | None = None


class ZiweiScopePalace(PartialOutput):
    scope_palace_name: str | None = None
    branch: str | None = None
    natal_palace_name: str | None = None
    natal_palace_ganzhi: str | None = None


class ZiweiFlowingStarBasis(PartialOutput):
    stem: str | None = None
    branch: str | None = None
    branch_origin: (
        Literal[
            "decadal_palace",
            "target_lunar_year_pillar",
            "target_effective_lunar_month_pillar",
            "target_solar_month_pillar",
            "target_day_pillar",
            "target_hour_pillar",
        ]
        | None
    ) = None
    effective_lunar_month: int | None = None
    lunar_date: LunarDate | None = None


class ZiweiScope(PartialOutput):
    scope: str | None = None
    status: str | None = None
    first_age: int | None = None
    unavailable_reason: str | None = None
    branch: str | None = None
    branch_index: int | None = None
    stem: str | None = None
    palace_ganzhi: str | None = None
    scope_palace_role: str | None = None
    natal_palace_name: str | None = None
    mutagen: dict[str, str] | None = None
    mutagen_natal_links: list[ZiweiMutagenNatalLink] | None = None
    palace_map: dict[str, str] | list[ZiweiScopePalace] | None = None
    stem_origin: str | None = None
    flowing_star_basis: ZiweiFlowingStarBasis | None = None
    flowing_stars: dict[str, str] | list[ZiweiFlowingStar] | None = None
    annual_three_sha: ZiweiAnnualThreeSha | None = None


class ZiweiInterpretationScope(PartialOutput):
    contract_version: str | None = None
    scope_palace_meaning: str | None = None
    transformation_meaning: str | None = None
    full_scope_palaces_supported: bool | None = None
    scope_palace_map_supported: bool | None = None


class ZiweiChildhoodLimit(PartialOutput):
    status: str | None = None
    nominal_age: int | None = None
    first_daxian_age: int | None = None
    natal_palace_name: str | None = None
    branch: str | None = None
    palace_ganzhi: str | None = None
    stem: str | None = None
    mutagen: dict[str, str] | None = None
    mutagen_natal_links: list[ZiweiMutagenNatalLink] | None = None
    palace_map: dict[str, str] | list[ZiweiScopePalace] | None = None


class ZiweiNominalAgeCalendar(PartialOutput):
    method_id: str | None = None
    basis: Literal["birth_civil_timezone"] | None = None
    age_divide: Literal["normal", "birthday"] | None = None
    day_divide: Literal["current", "forward"] | None = None
    rule: str | None = None
    timezone: str | None = None
    birth_datetime: str | None = None
    target_datetime: str | None = None
    birth_instant_utc: str | None = None
    target_instant_utc: str | None = None
    birth_lunar_date: LunarDate | None = None
    target_lunar_date: LunarDate | None = None
    birth_lunar_year: int | None = None
    target_lunar_year: int | None = None
    birth_placement_lunar_year: int | None = None
    target_civil_lunar_year: int | None = None
    nominal_age: int | None = None
    day_boundary: str | None = None


class ZiweiHoroscopeNatalPrerequisites(PartialOutput):
    schema_version: str | None = None
    origin: Literal["same_calculation_internal_natal_chart"] | None = None
    ruleset: ZiweiRuleset | None = None
    lunar_date: LunarDate | None = None
    year_stem: str | None = None
    hour_branch: str | None = None
    ming_gong: ZiweiPosition | None = None
    shen_gong: ZiweiPosition | None = None
    wuxing_ju: WuxingJu | None = None


class ZiweiHoroscope(PartialOutput):
    annual_cycles: Annotated[ZiweiYearBranchCycles | None, FULL_FACT] = None
    natal_prerequisites: ZiweiHoroscopeNatalPrerequisites | None = None
    engine: str | None = None
    school: str | None = None
    astro_type: str | None = None
    doujun_branch: str | None = None
    calendar_basis: ZiweiHoroscopeCalendarBasis | None = None
    calendar_rules: ZiweiCalendarRules | None = None
    ruleset: ZiweiRuleset | None = None
    nominal_age: int | None = None
    nominal_age_calendar: ZiweiNominalAgeCalendar | None = None
    childhood_limit: ZiweiChildhoodLimit | None = None
    interpretation_scope: ZiweiInterpretationScope | None = None
    scopes: list[ZiweiScope] | None = None
    decadal_list: list[dict[str, OpenJsonValue]] | None = None
    yearly_list: list[dict[str, OpenJsonValue]] | None = None
    monthly_list: list[dict[str, OpenJsonValue]] | None = None


class ZiweiFocusedRules(PartialOutput):
    sihua: dict[str, str] | None = None
    year_stem: str | None = None


class ZiweiNamedPatternCatalogue(PartialOutput):
    id: str | None = None
    version: str | None = None
    count: int | None = None
    rules: list[dict[str, str]] | None = None


class ZiweiRuleCatalogue(PartialOutput):
    named_patterns: ZiweiNamedPatternCatalogue | None = None
    ming_gong_method: str | None = None
    shen_gong_method: str | None = None
    palace_sequence: list[str] | None = None
    sihua_by_year_stem: dict[str, dict[str, str]] | None = None
    ruleset: ZiweiRuleset | None = None
    cycle_methods: dict[str, str] | None = None


class ZiweiBirthChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    person_info: PersonInfo | None = None
    ziwei_birth: ZiweiBirth | None = None


class ZiweiTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    birth_context: AnalysisContext | None = None
    person_info: PersonInfo | None = None
    ziwei_horoscope: ZiweiHoroscope | None = None


class ZiweiRulesOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    engine: str | None = None
    focused_rules: ZiweiFocusedRules | None = None
    requested_year_stem: str | None = None
    rule_catalogue: ZiweiRuleCatalogue | None = None
