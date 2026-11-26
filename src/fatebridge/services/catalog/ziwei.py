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

_COMPACT_RULESET_KEYS = (
    "id",
    "school",
    "astro_type",
    "day_divide",
    "year_divide",
    "horoscope_divide",
    "age_divide",
    "leap_month_rule",
    "sihua_rule",
    "brightness_rule",
)


def _slim_ruleset(ruleset: dict) -> dict:
    return {k: ruleset[k] for k in _COMPACT_RULESET_KEYS if k in ruleset}


def _compact_ziwei_birth(result: ServiceResult) -> ServiceResult:
    birth = result["ziwei_birth"]
    compact_birth: dict = {
        "engine": birth["engine"],
        "ruleset": {
            k: birth["ruleset"][k]
            for k in (
                "id",
                "school",
                "astro_type",
                "day_divide",
                "leap_month_rule",
                "sihua_rule",
            )
            if k in birth["ruleset"]
        },
        "calendar_rules": {
            "effective_birth_month": birth["calendar_rules"]["effective_birth_month"],
            "day_divide": birth["calendar_rules"]["day_divide"],
        },
        "ming_gong": birth["ming_gong"],
        "shen_gong": birth["shen_gong"],
        "laiyin_gong": birth["laiyin_gong"],
        "zidou_branch": birth["zidou_branch"],
        "wuxing_ju": {
            "label": birth["wuxing_ju"]["label"],
            "number": birth["wuxing_ju"]["number"],
        },
        "sihua": birth["sihua"],
        "chart_masters": {
            "life": birth["chart_masters"]["life"]["star"],
            "body": birth["chart_masters"]["body"]["star"],
        },
        "calendar_cycles": {
            k: birth["calendar_cycles"][k]
            for k in ("status", "changsheng_rule", "boshi_rule")
            if k in birth.get("calendar_cycles", {})
        },
        "reading_view": birth["reading_view"],
    }
    patterns = birth.get("named_patterns")
    if isinstance(patterns, dict):
        compact_birth["named_patterns"] = {
            "matched_count": patterns.get("matched_count"),
            "matched": [row["name"] for row in patterns.get("matched", [])],
        }
    return {
        "analysis_type": result["analysis_type"],
        "analysis_context": {
            "corrected_datetime": result["analysis_context"]["corrected_datetime"],
            "lunar_display": result["analysis_context"].get("lunar_display"),
            "timezone": result["analysis_context"]["timezone"],
        },
        "ziwei_birth": compact_birth,
    }


def _compact_ziwei_horoscope(result: ServiceResult) -> ServiceResult:
    horoscope = result["ziwei_horoscope"]
    scope_fields = {
        "scope",
        "status",
        "unavailable_reason",
        "first_age",
        "natal_palace_name",
        "branch",
        "stem",
        "palace_ganzhi",
        "mutagen",
    }
    compact_scopes = []
    for scope in horoscope["scopes"]:
        entry = {k: v for k, v in scope.items() if k in scope_fields}
        links = scope.get("mutagen_natal_links")
        if links:
            entry["mutagen_natal_links"] = [
                f"{l['transformation']}:{l['star']}@{l.get('natal_palace_name') or '?'}({l.get('scope_palace_name') or '?'})"
                for l in links
            ]
        stars = scope.get("flowing_stars")
        if stars:
            entry["flowing_stars"] = (
                stars
                if isinstance(stars, dict)
                else {
                    s["star"]: f"{s['branch']}({s['scope_palace_name']})" for s in stars
                }
            )
        if "annual_three_sha" in scope:
            entry["annual_three_sha"] = scope["annual_three_sha"]["branches"]
        compact_scopes.append(entry)

    compact_horoscope: dict = {
        "engine": horoscope["engine"],
        "school": horoscope["school"],
        "astro_type": horoscope["astro_type"],
        "nominal_age": horoscope["nominal_age"],
        "doujun_branch": horoscope["doujun_branch"],
        "ruleset": _slim_ruleset(horoscope["ruleset"]),
    }
    childhood = horoscope.get("childhood_limit")
    if isinstance(childhood, dict):
        if childhood.get("status") == "active":
            compact_horoscope["childhood_limit"] = {
                k: childhood[k]
                for k in (
                    "status",
                    "nominal_age",
                    "natal_palace_name",
                    "branch",
                    "palace_ganzhi",
                    "stem",
                    "mutagen",
                )
                if k in childhood
            }
        else:
            compact_horoscope["childhood_limit"] = {
                "status": childhood.get("status"),
                "first_daxian_age": childhood.get("first_daxian_age"),
            }
    compact_horoscope["scopes"] = compact_scopes
    for list_key in ("decadal_list", "yearly_list", "monthly_list"):
        if list_key in horoscope:
            compact_horoscope[list_key] = horoscope[list_key]

    return {
        "analysis_type": result["analysis_type"],
        "birth_context": {
            "corrected_datetime": result["birth_context"]["corrected_datetime"],
            "lunar_display": result["birth_context"].get("lunar_display"),
            "timezone": result["birth_context"]["timezone"],
        },
        "analysis_context": {
            "analysis_datetime": result["analysis_context"]["analysis_datetime"],
            "lunar_display": result["analysis_context"].get("lunar_display"),
            "timezone": result["analysis_context"]["timezone"],
        },
        "ziwei_horoscope": compact_horoscope,
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
        summary="紫微斗数本命盘（支持三合/中州/全书/飞星流派、天地人三盘、12宫飞星四化矩阵、来因宫、子斗及36项古典格局）。",
        operation_label_zh="紫微命盘",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/birth-chart",
        compact_view=_compact_ziwei_birth,
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
        compact_view=_compact_ziwei_horoscope,
    ),
    ToolSpec(
        name="ziwei_rules",
        bind=bind_kwargs(calculate_ziwei_rules),
        request_model_loader=request_model_ref(_ZIWEI_REQ, "ZiweiRulesRequest"),
        summary="紫微斗数规则查表：按年干与流派返回四化及格局目录。",
        operation_label_zh="紫微规则",
        family="metaphysics",
        rest_path="/api/ziwei/rules",
        compact_view=_compact_ziwei_rules,
    ),
]
