"""Ziwei school conventions, star brightness tables, and SiHua rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any, Literal, TypedDict

from fatebridge.utils.data import EARTHLY_BRANCHES, ZIWEI_BRANCH_SEQUENCE
from fatebridge.utils.errors import ParameterError

ZiweiSchool = Literal["default", "zhongzhou", "quanshu", "feixing"]
DEFAULT_ZIWEI_SCHOOL: ZiweiSchool = "default"
ZiweiAstroType = Literal["heaven", "earth", "human"]
DEFAULT_ZIWEI_ASTRO_TYPE: ZiweiAstroType = "heaven"
ZiweiRuleProfile = Literal["iztro_2_5_8", "quanshu_v2_excerpt"]
DEFAULT_ZIWEI_PROFILE: ZiweiRuleProfile = "iztro_2_5_8"
ZiweiNatalLeapMonthPolicy = Literal[
    "split_at_day_15", "all_current_month", "all_next_month"
]
ZiweiSihuaSource = Literal[
    "rule_profile",
    "iztro_2_5_8",
    "quanshu_v2",
    "naj_ming_v1",
    "feixing_liang",
    "qintian",
]
ZiweiDayDivide = Literal["current", "forward"]
DEFAULT_ZIWEI_DAY_DIVIDE: ZiweiDayDivide = "current"
ZiweiYearDivide = Literal["normal", "exact"]
DEFAULT_ZIWEI_YEAR_DIVIDE: ZiweiYearDivide = "normal"
ZiweiHoroscopeDivide = Literal["normal", "exact"]
DEFAULT_ZIWEI_HOROSCOPE_DIVIDE: ZiweiHoroscopeDivide = "normal"
ZiweiAgeDivide = Literal["normal", "birthday"]
DEFAULT_ZIWEI_AGE_DIVIDE: ZiweiAgeDivide = "normal"
ZiweiBrightnessSource = Literal[
    "rule_profile",
    "iztro_2_5_8",
    "quanshu_v2_selected_table",
    "ziwei_doushu_qs",
    "ziwei_doushu_xd1",
    "ziwei_doushu_zz",
    "ziwei_doushu_xd2",
]

NATAL_LEAP_MONTH_DEFAULTS: dict[ZiweiRuleProfile, ZiweiNatalLeapMonthPolicy] = {
    "iztro_2_5_8": "split_at_day_15",
    "quanshu_v2_excerpt": "all_next_month",
}

ZIWEI_NATAL_LEAP_MONTH_LABELS: dict[ZiweiNatalLeapMonthPolicy, str] = {
    "split_at_day_15": "闰月十五日及以前算当月，之后算下月",
    "all_current_month": "闰月全月沿用同名月序",
    "all_next_month": "闰月全月作下月（安身命条文）",
}

QUANSHU_SOURCE = "紫微斗数全书·卷二"
IZTRO_SOURCE = "iztro 2.5.8"
NAJ_MING_SOURCE = "内阁文库明刻本紫微斗数全书"
FEIXING_SOURCE = "梁若瑜飞星/钦天四化"
ZHONGZHOU_SOURCE = "中州派（王亭之）"

BRIGHTNESS_SOURCE_DESCRIPTION = (
    "本命庙旺表。rule_profile（默认）沿用基础盘式。iztro_2_5_8 取软件原表，"
    "quanshu_v2_selected_table 取《紫微斗数全书》卷二转录的十二宫表。"
    "ziwei_doushu_qs、ziwei_doushu_xd1、ziwei_doushu_zz、ziwei_doushu_xd2 "
    "取 Renhuai123/ziwei-doushu 固定版本软件对照表。空格为 null，不跨表补值。"
)

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

SIHUA_ORDER = ("化禄", "化权", "化科", "化忌")
MUTAGEN_SUFFIXES: tuple[str, ...] = SIHUA_ORDER

# Default 10-stem SiHua table (iztro 2.5.8 / 钦天四化)
ZIWEI_SIHUA_RULES: dict[str, dict[str, str]] = {
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

SIHUA_VARIANTS: dict[str, dict[str, dict[str, str]]] = {
    "iztro_2_5_8": {},
    "qintian": {},
    "quanshu_v2": {
        "壬": {"化禄": "天梁", "化权": "紫微", "化科": "天府", "化忌": "武曲"},
    },
    "naj_ming_v1": {
        "庚": {"化禄": "太阳", "化权": "武曲", "化科": "天同", "化忌": "天相"},
        "壬": {"化禄": "天梁", "化权": "紫微", "化科": "天府", "化忌": "武曲"},
    },
    "feixing_liang": {
        "庚": {"化禄": "太阳", "化权": "武曲", "化科": "天府", "化忌": "天相"},
    },
}

SEVEN_GRADES = tuple("庙旺得利平不陷")
FIVE_GRADES = tuple("庙旺平闲陷")
COMPATIBILITY_VARIANTS = {
    "ziwei_doushu_qs": "QS",
    "ziwei_doushu_xd1": "XD1",
    "ziwei_doushu_zz": "ZZ",
    "ziwei_doushu_xd2": "XD2",
}

# star name -> 12 brightness values (寅-indexed); None = not applicable.
# Fixed vs iztro 2.5.8: 太阳@酉="平", 太阴@酉="旺", 七杀@酉="旺".
ZIWEI_STAR_BRIGHTNESS: dict[str, list[str | None]] = {
    "紫微": ["旺", "旺", "得", "旺", "庙", "庙", "旺", "旺", "得", "旺", "平", "庙"],
    "天机": ["得", "旺", "利", "平", "庙", "陷", "得", "旺", "利", "平", "庙", "陷"],
    "太阳": ["旺", "庙", "旺", "旺", "旺", "得", "得", "平", "不", "陷", "陷", "不"],
    "武曲": ["得", "利", "庙", "平", "旺", "庙", "得", "利", "庙", "平", "旺", "庙"],
    "天同": ["利", "平", "平", "庙", "陷", "不", "旺", "平", "平", "庙", "旺", "不"],
    "廉贞": ["庙", "平", "利", "陷", "平", "利", "庙", "平", "利", "陷", "平", "利"],
    "天府": ["庙", "得", "庙", "得", "旺", "庙", "得", "旺", "庙", "得", "庙", "庙"],
    "太阴": ["旺", "陷", "陷", "陷", "不", "不", "利", "旺", "旺", "庙", "庙", "庙"],
    "贪狼": ["平", "利", "庙", "陷", "旺", "庙", "平", "利", "庙", "陷", "旺", "庙"],
    "巨门": ["庙", "庙", "陷", "旺", "旺", "不", "庙", "庙", "陷", "旺", "旺", "不"],
    "天相": ["庙", "陷", "得", "得", "庙", "得", "庙", "陷", "得", "得", "庙", "庙"],
    "天梁": ["庙", "庙", "庙", "陷", "庙", "旺", "陷", "得", "庙", "陷", "庙", "旺"],
    "七杀": ["庙", "旺", "庙", "平", "旺", "庙", "庙", "旺", "庙", "平", "旺", "庙"],
    "破军": ["得", "陷", "旺", "平", "庙", "旺", "得", "陷", "旺", "平", "庙", "旺"],
    "文昌": ["陷", "利", "得", "庙", "陷", "利", "得", "庙", "陷", "利", "得", "庙"],
    "文曲": ["平", "旺", "得", "庙", "陷", "旺", "得", "庙", "陷", "旺", "得", "庙"],
    "火星": ["庙", "利", "陷", "得", "庙", "利", "陷", "得", "庙", "利", "陷", "得"],
    "铃星": ["庙", "利", "陷", "得", "庙", "利", "陷", "得", "庙", "利", "陷", "得"],
    "擎羊": [None, "陷", "庙", None, "陷", "庙", None, "陷", "庙", None, "陷", "庙"],
    "陀罗": ["陷", None, "庙", "陷", None, "庙", "陷", None, "庙", "陷", None, "庙"],
}


def validate_school(school: str) -> ZiweiSchool:
    if school in ("default", "zhongzhou", "quanshu", "feixing"):
        return school  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微流派：{school!r}")


def validate_astro_type(astro_type: str) -> ZiweiAstroType:
    if astro_type in ("heaven", "earth", "human"):
        return astro_type  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微盘式（天地人三盘）：{astro_type!r}")


def validate_rule_profile(profile: str) -> ZiweiRuleProfile:
    if profile == "iztro_2_5_8":
        return "iztro_2_5_8"
    if profile == "quanshu_v2_excerpt":
        return "quanshu_v2_excerpt"
    raise ValueError(f"不支持的紫微规则配置：{profile!r}")


def validate_sihua_source(source: str) -> ZiweiSihuaSource:
    if source in SIHUA_VARIANTS or source == "rule_profile":
        return source  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微四化来源：{source!r}")


def validate_day_divide(day_divide: str) -> ZiweiDayDivide:
    if day_divide in ("current", "forward"):
        return day_divide  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微晚子分日口径：{day_divide!r}")


def validate_year_divide(year_divide: str) -> ZiweiYearDivide:
    if year_divide in ("normal", "exact"):
        return year_divide  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微年界口径：{year_divide!r}")


def validate_horoscope_divide(horoscope_divide: str) -> ZiweiHoroscopeDivide:
    if horoscope_divide in ("normal", "exact"):
        return horoscope_divide  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微流月分界口径：{horoscope_divide!r}")


def validate_age_divide(age_divide: str) -> ZiweiAgeDivide:
    if age_divide in ("normal", "birthday"):
        return age_divide  # type: ignore[return-value]
    raise ValueError(f"不支持的紫微虚岁分界口径：{age_divide!r}")


def resolve_school_and_profile(
    school: str = DEFAULT_ZIWEI_SCHOOL,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
) -> tuple[ZiweiSchool, ZiweiRuleProfile]:
    resolved_school = validate_school(school)
    resolved_profile = validate_rule_profile(rule_profile)
    if resolved_school == "quanshu":
        resolved_profile = "quanshu_v2_excerpt"
    elif resolved_school == "default" and resolved_profile == "quanshu_v2_excerpt":
        resolved_school = "quanshu"
    return resolved_school, resolved_profile


def natal_leap_month_policy_for(
    profile: ZiweiRuleProfile, requested: ZiweiNatalLeapMonthPolicy | None
) -> ZiweiNatalLeapMonthPolicy:
    return NATAL_LEAP_MONTH_DEFAULTS[profile] if requested is None else requested


def effective_lunar_month(
    month: int,
    day: int,
    is_leap: bool,
    profile: str,
    *,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
) -> int:
    """Resolve the effective month ordinal while preserving the calendar date."""
    resolved_profile = validate_rule_profile(profile)
    if not 1 <= month <= 12 or not 1 <= day <= 30:
        raise ValueError("紫微农历月日超出有效范围")
    policy = natal_leap_month_policy_for(resolved_profile, natal_leap_month_policy)
    if policy == "split_at_day_15":
        return month + int(is_leap and day > 15)
    if policy == "all_current_month":
        return month
    if policy == "all_next_month":
        return month + int(is_leap)
    raise ValueError(f"不支持的紫微本命闰月口径：{policy!r}")


def sihua_rules_for(
    baseline: dict[str, dict[str, str]],
    profile: str,
    *,
    sihua_source: str = "rule_profile",
    school: str = DEFAULT_ZIWEI_SCHOOL,
) -> dict[str, dict[str, str]]:
    resolved_school, resolved_profile = resolve_school_and_profile(school, profile)
    resolved_source = validate_sihua_source(sihua_source)
    rules = {stem: dict(mapping) for stem, mapping in baseline.items()}
    if resolved_source == "rule_profile":
        if resolved_profile == "quanshu_v2_excerpt" or resolved_school == "quanshu":
            variant_key = "quanshu_v2"
        elif resolved_school == "feixing":
            variant_key = "qintian"
        else:
            variant_key = "iztro_2_5_8"
    else:
        variant_key = resolved_source
    for stem, row in SIHUA_VARIANTS[variant_key].items():
        rules[stem] = dict(row)
    return rules


def resolved_sihua_rule_id(
    profile: ZiweiRuleProfile,
    *,
    sihua_source: ZiweiSihuaSource,
    school: ZiweiSchool,
) -> str:
    if sihua_source != "rule_profile":
        return sihua_source
    if profile == "quanshu_v2_excerpt" or school == "quanshu":
        return "quanshu_v2_transcription"
    if school == "feixing":
        return "qintian"
    return "iztro_2_5_8"


class _BrightnessMetadata(TypedDict):
    id: str
    source_kind: str
    source_url: str
    version: str
    branch_order: list[str]
    grade_scale: list[str]
    aliases: dict[str, str]
    blank_meaning: str


class BrightnessRulesetFields(TypedDict):
    brightness_rule: str
    brightness_table: _BrightnessMetadata


@dataclass(frozen=True)
class ZiweiBrightnessTable:
    _metadata: _BrightnessMetadata
    _branch_index: dict[str, int]
    _rows: dict[str, list[str | None]]

    @property
    def id(self) -> str:
        return self._metadata["id"]

    def lookup(self, star: str, branch: str) -> str | None:
        row = self._rows.get(self._metadata["aliases"].get(star, star))
        index = self._branch_index.get(branch)
        return row[index] if row is not None and index is not None else None

    def ruleset_fields(self) -> BrightnessRulesetFields:
        return {
            "brightness_rule": self.id,
            "brightness_table": {
                **self._metadata,
                "branch_order": list(self._metadata["branch_order"]),
                "grade_scale": list(self._metadata["grade_scale"]),
                "aliases": dict(self._metadata["aliases"]),
            },
        }


class _QuanshuBrightness(TypedDict):
    source: str
    branch_order: list[str]
    brightness: dict[str, list[str | None]]


class _CompatibilityBrightness(TypedDict):
    source: str
    revision: str
    branch_order: list[str]
    name_aliases: dict[str, str]
    tables: dict[str, dict[str, list[str | None]]]


@cache
def _compatibility_brightness() -> _CompatibilityBrightness:
    data: _CompatibilityBrightness = json.loads(
        files("fatebridge")
        .joinpath("data/classical/ziwei-doushu-brightness.json")
        .read_text(encoding="utf-8")
    )
    return data


@cache
def _brightness_table(table_id: str) -> ZiweiBrightnessTable:
    grades = SEVEN_GRADES
    expected_branches = ZIWEI_BRANCH_SEQUENCE
    if table_id == "iztro_2_5_8":
        rows = ZIWEI_STAR_BRIGHTNESS
        branches = list(ZIWEI_BRANCH_SEQUENCE)
        source_kind = "software_implementation"
        source_url = f"{IZTRO_SOURCE} stars.ts"
        version = "2.5.8"
        aliases = {"qingyangMin": "擎羊"}
    elif table_id == "quanshu_v2_selected_table":
        classical: _QuanshuBrightness = json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-quanshu-v2-table.json")
            .read_text(encoding="utf-8")
        )
        rows = classical["brightness"]
        branches = classical["branch_order"]
        source_kind = "classical_transcription"
        source_url = classical["source"]
        version = "oldid=1963110"
        aliases = {}
    else:
        variant = COMPATIBILITY_VARIANTS.get(table_id)
        if variant is None:
            raise ParameterError(
                f"不支持的紫微庙旺表：{table_id!r}",
                [
                    {
                        "path": "brightness_source",
                        "code": "unsupported_brightness_source",
                    }
                ],
            )
        compatibility = _compatibility_brightness()
        rows = compatibility["tables"][variant]
        branches = compatibility["branch_order"]
        expected_branches = EARTHLY_BRANCHES
        source_kind = "software_compatibility"
        source_url = compatibility["source"]
        version = compatibility["revision"]
        aliases = compatibility["name_aliases"]
        if variant in {"ZZ", "XD2"}:
            grades = FIVE_GRADES
    if branches != expected_branches or any(
        len(row) != len(branches) for row in rows.values()
    ):
        raise ValueError(f"紫微庙旺表地支序或行宽错误：{table_id}")
    return ZiweiBrightnessTable(
        _metadata={
            "id": table_id,
            "source_kind": source_kind,
            "source_url": source_url,
            "version": version,
            "branch_order": branches,
            "grade_scale": list(grades),
            "aliases": aliases,
            "blank_meaning": "no_grade_recorded_for_star_and_branch_in_selected_table",
        },
        _branch_index={branch: index for index, branch in enumerate(branches)},
        _rows=rows,
    )


def brightness_table_for(
    rule_profile: str, brightness_source: ZiweiBrightnessSource
) -> ZiweiBrightnessTable:
    if brightness_source == "rule_profile":
        return _brightness_table(
            "quanshu_v2_selected_table"
            if rule_profile == "quanshu_v2_excerpt"
            else "iztro_2_5_8"
        )
    return _brightness_table(brightness_source)


def lookup_star_brightness(
    star: str,
    branch: str,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    brightness_source: ZiweiBrightnessSource = "rule_profile",
) -> str | None:
    """Return the selected table's literal label, or None with no recorded cell."""
    validate_rule_profile(rule_profile)
    return brightness_table_for(rule_profile, brightness_source).lookup(star, branch)


