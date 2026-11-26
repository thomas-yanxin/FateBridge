"""Build Ziwei natal charts and publish their rule catalogue."""

from __future__ import annotations

from typing import Any, TypedDict

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.ziwei_aux_sources import auxiliary_placement_source_evidence
from fatebridge.core.ziwei.ziwei_auxiliary import (
    attach_natal_cycles,
    chart_masters,
)
from fatebridge.core.ziwei.ziwei_calendar import calendar_basis
from fatebridge.core.ziwei.ziwei_classical import (
    symbolic_properties,
)
from fatebridge.core.ziwei.ziwei_conditions import structural_condition_evidence
from fatebridge.core.ziwei.ziwei_cycle_sources import (
    cycle_source_evidence,
    year_branch_cycles,
)
from fatebridge.core.ziwei.ziwei_evidence import (
    natal_reading_view,
    palace_structural_evidence,
)
from fatebridge.core.ziwei.ziwei_flying import palace_sihua_relations
from fatebridge.core.ziwei.ziwei_horoscope import (
    build_ziwei_horoscope as build_ziwei_horoscope,
)
from fatebridge.core.ziwei.ziwei_ming_properties import ming_property_evidence
from fatebridge.core.ziwei.ziwei_named_patterns import (
    NATAL_PATTERN_STARS,
    QUAN_LU,
    NatalPatternStar,
    named_pattern_catalogue,
    natal_pattern_evidence,
)
from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    ZIWEI_NATAL_LEAP_MONTH_LABELS,
    ZIWEI_PALACE_SEQUENCE,
)
from fatebridge.core.ziwei.ziwei_rulesets import ZIWEI_SIHUA_RULES as ZIWEI_SIHUA_RULES
from fatebridge.core.ziwei.ziwei_rulesets import (
    ZiweiNatalLeapMonthPolicy,
    effective_lunar_month,
    natal_leap_month_policy_for,
    ordered_sihua_mapping,
    sihua_rules_for,
    validate_day_divide,
    validate_rule_profile,
    validate_sihua_source,
    ziwei_ruleset_metadata,
)
from fatebridge.core.ziwei.ziwei_sources import (
    natal_sihua_source_comparison,
    sihua_source_comparison,
    ziwei_day_source_evidence,
    ziwei_prerequisite_source_evidence,
)
from fatebridge.core.ziwei.ziwei_stars import natal_star_placement
from fatebridge.core.ziwei.ziwei_tables import (
    ZiweiBrightnessSource,
    brightness_table_for,
    split_star_mutagen,
)
from fatebridge.core.ziwei.ziwei_time_input import (
    lunar_year_ganzhi,
    resolve_ziwei_clock_state,
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
    """Derive the Five Elements Bureau and its starting age from the Ming palace."""
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
    return ordered_sihua_mapping(sihua)


def build_ziwei_chart(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
    include_calendar_basis: bool = False,
) -> dict[str, Any]:
    rule_profile = validate_rule_profile(rule_profile)
    validate_sihua_source(sihua_source)
    resolved_day_divide = validate_day_divide(day_divide)
    state = resolve_ziwei_clock_state(seed, resolved_day_divide, technique="紫微斗数")
    lunar_day = state.lunar_day
    leap_policy = natal_leap_month_policy_for(rule_profile, natal_leap_month_policy)
    lunar_month = effective_lunar_month(
        state.lunar_month,
        lunar_day,
        state.is_leap_month,
        rule_profile,
        natal_leap_month_policy=leap_policy,
    )
    ruleset = ziwei_ruleset_metadata(
        rule_profile,
        sihua_source=sihua_source,
        day_divide=resolved_day_divide,
        natal_leap_month_policy=leap_policy,
    )
    month_rule_source = {
        "split_at_day_15": ruleset["baseline_source"],
        "all_current_month": ZIWEI_NATAL_LEAP_MONTH_LABELS["all_current_month"],
        "all_next_month": ruleset["classical_source"],
    }[leap_policy]
    hour_branch = state.hour_branch
    hour_index = EARTHLY_BRANCHES.index(hour_branch) + 1
    year_stem, year_branch = lunar_year_ganzhi(state.lunar_year)

    ming_index = (lunar_month - hour_index) % 12
    shen_index = (lunar_month + hour_index - 2) % 12
    ming_branch = ZIWEI_BRANCH_SEQUENCE[ming_index]
    shen_branch = ZIWEI_BRANCH_SEQUENCE[shen_index]

    # 宫干按「五虎遁」规则从年干推出：
    #   甲己之年 → 寅宫起丙寅，乙庚 → 戊寅，丙辛 → 庚寅，丁壬 → 壬寅，戊癸 → 甲寅。
    # ZIWEI_BRANCH_SEQUENCE 以 寅=0 为起点顺数到丑=11，因此某宫位在序列中的位置
    # 就是它相对于寅的偏移量，可直接叠加到寅宫干基。
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
    # note (ziwei): The first palace is Ming and its stem/branch determine the bureau.
    wuxing_ju = _resolve_wuxing_ju(palace_stems[0], palace_branches[0])
    start_age = wuxing_ju["number"]

    # 大限方向: 阳男阴女顺行 / 阴男阳女逆行
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
        rule_profile=rule_profile,
    )
    palaces: list[dict[str, Any]] = []
    for index, palace_name in enumerate(ZIWEI_PALACE_SEQUENCE):
        # 软件首限命宫，摘录首限邻宫，其余按顺/逆方向排列；
        # 宫名序列已按地支递增方向排布（命→父母→福德→...→兄弟）。
        if is_daxian_forward:
            period_index = index  # 软件：命→父母→福德→...
        else:
            period_index = (-index) % 12  # 阴男/阳女：命→兄弟→夫妻→...
        if rule_profile == "quanshu_v2_excerpt":
            # 所选安大限诀从命前/后一宫起，首限为父母/兄弟。
            # 命宫仍为本命宫，不能因运限起点改变而搬移星曜。
            period_index = (period_index - 1) % 12
        period_start = start_age + period_index * 10
        palace: dict[str, Any] = {
            "name": palace_name,
            "ganzhi": f"{palace_stems[index]}{palace_branches[index]}",
            "daxian": f"{period_start}~{period_start + 9}" if is_gender_known else None,
            "daxian_period": period_index + 1 if is_gender_known else None,
            "stars": star_placement.stars_by_branch[palace_branches[index]],
        }
        palaces.append(palace)

    sihua_rules = sihua_rules_for(
        ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source
    )
    sihua = _apply_sihua_to_palaces(palaces, sihua_rules[year_stem])
    brightness_table = brightness_table_for(rule_profile, brightness_source)
    explicit_brightness = brightness_source != "rule_profile"
    if explicit_brightness:
        ruleset.update(brightness_table.ruleset_fields(ruleset["unresolved"]))
    pattern_stars: list[NatalPatternStar] = []
    for palace in palaces:
        palace_branch = palace["ganzhi"][1]
        palace["stars"] = sorted(set(palace["stars"]))
        detail: list[dict[str, Any]] = []
        for label in palace["stars"]:
            base_name, mutagen = split_star_mutagen(label)
            brightness = brightness_table.lookup(base_name, palace_branch)
            star_detail = {
                "name": base_name,
                "label": label,
                "brightness": brightness,
                "mutagen": mutagen,
            }
            if explicit_brightness:
                star_detail["brightness_source"] = brightness_table.id
            detail.append(star_detail)
            if base_name in NATAL_PATTERN_STARS or mutagen in QUAN_LU:
                pattern_stars.append(
                    {
                        "star": base_name,
                        "natal_branch": palace_branch,
                        "natal_palace_name": palace["name"],
                        "brightness": brightness,
                        "mutagen": mutagen,
                    }
                )
        palace["stars_detail"] = detail

    cycle_rules = attach_natal_cycles(
        palaces,
        element=wuxing_ju["element"],
        year_stem=year_stem,
        gender=gender,
        rule_profile=rule_profile,
    )
    for palace in palaces:
        palace["structural_evidence"] = palace_structural_evidence(palace, palaces)

    ming_palace = palaces[0]
    shen_palace = palaces[(shen_index - ming_index) % 12]
    result: dict[str, Any] = {
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "reading_view": natal_reading_view(palaces),
        "symbolic_properties": symbolic_properties(palaces),
        "ming_textual_properties": ming_property_evidence(
            palaces, ming_branch=ming_branch, shen_branch=shen_branch
        ),
        "ming_structural_conditions": structural_condition_evidence(
            palaces, ming_branch=ming_branch, year_stem=year_stem
        ),
        "named_patterns": natal_pattern_evidence(
            pattern_stars, ming_branch=ming_branch
        ),
        "auxiliary_placement_sources": auxiliary_placement_source_evidence(
            palaces,
            lunar_month=state.lunar_month,
            lunar_day=lunar_day,
            is_leap=state.is_leap_month,
            hour_branch=hour_branch,
            year_branch=year_branch,
            rule_profile=rule_profile,
        ),
        "sihua_source_comparison": natal_sihua_source_comparison(
            palaces,
            year_stem=year_stem,
            selected_sihua=sihua,
            compared_assignments_applied=sihua_source == "naj_ming_v1",
        ),
        "palace_sihua_relations": palace_sihua_relations(
            (
                (p["name"], p["ganzhi"], (star["name"] for star in p["stars_detail"]))
                for p in palaces
            ),
            sihua_rules,
            sihua_rule=ruleset["sihua_rule"],
        ),
        "void_systems": {
            "xun": {
                "source_branches": star_placement.xun_void_source_branches,
                "displayed_star_branches": star_placement.xun_void_displayed_branches,
                "display_rule": (
                    "both_branches_as_written"
                    if rule_profile == "quanshu_v2_excerpt"
                    else "software_primary_branch_by_year_polarity"
                ),
                "source": ruleset["classical_source"],
            },
            "source_name_mapping": {
                "天空地劫诀中的天空": "地空",
                "软件另列的天空": "年支顺一位的软件扩展，不是前述古名天空",
                "安天德月德解神诀中的本生年解神": "年解",
                "软件另列的解神": "月系解神，与原文的本生年解神分开",
            },
        },
        "calendar_cycles": {
            **cycle_rules,
            "year_branch_cycles": year_branch_cycles(
                year_branch, anchor_basis="natal_lunar_year_branch"
            ),
        },
        "cycle_source_comparison": cycle_source_evidence(
            palaces,
            cycle_rules,
            element=wuxing_ju["element"],
            year_stem=year_stem,
            gender=gender,
            rule_profile=rule_profile,
        ),
        "chart_masters": chart_masters(
            palaces,
            ming_branch=ming_branch,
            year_branch=year_branch,
            rule_profile=rule_profile,
        ),
        "rule_trace": [
            {
                "rule_id": "lunar_month_for_placement",
                "source": month_rule_source,
                "inputs": {
                    "month": state.lunar_month,
                    "day": lunar_day,
                    "is_leap_month": state.is_leap_month,
                },
                "outputs": {"effective_month": lunar_month},
            },
            {
                "rule_id": "ming_shen_month_hour",
                "source": "安身命例；寅起正月、命逆身顺",
                "inputs": {"effective_month": lunar_month, "hour_branch": hour_branch},
                "outputs": {"ming_branch": ming_branch, "shen_branch": shen_branch},
            },
            {
                "rule_id": "wuhu_dun_nayin_ju",
                "source": "起五行寅例与命宫干支纳音",
                "inputs": {
                    "lunar_year": state.lunar_year,
                    "year_stem": year_stem,
                    "ming_ganzhi": ming_palace["ganzhi"],
                },
                "outputs": {
                    "nayin": wuxing_ju["nayin"],
                    "ju_number": wuxing_ju["number"],
                    "source_comparison": ziwei_prerequisite_source_evidence(
                        lunar_month=state.lunar_month,
                        is_leap=state.is_leap_month,
                        effective_month=lunar_month,
                        hour_branch=hour_branch,
                        year_stem=year_stem,
                        shen_branch=shen_branch,
                        palaces=palaces,
                        nayin=wuxing_ju["nayin"],
                        bureau=wuxing_ju["number"],
                    ),
                },
            },
            {
                "rule_id": "ziwei_tianfu_placement",
                "source": "五行局生日安紫微；寅申轴对映安天府",
                "inputs": {"lunar_day": lunar_day, "ju_number": start_age},
                "outputs": {
                    "ziwei_branch": star_placement.ziwei_branch,
                    "tianfu_branch": star_placement.tianfu_branch,
                    "source_comparison": ziwei_day_source_evidence(
                        bureau=start_age,
                        lunar_day=lunar_day,
                        actual_branch=star_placement.ziwei_branch,
                    ),
                },
            },
            {
                "rule_id": "daxian_direction",
                "source": (
                    "明刊卷三安大限诀：阳男阴女从父母、阴男阳女从兄弟起"
                    if rule_profile == "quanshu_v2_excerpt"
                    else "软件首限命宫，阳男阴女顺、阴男阳女逆；未知性别不排运"
                ),
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
        "calendar_rules": {
            "year_boundary": "农历正月初一",
            "late_zi": (
                "晚子时算次日（次日农历与次日早子日/时干）"
                if resolved_day_divide == "forward"
                else "晚子时算当天（当日农历与当日日/时干）"
            ),
            "day_divide": resolved_day_divide,
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
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
) -> dict[str, Any]:
    resolved_day_divide = validate_day_divide(day_divide)
    rules = sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)
    ruleset = ziwei_ruleset_metadata(
        rule_profile, sihua_source=sihua_source, day_divide=resolved_day_divide
    )
    if brightness_source != "rule_profile":
        ruleset.update(
            brightness_table_for(rule_profile, brightness_source).ruleset_fields(
                ruleset["unresolved"]
            )
        )
    catalogue = {
        "named_patterns": named_pattern_catalogue(),
        "palace_sequence": list(ZIWEI_PALACE_SEQUENCE),
        "ming_gong_method": "寅宫起正月，顺数生月，逆数生时。",
        "shen_gong_method": "寅宫起正月，顺数生月，再顺数生时。",
        "sihua_by_year_stem": rules,
        "sihua_source_comparison": sihua_source_comparison(
            rules, compared_assignments_applied=sihua_source == "naj_ming_v1"
        ),
        "ruleset": ruleset,
        "cycle_methods": {
            "pre_decade": "所选局数起岁前不取大限宫、不生成大限四化；童限独立",
            "daxian_start": (
                "阳男阴女首限父母、阴男阳女首限兄弟；局数起岁，十年一宫"
                if rule_profile == "quanshu_v2_excerpt"
                else "首限命宫；阳男阴女顺、阴男阳女逆，局数起岁"
            ),
            "fire_bell": (
                "按所列年支二支安星，不推进生时；这是明确选择的年支定点读法"
                if rule_profile == "quanshu_v2_excerpt"
                else "年支起点起子时，火铃双顺至生时；软件约定"
            ),
            "changsheng": (
                "男顺女逆"
                if rule_profile == "quanshu_v2_excerpt"
                else "阳男阴女顺、阴男阳女逆"
            ),
            "boshi": "禄存起博士，阳男阴女顺、阴男阳女逆",
            "annual_lucun_yang_tuo": "目标年干定流禄，前一位流羊、后一位流陀；不搬移本命星",
            "late_zi": (
                "晚子（23:00-23:59）算次日早子；农历日序与流日/流时天干同步翻至次日"
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
            "sihua": ordered_sihua_mapping(rules[year_stem]),
        }
    return {
        "requested_year_stem": year_stem,
        "rule_catalogue": catalogue,
        "focused_rules": focused,
    }
