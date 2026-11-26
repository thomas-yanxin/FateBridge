"""Zi Wei Dou Shu tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import ServiceResult, ToolSpec

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


def _compact_ziwei_horoscope(result: ServiceResult) -> ServiceResult:
    horoscope = result["ziwei_horoscope"]
    fields = {
        "scope",
        "status",
        "unavailable_reason",
        "first_age",
        "palace_name",
        "scope_palace_role",
        "branch",
        "stem",
        "stem_origin",
        "mutagen",
    }
    return {
        **result,
        "ziwei_horoscope": {
            **{
                key: value for key, value in horoscope.items() if key != "annual_cycles"
            },
            "scopes": [
                {key: value for key, value in scope.items() if key in fields}
                for scope in horoscope["scopes"]
            ],
        },
    }


def _compact_ziwei_rules(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "rule_catalogue": {
            key: value
            for key, value in result["rule_catalogue"].items()
            if key != "named_patterns"
        },
    }


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="ziwei_birth_chart",
        bind=bind_person(calculate_ziwei_birth, also_pass=("birth_utc_offset",)),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiBirthRequest"),
        summary="紫微斗数本命盘（星位、结构与循环来源；四化可显式选明刊原表，未知性别保留可确定标记）。",
        operation_label_zh="紫微命盘",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/birth-chart",
    ),
    ToolSpec(
        name="ziwei_timing",
        bind=bind_person(calculate_ziwei_horoscope, also_pass=("birth_utc_offset",)),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiHoroscopeRequest"),
        summary="紫微斗数运限（六层索引与童限）；沿用所选四化表，未知性别仅大限/小限标不可定。",
        operation_label_zh="紫微运限",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/timing",
        compact_view=_compact_ziwei_horoscope,
    ),
    ToolSpec(
        name="ziwei_rules",
        bind=bind_kwargs(calculate_ziwei_rules),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiRulesRequest"),
        summary="紫微斗数规则查表：按年干返回四化参照；排盘用 ziwei_birth_chart/ziwei_timing。",
        operation_label_zh="紫微规则",
        family="metaphysics",
        rest_path="/api/ziwei/rules",
        compact_view=_compact_ziwei_rules,
    ),
]
