"""Build Ziwei natal charts and publish their rule catalogue."""

from __future__ import annotations

from typing import Any, TypedDict

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.calendar import calendar_basis, resolve_ziwei_clock_state
from fatebridge.core.ziwei.flying import build_flying_sihua
from fatebridge.core.ziwei.horoscope import (
    build_ziwei_horoscope as build_ziwei_horoscope,
)
from fatebridge.core.ziwei.patterns import (
    ZIWEI_MAJOR_STARS,
    evaluate_named_patterns,
    named_pattern_catalogue,
)
from fatebridge.core.ziwei.stars import (
    attach_natal_cycles,
    chart_masters,
    compute_zidou_branch,
    natal_star_placement,
    year_branch_cycles,
)
from fatebridge.core.ziwei.tables import (
    DEFAULT_ZIWEI_ASTRO_TYPE,
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    DEFAULT_ZIWEI_SCHOOL,
    DEFAULT_ZIWEI_YEAR_DIVIDE,
    ZIWEI_NATAL_LEAP_MONTH_LABELS,
    ZIWEI_PALACE_SEQUENCE,
    ZIWEI_SIHUA_RULES,
    ZiweiBrightnessSource,
    ZiweiNatalLeapMonthPolicy,
    brightness_table_for,
    effective_lunar_month,
    natal_leap_month_policy_for,
    resolve_school_and_profile,
    sihua_rules_for,
    split_star_mutagen,
    validate_astro_type,
    validate_day_divide,
    validate_sihua_source,
    validate_year_divide,
    ziwei_ruleset_metadata,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    ZIWEI_BRANCH_SEQUENCE,
    get_nayin,
)

__all__ = [
    "ZIWEI_SIHUA_RULES",
    "build_ziwei_chart",
    "build_ziwei_horoscope",
    "build_ziwei_rules",
]

WUXING_JU_NUMBER_BY_ELEMENT: dict[str, int] = {
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "火": 6,
}

WUXING_JU_LABEL_BY_NUMBER: dict[int, str] = {
    2: "水二局",
    3: "木三局",
    4: "金四局",
    5: "土五局",
    6: "火六局",
}


class ZiweiBureau(TypedDict):
    number: int
    element: str
    label: str
    nayin: str


def _resolve_wuxing_ju(ming_stem: str, ming_branch: str) -> ZiweiBureau:
    nayin = get_nayin(ming_stem, ming_branch)
    element = nayin[-1] if nayin and nayin != "未知纳音" else ""
    if element not in WUXING_JU_NUMBER_BY_ELEMENT:
        raise ValueError(f"命宫干支无法确定五行局：{ming_stem}{ming_branch}")
    number = WUXING_JU_NUMBER_BY_ELEMENT[element]
    return {
        "number": number,
        "element": element,
        "label": WUXING_JU_LABEL_BY_NUMBER[number],
        "nayin": nayin,
    }


def _apply_sihua_to_palaces(
    palaces: list[dict[str, Any]],
    sihua: dict[str, str],
) -> dict[str, str]:
    for transformation_label, star_name in sihua.items():
        for palace in palaces:
            if star_name in palace["stars"]:
                palace["stars"] = [
                    f"{label}{transformation_label}" if label == star_name else label
                    for label in palace["stars"]
                ]
                break
    return dict(sihua)


def _palace_structural_evidence(palace: dict[str, Any]) -> dict[str, Any]:
    """Reference 三方四正 branches instead of deepcopying 48x star lists."""
    index = ZIWEI_BRANCH_SEQUENCE.index(palace["ganzhi"][1])
    major = [
        s["name"] for s in palace["stars_detail"] if s["name"] in ZIWEI_MAJOR_STARS
    ]
    return {
        "major_stars": major,
        "is_empty_main_palace": not major,
        "sanfang_sizheng_branches": [
            ZIWEI_BRANCH_SEQUENCE[(index + offset) % 12] for offset in (0, 4, 8, 6)
        ],
        "opposite_stars_relocated": False,
    }


def natal_reading_view(palaces: list[dict[str, Any]]) -> dict[str, Any]:
    """Lossless star facts and branch references for compact first responses."""
    return {
        "schema_version": "ziwei_natal_reading_v1",
        "star_occurrence_count": sum(len(p["stars_detail"]) for p in palaces),
        "distinct_star_count": len(
            {s["name"] for p in palaces for s in p["stars_detail"]}
        ),
        "null_star_fields_omitted": ["brightness", "mutagen"],
        "sanfang_branch_order": ["本宫", "三合", "三合", "对宫"],
        "palaces": [
            {
                "name": p["name"],
                "ganzhi": p["ganzhi"],
                "stars": [
                    {
                        key: star[key]
                        for key in ("name", "brightness", "mutagen")
                        if star[key] is not None
                    }
                    for star in p["stars_detail"]
                ],
                "major_stars": list(p["structural_evidence"]["major_stars"]),
                "sanfang_sizheng_branches": list(
                    p["structural_evidence"]["sanfang_sizheng_branches"]
                ),
                "changsheng12": p["changsheng12"],
                "boshi12": p["boshi12"],
                "daxian": p["daxian"],
            }
            for p in palaces
        ],
    }


