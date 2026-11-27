"""Request contracts for Zi Wei Dou Shu."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.core.requests.birth import FateBridgeRequest
from fatebridge.core.ziwei.tables import (
    BRIGHTNESS_SOURCE_DESCRIPTION,
    DEFAULT_ZIWEI_AGE_DIVIDE,
    DEFAULT_ZIWEI_ASTRO_TYPE,
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    DEFAULT_ZIWEI_SCHOOL,
    DEFAULT_ZIWEI_YEAR_DIVIDE,
    ZiweiAgeDivide,
    ZiweiAstroType,
    ZiweiBrightnessSource,
    ZiweiDayDivide,
    ZiweiHoroscopeDivide,
    ZiweiNatalLeapMonthPolicy,
    ZiweiRuleProfile,
    ZiweiSchool,
    ZiweiSihuaSource,
    ZiweiYearDivide,
)

ZiweiAgeBasis = Literal["birth_civil_timezone"]


class ZiweiSharedOptions(FateBridgeRequest):
    """Shared birth offset and rule-profile options for Zi Wei natal and timing requests."""

    birth_utc_offset: str | None = Field(
        default=None,
        description="出生钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与解析后的birth_timezone核对，用于选择重复钟时。",
    )
    school: ZiweiSchool = Field(
        default=DEFAULT_ZIWEI_SCHOOL,
        description="紫微流派：default（通行三合/iztro基线）、zhongzhou（中州派：年支定命主、阴男阳女天伤天使互换、截空、大耗/龙德/劫杀、岁破）、quanshu（全书摘录）、feixing（飞星/钦天四化矩阵与来因宫）。",
    )
    astro_type: ZiweiAstroType = Field(
        default=DEFAULT_ZIWEI_ASTRO_TYPE,
        description="天地人三盘：heaven（天盘，默认命宫起盘）、earth（地盘，身宫为命宫重排）、human（人盘，福德宫为命宫重排）。",
    )
    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="紫微规则配置：iztro_2_5_8（软件基线）或 quanshu_v2_excerpt（全书摘录）。",
    )
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = Field(
        default=None,
        description="闰月月序口径：split_at_day_15（十五日前作当月、十六日起作下月）、all_current_month（全月作当月）、all_next_month（全月作下月）。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="四化表：rule_profile（随流派/配置）、iztro_2_5_8、quanshu_v2、naj_ming_v1（明刊庚日武同相）、feixing_liang（梁若瑜飞星）、qintian（钦天四化）。",
    )
    brightness_source: ZiweiBrightnessSource = Field(
        default="rule_profile", description=BRIGHTNESS_SOURCE_DESCRIPTION
    )
    day_divide: ZiweiDayDivide = Field(
        default=DEFAULT_ZIWEI_DAY_DIVIDE,
        description="晚子（23:00-23:59）分日口径：current（当日）或 forward（次日早子翻日，虚岁与流年同步）。",
    )
    year_divide: ZiweiYearDivide = Field(
        default=DEFAULT_ZIWEI_YEAR_DIVIDE,
        description="年界口径：normal（正月初一换年，默认）或 exact（立春换年）。",
    )


class ZiweiBirthRequest(ZiweiSharedOptions):
    """Request model for Zi Wei birth chart analysis."""


class ZiweiHoroscopeRequest(ZiweiSharedOptions):
    """Request model for 紫微斗数 horoscope (运限) at an analysis date-time."""

    analysis_year: int | None = Field(
        default=None,
        description="分析公历年（可选）；省略全部分析时间分量时按本次as_of或执行开始时刻，部分省略时缺失的年/月/日取当前值，时/分默认0。",
    )
    analysis_month: int | None = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12, optional)"
    )
    analysis_day: int | None = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31, optional)"
    )
    analysis_hour: int | None = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23, optional)"
    )
    analysis_minute: int | None = Field(
        default=None,
        ge=0,
        le=59,
        description="Analysis minute (0-59, optional)",
    )
    analysis_timezone: str = Field(
        default="Asia/Shanghai",
        description="分析钟表时间的时区，与出生时区独立；默认 Asia/Shanghai。",
    )
    analysis_utc_offset: str | None = Field(
        default=None,
        description="分析钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS。",
    )
    nominal_age_basis: ZiweiAgeBasis = Field(
        default="birth_civil_timezone",
        description="岁序基准时区：birth_civil_timezone（出生民用时区）。",
    )
    horoscope_divide: ZiweiHoroscopeDivide = Field(
        default=DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
        description="流月分界口径：normal（农历月建，默认）或 exact（节气月建）。",
    )
    age_divide: ZiweiAgeDivide = Field(
        default=DEFAULT_ZIWEI_AGE_DIVIDE,
        description="虚岁换岁口径：normal（正月初一换岁，默认）或 birthday（按农历生日换岁）。",
    )
    include_decadal_list: bool = Field(
        default=False,
        description="是否返回十二步大限速览列表（decadal_list）。",
    )
    include_yearly_list: bool = Field(
        default=False,
        description="是否返回当前大限十年流年速览列表（yearly_list）。",
    )
    include_monthly_list: bool = Field(
        default=False,
        description="是否返回目标年十二流月速览列表（monthly_list）。",
    )


class ZiweiRulesRequest(FateBridgeBaseRequest):
    """Request model for Zi Wei rule catalogue lookup."""

    school: ZiweiSchool = Field(
        default=DEFAULT_ZIWEI_SCHOOL,
        description="紫微流派：default / zhongzhou / quanshu / feixing。",
    )
    astro_type: ZiweiAstroType = Field(
        default=DEFAULT_ZIWEI_ASTRO_TYPE,
        description="天地人三盘：heaven / earth / human。",
    )
    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="要查询的紫微规则配置。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="要查询的四化表。",
    )
    brightness_source: ZiweiBrightnessSource = Field(
        default="rule_profile", description=BRIGHTNESS_SOURCE_DESCRIPTION
    )
    day_divide: ZiweiDayDivide = Field(
        default=DEFAULT_ZIWEI_DAY_DIVIDE,
        description="晚子（23:00-23:59）分日口径：current 或 forward。",
    )
    year_divide: ZiweiYearDivide = Field(
        default=DEFAULT_ZIWEI_YEAR_DIVIDE,
        description="年界口径：normal 或 exact。",
    )
    year_stem: str | None = Field(
        default=None,
        description="Optional heavenly stem filter, e.g. 甲",
    )
