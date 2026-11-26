"""Civil-time inputs for Human Design, without irrelevant house coordinates."""

from typing import Any, Literal

from pydantic import Field, model_validator

from fatebridge.core.requests.base import FateBridgeBaseRequest


class HumanDesignRequest(FateBridgeBaseRequest):
    name: str | None = Field(default=None, description="显示名称，不参与计算")
    birth_year: int = Field(ge=1800, le=2399, description="公历年；不自动转换儒略历")
    birth_month: int = Field(ge=1, le=12, description="公历出生月，1至12")
    birth_day: int = Field(ge=1, le=31, description="公历出生日，另校验月份实际天数")
    birth_hour: int = Field(
        ge=0, le=23, description="记录的当地民用出生时；未知时不能套默认"
    )
    birth_minute: int = Field(ge=0, le=59, description="出生分钟，必须提供")
    birth_second: int = Field(
        default=0,
        ge=0,
        le=60,
        description="省略按第0秒计算；60仅接受冻结IERS已公布的UTC正闰秒",
    )
    birth_timezone: str = Field(
        description="必须提供 IANA 时区、UTC 偏移或十进制小时数"
    )
    node_mode: Literal["true", "mean"] = Field(
        default="true",
        description="真交点或平交点",
    )
    require_swiss_files: bool = Field(
        default=False,
        description="为真时要求实际使用 Swiss 数据文件；否则允许 Moshier 后端",
    )
    birth_time_uncertainty_minutes: int = Field(
        default=0,
        ge=0,
        le=60,
        description="可选出生时间正负误差分钟（1–60）；0表示未评估",
    )
    cycle_reference_datetime: str | None = Field(
        default=None,
        description="可选带时区ISO时刻，计算出生起65儒略年内土星回归、天王星对冲及凯龙星回归",
    )
    transit_datetime: str | None = Field(
        default=None,
        description="可选带时区ISO行运时刻，叠加当前行运闸门与通道",
    )
    partner: dict[str, Any] | None = Field(
        default=None,
        description="可选合盘对象出生参数（含 birth_year..birth_timezone），计算关系合盘通道",
    )

    @model_validator(mode="after")
    def _validate_clock(self) -> "HumanDesignRequest":
        from fatebridge.core.human_design.time import resolve_birth_clock

        resolve_birth_clock(
            birth_year=self.birth_year,
            birth_month=self.birth_month,
            birth_day=self.birth_day,
            birth_hour=self.birth_hour,
            birth_minute=self.birth_minute,
            birth_second=self.birth_second,
            birth_timezone=self.birth_timezone,
        )
        if self.cycle_reference_datetime is not None:
            from fatebridge.core.human_design.cycles import validate_cycle_reference

            validate_cycle_reference(
                **self.model_dump(
                    include={
                        "birth_year",
                        "birth_month",
                        "birth_day",
                        "birth_hour",
                        "birth_minute",
                        "birth_second",
                        "birth_timezone",
                        "cycle_reference_datetime",
                    }
                )
            )
        return self
