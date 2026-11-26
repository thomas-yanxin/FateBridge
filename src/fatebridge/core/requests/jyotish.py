"""Request schemas for standalone Jyotish (Vedic Chart & Dasha) calculations."""

from typing import Literal

from pydantic import Field

from fatebridge.core.requests.base import FateBridgeBaseRequest


class VedicChartRequest(FateBridgeBaseRequest):
    name: str | None = Field(default=None, description="姓名或备注，不参与计算")
    birth_year: int = Field(ge=1800, le=2399, description="公历出生年")
    birth_month: int = Field(ge=1, le=12, description="公历出生月")
    birth_day: int = Field(ge=1, le=31, description="公历出生日")
    birth_hour: int = Field(ge=0, le=23, description="出生小时（0-23）")
    birth_minute: int = Field(default=0, ge=0, le=59, description="出生分钟（0-59）")
    birth_second: int = Field(default=0, ge=0, le=60, description="出生秒（0-60）")
    birth_timezone: str | None = Field(default=None, description="IANA 时区或 UTC 偏移")
    birth_place: str | None = Field(default=None, description="出生地名称")
    birth_longitude: float = Field(
        default=77.2090, ge=-180, le=180, description="出生地经度"
    )
    birth_latitude: float = Field(
        default=28.6139, ge=-90, le=90, description="出生地纬度"
    )
    ayanamsa: Literal["lahiri", "true_citra", "raman", "kp", "true_pushya"] = Field(
        default="lahiri", description="恒星岁差体系"
    )
    node_mode: Literal["mean", "true"] = Field(
        default="mean", description="罗睺/计都交点模式"
    )
    divisions: list[int] | None = Field(
        default=None, description="十六分盘列表（如 [9, 10]）；D1 始终计算"
    )
    ashtakavarga_profile: Literal["rao", "aiyar"] = Field(
        default="rao", description="八分表计算口径：rao 或 aiyar"
    )
    saptavargaja_profile: Literal["santhanam_27", "raman_30"] = Field(
        default="santhanam_27", description="七分盘力量表口径"
    )
    drekkana_profile: Literal["santhanam_27_6", "raman_36"] = Field(
        default="santhanam_27_6", description="三分盘力量口径"
    )
    cheshta_model: Literal["simon1994_j2000", "unadjudicated"] = Field(
        default="simon1994_j2000", description="五星运动力平位置模型"
    )


class VimshottariDashaRequest(FateBridgeBaseRequest):
    name: str | None = Field(default=None, description="姓名或备注，不参与计算")
    birth_year: int = Field(ge=1800, le=2399, description="公历出生年")
    birth_month: int = Field(ge=1, le=12, description="公历出生月")
    birth_day: int = Field(ge=1, le=31, description="公历出生日")
    birth_hour: int = Field(ge=0, le=23, description="出生小时（0-23）")
    birth_minute: int = Field(default=0, ge=0, le=59, description="出生分钟（0-59）")
    birth_second: int = Field(default=0, ge=0, le=60, description="出生秒（0-60）")
    birth_timezone: str | None = Field(default=None, description="IANA 时区或 UTC 偏移")
    birth_place: str | None = Field(default=None, description="出生地名称")
    birth_longitude: float = Field(
        default=77.2090, ge=-180, le=180, description="出生地经度"
    )
    birth_latitude: float = Field(
        default=28.6139, ge=-90, le=90, description="出生地纬度"
    )
    ayanamsa: Literal["lahiri", "true_citra", "raman", "kp", "true_pushya"] = Field(
        default="lahiri", description="恒星岁差体系"
    )
    year_basis: Literal[
        "julian_365_25", "sidereal_365_25636", "tropical_365_2425", "savana_360"
    ] = Field(default="julian_365_25", description="达沙年长口径")
    dasha_depth: int = Field(default=2, ge=2, le=6, description="达沙递归层数（2-6）")
    analysis_timezone: str | None = Field(default=None, description="分析时刻时区")
    analysis_year: int | None = Field(default=None, description="分析公历年")
    analysis_month: int | None = Field(
        default=None, ge=1, le=12, description="分析公历月"
    )
    analysis_day: int | None = Field(
        default=None, ge=1, le=31, description="分析公历日"
    )
    analysis_hour: int | None = Field(default=None, ge=0, le=23, description="分析小时")
    analysis_minute: int | None = Field(
        default=None, ge=0, le=59, description="分析分钟"
    )
    include_yogini: bool = Field(default=False, description="是否附带36年Yogini Dasha")
    include_ashtottari: bool = Field(
        default=False, description="是否附带108年Ashtottari Dasha"
    )
    include_chara: bool = Field(
        default=False, description="是否附带Jaimini Chara Dasha"
    )