def split_star_mutagen(star_label: str) -> tuple[str, str | None]:
    """Separate a star name from its optional transformation suffix."""
    for suffix in MUTAGEN_SUFFIXES:
        if star_label.endswith(suffix):
            return star_label[: -len(suffix)], suffix
    return star_label, None


def ziwei_ruleset_metadata(
    profile: str,
    *,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    sihua_source: str = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
    horoscope_divide: str = DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
    age_divide: str = DEFAULT_ZIWEI_AGE_DIVIDE,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
) -> dict[str, Any]:
    resolved_school, resolved_profile = resolve_school_and_profile(school, profile)
    resolved_astro = validate_astro_type(astro_type)
    resolved_sihua = validate_sihua_source(sihua_source)
    resolved_day_divide = validate_day_divide(day_divide)
    resolved_year_divide = validate_year_divide(year_divide)
    resolved_horoscope_divide = validate_horoscope_divide(horoscope_divide)
    resolved_age_divide = validate_age_divide(age_divide)
    leap_month_rule = natal_leap_month_policy_for(
        resolved_profile, natal_leap_month_policy
    )
    excerpt = resolved_profile == "quanshu_v2_excerpt"
    sihua_rule = resolved_sihua_rule_id(
        resolved_profile, sihua_source=resolved_sihua, school=resolved_school
    )
    overrides: list[str] = []
    if leap_month_rule == "all_next_month":
        overrides.append("闰月全作下月")
    elif leap_month_rule == "all_current_month":
        overrides.append("闰月全作当月")
    if excerpt:
        overrides.extend(
            [
                "壬年天府化科",
                "长生男顺女逆",
                "旬空列两支",
                "首大限从父母或兄弟起",
                "火铃取年支定点读法",
            ]
        )
    if resolved_school == "zhongzhou":
        overrides.extend(
            [
                "中州派年支定命主",
                "阴男阳女天伤天使互换",
                "中州截空/大耗/龙德/劫杀",
                "岁破代大耗",
            ]
        )
    elif resolved_school == "feixing":
        overrides.append("飞星/钦天四化矩阵与来因宫")
    if resolved_astro != "heaven":
        overrides.append(f"{resolved_astro}_palace_rearrangement")
    result: dict[str, Any] = {
        "id": resolved_profile,
        "version": "2.0.0",
        "school": resolved_school,
        "astro_type": resolved_astro,
        "day_divide": resolved_day_divide,
        "year_divide": resolved_year_divide,
        "horoscope_divide": resolved_horoscope_divide,
        "age_divide": resolved_age_divide,
        "leap_month_rule": leap_month_rule,
        "target_leap_month_rule": leap_month_rule,
        "sihua_source": resolved_sihua,
        "sihua_rule": sihua_rule,
        "brightness_rule": ("quanshu_v2_selected_table" if excerpt else "iztro_2_5_8"),
        "overrides": overrides,
    }
    return result
