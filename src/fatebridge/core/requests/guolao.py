"""Request schema for Guolao Xingzong (七政四余 / 果老星宗) calculations."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from fatebridge.core.requests.base import (
    FateBridgeBaseRequest,
    OfflineHouseValidatorMixin,
)


class GuolaoChartRequest(OfflineHouseValidatorMixin, FateBridgeBaseRequest):
    name: str | None = Field(default=None, description="姓名或备注标签，不参与计算")
    birth_year: int = Field(ge=1800, le=2399, description="公历出生年")
    birth_month: int = Field(ge=1, le=12, description="公历出生月")
    birth_day: int = Field(ge=1, le=31, description="公历出生日")
    birth_hour: int = Field(ge=0, le=23, description="出生小时（0-23）")
    birth_minute: int = Field(default=0, ge=0, le=59, description="出生分钟（0-59）")
    birth_second: int = Field(default=0, ge=0, le=60, description="出生秒（0-60）")
    birth_timezone: str | None = Field(default=None, description="IANA 时区或 UTC 偏移")
    birth_place: str | None = Field(
        default=None, description="出生地名称（可辅助解析时区）"
    )
    birth_longitude: float | None = Field(
        default=116.4074, ge=-180, le=180, description="出生地经度"
    )
    birth_latitude: float | None = Field(
        default=39.9042, ge=-90, le=90, description="出生地纬度"
    )
    use_true_solar_time: bool = Field(default=True, description="是否标记使用真太阳时")
    house_system: int | str | None = Field(default=None, description="参考天文宫位制")
    zodiac_type: Literal["Tropic", "Sidereal"] | None = Field(
        default=None, description="黄道体制"
    )
    mansion_frame: Literal[
        "modern_equatorial",
        "modern_ecliptic",
        "shoushi_ecliptic",
        "shoushi_equatorial",
    ] = Field(
        default="modern_equatorial",
        description="宿度体系：modern_equatorial/ecliptic（今度360°）或 shoushi_ecliptic/equatorial（古度365.2575°）",
    )
    life_degree_method: Literal["sun_degree_in_palace", "ascendant"] = Field(
        default="sun_degree_in_palace",
        description="命度算法：sun_degree_in_palace（太阳所在宫度入命宫）或 ascendant",
    )
    analysis_datetime: datetime | None = Field(
        default=None,
        description="可选带时区流年推运时刻（计算小限、洞微大限当前限及行运星象）",
    )
    month_basis: Literal["jie_month", "chinese_lunar_utc8"] | None = Field(
        default=None, description="可选月限起算标准：jie_month 或 chinese_lunar_utc8"
    )
