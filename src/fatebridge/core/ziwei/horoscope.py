"""Calculate Ziwei progression scopes, childhood limit, Doujun, and batch horizons."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.calendar import (
    calendar_basis,
    lunar_year_ganzhi,
    nominal_age_calendar,
    resolve_exact_month_pillar,
    resolve_ziwei_clock_state,
)
from fatebridge.core.ziwei.stars import (
    ZiweiFlowingScope,
    annual_text_stars,
    annual_three_sha,
    compute_doujun_branch,
    flowing_horoscope_stars,
    year_branch_cycles,
)
from fatebridge.core.ziwei.tables import (
    DEFAULT_ZIWEI_AGE_DIVIDE,
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    DEFAULT_ZIWEI_SCHOOL,
    DEFAULT_ZIWEI_YEAR_DIVIDE,
    ZIWEI_PALACE_SEQUENCE,
    ZIWEI_SIHUA_RULES,
    effective_lunar_month,
    resolve_school_and_profile,
    sihua_rules_for,
    validate_age_divide,
    validate_day_divide,
    validate_horoscope_divide,
    validate_sihua_source,
    ziwei_ruleset_metadata,
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

CHILDHOOD_PALACES = (
    "命宫",
    "财帛宫",
    "疾厄宫",
    "夫妻宫",
    "福德宫",
    "官禄宫",
)


def _palace_by_branch(palaces: list[dict[str, Any]], branch: str) -> dict[str, Any]:
    palace = next((p for p in palaces if p["ganzhi"][1] == branch), None)
    if palace is None:
        raise ValueError(f"未找到地支为 {branch!r} 的宫位")
    return palace


def palace_for_nominal_age(
    palaces: list[dict[str, Any]], nominal_age: int
) -> dict[str, Any]:
    for palace in palaces:
        lo, hi = (int(x) for x in palace["daxian"].split("~"))
        if lo <= nominal_age <= hi:
            return palace
    first_age = min(int(p["daxian"].split("~")[0]) for p in palaces)
    if 1 <= nominal_age < first_age:
        raise ValueError("按所选五行局起岁，尚未起正式大限")
    raise ValueError("目标虚岁超出紫微大限支持范围")


def xiaoxian_branch(year_branch: str, nominal_age: int, gender: str) -> str:
    canonical_gender = normalize_gender(gender)
    if canonical_gender not in {"男", "女"}:
        raise ValueError("紫微小限顺逆需要明确性别，不能用未知性别代替女命")
    start = XIAOXIAN_START_BY_YEAR_BRANCH[year_branch]
    start_branch_index = ZIWEI_BRANCH_SEQUENCE.index(start)
    age_offset = (nominal_age - 1) % 12
    direction = 1 if canonical_gender == "男" else -1
    return ZIWEI_BRANCH_SEQUENCE[(start_branch_index + direction * age_offset) % 12]


def scope_palace_map(
    ming_branch: str,
    palaces: list[dict[str, Any]],
) -> dict[str, str]:
    """Compact 12-palace functional mapping: scope_palace_name -> 'branch:natal_palace_name'."""
    by_branch = {p["ganzhi"][1]: p["name"] for p in palaces}
    index = ZIWEI_BRANCH_SEQUENCE.index(ming_branch)
    return {
        role: f"{(b := ZIWEI_BRANCH_SEQUENCE[(index + offset) % 12])}:{by_branch[b]}"
        for offset, role in enumerate(ZIWEI_PALACE_SEQUENCE)
    }


def _scope_roles_by_branch(
    ming_branch: str,
) -> dict[str, str]:
    index = ZIWEI_BRANCH_SEQUENCE.index(ming_branch)
    return {
        ZIWEI_BRANCH_SEQUENCE[(index + offset) % 12]: role
        for offset, role in enumerate(ZIWEI_PALACE_SEQUENCE)
    }


def _link_mutagen_to_natal_stars(
    mutagen: dict[str, str],
    palaces: list[dict[str, Any]],
    roles: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for transformation, star_name in mutagen.items():
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
            continue
        for palace, star in matches:
            branch = palace["ganzhi"][1]
            entry: dict[str, Any] = {
                "transformation": transformation,
                "star": star_name,
                "natal_palace_name": palace["name"],
                "natal_branch": branch,
            }
            if star["brightness"] is not None:
                entry["natal_star_brightness"] = star["brightness"]
            if star["mutagen"] is not None:
                entry["natal_mutagen"] = star["mutagen"]
            if roles is not None:
                entry["scope_palace_name"] = roles[branch]
            links.append(entry)
    return links


def _horoscope_scope(
    scope: str,
    palace: dict[str, Any],
    stem: str,
    sihua_rules: dict[str, dict[str, str]],
) -> dict[str, Any]:
    branch = palace["ganzhi"][1]
    return {
        "scope": scope,
        "scope_palace_role": "ming_palace_activity_index",
        "natal_palace_name": palace["name"],
        "branch": branch,
        "branch_index": ZIWEI_BRANCH_SEQUENCE.index(branch),
        "palace_ganzhi": palace["ganzhi"],
        "stem": stem,
        "mutagen": dict(sihua_rules[stem]),
    }


def _unavailable_gender_scope(
    scope: str, *, first_age: int | None = None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "scope": scope,
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
    return record


def _build_childhood_limit(
    palaces: list[dict[str, Any]],
    nominal_age: int,
    first_daxian_age: int,
    sihua_rules: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Active 童限 for ages 1–6 (一命二财三疾厄，四岁夫妻五福德，六岁事业)."""
    if 1 <= nominal_age <= 6:
        palace_name = CHILDHOOD_PALACES[nominal_age - 1]
        palace = next(p for p in palaces if p["name"] == palace_name)
        stem = palace["ganzhi"][0]
        branch = palace["ganzhi"][1]
        mutagen = dict(sihua_rules[stem])
        pmap = scope_palace_map(branch, palaces)
        roles = _scope_roles_by_branch(branch)
        return {
            "status": "active",
            "nominal_age": nominal_age,
            "first_daxian_age": first_daxian_age,
            "natal_palace_name": palace["name"],
            "branch": branch,
            "palace_ganzhi": palace["ganzhi"],
            "stem": stem,
            "mutagen": mutagen,
            "mutagen_natal_links": _link_mutagen_to_natal_stars(
                mutagen, palaces, roles
            ),
            "palace_map": pmap,
        }
    return {
        "status": "not_active",
        "nominal_age": nominal_age,
        "first_daxian_age": first_daxian_age,
        "natal_palace_name": None,
        "branch": None,
        "palace_ganzhi": None,
        "stem": None,
        "mutagen": None,
    }


