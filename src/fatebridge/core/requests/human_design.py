"""Civil-time inputs for Human Design, without irrelevant house coordinates."""

from typing import Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.requests.base import _DeferredModel


class HumanDesignRequest(_DeferredModel):
    name: Optional[str] = Field(default=None, description="显示名称，不参与计算")
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
        description="省略按所记分钟的第0秒计算；60仅接受冻结IERS已公布且经当地时区换算确认的UTC正闰秒，不认证出生记录精度",
    )
    birth_timezone: str = Field(
        description="必须提供 IANA 时区、UTC 偏移或十进制小时数；显式偏移限±15小时，十进制按最近微秒取偶转换并回显量化；DST 重复时刻需用明确偏移消歧；时区规则未指定当地偏移的历史日期须补充已核实偏移，不能当作零偏移"
    )
    node_mode: Literal["true", "mean"] = Field(
        default="true",
        description="真交点或平交点；这是一项显式计算约定，未认证与原版软件完全一致",
    )
    require_swiss_files: bool = Field(
        default=False,
        description="为真时要求实际使用 Swiss 数据文件；否则允许并回显 Moshier 后端",
    )
    birth_time_uncertainty_minutes: int = Field(
        default=0,
        ge=0,
        le=60,
        description="可选的出生时间正负范围；10秒TT网格、速度变号及已观测多依赖过渡细查，不认证连续区间穷尽；0表示未评估",
    )
    cycle_reference_datetime: Optional[str] = Field(
        default=None,
        description="可选带时区ISO时刻；当地时间的小数按最低已给单位（小时、分钟或秒）精确展开，最多6位，超限拒绝而非截断。提供才计算出生起65儒略年内土星首轮回归、天王星对冲及凯龙星首轮回归的多次交会与该时刻的相对位置。须在源定义的连续TT上不早于出生；输入顺序校验不认证微秒级天文精度。不按生日划阶段，不默认当前时间。有限采样不认证穷尽。",
    )
    compare_cycle_origins: bool = Field(
        default=False,
        description="可选比较人格与实际88度太阳弧设计TT两个周期原点；须同时提供cycle_reference_datetime。人格主结果不改，设计原点仅为数学敏感性假设，未获原典优先性认证；完整保留两边交会及失败，不指定首末触优先或人生阶段。",
    )

    @model_validator(mode="after")
    def _validate_clock(self) -> "HumanDesignRequest":
        if self.compare_cycle_origins and self.cycle_reference_datetime is None:
            raise ValueError("周期原点对照须提供cycle_reference_datetime")
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
            from fatebridge.core.human_design_cycle_input import (
                validate_cycle_reference,
            )

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
