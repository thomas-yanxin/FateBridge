"""Ziwei horoscope and limit output contracts."""

from typing import Literal

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import LunarDate
from fatebridge.core.contracts.output_ziwei_calendar import ZiweiHoroscopeCalendarBasis
from fatebridge.core.contracts.output_ziwei_palaces import (
    ZiweiAnnualThreeSha,
    ZiweiFlowingStar,
    ZiweiPosition,
    ZiweiRuleset,
    ZiweiRuleTrace,
    ZiweiSihuaSourceComparison,
    ZiweiStar,
)
from fatebridge.core.contracts.output_ziwei_structure import (
    WuxingJu,
    ZiweiCalendarRules,
)


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
    natal_stars_detail: list[ZiweiStar] | None = None


class ZiweiScope(PartialOutput):
    scope: str | None = None
    status: str | None = None
    first_age: int | None = None
    unavailable_reason: str | None = None
    branch: str | None = None
    branch_index: int | None = None
    stem: str | None = None
    palace_ganzhi: str | None = None
    palace_name: str | None = None
    scope_palace_role: str | None = None
    natal_palace_name: str | None = None
    mutagen: dict[str, str] | None = None
    mutagen_natal_links: list[ZiweiMutagenNatalLink] | None = None
    palace_map: list[ZiweiScopePalace] | None = None
    stem_origin: str | None = None
    flowing_stars: list[ZiweiFlowingStar] | None = None
    annual_three_sha: ZiweiAnnualThreeSha | None = None


class ZiweiInterpretationScope(PartialOutput):
    contract_version: str | None = None
    scope_palace_meaning: str | None = None
    transformation_meaning: str | None = None
    full_scope_palaces_supported: bool | None = None
    scope_palace_map_supported: bool | None = None
    limitations: list[str] | None = None


class ZiweiChildhoodLimit(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    status: str | None = None
    given_age_ordinal: int | None = None
    source_palace_label: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    natal_palace_ganzhi: str | None = None
    natal_stars_detail: list[ZiweiStar] | None = None
    source: str | None = None
    printed_volume: str | None = None
    frame: int | None = None
    source_section: str | None = None
    source_reading: str | None = None
    source_reading_caveat: str | None = None
    age_boundary_rule_verified: Literal[False] | None = None
    pre_decade_substitution_verified: Literal[False] | None = None
    childhood_sihua_supported: Literal[False] | None = None
    natal_stars_are_not_childhood_transformations: Literal[True] | None = None
    unresolved_reason: str | None = None


class ZiweiDecadeHalf(PartialOutput):
    status: str | None = None
    nominal_age: int | None = None
    natal_branch: str | None = None
    selected_decade_age_range: list[int] | None = None
    year_ordinal_in_decade: int | None = None
    half: Literal["upper_five_years", "lower_five_years"] | None = None
    selected_half_age_range: list[int] | None = None
    textual_group: Literal["north", "south"] | None = None
    conditional_on_existing_age_convention: Literal[True] | None = None
    calendar_boundaries_classically_verified: Literal[False] | None = None
    unresolved_reason: str | None = None


class ZiweiSmallLimitHalf(PartialOutput):
    status: str | None = None
    half: None = None
    half_start: None = None
    half_end: None = None
    north_textual_half: str | None = None
    south_textual_half: str | None = None
    unresolved_reason: str | None = None


class ZiweiLimitGroupOccurrence(PartialOutput):
    star: str | None = None
    natal_branch: str | None = None
    natal_palace_name: str | None = None
    natal_mutagen: str | None = None
    calculation_path: str | None = None


class ZiweiLimitStarGroup(PartialOutput):
    star: str | None = None
    definition_id: str | None = None
    source_frame: int | None = None
    source_quote: str | None = None
    textual_group: Literal["north", "south", "both"] | None = None
    textual_daxian_half: Literal["upper_five_years", "lower_five_years"] | None = None
    unresolved_reason: str | None = None
    actual_occurrences: list[ZiweiLimitGroupOccurrence] | None = None
    selected_as_relevant_star: None = None


class ZiweiLimitSubperiods(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    source: str | None = None
    frame: int | None = None
    source_section: str | None = None
    source_reading: dict[str, str] | None = None
    transcription_method: str | None = None
    independent_human_reviewers: int | None = None
    independent_model_reviewers: int | None = None
    daxian: ZiweiDecadeHalf | None = None
    xiaoxian: ZiweiSmallLimitHalf | None = None
    group_definition_source: str | None = None
    group_definition_section: str | None = None
    natal_star_groups: list[ZiweiLimitStarGroup] | None = None
    unclassified_natal_stars: list[str] | None = None
    relevant_star_geometry_defined: Literal[False] | None = None
    full_traditional_judgment: None = None
    source_outcome_claim_adopted: Literal[False] | None = None
    actual_assignments_modified: Literal[False] | None = None
    whole_section_certified: Literal[False] | None = None
    whole_book_acceptance_passed: Literal[False] | None = None
    limitations: list[str] | None = None


class ZiweiAgeSourceCitation(PartialOutput):
    source_url: str | None = None
    frame: int | None = None
    section: str | None = None
    quote: str | None = None
    establishes: str | None = None
    does_not_establish_in_this_passage: str | None = None


class ZiweiAgeSourceScope(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    review_scope: str | None = None
    manual_readers: int | None = None
    independent_reviewers: int | None = None
    citations: list[ZiweiAgeSourceCitation] | None = None
    software_age_convention: str | None = None
    source_does_not_certify_software_age_convention: Literal[True] | None = None
    age_boundary_classically_verified: Literal[False] | None = None
    whole_book_acceptance_passed: Literal[False] | None = None
    correction_history: list[dict[str, str]] | None = None


class ZiweiNominalAgeCalendar(PartialOutput):
    method_id: str | None = None
    basis: Literal["birth_civil_timezone"] | None = None
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
    physical_order_checked: bool | None = None
    date_lookup_convention: str | None = None
    age_boundary_classically_verified: Literal[False] | None = None
    boundary_source_evidence: ZiweiAgeSourceScope | None = None


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
    rule_trace: list[ZiweiRuleTrace] | None = None
    separate_birth_run: Literal[False] | None = None
    classical_birth_year_boundary_verified: Literal[False] | None = None


class ZiweiHoroscope(PartialOutput):
    natal_prerequisites: ZiweiHoroscopeNatalPrerequisites | None = None
    sihua_source_comparison: ZiweiSihuaSourceComparison | None = None
    engine: str | None = None
    calendar_basis: ZiweiHoroscopeCalendarBasis | None = None
    calendar_rules: ZiweiCalendarRules | None = None
    ruleset: ZiweiRuleset | None = None
    source_comparison: dict[str, OpenJsonValue] | None = None
    nominal_age: int | None = None
    nominal_age_calendar: ZiweiNominalAgeCalendar | None = None
    childhood_limit: ZiweiChildhoodLimit | None = None
    ming_limit_subperiods: ZiweiLimitSubperiods | None = None
    interpretation_scope: ZiweiInterpretationScope | None = None
    scopes: list[ZiweiScope] | None = None


class ZiweiFocusedRules(PartialOutput):
    sihua: dict[str, str] | None = None
    year_stem: str | None = None


class ZiweiRuleCatalogue(PartialOutput):
    ming_gong_method: str | None = None
    shen_gong_method: str | None = None
    palace_sequence: list[str] | None = None
    sihua_by_year_stem: dict[str, dict[str, str]] | None = None
    sihua_source_comparison: ZiweiSihuaSourceComparison | None = None
    ruleset: ZiweiRuleset | None = None
    cycle_methods: dict[str, str] | None = None