def _natal_prerequisites(chart: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "ziwei_horoscope_natal_prerequisites_v2",
        "origin": "same_calculation_internal_natal_chart",
        "ruleset": {
            key: chart["ruleset"][key]
            for key in (
                "id",
                "version",
                "school",
                "astro_type",
                "sihua_source",
                "leap_month_rule",
            )
            if key in chart["ruleset"]
        },
        "lunar_date": dict(chart["lunar_date"]),
        "year_stem": chart["year_stem"],
        "hour_branch": chart["hour_branch"],
        "ming_gong": dict(chart["ming_gong"]),
        "shen_gong": dict(chart["shen_gong"]),
        "wuxing_ju": dict(chart["wuxing_ju"]),
    }


def build_decadal_list(
    palaces: list[dict[str, Any]],
    sihua_rules: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        (p for p in palaces if p.get("daxian_period") is not None),
        key=lambda p: int(p["daxian_period"]),
    )
    return [
        {
            "period": p["daxian_period"],
            "age_range": p["daxian"],
            "natal_palace_name": p["name"],
            "branch": p["ganzhi"][1],
            "stem": p["ganzhi"][0],
            "palace_ganzhi": p["ganzhi"],
            "mutagen": dict(sihua_rules[p["ganzhi"][0]]),
        }
        for p in ordered
    ]


