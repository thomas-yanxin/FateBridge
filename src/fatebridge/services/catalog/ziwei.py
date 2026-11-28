"""Zi Wei Dou Shu tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy

_ZIWEI_REQ = "fatebridge.core.requests.ziwei"

calculate_ziwei_birth = service_ref(
    "fatebridge.services.ziwei", "calculate_ziwei_birth"
)
calculate_ziwei_horoscope = service_ref(
    "fatebridge.services.ziwei", "calculate_ziwei_horoscope"
)
calculate_ziwei_rules = service_ref(
    "fatebridge.services.ziwei", "calculate_ziwei_rules"
)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="ziwei_birth_chart",
        bind=bind_person(calculate_ziwei_birth, also_pass=("birth_utc_offset",)),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiBirthRequest"),
        summary="紫微斗数本命盘（支持三合/中州/全书/飞星流派、天地人三盘、12宫飞星四化矩阵、来因宫、子斗及36项古典格局）。",
        operation_label_zh="紫微命盘",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/birth-chart",
        default_omit=(
            "person_info",
            "ziwei_birth.palaces",
            "ziwei_birth.flying_sihua",
            "ziwei_birth.void_systems",
            "ziwei_birth.calendar_basis",
            "ziwei_birth.calendar_cycles.year_branch_cycles",
        ),
    ),
    ToolSpec(
        name="ziwei_timing",
        bind=bind_person(calculate_ziwei_horoscope, also_pass=("birth_utc_offset",)),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiHoroscopeRequest"),
        summary="紫微斗数运限（大限/童限/小限/流年/流月/流日/流时、流年斗君、及可选大限/流年/流月批量列表）。",
        operation_label_zh="紫微运限",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/timing",
        default_omit=(
            "person_info",
            "ziwei_horoscope.annual_cycles",
            "ziwei_horoscope.natal_prerequisites",
            "ziwei_horoscope.nominal_age_calendar",
            "ziwei_horoscope.calendar_basis",
            "ziwei_horoscope.interpretation_scope",
            "ziwei_horoscope.calendar_rules",
            "ziwei_horoscope.scopes.*.scope_palace_role",
            "ziwei_horoscope.scopes.*.branch_index",
            "ziwei_horoscope.scopes.*.stem_origin",
            "ziwei_horoscope.scopes.*.palace_map",
            "ziwei_horoscope.scopes.*.flowing_star_basis",
            "ziwei_horoscope.scopes.*.flowing_stars",
        ),
        reproducibility=ReproducibilityPolicy(
            current_time_fields=(
                "analysis_year",
                "analysis_month",
                "analysis_day",
                "analysis_hour",
                "analysis_minute",
            )
        ),
    ),
    ToolSpec(
        name="ziwei_rules",
        bind=bind_kwargs(calculate_ziwei_rules),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiRulesRequest"),
        summary="紫微斗数规则查表：按年干与流派返回四化及格局目录。",
        operation_label_zh="紫微规则",
        family="metaphysics",
        rest_path="/api/ziwei/rules",
        default_omit=("rule_catalogue.named_patterns",),
    ),
]
