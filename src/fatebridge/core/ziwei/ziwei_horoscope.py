"""Calculate Ziwei progression scopes and link them to unchanged natal stars."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.ziwei_age import nominal_age_calendar
from fatebridge.core.ziwei.ziwei_auxiliary import (
    ZiweiFlowingScope,
    flowing_horoscope_stars,
)
from fatebridge.core.ziwei.ziwei_calendar import calendar_basis
from fatebridge.core.ziwei.ziwei_childhood import childhood_limit
from fatebridge.core.ziwei.ziwei_classical import annual_text_stars, annual_three_sha
from fatebridge.core.ziwei.ziwei_cycle_sources import year_branch_cycles
from fatebridge.core.ziwei.ziwei_evidence import (
    horoscope_natal_prerequisites,
    scope_palace_map,
)
from fatebridge.core.ziwei.ziwei_limit_sources import limit_source_evidence
from fatebridge.core.ziwei.ziwei_named_patterns import limit_pattern_evidence
from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    ZIWEI_PALACE_SEQUENCE,
    ZIWEI_SIHUA_RULES,
    effective_lunar_month,
    sihua_rules_for,
    validate_day_divide,
    validate_rule_profile,
    validate_sihua_source,
    ziwei_ruleset_metadata,
)
from fatebridge.core.ziwei.ziwei_sources import sihua_source_comparison
from fatebridge.core.ziwei.ziwei_subperiods import limit_subperiod_evidence
from fatebridge.core.ziwei.ziwei_time_input import (
    lunar_year_ganzhi,
    resolve_ziwei_clock_state,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    ZIWEI_BRANCH_SEQUENCE,
)

XIAOXIAN_START_BY_YEAR_BRANCH = {
    "寅": "辰",
    "午": "辰",
    "戌": "辰",
    "申": "戌",
    "子": "戌",
    "辰": "戌",
    "巳": "未",
    "酉": "未",
    "丑": "未",
    "亥": "丑",
    "卯": "丑",
    "未": "丑",
}


def _palace_by_branch(palaces: list[dict[str, Any]], branch: str) -> dict[str, Any]:
    palace = next((p for p in palaces if p["ganzhi"][1] == branch), None)
    if palace is None:
        raise ValueError(f"未找到地支为 {branch!r} 的宫位")
    else:
        pass
    return palace


def palace_for_nominal_age(
    palaces: list[dict[str, Any]], nominal_age: int
) -> dict[str, Any]:
    for palace in palaces:
        lo, hi = (int(x) for x in palace["daxian"].split("~"))
        if lo <= nominal_age <= hi:
            return palace
        else:
            pass
    first_age = min(int(p["daxian"].split("~")[0]) for p in palaces)
    if 1 <= nominal_age < first_age:
        raise ValueError("按所选五行局起岁，尚未起正式大限；童限不能替代大限取宫")
    else:
        pass
    raise ValueError("目标虚岁超出紫微大限支持范围")


def xiaoxian_branch(year_branch: str, nominal_age: int, gender: str) -> str:
    canonical_gender = normalize_gender(gender)
    if canonical_gender not in {"男", "女"}:
        raise ValueError("紫微小限顺逆需要明确性别，不能用未知性别代替女命")
    else:
        pass
    start = XIAOXIAN_START_BY_YEAR_BRANCH[year_branch]
    start_branch_index = ZIWEI_BRANCH_SEQUENCE.index(start)
    age_offset = (nominal_age - 1) % 12
    direction = 1 if canonical_gender == "男" else -1
    return ZIWEI_BRANCH_SEQUENCE[(start_branch_index + direction * age_offset) % 12]


def _horoscope_scope(
    scope: str,
    palace: dict[str, Any],
    stem: str,
    rule_profile: str,
    *,
    sihua_source: str = "rule_profile",
) -> dict[str, Any]:
    branch = palace["ganzhi"][1]
    return {
        "scope": scope,
        "palace_name": palace["name"],
        # The index names the natal palace occupied by this scope's Ming
        # activity index. It is not a rotated scope-specific functional palace.
        "scope_palace_role": "ming_palace_activity_index",
        "natal_palace_name": palace["name"],
        "branch": branch,
        "branch_index": ZIWEI_BRANCH_SEQUENCE.index(branch),
        "palace_ganzhi": palace["ganzhi"],
        "stem": stem,
        "mutagen": sihua_rules_for(
            ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source
        )[stem],
    }


def _link_mutagen_to_natal_stars(
    scope: dict[str, Any], palaces: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Join the computed transformations to computed natal star placements.

    No scope palace rotation or career interpretation is performed here. Keep
    the natal transformation separately so it cannot be mistaken for the new
    transformation of this scope.
    """
    links = []
    for transformation, star_name in scope["mutagen"].items():
        matches = [
            (palace, star)
            for palace in palaces
            for star in palace["stars_detail"]
            if star["name"] == star_name
        ]
        if not matches:
            links.append(
                {
                    "transformation": transformation,
                    "star": star_name,
                    "status": "not_located_in_natal_chart",
                }
            )
        else:
            pass
        for palace, star in matches:
            links.append(
                {
                    "transformation": transformation,
                    "star": star_name,
                    "status": "matched",
                    "natal_palace_name": palace["name"],
                    "natal_palace_ganzhi": palace["ganzhi"],
                    "natal_branch": palace["ganzhi"][1],
                    "natal_star_label": star["label"],
                    "natal_star_brightness": star["brightness"],
                    "natal_mutagen": star["mutagen"],
                }
            )
    return links


