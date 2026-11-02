"""Request contracts for timing."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, model_validator

from fatebridge.core.requests.birth import BaziClockRequest


class TimingAnalysisRequest(BaziClockRequest):
    """Request model for comprehensive timing analysis."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="完全省略全部analysis_*日期分量时，使用本次as_of或执行开始时刻的完整当地瞬间；提供任一日期分量时沿用部分日期规则：缺年/月取当前年/月，缺日取1、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    analysis_hour: Optional[int] = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23)"
    )
    analysis_minute: Optional[int] = Field(
        default=None, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_age: Optional[int] = Field(
        default=None, ge=0, description="Analysis age override"
    )
    birth_time_uncertainty_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        le=120,
        description="仅传用户确认的名义出生参考正负UTC经过分钟范围；保留分钟网格，并补充计算节令、钟面、大运名义月进位与当前分析日附近未来跳时逆像探针。未认证全部连续交运状态或极值。None表示未提供范围，不表示精确生时。",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class DayunAnalysisRequest(BaziClockRequest):
    """Request model for dayun analysis."""

    gender: str = Field(
        description=(
            "性别（必填：决定大运顺逆/起运方向，无法以默认值替代）。"
            "接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法。"
        )
    )
    analysis_age: Optional[int] = Field(
        default=None,
        ge=0,
        description="显式年龄参考；省略时按分析时刻及交运边界选运。不能与analysis_*日期同时传入。",
    )
    birth_time_uncertainty_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        le=120,
        description="仅传用户确认的名义出生参考正负UTC经过分钟范围；保留分钟网格，并补充计算节令、钟面、大运名义月进位与当前分析日附近未来跳时逆像探针。未认证全部连续交运状态或极值。None表示未提供范围，不表示精确生时。",
    )
    analysis_year: Optional[int] = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间选运；显式部分日期缺年取当前年、缺月日取1、缺时分取0。不能与analysis_age组合。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Target local Gregorian month (1..12) for period-boundary selection. With any analysis_* date component, omitted month defaults to January. Cannot combine with analysis_age.",
    )
    analysis_day: Optional[int] = Field(
        default=None,
        ge=1,
        le=31,
        description="Target local Gregorian day, validated with year/month; defaults to 1 when a date component is supplied. Cannot combine with analysis_age.",
    )
    analysis_hour: Optional[int] = Field(
        default=None,
        ge=0,
        le=23,
        description="Target civil-clock hour (0..23) in the resolved birth timezone; defaults to midnight with a supplied analysis date. Used to distinguish exact luck-period boundaries, not to predict an event hour.",
    )
    analysis_minute: Optional[int] = Field(
        default=None,
        ge=0,
        le=59,
        description="Target civil-clock minute (0..59); defaults to 0 with a supplied analysis date. Omit all analysis_* components to use the current/as_of instant. Cannot combine with analysis_age.",
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
            raise ValueError("analysis_age年龄参考不能与analysis_*分析日期同时使用")
        return self

    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class LiunianAnalysisRequest(BaziClockRequest):
    """Request model for liunian analysis."""

    target_year: int = Field(description="Target analysis year")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class LiuriAnalysisRequest(BaziClockRequest):
    """Request model for liuri analysis."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间取流日，保留晚子时规则；显式部分日期缺年月日取当前值、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    analysis_hour: Optional[int] = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23)"
    )
    analysis_minute: Optional[int] = Field(
        default=None, ge=0, le=59, description="Analysis minute (0-59)"
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class LiushiAnalysisRequest(BaziClockRequest):
    """Request model for liushi analysis."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间分析；显式部分日期缺年月日时取当前值，缺分钟取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    analysis_hour: Optional[int] = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23)"
    )
    analysis_minute: Optional[int] = Field(
        default=None, ge=0, le=59, description="Analysis minute (0-59)"
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class JieqiTimelineRequest(BaziClockRequest):
    """Request model for jieqi timeline analysis."""

    target_year: Optional[int] = Field(default=None, description="Target year")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class LiuyueAnalysisRequest(BaziClockRequest):
    """Request model for liuyue analysis."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="日期全部省略时按本次as_of或执行开始时刻的完整当地瞬间取节令月；显式部分日期缺年/月取当前年/月，缺日取15、缺时分取0。 显式日期的不存在或重复钟时须用有效钟时或明确UTC偏移消歧。",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    analysis_hour: Optional[int] = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23)"
    )
    analysis_minute: Optional[int] = Field(
        default=None, ge=0, le=59, description="Analysis minute (0-59)"
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
