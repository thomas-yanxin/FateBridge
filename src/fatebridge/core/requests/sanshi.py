"""Request contracts for SanShi (Liuren, Qimen, Taiyi) and Jinkou."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, model_validator

from fatebridge.core.requests.base import (
    FateBridgeBaseRequest,
    RequiredAnalysisClockFields,
)
from fatebridge.core.requests.birth import FateBridgeRequest

GuirenProfile = Literal["liuren_common_v1", "tanyuan_xieji_v1"]
DEFAULT_GUIREN_PROFILE: GuirenProfile = "liuren_common_v1"
TaiyiHourProfile = Literal["jinjing_hour_solstice_v1", "key_hour_winter_jiazi_v1"]
TaiyiMonthProfile = Literal["jinjing_month_jie_360_v1", "key_month_tianzheng_jie_v1"]
TaiyiYearProfile = Literal[
    "jinjing_year_lunar_civil_v1",
    "jinjing_year_historical_table_v1",
    "jinjing_year_qiliang_table_v1",
]
TaiyiShijiProfile = Literal[
    "jinjing_vol2_rotation_v1",
    "jinjing_vol3_table_v1",
    "jinjing_vol3_table_literal_v1",
]


class QimenOptions(FateBridgeBaseRequest):
    """Typed Qi Men Dun Jia configuration options."""

    layout: Literal["direct", "rotating", "fei"] = Field(
        default="direct",
        description="排盘法：direct/rotating（转盘）或 fei（飞盘）。",
    )
    ju_method: Literal["zhirun", "chaibu", "maoshan"] = Field(
        default="zhirun",
        description="定局法：zhirun（默认置闰）、chaibu（拆补）或 maoshan（茅山）。",
    )
    lodging_policy: Literal["kun2", "gen8", "yin_gen_yang_kun"] = Field(
        default="kun2",
        description="转盘中五寄宫：kun2（默认寄坤二）、gen8（寄艮八）或 yin_gen_yang_kun（阳遁寄坤阴遁寄艮）。",
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
        description="year年计附金镜年度十神；month按十二节月；day采用金钥匙冬至前甲子积日；hour按所选时计。",
    )
    hour_profile: TaiyiHourProfile | None = Field(
        default=None,
        description="仅hour时计：省略用jinjing_hour_solstice_v1（至点置一）；key_hour_winter_jiazi_v1按金钥匙冬至前甲子日连续积时、时支合神和阴阳四门。",
    )
    month_profile: TaiyiMonthProfile | None = Field(
        default=None,
        description="仅month：省略为jinjing_month_jie_360_v1；key_month_tianzheng_jie_v1采用金钥匙完年乘十二、加天地二正和本月名义序。",
    )
    year_profile: TaiyiYearProfile | None = Field(
        default=None,
        description="仅year：省略或jinjing_year_lunar_civil_v1用通用现代农历岁首；jinjing_year_historical_table_v1选381—385晋历主表；jinjing_year_qiliang_table_v1选501—505齐梁史历表。",
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
        description="大六壬昼夜贵人表：liuren_common_v1 为既有表；tanyuan_xieji_v1 按探原日夜贵人歌。",
    )
    is_diurnal: bool | None = Field(
        default=None,
        description="显式昼贵/夜贵：true 昼、false 夜；省略按卯至申昼、酉至寅夜。",
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
        description="出生民用时区；显式值优先，否则按唯一解析的birth_place补全。出生与分析瞬间均转换到该时区计算农历虚岁，不移动分析课盘。",
    )
    birth_utc_offset: str | None = Field(
        default=None,
        description="出生民用钟时的明确UTC偏移，格式±HH:MM或±HH:MM:SS；与出生时区核对并选择重复时刻，不替换命名时区。",
    )
    guiren_profile: GuirenProfile = Field(
        default=DEFAULT_GUIREN_PROFILE,
        description="大六壬昼夜贵人表：liuren_common_v1 或 tanyuan_xieji_v1。",
    )
    is_diurnal: bool | None = Field(
        default=None, description="分析时刻是否按昼贵起课；省略按时支区分昼夜。"
    )


class QimenAnalysisRequest(RequiredAnalysisClockFields, FateBridgeBaseRequest):
    """Request model for Qi Men analysis."""

    qimen_options: QimenOptions = Field(
        default_factory=QimenOptions,
        description="奇门选项：ju_method=zhirun（默认置闰）/chaibu（拆补）；god_profile=yanyi_text（默认卷三正文）/yanyi_diagrams（卷四圆图）；season_profile=yanyi_vol1_verse（默认卷一赋）/yanyi_vol3_table/yanyi_vol3_prose；layout=direct/rotating。",
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
        description="年计农历岁首按输入钟表日期；月计按真实节气瞬间；日/时计为true时用真太阳钟，为false时按时区钟表计数。",
    )


class JinkouAnalysisRequest(LiuRengGodsRequest):
    """Request model for Jin Kou analysis."""

    di_fen: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = Field(
        default=None,
        description="地分十二地支；不填按时支作软件回退。",
    )
    natal_branch: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = Field(
        default=None,
        description="问课对象已确认的本命年支，用于京本将命大绝配对及本命另课。省略且已给birth_year_ganzhi时取其年支；两者并给须一致。",
    )
    birth_year_ganzhi: str | None = Field(
        default=None,
        strict=True,
        description="已确认的完整出生年干支，须属六十甲子；供京本六甲旬起行年、本命年支和本命另课。",
    )
    year_fate_age: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=150,
        description="明确提供的一岁起算行年岁序，非周岁。与出生年干支及已知男/女齐备才另起行年课。",
    )

    @model_validator(mode="after")
    def consistent_jinkou_natal_facts(self) -> "JinkouAnalysisRequest":
        from fatebridge.core.metaphysics.jinkou_year_fate import confirmed_natal_branch

        confirmed_natal_branch(
            self.birth_year_ganzhi, self.natal_branch, self.year_fate_age
        )
        return self
