"""Request contracts for metaphysics."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.taiyi_hour import TaiyiHourProfile
from fatebridge.core.metaphysics.taiyi_month import TaiyiMonthProfile
from fatebridge.core.metaphysics.taiyi_year_calendar import TaiyiYearProfile
from fatebridge.core.requests.base import _DeferredModel
from fatebridge.core.requests.birth import FateBridgeRequest
from fatebridge.core.ziwei_age import ZiweiAgeBasis
from fatebridge.core.ziwei_rulesets import (
    DEFAULT_ZIWEI_PROFILE,
    ZiweiRuleProfile,
    ZiweiSihuaSource,
)


class ZiweiBirthRequest(FateBridgeRequest):
    """Request model for Zi Wei birth chart analysis."""

    birth_utc_offset: Optional[str] = Field(
        default=None,
        description="出生钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与解析后的birth_timezone核对，用于选择重复钟时，不替换命名时区。省略仍拒绝歧义或不存在的钟时。",
    )

    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="紫微规则：iztro_2_5_8 保留软件口径；quanshu_v2_excerpt 1.3.2 选择闰月、四化、亮度、长生、旬空双支、部分流年星，以及邻宫起大限、火铃年支定点读法；另用sihua_source显式选四化表，非全书认证。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="四化表：rule_profile沿用基础配置；naj_ming_v1显式取明刊卷三原页（庚日武同相、壬梁紫府武）。只选四化表，不代表整部原典获认证。",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class ZiweiHoroscopeRequest(FateBridgeRequest):
    """Request model for 紫微斗数 horoscope (运限) at a target date-time."""

    birth_utc_offset: Optional[str] = Field(
        default=None,
        description="出生钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与出生时区核对并选择重复钟时，不替换命名时区。",
    )

    target_year: int = Field(description="Target year, e.g., 2026")
    target_month: int = Field(ge=1, le=12, description="Target month (1-12)")
    target_day: int = Field(ge=1, le=31, description="Target day (1-31)")
    target_hour: int = Field(ge=0, le=23, description="Target hour (0-23)")
    target_minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Target minute (0-59); does not imply minute-level predictive accuracy",
    )
    target_timezone: str = Field(
        default="Asia/Shanghai",
        description="目标钟表时间的时区，与出生时区独立；默认 Asia/Shanghai，不对目标时刻做真太阳时修正。",
    )
    target_utc_offset: Optional[str] = Field(
        default=None,
        description="目标钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与target_timezone核对并选择重复钟时。省略仍拒绝歧义或不存在的目标钟时；实际先后按UTC瞬间比较。",
    )
    nominal_age_basis: ZiweiAgeBasis = Field(
        default="birth_civil_timezone",
        description="岁序默认birth_civil_timezone：出生与目标实际瞬间都按出生民用时区查农历年，正月初一00:00换岁，独立于真太阳安星及目标流曜钟。legacy_mixed_clock显式回放旧的目标钟表年减出生排盘年，可能拒绝春节边界；两者均非原典岁首认证。",
    )
    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="与本命盘共用的版本化紫微规则；quanshu_v2_excerpt 1.3.2 首大限从父母或兄弟起，火铃按年支定点读法；仍是部分摘录配置。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="本命与可用运限层共用所选四化表；naj_ming_v1取明刊原页。运限按宫干／时间干复用仍为软件约定，不据此认证古典运限法。",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class ZiweiRulesRequest(_DeferredModel):
    """Request model for Zi Wei rule catalogue lookup."""

    rule_profile: ZiweiRuleProfile = Field(
        default=DEFAULT_ZIWEI_PROFILE,
        description="要查询的紫微规则配置；quanshu_v2_excerpt 1.3.2 包括邻宫起大限、火铃年支定点读法，非全书认证。",
    )
    sihua_source: ZiweiSihuaSource = Field(
        default="rule_profile",
        description="要查询的实际四化表；naj_ming_v1为明刊卷三原页，不改变基础安星配置。",
    )
    year_stem: Optional[str] = Field(
        default=None,
        description="Optional heavenly stem filter, e.g. 甲",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class LiuRengGodsRequest(_DeferredModel):
    """Request model for Liu Ren divination."""

    analysis_year: int = Field(description="Analysis year, e.g., 2026")
    guiren_profile: GuirenProfile = Field(
        default=DEFAULT_GUIREN_PROFILE,
        description="大六壬昼夜贵人表：liuren_common_v1 为既有表；tanyuan_xieji_v1 按探原日夜贵人歌。金口诀仅影响附带六壬盘，本课独立用古本表。",
    )
    is_diurnal: Optional[bool] = Field(
        default=None,
        description="显式昼贵/夜贵：true 昼、false 夜；省略按卯至申昼、酉至寅夜。未自动计算当地星没星出。",
    )
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="起课钟表秒数，保留交中气和太阳时辰边界；不代表秒级预测能力。",
    )
    analysis_timezone: Optional[str] = Field(
        default=None, description="Analysis timezone (IANA name or UTC offset)"
    )
    analysis_utc_offset: Optional[str] = Field(
        default=None,
        description="起课民用钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与analysis_timezone共同核对并选择重复时刻，不替换命名时区规则。省略时拒绝歧义或不存在的钟时。",
    )
    analysis_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Analysis longitude"
    )
    gender: Optional[str] = Field(
        default="未知",
        description=(
            "性别（可选）。接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；"
            "省略默认 未知。"
        ),
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time correction (default on — 式占 keys off the apparent-solar 时辰)",
    )


class LiuRengRunyearRequest(FateBridgeRequest):
    """Request model for Liu Ren runyear analysis."""

    birth_timezone: Optional[str] = Field(
        default=None,
        description="出生民用时区；显式值优先，否则按唯一解析的birth_place补全。已给但无法解析的地名、或只有经度时须明确时区；地理信息全缺时沿用Asia/Shanghai并标记默认假设。出生与分析瞬间均转换到该时区计算农历虚岁，不移动分析课盘。",
    )
    birth_utc_offset: Optional[str] = Field(
        default=None,
        description="出生民用钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与显式或出生地补全后的出生时区核对并选择重复时刻，不替换命名时区。省略时拒绝歧义或不存在的出生钟时。仅用于出生民用时刻与农历年，不移动分析起课时刻。",
    )
    analysis_year: int = Field(description="Analysis year, e.g., 2026")
    guiren_profile: GuirenProfile = Field(
        default=DEFAULT_GUIREN_PROFILE,
        description="大六壬昼夜贵人表；tanyuan_xieji_v1 仅采用探原贵人表，不代表全书取传配置。",
    )
    is_diurnal: Optional[bool] = Field(
        default=None, description="分析时刻是否按昼贵起课；省略按时支区分昼夜。"
    )
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="分析时刻秒数（0-59），保留中气换将与时辰边界。",
    )
    analysis_timezone: Optional[str] = Field(
        default=None, description="Analysis timezone (IANA name or UTC offset)"
    )
    analysis_utc_offset: Optional[str] = Field(
        default=None,
        description="起课民用钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与analysis_timezone共同核对并选择重复时刻，不替换命名时区规则。省略时拒绝歧义或不存在的钟时。",
    )
    analysis_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Analysis longitude"
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class QimenAnalysisRequest(_DeferredModel):
    """Request model for Qi Men analysis."""

    analysis_year: int = Field(description="Analysis year, e.g., 2026")
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_timezone: Optional[str] = Field(
        default=None, description="Analysis timezone (IANA name or UTC offset)"
    )
    analysis_utc_offset: Optional[str] = Field(
        default=None,
        description="起局钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与analysis_timezone共同核对并消除重复小时歧义，不替换该时区的全年规则。省略时拒绝不明确或不存在的钟时。",
    )
    analysis_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Analysis longitude"
    )
    qimen_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="奇门选项：ju_method=zhirun（默认置闰）/chaibu（拆补）；god_profile=yanyi_text（默认卷三正文）/yanyi_diagrams（卷四圆图）；season_profile=yanyi_vol1_verse（默认卷一赋）/yanyi_vol3_table/yanyi_vol3_prose；仅支持转盘layout=direct、palaceShift=0",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time correction (default on — 奇门 定局 keys off the apparent-solar 时辰)",
    )


class TaiyiAnalysisRequest(_DeferredModel):
    """Request model for Taiyi analysis.

    太乙 does NOT take 奇门's ``qimen_options`` (layout/palaceShift) — it used to
    inherit ``QimenAnalysisRequest`` purely to reuse the date/time fields, which
    leaked ``qimen_options`` onto the 太乙 schema where it is meaningless. The
    fields below are exactly what ``calculate_taiyi_analysis`` consumes.
    """

    analysis_year: int = Field(
        description="推算公历年，例如2026；历史儒略历标签须先明确转换，不按1582年自动切换历制。"
    )
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="起盘秒数，用于节气实刻边界；不是秒级预测精度。",
    )
    calculation_mode: Literal["year", "month", "day", "hour"] = Field(
        default="year",
        description="year年计附金镜年度十神；month按十二节月；day明确采用金钥匙冬至前甲子积日，不乘十二，所选钟面零时换日、二至实刻换遁，附十精及未决异数；hour按所选时计。月/日/时计均为声明的现代天文适配，非完整古历复原。",
    )
    hour_profile: Optional[TaiyiHourProfile] = Field(
        default=None,
        description="仅hour时计：省略用jinjing_hour_solstice_v1（现代至点置一）；key_hour_winter_jiazi_v1按金钥匙冬至前甲子日连续积时、时支合神和阴阳四门，仍为现代日期/23时子初适配，非古历全书认证。不可按吉凶结果择优。",
    )
    month_profile: Optional[TaiyiMonthProfile] = Field(
        default=None,
        description="仅month：省略为jinjing_month_jie_360_v1；key_month_tianzheng_jie_v1采用金钥匙完年乘十二、加天地二正和本月名义序，仍以现代节月为界，非完整古历月界；源文门数冲突保留，不按吉凶择法。",
    )
    analysis_timezone: Optional[str] = Field(
        default=None, description="Analysis timezone (IANA name or UTC offset)"
    )
    analysis_utc_offset: Optional[str] = Field(
        default=None,
        description="明确的输入民用UTC偏移，格式±HH:MM或±HH:MM:SS；与analysis_timezone在该钟时联合核对，用于选择夏令时回拨中的一次，不替换命名时区。省略仍拒绝重复钟时；不存在的钟时及与时区不符的偏移均拒绝。不能按盘面结果猜选偏移。",
    )
    year_profile: Optional[TaiyiYearProfile] = Field(
        default=None,
        description="仅year：省略或jinjing_year_lunar_civil_v1保留通用现代农历岁首；jinjing_year_historical_table_v1选381—385晋历主表；jinjing_year_qiliang_table_v1选501—505齐梁史历表，保留502年闰四月及未决闰五月／六月候选。两者范围外均拒绝。输入仍用推算公历和明确时区；非全部古历、并立王朝异历或原典岁首裁定，不按吉凶择法。",
    )
    analysis_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Analysis longitude"
    )
    gender: Optional[str] = Field(
        default="未知",
        description=(
            "性别（可选）。接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；"
            "省略默认 未知；当前年计不使用性别定局。"
        ),
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
    use_true_solar_time: bool = Field(
        default=False,
        description="年计农历岁首按输入钟表日期；月计按真实节气瞬间。日/时计为true时用经度及均时差的本地真太阳钟，为false时按时区钟表标签计数。日计所选钟面零时换日，时计23时子初，不能混用。",
    )


class JinkouAnalysisRequest(LiuRengGodsRequest):
    """Request model for Jin Kou analysis."""

    di_fen: Optional[
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    ] = Field(
        default=None,
        description="地分十二地支；不填按时支作软件回退，并非已观测的来人方位。",
    )
    natal_branch: Optional[
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    ] = Field(
        default=None,
        description="问课对象已确认的本命年支，用于京本将命大绝配对及本命另课。另课以本命支作派生地分，保留本次占时，与原地分主课分列。省略且已给birth_year_ganzhi时取其明确年支；两者并给须一致。不由占时、地分或行年推定，不要求补猜出生时刻。",
    )
    birth_year_ganzhi: Optional[str] = Field(
        default=None,
        strict=True,
        description="已确认的完整出生年干支，须属六十甲子；供京本六甲旬起行年、本命年支和本命另课。本命另课不要求性别或岁序。不是公历年份，不从占时、年龄反推或代猜岁首。",
    )
    year_fate_age: Optional[int] = Field(
        default=None,
        strict=True,
        ge=1,
        le=150,
        description="明确提供的一岁起算行年岁序，非周岁或寿限。与出生年干支及已知男/女齐备才另起行年课；不由生日、占时推算，也未认证原典换岁边界。",
    )

    @model_validator(mode="after")
    def consistent_jinkou_natal_facts(self) -> "JinkouAnalysisRequest":
        from fatebridge.core.metaphysics.jinkou_year_fate import confirmed_natal_branch

        confirmed_natal_branch(
            self.birth_year_ganzhi, self.natal_branch, self.year_fate_age
        )
        return self