def build_yearly_list(
    palaces: list[dict[str, Any]],
    *,
    birth_lunar_year: int,
    natal_year_branch: str,
    start_lunar_year: int,
    gender: str,
    sihua_rules: dict[str, dict[str, str]],
    count: int = 10,
) -> list[dict[str, Any]]:
    canonical_gender = normalize_gender(gender)
    known = canonical_gender in {"男", "女"}
    rows: list[dict[str, Any]] = []
    for offset in range(count):
        yr = start_lunar_year + offset
        age = yr - birth_lunar_year + 1
        stem, branch = lunar_year_ganzhi(yr)
        palace = _palace_by_branch(palaces, branch)
        rows.append(
            {
                "lunar_year": yr,
                "nominal_age": age,
                "year_ganzhi": f"{stem}{branch}",
                "natal_palace_name": palace["name"],
                "branch": branch,
                "xiaoxian_branch": (
                    xiaoxian_branch(natal_year_branch, age, canonical_gender)
                    if known and age >= 1
                    else None
                ),
                "mutagen": dict(sihua_rules[stem]),
            }
        )
    return rows


def build_monthly_list(
    palaces: list[dict[str, Any]],
    *,
    target_year_stem: str,
    doujun_branch: str,
    sihua_rules: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    doujun_idx = ZIWEI_BRANCH_SEQUENCE.index(doujun_branch)
    yin_stem_base = (HEAVENLY_STEMS.index(target_year_stem) * 2 + 2) % 10
    rows: list[dict[str, Any]] = []
    for month_num in range(1, 13):
        m_branch = ZIWEI_BRANCH_SEQUENCE[(doujun_idx + month_num - 1) % 12]
        m_stem = HEAVENLY_STEMS[(yin_stem_base + month_num - 1) % 10]
        palace = _palace_by_branch(palaces, m_branch)
        rows.append(
            {
                "lunar_month": month_num,
                "month_ganzhi": f"{m_stem}{ZIWEI_BRANCH_SEQUENCE[(month_num - 1) % 12]}",
                "palace_branch": m_branch,
                "natal_palace_name": palace["name"],
                "palace_ganzhi": palace["ganzhi"],
                "mutagen": dict(sihua_rules[m_stem]),
            }
        )
    return rows


def build_ziwei_horoscope(
    *,
    chart: dict[str, Any],
    gender: str,
    target_seed: MetaphysicsSeed,
    birth_seed: MetaphysicsSeed | None = None,
    nominal_age_basis: str = "birth_civil_timezone",
    day_divide: str | None = None,
    horoscope_divide: str | None = None,
    age_divide: str | None = None,
    include_decadal_list: bool = False,
    include_yearly_list: bool = False,
    include_monthly_list: bool = False,
) -> dict[str, Any]:
    """Compute six horoscope scopes, active childhood limit, Doujun, and optional horizons."""
    palaces = chart["palaces"]
    ruleset_in = chart.get("ruleset", {})
    school, rule_profile = resolve_school_and_profile(
        ruleset_in.get("school", DEFAULT_ZIWEI_SCHOOL),
        ruleset_in.get("id", DEFAULT_ZIWEI_PROFILE),
    )
    astro_type = ruleset_in.get("astro_type", "heaven")
    sihua_source = validate_sihua_source(ruleset_in.get("sihua_source", "rule_profile"))
    chart_day_divide = validate_day_divide(
        str(
            ruleset_in.get("day_divide")
            or chart.get("calendar_rules", {}).get("day_divide")
            or DEFAULT_ZIWEI_DAY_DIVIDE
        )
    )
    resolved_day_divide = (
        validate_day_divide(day_divide) if day_divide is not None else chart_day_divide
    )
    if resolved_day_divide != chart_day_divide:
        raise ValueError("本命与运限晚子分日口径不一致，须按同一口径重建命盘")
    resolved_year_divide = ruleset_in.get("year_divide", DEFAULT_ZIWEI_YEAR_DIVIDE)
    resolved_horoscope_divide = validate_horoscope_divide(
        horoscope_divide
        if horoscope_divide is not None
        else ruleset_in.get("horoscope_divide", DEFAULT_ZIWEI_HOROSCOPE_DIVIDE)
    )
    resolved_age_divide = validate_age_divide(
        age_divide
        if age_divide is not None
        else ruleset_in.get("age_divide", DEFAULT_ZIWEI_AGE_DIVIDE)
    )
    leap_policy = ruleset_in.get("leap_month_rule")

    sihua_rules = sihua_rules_for(
        ZIWEI_SIHUA_RULES,
        rule_profile,
        sihua_source=sihua_source,
        school=school,
    )

    natal_lunar = chart["lunar_date"]
    age_calendar = nominal_age_calendar(
        birth_seed=birth_seed,
        target_seed=target_seed,
        birth_placement_year=int(natal_lunar["year"]),
        basis=nominal_age_basis,
        day_divide=resolved_day_divide,
        age_divide=resolved_age_divide,
    )
    target_state = resolve_ziwei_clock_state(
        target_seed,
        resolved_day_divide,
        technique="紫微斗数运限",
        year_divide=resolved_year_divide,
    )
    nominal_age = age_calendar["nominal_age"]
    natal_year_branch = lunar_year_ganzhi(int(natal_lunar["year"]))[1]
    target_year_stem, target_year_branch = (
        target_state.year_stem,
        target_state.year_branch,
    )

    canonical_gender = normalize_gender(gender)
    is_gender_known = canonical_gender in {"男", "女"}
    first_daxian_age = int(chart["wuxing_ju"]["number"])
    if nominal_age < first_daxian_age:
        daxian: dict[str, Any] = {
            "scope": "大限",
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
            "unavailable_reason": "before_bureau_start_age",
            "first_age": first_daxian_age,
        }
    elif not is_gender_known:
        daxian = _unavailable_gender_scope("大限", first_age=first_daxian_age)
    else:
        daxian_palace = palace_for_nominal_age(palaces, nominal_age)
        daxian = _horoscope_scope(
            "大限", daxian_palace, daxian_palace["ganzhi"][0], sihua_rules
        )
        daxian["status"] = "computed"
        daxian["first_age"] = first_daxian_age

    if not is_gender_known:
        xiaoxian = _unavailable_gender_scope("小限")
    else:
        xiao_palace = _palace_by_branch(
            palaces, xiaoxian_branch(natal_year_branch, nominal_age, canonical_gender)
        )
        xiaoxian = _horoscope_scope(
            "小限", xiao_palace, xiao_palace["ganzhi"][0], sihua_rules
        )

    natal_month = int(chart["calendar_rules"]["effective_birth_month"])
    target_month = effective_lunar_month(
        target_state.lunar_month,
        target_state.lunar_day,
        target_state.is_leap_month,
        rule_profile,
        natal_leap_month_policy=leap_policy,
    )
    doujun_branch = compute_doujun_branch(
        target_year_branch, natal_month, chart["hour_branch"]
    )
    doujun_index = ZIWEI_BRANCH_SEQUENCE.index(doujun_branch)

    if resolved_horoscope_divide == "exact":
        month_stem, month_pillar_branch = resolve_exact_month_pillar(
            target_seed.input_datetime,
            target_seed.timezone,
            year_divide=resolved_year_divide,
        )
        exact_month_ordinal = ZIWEI_BRANCH_SEQUENCE.index(month_pillar_branch) + 1
        month_index = (doujun_index + exact_month_ordinal - 1) % 12
    else:
        month_index = (doujun_index + target_month - 1) % 12
        month_stem = HEAVENLY_STEMS[
            (HEAVENLY_STEMS.index(target_year_stem) * 2 + 2 + target_month - 1) % 10
        ]
        month_pillar_branch = ZIWEI_BRANCH_SEQUENCE[(target_month - 1) % 12]

    day_index = (month_index + target_state.lunar_day - 1) % 12
    hour_index = (day_index + EARTHLY_BRANCHES.index(target_state.hour_branch)) % 12

    flowing = [
        _horoscope_scope(
            "流年",
            _palace_by_branch(palaces, target_year_branch),
            target_year_stem,
            sihua_rules,
        )
    ]
    for scope_name, index, stem in (
        ("流月", month_index, month_stem),
        ("流日", day_index, target_state.day_stem),
        ("流时", hour_index, target_state.hour_stem),
    ):
        flowing.append(
            _horoscope_scope(
                scope_name,
                _palace_by_branch(palaces, ZIWEI_BRANCH_SEQUENCE[index]),
                stem,
                sihua_rules,
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
        "目标农历年干" if resolved_year_divide == "normal" else "目标立春年干",
        (
            "目标节气月干"
            if resolved_horoscope_divide == "exact"
            else "目标农历月序五虎遁月干"
        ),
        day_origin,
        hour_origin,
    )
    star_inputs: dict[ZiweiFlowingScope, tuple[str, str]] = {
        "大限": (daxian["branch"], "decadal_palace"),
        "流年": (target_year_branch, "target_lunar_year_pillar"),
        "流月": (
            month_pillar_branch,
            (
                "target_solar_month_pillar"
                if resolved_horoscope_divide == "exact"
                else "target_effective_lunar_month_pillar"
            ),
        ),
        "流日": (target_state.day_branch, "target_day_pillar"),
        "流时": (target_state.hour_branch, "target_hour_pillar"),
    }
    for scope_record, stem_origin in zip(scopes, stem_origins, strict=True):
        if scope_record.get("status") in {"not_started", "unavailable"}:
            continue
        scope_record["stem_origin"] = stem_origin
        pmap = scope_palace_map(scope_record["branch"], palaces)
        scope_record["palace_map"] = pmap
        roles = _scope_roles_by_branch(scope_record["branch"])
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
            flowing_list = flowing_horoscope_stars(
                roles,
                scope=scope,
                stem=scope_record["stem"],
                pillar_branch=pillar_branch,
            )
            if scope == "流年" and rule_profile == "quanshu_v2_excerpt":
                flowing_list.extend(
                    annual_text_stars(roles, year_branch=target_year_branch)
                )
                scope_record["annual_three_sha"] = annual_three_sha(target_year_branch)
            scope_record["flowing_stars"] = {
                row["star"]: f"{row['branch']}({row['scope_palace_name']})"
                for row in flowing_list
            }
        scope_record["mutagen_natal_links"] = _link_mutagen_to_natal_stars(
            scope_record["mutagen"], palaces, roles
        )

    ruleset = ziwei_ruleset_metadata(
        rule_profile,
        school=school,
        astro_type=astro_type,
        sihua_source=sihua_source,
        day_divide=resolved_day_divide,
        year_divide=resolved_year_divide,
        horoscope_divide=resolved_horoscope_divide,
        age_divide=resolved_age_divide,
        natal_leap_month_policy=leap_policy,
    )
    if "brightness_table" in ruleset_in:
        ruleset["brightness_rule"] = ruleset_in["brightness_rule"]
        ruleset["brightness_table"] = dict(ruleset_in["brightness_table"])

    result: dict[str, Any] = {
        "engine": "fatebridge-offline",
        "school": school,
        "astro_type": astro_type,
        "nominal_age": nominal_age,
        "doujun_branch": doujun_branch,
        "annual_cycles": year_branch_cycles(
            target_year_branch, anchor_basis="target_lunar_year_branch", school=school
        ),
        "natal_prerequisites": _natal_prerequisites(chart),
        "nominal_age_calendar": age_calendar,
        "childhood_limit": _build_childhood_limit(
            palaces, nominal_age, first_daxian_age, sihua_rules
        ),
        "calendar_rules": chart["calendar_rules"],
        "ruleset": ruleset,
        "interpretation_scope": {
            "contract_version": "scope_palace_mapping_v4",
            "scope_palace_meaning": "运限命宫活动索引所临的本命宫",
            "transformation_meaning": "本层四化连接本命星位；scope_palace_name 标记本层功能宫",
            "scope_palace_map_supported": True,
            "full_scope_palaces_supported": False,
        },
        "scopes": scopes,
    }
    if include_decadal_list:
        result["decadal_list"] = build_decadal_list(palaces, sihua_rules)
    if include_yearly_list:
        if daxian.get("status") == "computed":
            lo_age = int(
                _palace_by_branch(palaces, daxian["branch"])["daxian"].split("~")[0]
            )
            decade_start_year = int(natal_lunar["year"]) + lo_age - 1
        else:
            decade_start_year = int(natal_lunar["year"])
        result["yearly_list"] = build_yearly_list(
            palaces,
            birth_lunar_year=int(natal_lunar["year"]),
            natal_year_branch=natal_year_branch,
            start_lunar_year=decade_start_year,
            gender=canonical_gender,
            sihua_rules=sihua_rules,
            count=10,
        )
    if include_monthly_list:
        result["monthly_list"] = build_monthly_list(
            palaces,
            target_year_stem=target_year_stem,
            doujun_branch=doujun_branch,
            sihua_rules=sihua_rules,
        )
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
        }
    return result
