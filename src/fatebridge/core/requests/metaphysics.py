"""Request contracts for metaphysics."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, model_validator

from fatebridge.core.metaphysics.jinkou_year_fate import confirmed_natal_branch
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.taiyi_hour import TaiyiHourProfile
from fatebridge.core.metaphysics.taiyi_month import TaiyiMonthProfile
from fatebridge.core.metaphysics.taiyi_shiji import TaiyiShijiProfile
from fatebridge.core.metaphysics.taiyi_year_calendar import TaiyiYearProfile
from fatebridge.core.requests.base import (
    FateBridgeBaseRequest,
    RequiredAnalysisClockFields,
)
from fatebridge.core.requests.birth import FateBridgeRequest
from fatebridge.core.ziwei.ziwei_age import ZiweiAgeBasis
from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    ZiweiDayDivide,
    ZiweiNatalLeapMonthPolicy,
    ZiweiRuleProfile,
    ZiweiSihuaSource,
)
from fatebridge.core.ziwei.ziwei_tables import (
    BRIGHTNESS_SOURCE_DESCRIPTION,
    ZiweiBrightnessSource,
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


class QimenOptions(FateBridgeBaseRequest):
    """Typed Qi Men Dun Jia configuration options."""

    layout: Literal["direct", "rotating"] = Field(
        default="direct",
        description="转盘排法：仅支持 direct/rotating；飞盘/镜像/反转未实现。",
    )
    palaceShift: StrictInt = Field(
        default=0,
        ge=0,
        le=0,
        description="九宫平移量；仅允许 0（移动九宫内容不能冒充飞盘排法）。",
    )
    palace_shift: StrictInt = Field(
        default=0,
        ge=0,
        le=0,
        description="palaceShift 的蛇形命名别名；仅允许 0。",
    )
    ju_method: Literal["zhirun", "chaibu"] = Field(
        default="zhirun",
        description="定局法：zhirun（默认置闰）或 chaibu（拆补）。",
    )
    god_profile: Literal["yanyi_text", "yanyi_diagrams"] = Field(
        default="yanyi_text",
        description="八神表：yanyi_text（默认卷三正文）或 yanyi_diagrams（卷四圆图）。",
    )
    season_profile: Literal[
        "yanyi_vol1_verse", "yanyi_vol3_table", "yanyi_vol3_prose"
    ] = Field(
        default="yanyi_vol1_verse",
        description="九星旺衰表：yanyi_vol1_verse（默认卷一烟波钓叟赋）、yanyi_vol3_table（卷三表）或 yanyi_vol3_prose（卷三正文）。",
    )


class TaiyiOptions(FateBridgeBaseRequest):
    """Typed Taiyi Shenshu calculation mode and edition-profile options."""

    calculation_mode: Literal["year", "month", "day", "hour"] = Field(
        default="year",
        description="year年计附金镜年度十神；month按十二节月；day明确采用金钥匙冬至前甲子积日，不乘十二，所选钟面零时换日、二至实刻换遁，附十精及未决异数；hour按所选时计。月/日/时计均为声明的现代天文适配，非完整古历复原。",
    )
    hour_profile: TaiyiHourProfile | None = Field(
        default=None,
        description="仅hour时计：省略用jinjing_hour_solstice_v1（现代至点置一）；key_hour_winter_jiazi_v1按金钥匙冬至前甲子日连续积时、时支合神和阴阳四门，仍为现代日期/23时子初适配，非古历全书认证。不可按吉凶结果择优。",
    )
    month_profile: TaiyiMonthProfile | None = Field(
        default=None,
        description="仅month：省略为jinjing_month_jie_360_v1；key_month_tianzheng_jie_v1采用金钥匙完年乘十二、加天地二正和本月名义序，仍以现代节月为界，非完整古历月界；源文门数冲突保留，不按吉凶择法。",
    )
    year_profile: TaiyiYearProfile | None = Field(
        default=None,
        description="仅year：省略或jinjing_year_lunar_civil_v1保留通用现代农历岁首；jinjing_year_historical_table_v1选381—385晋历主表；jinjing_year_qiliang_table_v1选501—505齐梁史历表，保留502年闰四月及未决闰五月／六月候选。两者范围外均拒绝。输入仍用推算公历和明确时区；非全部古历、并立王朝异历或原典岁首裁定，不按吉凶择法。",
    )
    shiji_profile: TaiyiShijiProfile | None = Field(
        default=None,
        description=(
            "始击来源。默认 jinjing_vol2_rotation_v1 按《金镜》卷二推演。"
            "jinjing_vol3_table_v1 对阴遁37、43、44局采用卷三表列始击并按卷二重算客算。"
            "jinjing_vol3_table_literal_v1 对这三局采用卷三表列始击和客算。"
        ),
    )

    @model_validator(mode="after")
    def _validate_mode_profiles(self) -> "TaiyiOptions":
        if self.year_profile is not None and self.calculation_mode != "year":
            raise ValueError("year_profile仅用于year年计")
        if self.month_profile is not None and self.calculation_mode != "month":
            raise ValueError("month_profile仅用于month月计")
        if self.hour_profile is not None and self.calculation_mode != "hour":
            raise ValueError("hour_profile仅用于hour时计，不能用于年计、月计或日计")
        return self


class LiuRengGodsRequest(RequiredAnalysisClockFields, FateBridgeBaseRequest):
    """Request model for Liu Ren divination."""

    guiren_profile: GuirenProfile = Field(
        default=DEFAULT_GUIREN_PROFILE,
        description="大六壬昼夜贵人表：liuren_common_v1 为既有表；tanyuan_xieji_v1 按探原日夜贵人歌。金口诀仅影响附带六壬盘，本课独立用古本表。",
    )
    is_diurnal: bool | None = Field(
        default=None,
        description="显式昼贵/夜贵：true 昼、false 夜；省略按卯至申昼、酉至寅夜。未自动计算当地星没星出。",
    )
    gender: str | None = Field(
        default="未知",
        description=(
            "性别（可选）。接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；"
            "省略默认 未知。"
        ),
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time correction (default on — 式占 keys off the apparent-solar 时辰)",
    )


class LiuRengRunyearRequest(RequiredAnalysisClockFields, FateBridgeRequest):
    """Request model for Liu Ren runyear analysis."""

    birth_timezone: str | None = Field(
        default=None,
        description="出生民用时区；显式值优先，否则按唯一解析的birth_place补全。已给但无法解析的地名、或只有经度时须明确时区；地理信息全缺时沿用Asia/Shanghai并标记默认假设。出生与分析瞬间均转换到该时区计算农历虚岁，不移动分析课盘。",
    )
    birth_utc_offset: str | None = Field(
        default=None,
        description="出生民用钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与显式或出生地补全后的出生时区核对并选择重复时刻，不替换命名时区。省略时拒绝歧义或不存在的出生钟时。仅用于出生民用时刻与农历年，不移动分析起课时刻。",
    )
    guiren_profile: GuirenProfile = Field(
        default=DEFAULT_GUIREN_PROFILE,
        description="大六壬昼夜贵人表；tanyuan_xieji_v1 仅采用探原贵人表，不代表全书取传配置。",
    )
    is_diurnal: bool | None = Field(
        default=None, description="分析时刻是否按昼贵起课；省略按时支区分昼夜。"
    )


class QimenAnalysisRequest(RequiredAnalysisClockFields, FateBridgeBaseRequest):
    """Request model for Qi Men analysis."""

    qimen_options: QimenOptions = Field(
        default_factory=QimenOptions,
        description="奇门选项：ju_method=zhirun（默认置闰）/chaibu（拆补）；god_profile=yanyi_text（默认卷三正文）/yanyi_diagrams（卷四圆图）；season_profile=yanyi_vol1_verse（默认卷一赋）/yanyi_vol3_table/yanyi_vol3_prose；仅支持转盘layout=direct、palaceShift=0",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time correction (default on — 奇门 定局 keys off the apparent-solar 时辰)",
    )


class TaiyiAnalysisRequest(RequiredAnalysisClockFields, TaiyiOptions):
    """Request model for Taiyi analysis."""

    analysis_year: int = Field(
        description="推算公历年，例如2026；历史儒略历标签须先明确转换，不按1582年自动切换历制。"
    )
    gender: str | None = Field(
        default="未知",
        description=(
            "性别（可选）。接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；"
            "省略默认 未知；当前年计不使用性别定局。"
        ),
    )
    use_true_solar_time: bool = Field(
        default=False,
        description="年计农历岁首按输入钟表日期；月计按真实节气瞬间。日/时计为true时用经度及均时差的本地真太阳钟，为false时按时区钟表标签计数。日计所选钟面零时换日，时计23时子初，不能混用。",
    )


class JinkouAnalysisRequest(LiuRengGodsRequest):
    """Request model for Jin Kou analysis."""

    di_fen: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = Field(
        default=None,
        description="地分十二地支；不填按时支作软件回退，并非已观测的来人方位。",
    )
    natal_branch: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = Field(
        default=None,
        description="问课对象已确认的本命年支，用于京本将命大绝配对及本命另课。另课以本命支作派生地分，保留本次占时，与原地分主课分列。省略且已给birth_year_ganzhi时取其明确年支；两者并给须一致。不由占时、地分或行年推定，不要求补猜出生时刻。",
    )
    birth_year_ganzhi: str | None = Field(
        default=None,
        strict=True,
        description="已确认的完整出生年干支，须属六十甲子；供京本六甲旬起行年、本命年支和本命另课。本命另课不要求性别或岁序。不是公历年份，不从占时、年龄反推或代猜岁首。",
    )
    year_fate_age: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=150,
        description="明确提供的一岁起算行年岁序，非周岁或寿限。与出生年干支及已知男/女齐备才另起行年课；不由生日、占时推算，也未认证原典换岁边界。",
    )

    @model_validator(mode="after")
    def consistent_jinkou_natal_facts(self) -> "JinkouAnalysisRequest":

        confirmed_natal_branch(
            self.birth_year_ganzhi, self.natal_branch, self.year_fate_age
        )
        return self
