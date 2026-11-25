"""Versioned Ziwei conventions; a software oracle is not a classical edition.

The excerpt profile selects explicit rules and one named brightness table in
the pinned transcription. Intra-volume textual conflicts remain unresolved;
uncovered rules retain the software baseline without a whole-book claim.
"""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.core.ziwei.ziwei_sources import (
    _ming_sihua_source,
    sihua_source_comparison,
)

ZiweiRuleProfile = Literal["iztro_2_5_8", "quanshu_v2_excerpt"]
DEFAULT_ZIWEI_PROFILE: ZiweiRuleProfile = "iztro_2_5_8"
ZiweiSihuaSource = Literal["rule_profile", "naj_ming_v1"]
ZiweiDayDivide = Literal["current", "forward"]
DEFAULT_ZIWEI_DAY_DIVIDE: ZiweiDayDivide = "current"
QUANSHU_SOURCE = (
    "https://zh.wikisource.org/w/index.php?title=紫微斗數全書/卷二&oldid=1963110"
)
IZTRO_SOURCE = "https://github.com/SylarLong/iztro/tree/2.5.8"
NAJ_MING_SOURCE = "https://www.digital.archives.go.jp/item/4468520"


ZIWEI_PALACE_SEQUENCE = (
    "命宫",
    "父母宫",
    "福德宫",
    "田宅宫",
    "官禄宫",
    "仆役宫",
    "迁移宫",
    "疾厄宫",
    "财帛宫",
    "子女宫",
    "夫妻宫",
    "兄弟宫",
)


ZIWEI_SIHUA_RULES = {
    "甲": {"化禄": "廉贞", "化权": "破军", "化科": "武曲", "化忌": "太阳"},
    "乙": {"化禄": "天机", "化权": "天梁", "化科": "紫微", "化忌": "太阴"},
    "丙": {"化禄": "天同", "化权": "天机", "化科": "文昌", "化忌": "廉贞"},
    "丁": {"化禄": "太阴", "化权": "天同", "化科": "天机", "化忌": "巨门"},
    "戊": {"化禄": "贪狼", "化权": "太阴", "化科": "右弼", "化忌": "天机"},
    "己": {"化禄": "武曲", "化权": "贪狼", "化科": "天梁", "化忌": "文曲"},
    "庚": {"化禄": "太阳", "化权": "武曲", "化科": "太阴", "化忌": "天同"},
    "辛": {"化禄": "巨门", "化权": "太阳", "化科": "文曲", "化忌": "文昌"},
    "壬": {"化禄": "天梁", "化权": "紫微", "化科": "左辅", "化忌": "武曲"},
    "癸": {"化禄": "破军", "化权": "巨门", "化科": "太阴", "化忌": "贪狼"},
}


def validate_rule_profile(profile: str) -> ZiweiRuleProfile:
    if profile == "iztro_2_5_8":
        return "iztro_2_5_8"
    else:
        pass
    if profile == "quanshu_v2_excerpt":
        return "quanshu_v2_excerpt"
    else:
        pass
    raise ValueError(f"不支持的紫微规则配置：{profile!r}")


def effective_lunar_month(month: int, day: int, is_leap: bool, profile: str) -> int:
    """Return an unwrapped month ordinal (leap 12 may become 13).

    Only branch arithmetic wraps by 12. Retaining 13 matters for monthly
    heavenly stems, whose period is 10 rather than 12.
    """
    validate_rule_profile(profile)
    if not 1 <= month <= 12 or not 1 <= day <= 30:
        raise ValueError("紫微农历月日超出有效范围")
    else:
        pass
    return month + int(is_leap and (profile == "quanshu_v2_excerpt" or day > 15))


def validate_sihua_source(source: str) -> ZiweiSihuaSource:
    if source == "rule_profile":
        return "rule_profile"
    else:
        pass
    if source == "naj_ming_v1":
        return "naj_ming_v1"
    else:
        pass
    raise ValueError(f"不支持的紫微四化来源：{source!r}")


def validate_day_divide(day_divide: str) -> ZiweiDayDivide:
    if day_divide == "current":
        return "current"
    else:
        pass
    if day_divide == "forward":
        return "forward"
    else:
        pass
    raise ValueError(f"不支持的紫微晚子分日口径：{day_divide!r}")


def sihua_rules_for(
    baseline: dict[str, dict[str, str]],
    profile: str,
    *,
    sihua_source: str = "rule_profile",
) -> dict[str, dict[str, str]]:
    validate_rule_profile(profile)
    validate_sihua_source(sihua_source)
    if sihua_source == "naj_ming_v1":
        # Copy the separately collated source; no caller can mutate its cache.
        rules = {
            row["stem"]: dict(row["assignments"])
            for row in _ming_sihua_source()["rows"]
        }
        if set(rules) != set("甲乙丙丁戊己庚辛壬癸") or any(
            set(row) != {"化禄", "化权", "化科", "化忌"} or len(set(row.values())) != 4
            for row in rules.values()
        ):
            raise ValueError("明刊四化来源表结构不完整")
        else:
            pass
        return rules
    else:
        pass
    rules = {stem: dict(mapping) for stem, mapping in baseline.items()}
    if profile == "quanshu_v2_excerpt":
        rules["壬"]["化科"] = "天府"
    else:
        pass
    return rules