def build_ziwei_chart(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
    include_calendar_basis: bool = False,
) -> dict[str, Any]:
    resolved_school, resolved_profile = resolve_school_and_profile(school, rule_profile)
    resolved_astro = validate_astro_type(astro_type)
    resolved_sihua_source = validate_sihua_source(sihua_source)
    resolved_day_divide = validate_day_divide(day_divide)
    resolved_year_divide = validate_year_divide(year_divide)

    state = resolve_ziwei_clock_state(
        seed,
        resolved_day_divide,
        technique="紫微斗数",
        year_divide=resolved_year_divide,
    )
    lunar_day = state.lunar_day
    leap_policy = natal_leap_month_policy_for(resolved_profile, natal_leap_month_policy)
    lunar_month = effective_lunar_month(
        state.lunar_month,
        lunar_day,
        state.is_leap_month,
        resolved_profile,
        natal_leap_month_policy=leap_policy,
    )
    ruleset = ziwei_ruleset_metadata(
        resolved_profile,
        school=resolved_school,
        astro_type=resolved_astro,
        sihua_source=resolved_sihua_source,
        day_divide=resolved_day_divide,
        year_divide=resolved_year_divide,
        natal_leap_month_policy=leap_policy,
    )
    hour_branch = state.hour_branch
    hour_index = EARTHLY_BRANCHES.index(hour_branch) + 1
    year_stem, year_branch = state.year_stem, state.year_branch

    raw_ming_index = (lunar_month - hour_index) % 12
    shen_index = (lunar_month + hour_index - 2) % 12
    fude_index = (raw_ming_index + 2) % 12
    if resolved_astro == "earth":
        ming_index = shen_index
    elif resolved_astro == "human":
        ming_index = fude_index
    else:
        ming_index = raw_ming_index

    ming_branch = ZIWEI_BRANCH_SEQUENCE[ming_index]
    shen_branch = ZIWEI_BRANCH_SEQUENCE[shen_index]

    year_stem_index = HEAVENLY_STEMS.index(year_stem)
    yin_stem_base = (year_stem_index * 2 + 2) % len(HEAVENLY_STEMS)
    palace_stems = [
        HEAVENLY_STEMS[
            (yin_stem_base + (ming_index + offset) % 12) % len(HEAVENLY_STEMS)
        ]
        for offset in range(12)
    ]
    palace_branches = (
        ZIWEI_BRANCH_SEQUENCE[ming_index:] + ZIWEI_BRANCH_SEQUENCE[:ming_index]
    )
    wuxing_ju = _resolve_wuxing_ju(palace_stems[0], palace_branches[0])
    start_age = wuxing_ju["number"]

    is_yang_year = year_stem_index % 2 == 0
    canonical_gender = normalize_gender(gender)
    is_gender_known = canonical_gender in {"男", "女"}
    is_daxian_forward = (canonical_gender == "男" and is_yang_year) or (
        canonical_gender == "女" and not is_yang_year
    )
    daxian_direction_label = (
        ("顺行" if is_daxian_forward else "逆行")
        if is_gender_known
        else "未定（缺少性别）"
    )

    star_placement = natal_star_placement(
        bureau_number=start_age,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        hour_branch=hour_branch,
        year_stem=year_stem,
        year_branch=year_branch,
        ming_branch=ming_branch,
        shen_branch=shen_branch,
        rule_profile=resolved_profile,
        school=resolved_school,
        gender=canonical_gender,
    )
    palaces: list[dict[str, Any]] = []
    for index, palace_name in enumerate(ZIWEI_PALACE_SEQUENCE):
        period_index = index if is_daxian_forward else (-index) % 12
        if resolved_profile == "quanshu_v2_excerpt":
            period_index = (period_index - 1) % 12
        period_start = start_age + period_index * 10
        ganzhi = f"{palace_stems[index]}{palace_branches[index]}"
        palaces.append(
            {
                "name": palace_name,
                "ganzhi": ganzhi,
                "is_original_palace": ganzhi[0] == year_stem
                and ganzhi[1] not in ("子", "丑"),
                "daxian": (
                    f"{period_start}~{period_start + 9}" if is_gender_known else None
                ),
                "daxian_period": period_index + 1 if is_gender_known else None,
                "stars": star_placement.stars_by_branch[palace_branches[index]],
            }
        )

    sihua_rules = sihua_rules_for(
        ZIWEI_SIHUA_RULES,
        resolved_profile,
        sihua_source=resolved_sihua_source,
        school=resolved_school,
    )
    sihua = _apply_sihua_to_palaces(palaces, sihua_rules[year_stem])
    brightness_table = brightness_table_for(resolved_profile, brightness_source)
    explicit_brightness = brightness_source != "rule_profile"
    if explicit_brightness:
        ruleset.update(brightness_table.ruleset_fields())

    for palace in palaces:
        palace_branch = palace["ganzhi"][1]
        palace["stars"] = sorted(set(palace["stars"]))
        detail: list[dict[str, Any]] = []
        for label in palace["stars"]:
            base_name, mutagen = split_star_mutagen(label)
            brightness = brightness_table.lookup(base_name, palace_branch)
            star_detail: dict[str, Any] = {
                "name": base_name,
                "label": label,
                "brightness": brightness,
                "mutagen": mutagen,
            }
            if explicit_brightness:
                star_detail["brightness_source"] = brightness_table.id
            detail.append(star_detail)
        palace["stars_detail"] = detail

    cycle_rules = attach_natal_cycles(
        palaces,
        element=wuxing_ju["element"],
        year_stem=year_stem,
        gender=gender,
        rule_profile=resolved_profile,
    )
    for palace in palaces:
        palace["structural_evidence"] = _palace_structural_evidence(palace)

    ming_palace = palaces[0]
    shen_palace = next(p for p in palaces if p["ganzhi"][1] == shen_branch)
    zidou_branch = compute_zidou_branch(lunar_month, hour_branch)
    flying_sihua = build_flying_sihua(
        palaces,
        sihua_rules,
        year_stem=year_stem,
        sihua_rule=ruleset["sihua_rule"],
    )
    named_patterns = evaluate_named_patterns(
        palaces, ming_branch=ming_branch, shen_branch=shen_branch
    )

    result: dict[str, Any] = {
        "engine": "fatebridge-offline",
        "school": resolved_school,
        "astro_type": resolved_astro,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "reading_view": natal_reading_view(palaces),
        "named_patterns": named_patterns,
        "flying_sihua": flying_sihua,
        "void_systems": {
            "xun": {
                "source_branches": star_placement.xun_void_source_branches,
                "displayed_star_branches": star_placement.xun_void_displayed_branches,
                "display_rule": (
                    "both_branches_as_written"
                    if resolved_profile == "quanshu_v2_excerpt"
                    else "polarity_single_branch"
                ),
            }
        },
        "calendar_cycles": {
            **cycle_rules,
            "year_branch_cycles": year_branch_cycles(
                year_branch,
                anchor_basis="natal_lunar_year_branch",
                school=resolved_school,
            ),
        },
        "chart_masters": chart_masters(
            palaces,
            ming_branch=ming_branch,
            year_branch=year_branch,
            school=resolved_school,
        ),
        "rule_trace": [
            {
                "rule_id": "lunar_month_for_placement",
                "source": leap_policy,
                "inputs": {
                    "month": state.lunar_month,
                    "day": lunar_day,
                    "is_leap_month": state.is_leap_month,
                },
                "outputs": {"effective_month": lunar_month},
            },
            {
                "rule_id": "ming_shen_month_hour",
                "source": f"astro_type={resolved_astro}",
                "inputs": {"effective_month": lunar_month, "hour_branch": hour_branch},
                "outputs": {"ming_branch": ming_branch, "shen_branch": shen_branch},
            },
            {
                "rule_id": "wuhu_dun_nayin_ju",
                "source": "五虎遁与命宫纳音",
                "inputs": {
                    "lunar_year": state.lunar_year,
                    "year_stem": year_stem,
                    "ming_ganzhi": ming_palace["ganzhi"],
                },
                "outputs": {
                    "nayin": wuxing_ju["nayin"],
                    "ju_number": wuxing_ju["number"],
                },
            },
            {
                "rule_id": "ziwei_tianfu_placement",
                "source": "五行局生日安紫微天府",
                "inputs": {"lunar_day": lunar_day, "ju_number": start_age},
                "outputs": {
                    "ziwei_branch": star_placement.ziwei_branch,
                    "tianfu_branch": star_placement.tianfu_branch,
                },
            },
            {
                "rule_id": "daxian_direction",
                "source": resolved_profile,
                "inputs": {"year_stem": year_stem, "gender": canonical_gender},
                "outputs": {
                    "direction": daxian_direction_label,
                    "initial_palace_name": (
                        next(p["name"] for p in palaces if p["daxian_period"] == 1)
                        if is_gender_known
                        else None
                    ),
                    "first_age_given_bureau": start_age,
                },
            },
        ],
        "year_stem": year_stem,
        "lunar_date": {
            "year": state.lunar_year,
            "month": state.lunar_month,
            "day": state.lunar_day,
            "is_leap_month": state.is_leap_month,
        },
        "hour_branch": hour_branch,
        "zidou_branch": zidou_branch,
        "laiyin_gong": flying_sihua["laiyin_gong"],
        "calendar_rules": {
            "year_boundary": (
                "立春" if resolved_year_divide == "exact" else "农历正月初一"
            ),
            "late_zi": (
                "晚子时算次日（次日农历与次日早子日/时干）"
                if resolved_day_divide == "forward"
                else "晚子时算当天（当日农历与当日日/时干）"
            ),
            "day_divide": resolved_day_divide,
            "year_divide": resolved_year_divide,
            "leap_month": ZIWEI_NATAL_LEAP_MONTH_LABELS[leap_policy],
            "effective_birth_month": lunar_month,
        },
        "ruleset": ruleset,
        "ming_gong": {
            "name": "命宫",
            "branch": ming_branch,
            "ganzhi": ming_palace["ganzhi"],
        },
        "shen_gong": {
            "name": "身宫",
            "branch": shen_branch,
            "ganzhi": shen_palace["ganzhi"],
        },
        "wuxing_ju": wuxing_ju,
        "daxian_direction": daxian_direction_label,
        "sihua": sihua,
        "palaces": palaces,
    }
    if include_calendar_basis:
        result["calendar_basis"] = calendar_basis(
            seed,
            placement_label=state.placement_label,
            placement_context=state.lunar,
            day_divide=resolved_day_divide,
        )
    return result