def _unavailable_gender_scope(
    scope: str, *, first_age: int | None = None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "scope": scope,
        "palace_name": None,
        "scope_palace_role": None,
        "natal_palace_name": None,
        "branch": None,
        "branch_index": None,
        "palace_ganzhi": None,
        "stem": None,
        "mutagen": None,
        "palace_map": [],
        "mutagen_natal_links": [],
        "stem_origin": None,
        "status": "unavailable",
        "unavailable_reason": "gender_required_for_direction",
    }
    if first_age is not None:
        record["first_age"] = first_age
    else:
        pass
    return record


def build_ziwei_horoscope(
    *,
    chart: dict[str, Any],
    gender: str,
    target_seed: MetaphysicsSeed,
    birth_seed: MetaphysicsSeed | None = None,
    nominal_age_basis: str = "birth_civil_timezone",
    day_divide: str | None = None,
) -> dict[str, Any]:
    """Six scopes using lunar-year ages and the natal-month/hour Dou Jun.

    Scope ``branch`` identifies the natal palace occupied by the active Ming.
    The scope calendar stem and branch govern its own flowing stars.
    Flowing scopes retain the target clock. Age ordinals use one civil clock
    for both physical endpoints. A chart alone cannot supply its birth instant.
    """
    palaces = chart["palaces"]
    rule_profile = chart.get("ruleset", {}).get("id", DEFAULT_ZIWEI_PROFILE)
    validate_rule_profile(rule_profile)
    sihua_source = chart.get("ruleset", {}).get("sihua_source", "rule_profile")
    validate_sihua_source(sihua_source)
    chart_day_divide = validate_day_divide(
        str(
            chart.get("ruleset", {}).get("day_divide")
            or chart.get("calendar_rules", {}).get("day_divide")
            or DEFAULT_ZIWEI_DAY_DIVIDE
        )
    )
    resolved_day_divide = (
        validate_day_divide(day_divide) if day_divide is not None else chart_day_divide
    )
    if resolved_day_divide != chart_day_divide:
        raise ValueError("本命与运限晚子分日口径不一致，须按同一口径重建命盘")
    else:
        pass
    named_rule = chart.get("ruleset", {}).get("sihua_rule") == "naj_ming_v1"
    named_version = str(chart.get("ruleset", {}).get("version", "")).endswith(
        "+sihua.naj-ming-v1"
    )
    if named_rule != named_version or named_rule != (sihua_source == "naj_ming_v1"):
        raise ValueError("本命四化来源身份不一致，须保留实际所选表的完整规则信息")
    else:
        pass
    if (
        named_rule
        and dict(chart["sihua"])
        != sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)[
            chart["year_stem"]
        ]
    ):
        raise ValueError("本命四化与所选明刊来源不一致，须按实际来源重建命盘")
    else:
        pass

    natal_lunar = chart["lunar_date"]
    age_calendar = nominal_age_calendar(
        birth_seed=birth_seed,
        target_seed=target_seed,
        birth_placement_year=int(natal_lunar["year"]),
        basis=nominal_age_basis,
    )
    target_state = resolve_ziwei_clock_state(
        target_seed, resolved_day_divide, technique="紫微斗数运限"
    )
    nominal_age = age_calendar["nominal_age"]
    natal_year_branch = lunar_year_ganzhi(int(natal_lunar["year"]))[1]
    target_year_stem, target_year_branch = lunar_year_ganzhi(target_state.lunar_year)

    canonical_gender = normalize_gender(gender)
    is_gender_known = canonical_gender in {"男", "女"}
    first_daxian_age = int(chart["wuxing_ju"]["number"])
    daxian: dict[str, Any]
    if nominal_age < first_daxian_age:
        # The six literal childhood labels do not establish a substitute
        # formal decade, a decade palace stem, or decade transformations.
        # Retain the scope slot with explicit nulls so absence is observable.
        daxian = {
            "scope": "大限",
            "palace_name": None,
            "scope_palace_role": None,
            "natal_palace_name": None,
            "branch": None,
            "branch_index": None,
            "palace_ganzhi": None,
            "stem": None,
            "mutagen": None,
            "palace_map": [],
            "mutagen_natal_links": [],
            "stem_origin": None,
            "status": "not_started",
            "unavailable_reason": "before_selected_bureau_start_no_childhood_substitution",
            "first_age": first_daxian_age,
        }
    elif not is_gender_known:
        daxian = _unavailable_gender_scope("大限", first_age=first_daxian_age)
    else:
        daxian_palace = palace_for_nominal_age(palaces, nominal_age)
        daxian = _horoscope_scope(
            "大限",
            daxian_palace,
            daxian_palace["ganzhi"][0],
            rule_profile,
            sihua_source=sihua_source,
        )
        daxian["status"] = "computed"
        daxian["first_age"] = first_daxian_age

    if not is_gender_known:
        xiaoxian = _unavailable_gender_scope("小限")
    else:
        xiao_palace = _palace_by_branch(
            palaces, xiaoxian_branch(natal_year_branch, nominal_age, canonical_gender)
        )
        # 小限 四化 follows the 宫干 of the 小限 palace (iztro convention), not the 流年 stem.
        xiaoxian = _horoscope_scope(
            "小限",
            xiao_palace,
            xiao_palace["ganzhi"][0],
            rule_profile,
            sihua_source=sihua_source,
        )

    natal_month = chart["calendar_rules"]["effective_birth_month"]
    target_month = effective_lunar_month(
        target_state.lunar_month,
        target_state.lunar_day,
        target_state.is_leap_month,
        # note (ziwei): Flowing leap months retain the default convention for both natal profiles.
        DEFAULT_ZIWEI_PROFILE,
    )
    # Reverse from the year's palace to birth month, then forward to birth
    # hour; the result is 正月斗君. Count the target month/day/hour from it.
    doujun_index = (
        ZIWEI_BRANCH_SEQUENCE.index(target_year_branch)
        - natal_month
        + EARTHLY_BRANCHES.index(chart["hour_branch"])
        + 1
    ) % 12
    month_index = (doujun_index + target_month - 1) % 12
    day_index = (month_index + target_state.lunar_day - 1) % 12
    hour_index = (day_index + EARTHLY_BRANCHES.index(target_state.hour_branch)) % 12
    month_stem = HEAVENLY_STEMS[
        (HEAVENLY_STEMS.index(target_year_stem) * 2 + 2 + target_month - 1) % 10
    ]
    flowing = [
        _horoscope_scope(
            "流年",
            _palace_by_branch(palaces, target_year_branch),
            target_year_stem,
            rule_profile,
            sihua_source=sihua_source,
        )
    ]
    for scope, index, stem in (
        ("流月", month_index, month_stem),
        ("流日", day_index, target_state.day_stem),
        ("流时", hour_index, target_state.hour_stem),
    ):
        flowing.append(
            _horoscope_scope(
                scope,
                _palace_by_branch(palaces, ZIWEI_BRANCH_SEQUENCE[index]),
                stem,
                rule_profile,
                sihua_source=sihua_source,
            )
        )

    scopes = [daxian, xiaoxian, *flowing]
    if target_state.is_late_zi:
        day_origin = (
            "目标次日日干（晚子算次日）"
            if resolved_day_divide == "forward"
            else "目标当日日干（晚子算当日）"
        )
        hour_origin = (
            "目标次日早子时干（晚子算次日）"
            if resolved_day_divide == "forward"
            else "目标当日早子时干（晚子算当日）"
        )
    else:
        day_origin = "目标日柱天干"
        hour_origin = "目标时柱天干"
    stem_origins = (
        "本命所临宫干",
        "本命所临宫干",
        "目标农历年干",
        "目标农历月序五虎遁月干",
        day_origin,
        hour_origin,
    )
    star_inputs: dict[ZiweiFlowingScope, tuple[str, str]] = {
        "大限": (daxian["branch"], "decadal_palace"),
        "流年": (target_year_branch, "target_lunar_year_pillar"),
        "流月": (
            ZIWEI_BRANCH_SEQUENCE[(target_month - 1) % 12],
            "target_effective_lunar_month_pillar",
        ),
        "流日": (target_state.day_branch, "target_day_pillar"),
        "流时": (target_state.hour_branch, "target_hour_pillar"),
    }
    for scope_record, stem_origin in zip(scopes, stem_origins, strict=True):
        if scope_record.get("status") in {"not_started", "unavailable"}:
            continue
        scope_record["stem_origin"] = stem_origin
        scope_record["palace_map"] = scope_palace_map(
            scope_record["branch"], palaces, ZIWEI_PALACE_SEQUENCE
        )
        scope = scope_record["scope"]
        if scope in star_inputs:
            pillar_branch, branch_origin = star_inputs[scope]
            scope_record["flowing_star_basis"] = {
                "stem": scope_record["stem"],
                "branch": pillar_branch,
                "branch_origin": branch_origin,
            }
            if scope == "流月":
                scope_record["flowing_star_basis"].update(
                    effective_lunar_month=target_month,
                    lunar_date={
                        "year": target_state.lunar_year,
                        "month": target_state.lunar_month,
                        "day": target_state.lunar_day,
                        "is_leap_month": target_state.is_leap_month,
                    },
                )
            scope_record["flowing_stars"] = flowing_horoscope_stars(
                scope_record["palace_map"],
                scope=scope,
                stem=scope_record["stem"],
                pillar_branch=pillar_branch,
            )
        if scope == "流年" and rule_profile == "quanshu_v2_excerpt":
            scope_record["flowing_stars"].extend(
                annual_text_stars(
                    scope_record["palace_map"], year_branch=target_year_branch
                )
            )
            scope_record["annual_three_sha"] = annual_three_sha(target_year_branch)
        scope_record["mutagen_natal_links"] = _link_mutagen_to_natal_stars(
            scope_record, palaces
        )
        roles = {
            p["branch"]: p["scope_palace_name"] for p in scope_record["palace_map"]
        }
        for link in scope_record["mutagen_natal_links"]:
            if link["status"] == "matched":
                link["scope_palace_name"] = roles[link["natal_branch"]]
            else:
                pass

    table_evidence = sihua_source_comparison(
        sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source),
        compared_assignments_applied=sihua_source == "naj_ming_v1",
    )
    table_evidence.update(
        scope="natal_table_reused_for_scopes_by_software_convention",
        dynamic_reuse_classically_verified=False,
    )
    lu_ma_branches = {
        star["name"]: palace["ganzhi"][1]
        for palace in palaces
        for star in palace["stars_detail"]
        if star["name"] in {"禄存", "天马"}
    }
    ruleset = ziwei_ruleset_metadata(
        rule_profile,
        sihua_source=sihua_source,
        day_divide=resolved_day_divide,
        natal_leap_month_policy=chart["ruleset"]["leap_month_rule"],
    )
    if "brightness_table" in chart["ruleset"]:
        ruleset.update(
            brightness_rule=chart["ruleset"]["brightness_rule"],
            brightness_table=deepcopy(chart["ruleset"]["brightness_table"]),
            unresolved=list(chart["ruleset"]["unresolved"]),
        )
    result: dict[str, Any] = {
        "engine": "fatebridge-offline",
        "annual_cycles": year_branch_cycles(
            target_year_branch, anchor_basis="target_lunar_year_branch"
        ),
        "natal_prerequisites": horoscope_natal_prerequisites(chart),
        "nominal_age": nominal_age,
        "nominal_age_calendar": age_calendar,
        "sihua_source_comparison": table_evidence,
        "childhood_limit": childhood_limit(chart, nominal_age),
        "ming_limit_subperiods": limit_subperiod_evidence(
            palaces, scopes, nominal_age=nominal_age
        ),
        "named_pattern_limit_evidence": limit_pattern_evidence(
            target_lunar_year=target_state.lunar_year,
            annual_branch=target_year_branch,
            daxian_branch=daxian["branch"],
            xiaoxian_branch=xiaoxian["branch"],
            natal_lucun_branch=lu_ma_branches.get("禄存"),
            natal_tianma_branch=lu_ma_branches.get("天马"),
        ),
        "calendar_rules": chart["calendar_rules"],
        "ruleset": ruleset,
        "source_comparison": limit_source_evidence(
            chart,
            scopes,
            nominal_age=nominal_age,
            gender=canonical_gender,
            natal_year_branch=natal_year_branch,
            target_year_branch=target_year_branch,
            actual_doujun_branch=ZIWEI_BRANCH_SEQUENCE[doujun_index],
        ),
        "interpretation_scope": {
            "contract_version": "scope_palace_mapping_v3",
            "scope_palace_meaning": "运限命宫活动索引所临的本命宫",
            "transformation_meaning": "本层四化连接本命星位；scope_palace_name 单独标记本层功能宫",
            "scope_palace_map_supported": True,
            "full_scope_palaces_supported": False,
            "limitations": [
                "已提供十二宫功能名映射与部分流曜，范围由所选规则配置与实际字段确定；未提供全部流曜及飞宫体系",
                "本命星位未随旋宫搬移",
                "未起正式大限时该层标记not_started，不取童限宫、不生成大限四化；其他层分别计算",
                "未据此判定职业事件或吉凶",
            ],
        },
        "scopes": scopes,
    }
    if "calendar_basis" in chart:
        result["calendar_basis"] = {
            "birth": chart["calendar_basis"],
            "target": calendar_basis(
                target_seed,
                placement_label=target_state.placement_label,
                placement_context=target_state.lunar,
                day_divide=resolved_day_divide,
            ),
            "nominal_age_rule": age_calendar["rule"],
            "age_boundary_classically_verified": age_calendar[
                "age_boundary_classically_verified"
            ],
        }
    return result