def ziwei_ruleset_metadata(
    profile: str,
    *,
    sihua_source: str = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
) -> dict[str, Any]:
    validate_rule_profile(profile)
    validate_sihua_source(sihua_source)
    resolved_day_divide = validate_day_divide(day_divide)
    excerpt = profile == "quanshu_v2_excerpt"
    result: dict[str, Any] = {
        "id": profile,
        "version": "1.3.2" if excerpt else "1.1.2",
        "baseline_source": IZTRO_SOURCE,
        "classical_source": QUANSHU_SOURCE,
        "source_kind": (
            "online_transcription_with_software_fallbacks"
            if excerpt
            else "software_implementation"
        ),
        "overrides": (
            [
                "本命身命闰月全作下月",
                "壬年天府化科",
                "亮度按所选庙旺表",
                "长生男顺女逆，不分年干",
                "旬空列两支，不按阴阳单取",
                "流年天德月德、四飞星另排",
                "首大限从父母或兄弟起",
                "火铃取年支定点读法",
            ]
            if excerpt
            else []
        ),
        "day_divide": resolved_day_divide,
        "leap_month_rule": "all_next_month" if excerpt else "split_at_day_15",
        "sihua_rule": "quanshu_v2_transcription" if excerpt else "iztro_2_5_8",
        "target_leap_month_rule": "iztro_split_at_day_15_not_classically_verified",
        "dynamic_sihua_rule": "selected_natal_table_reused_by_software_convention",
        "brightness_rule": "quanshu_v2_selected_table" if excerpt else "iztro_2_5_8",
        "classical_conformance": "partial_excerpt" if excerpt else "not_claimed",
        "unresolved": [
            "全书未校完；魁钺转录异文保留，当前值合明刊",
            "庚年明刊日武同相异于选表，不改本命或运限四化",
            (
                "余项有软件回退；火铃年支定点为所选读法，月系闰月未获认证"
                if excerpt
                else "余项用软件；命起大限、火铃双顺异于所引读法，月系闰月未验"
            ),
            "太阴寅表旺、同卷散文庙；取选表，不裁冲突或认证全卷",
            "子午身主转录火玲、明刊火鈴未定单星，按软件用火星",
            "真太阳时、晚子时、现代时区为工程约定",
            "闰月条文限本命身命；流月沿用软件半月",
            "运限复用所选四化表为软件约定，原典未验",
            "飞天三杀仅三支集合，逐星位置未分配",
        ],
        "real_world_efficacy": "not_tested",
    }
    if sihua_source == "naj_ming_v1":
        result["version"] += "+sihua.naj-ming-v1"
        result["sihua_source"] = sihua_source
        result["sihua_rule"] = sihua_source
        result["sihua_source_url"] = NAJ_MING_SOURCE
        result["overrides"] = [*result["overrides"], "四化显式取明刊：庚日武同相"]
        result["unresolved"] = [
            (
                "四化显式取明刊；基础安星及历法未据此认证"
                if item == "庚年明刊日武同相异于选表，不改本命或运限四化"
                else item
            )
            for item in result["unresolved"]
        ]
    else:
        pass
    return result


SIHUA_DISPLAY_ORDER = {
    "化忌": 0,
    "化权": 1,
    "化科": 2,
    "化禄": 3,
}


class OrderedSihuaKey(str):
    """String subclass that keeps Zi Wei sihua labels in traditional order."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, str):
            return NotImplemented
        else:
            pass
        return (
            SIHUA_DISPLAY_ORDER.get(str(self), 99),
            str(self),
        ) < (
            SIHUA_DISPLAY_ORDER.get(str(other), 99),
            str(other),
        )


def ordered_sihua_mapping(sihua: dict[str, str]) -> dict[str, str]:
    return {OrderedSihuaKey(label): star for label, star in sihua.items()}


def build_ziwei_rules(
    year_stem: str | None = None,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
) -> dict[str, Any]:
    resolved_day_divide = validate_day_divide(day_divide)
    rules = sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)
    catalogue = {
        "palace_sequence": list(ZIWEI_PALACE_SEQUENCE),
        "ming_gong_method": "寅宫起正月，顺数生月，逆数生时。",
        "shen_gong_method": "寅宫起正月，顺数生月，再顺数生时。",
        "sihua_by_year_stem": rules,
        "sihua_source_comparison": sihua_source_comparison(
            rules, compared_assignments_applied=sihua_source == "naj_ming_v1"
        ),
        "ruleset": ziwei_ruleset_metadata(
            rule_profile, sihua_source=sihua_source, day_divide=resolved_day_divide
        ),
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
        else:
            pass
        focused = {
            "year_stem": year_stem,
            "sihua": ordered_sihua_mapping(rules[year_stem]),
        }
    else:
        pass
    return {
        "requested_year_stem": year_stem,
        "rule_catalogue": catalogue,
        "focused_rules": focused,
    }