def build_ziwei_rules(
    year_stem: str | None = None,
    *,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
) -> dict[str, Any]:
    resolved_school, resolved_profile = resolve_school_and_profile(school, rule_profile)
    resolved_astro = validate_astro_type(astro_type)
    resolved_day_divide = validate_day_divide(day_divide)
    resolved_year_divide = validate_year_divide(year_divide)
    rules = sihua_rules_for(
        ZIWEI_SIHUA_RULES,
        resolved_profile,
        sihua_source=sihua_source,
        school=resolved_school,
    )
    ruleset = ziwei_ruleset_metadata(
        resolved_profile,
        school=resolved_school,
        astro_type=resolved_astro,
        sihua_source=sihua_source,
        day_divide=resolved_day_divide,
        year_divide=resolved_year_divide,
    )
    if brightness_source != "rule_profile":
        ruleset.update(
            brightness_table_for(resolved_profile, brightness_source).ruleset_fields()
        )
    catalogue = {
        "named_patterns": named_pattern_catalogue(),
        "palace_sequence": list(ZIWEI_PALACE_SEQUENCE),
        "ming_gong_method": "寅宫起正月，顺数生月，逆数生时。",
        "shen_gong_method": "寅宫起正月，顺数生月，再顺数生时。",
        "sihua_by_year_stem": rules,
        "ruleset": ruleset,
        "cycle_methods": {
            "childhood_limit": "一命二财三疾厄，四岁夫妻五福德，六岁官禄（童限1-6岁）",
            "daxian_start": (
                "阳男阴女首限父母、阴男阳女首限兄弟；局数起岁，十年一宫"
                if resolved_profile == "quanshu_v2_excerpt"
                else "首限命宫；阳男阴女顺、阴男阳女逆，局数起岁"
            ),
            "fire_bell": (
                "年支定点"
                if resolved_profile == "quanshu_v2_excerpt"
                else "年支起点起子时，火铃双顺至生时"
            ),
            "changsheng": (
                "男顺女逆"
                if resolved_profile == "quanshu_v2_excerpt"
                else "阳男阴女顺、阴男阳女逆"
            ),
            "boshi": "禄存起博士，阳男阴女顺、阴男阳女逆",
            "late_zi": (
                "晚子（23:00-23:59）算次日早子；农历日序、虚岁换岁与流日/流时天干同步翻至次日"
                if resolved_day_divide == "forward"
                else "晚子（23:00-23:59）算当日；农历日序与流日/流时天干均按当日取值"
            ),
        },
    }
    focused = None
    if year_stem:
        if year_stem not in rules:
            raise ValueError("紫微四化年干必须为甲乙丙丁戊己庚辛壬癸之一")
        focused = {
            "year_stem": year_stem,
            "sihua": dict(rules[year_stem]),
        }
    return {
        "requested_year_stem": year_stem,
        "rule_catalogue": catalogue,
        "focused_rules": focused,
    }
