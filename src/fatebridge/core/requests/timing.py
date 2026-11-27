"""Request contracts for timing."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from fatebridge.core.bazi.policies import YearBoundaryPolicy
from fatebridge.core.requests.base import OptionalAnalysisClockFields
from fatebridge.core.requests.birth import BaziClockRequest

_YEAR_BOUNDARY_DESCRIPTION = (
    "年柱换年口径：lichun（默认，立春换年；提供月份/日期时按立春精确时刻判断，"
    "仅传analysis_year时视为该太阳年）或 gregorian（按公历整数年份）。"
)


class TimingAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for comprehensive timing analysis."""

    analysis_year: int | None = Field(
        default=None,
        description="完全省略全部analysis_*日期分量时，使用本次as_of或执行开始时刻的完整当地瞬间；提供任一日期分量时沿用部分日期规则：缺年/月取当前年/月，缺日取1、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_age: int | None = Field(
        default=None, ge=0, description="Analysis age override"
    )
    birth_time_uncertainty_minutes: int | None = Field(
        default=None,
        ge=0,
        le=120,
        description="仅传用户确认的名义出生参考正负UTC经过分钟范围；保留分钟网格，并补充计算节令、钟面、大运名义月进位与当前分析日附近未来跳时逆像探针。未认证全部连续交运状态或极值。None表示未提供范围，不表示精确生时。",
    )
    year_boundary_policy: YearBoundaryPolicy = Field(
        default="lichun", description=_YEAR_BOUNDARY_DESCRIPTION
    )
    include_timelines: bool = Field(
        default=False,
        description="是否同时返回分析年的二十四节气网格、十二节流月时间轴与节气节点时间轴。",
    )


class DayunAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for dayun analysis."""

    gender: str = Field(
        description=(
            "性别（必填：决定大运顺逆/起运方向，无法以默认值替代）。"
            "接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法。"
        )
    )
    analysis_age: int | None = Field(
        default=None,
        ge=0,
        description="显式年龄参考；省略时按分析时刻及交运边界选运。不能与analysis_*日期同时传入。",
    )
    birth_time_uncertainty_minutes: int | None = Field(
        default=None,
        ge=0,
        le=120,
        description="仅传用户确认的名义出生参考正负UTC经过分钟范围；保留分钟网格，并补充计算节令、钟面、大运名义月进位与当前分析日附近未来跳时逆像探针。未认证全部连续交运状态或极值。None表示未提供范围，不表示精确生时。",
    )
    analysis_year: int | None = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间选运；显式部分日期缺年取当前年、缺月日取1、缺时分取0。不能与analysis_age组合。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )

    @model_validator(mode="after")
    def separate_age_and_date(self) -> DayunAnalysisRequest:
        if self.analysis_age is not None and any(
            value is not None
            for value in (
                self.analysis_year,
                self.analysis_month,
                self.analysis_day,
                self.analysis_hour,
                self.analysis_minute,
            )
        ):
            raise PydanticCustomError(
                "conflicting_analysis_reference",
                "analysis_age年龄参考不能与analysis_*分析日期同时使用",
                {"path": "analysis_age"},
            )
        return self


class LiunianAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for liunian analysis."""

    analysis_year: int | None = Field(
        default=None,
        description=(
            "目标分析年份；省略全部analysis_*日期分量时取本次as_of或执行开始时刻。"
            "仅传analysis_year且year_boundary_policy=lichun时，按该太阳年计算流年；"
            "同时传入analysis_month等细分日期时，按该时刻在立春前后的实际归属年。"
        ),
    )
    end_year: int | None = Field(
        default=None,
        description="可选结束年份；传入时返回从起始年到end_year的多年流年时间轴（含首尾最多20年）。",
    )
    year_boundary_policy: YearBoundaryPolicy = Field(
        default="lichun", description=_YEAR_BOUNDARY_DESCRIPTION
    )

    @model_validator(mode="after")
    def validate_year_range(self) -> LiunianAnalysisRequest:
        if self.end_year is not None and self.analysis_year is not None:
            if self.end_year < self.analysis_year:
                raise PydanticCustomError(
                    "invalid_year_range",
                    "end_year不能小于analysis_year",
                    {"path": "end_year"},
                )
            if self.end_year - self.analysis_year + 1 > 20:
                raise PydanticCustomError(
                    "year_range_too_large",
                    "年份扫描范围最多20年（end_year - analysis_year + 1 <= 20）",
                    {"path": "end_year"},
                )
        return self


class LiuriAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for liuri analysis."""

    analysis_year: int | None = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间取流日，保留晚子时规则；显式部分日期缺年月日取当前值、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    scan_days: int | None = Field(
        default=None,
        ge=1,
        le=31,
        description="可选连续扫描天数（1–31）；传入时返回从分析日起的逐日流日时间轴。",
    )


class LiushiAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for liushi analysis."""

    analysis_year: int | None = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间分析；显式部分日期缺年月日时取当前值，缺分钟取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )


class JieqiTimelineRequest(BaziClockRequest):
    """Request model for jieqi timeline analysis."""

    analysis_year: int | None = Field(default=None, description="Target year")


class LiuyueAnalysisRequest(OptionalAnalysisClockFields, BaziClockRequest):
    """Request model for liuyue analysis."""

    analysis_year: int | None = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间取节令月；显式部分日期缺年/月取当前年/月，缺日取15、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    year_boundary_policy: YearBoundaryPolicy = Field(
        default="lichun", description=_YEAR_BOUNDARY_DESCRIPTION
    )
    scan_months: int | None = Field(
        default=None,
        ge=1,
        le=24,
        description="可选连续扫描节令月数（1–24）；传入时按十二节顺序返回连续流月时间轴。",
    )
