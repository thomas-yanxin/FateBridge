"""Request contracts for Zi Wei Dou Shu."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.core.requests.birth import FateBridgeRequest

ZiweiAgeBasis = Literal["birth_civil_timezone"]
ZiweiRuleProfile = Literal["iztro_2_5_8", "quanshu_v2_excerpt"]
DEFAULT_ZIWEI_PROFILE: ZiweiRuleProfile = "iztro_2_5_8"
ZiweiNatalLeapMonthPolicy = Literal[
    "split_at_day_15", "all_current_month", "all_next_month"
]
ZiweiSihuaSource = Literal["rule_profile", "naj_ming_v1"]
ZiweiDayDivide = Literal["current", "forward"]
DEFAULT_ZIWEI_DAY_DIVIDE: ZiweiDayDivide = "current"
ZiweiBrightnessSource = Literal[
    "rule_profile",
    "iztro_2_5_8",
    "quanshu_v2_selected_table",
    "ziwei_doushu_qs",
    "ziwei_doushu_xd1",
    "ziwei_doushu_zz",
    "ziwei_doushu_xd2",
]
BRIGHTNESS_SOURCE_DESCRIPTION = (
    "本命庙旺表。rule_profile（默认）沿用基础盘式。iztro_2_5_8 取软件原表，"
    "quanshu_v2_selected_table 取《紫微斗数全书》卷二转录的十二宫表。"
    "ziwei_doushu_qs、ziwei_doushu_xd1、ziwei_doushu_zz、ziwei_doushu_xd2 "
    "取 Renhuai123/ziwei-doushu 固定版本软件对照表。空格为 null，不跨表补值。"
    "安星、历法、四化及运限起法仍按各自规则。"
)


class ZiweiSharedOptions(FateBridgeRequest):
    """Shared birth offset and rule-profile options for Zi Wei natal and timing requests."""

    birth_utc_offset: str | None = Field(
        default=None,
        description="出生钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与解析后的birth_timezone核对，用于选择重复钟时，不替换命名时区。省略仍拒绝歧义或不存在的钟时。",
    )
    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="紫微规则：iztro_2_5_8 保留软件口径；quanshu_v2_excerpt 1.3.2 选择闰月、四化、亮度、长生、旬空双支、部分流年星，以及邻宫起大限、火铃年支定点读法；另用sihua_source显式选四化表，非全书认证。",
    )
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = Field(
        default=None,
        description="本命闰月安星月序：split_at_day_15（初一至十五沿用同名月序，十六日起后移一月）、all_current_month（全月原位）、all_next_month（全月后移）。保留出生农历年、日、闰月标记；闰十二月后移为本年安星月序13。省略按rule_profile：iztro分半，摘录全月后移。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="四化表：rule_profile沿用基础配置；naj_ming_v1显式取明刊卷三原页（庚日武同相、壬梁紫府武）。只选四化表，不代表整部原典获认证。",
    )
    brightness_source: ZiweiBrightnessSource = Field(
        default="rule_profile", description=BRIGHTNESS_SOURCE_DESCRIPTION
    )
    day_divide: ZiweiDayDivide = Field(
        default=DEFAULT_ZIWEI_DAY_DIVIDE,
        description="晚子（23:00-23:59）分日口径：current（默认，当日农历与当日日/时干）或 forward（算次日早子农历与次日早子日/时干）。",
    )


class ZiweiBirthRequest(ZiweiSharedOptions):
    """Request model for Zi Wei birth chart analysis."""


class ZiweiHoroscopeRequest(ZiweiSharedOptions):
    """Request model for 紫微斗数 horoscope (运限) at an analysis date-time."""

    analysis_year: int = Field(description="Analysis year, e.g., 2026")
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Analysis minute (0-59); does not imply minute-level predictive accuracy",
    )
    analysis_timezone: str = Field(
        default="Asia/Shanghai",
        description="分析钟表时间的时区，与出生时区独立；默认 Asia/Shanghai，不对分析时刻做真太阳时修正。",
    )
    analysis_utc_offset: str | None = Field(
        default=None,
        description="分析钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与analysis_timezone核对并选择重复钟时。省略仍拒绝歧义或不存在的分析钟时；实际先后按UTC瞬间比较。",
    )
    nominal_age_basis: ZiweiAgeBasis = Field(
        default="birth_civil_timezone",
        description="岁序默认birth_civil_timezone：出生与目标实际瞬间都按出生民用时区查农历年，正月初一00:00换岁，独立于真太阳安星及目标流曜钟。该软件约定尚非原典岁首认证。",
    )


class ZiweiRulesRequest(FateBridgeBaseRequest):
    """Request model for Zi Wei rule catalogue lookup."""

    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="要查询的紫微规则配置；quanshu_v2_excerpt 1.3.2 包括邻宫起大限、火铃年支定点读法，非全书认证。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="要查询的实际四化表；naj_ming_v1为明刊卷三原页，不改变基础安星配置。",
    )
    brightness_source: ZiweiBrightnessSource = Field(
        default="rule_profile", description=BRIGHTNESS_SOURCE_DESCRIPTION
    )
    day_divide: ZiweiDayDivide = Field(
        default=DEFAULT_ZIWEI_DAY_DIVIDE,
        description="晚子（23:00-23:59）分日口径：current 或 forward。",
    )
    year_stem: str | None = Field(
        default=None,
        description="Optional heavenly stem filter, e.g. 甲",
    )
