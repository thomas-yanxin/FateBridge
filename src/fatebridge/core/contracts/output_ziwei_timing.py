"""Ziwei horoscope, childhood limit, horizon lists, and rule catalogue contracts."""

from typing import Annotated, Literal

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_chinese_calendar import LunarDate
from fatebridge.core.contracts.output_ziwei_calendar import ZiweiHoroscopeCalendarBasis
from fatebridge.core.contracts.output_ziwei_palaces import (
    ZiweiAnnualThreeSha,
    ZiweiFlowingStar,
    ZiweiPosition,
    ZiweiRuleset,
    ZiweiRuleTrace,
    ZiweiYearBranchCycles,
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
