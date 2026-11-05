"""Request contracts for compatibility."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.requests.base import _DeferredModel
from fatebridge.core.sukuyo_calendar_basis import SukuyoCalendarBasis


class TwoPersonCompatibilityRequest(_DeferredModel):
    """Request model for two-person compatibility analysis."""

    person1_name: str = Field(description="First person name")
    person1_birth_year: int = Field(description="First person birth year, e.g., 1990")
    person1_birth_month: int = Field(
        ge=1, le=12, description="First person birth month"
    )
    person1_birth_day: int = Field(ge=1, le=31, description="First person birth day")
    person1_birth_hour: int = Field(ge=0, le=23, description="First person birth hour")
    person1_gender: str = Field(
        default="未知",
        description=(
            "第一人性别（影响大运顺逆与部分六亲判断）。"
            "接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；省略默认 未知。"
        ),
    )
    person1_birth_place: str = Field(
        default="未提供", description="First person birth place"
    )
    person1_birth_minute: int = Field(
        default=0, ge=0, le=59, description="First person birth minute"
    )
    person1_birth_timezone: Optional[str] = Field(
        default=None, description="First person birth timezone"
    )
    person1_birth_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="First person birth longitude"
    )
    person1_use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time for first person (八字 default on)",
    )
    person2_name: str = Field(description="Second person name")
    person2_birth_year: int = Field(description="Second person birth year, e.g., 1992")
    person2_birth_month: int = Field(
        ge=1, le=12, description="Second person birth month"
    )
    person2_birth_day: int = Field(ge=1, le=31, description="Second person birth day")
    person2_birth_hour: int = Field(ge=0, le=23, description="Second person birth hour")
    person2_gender: str = Field(
        default="未知",
        description=(
            "第二人性别（影响大运顺逆与部分六亲判断）。"
            "接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法；省略默认 未知。"
        ),
    )
    person2_birth_place: str = Field(
        default="未提供", description="Second person birth place"
    )
    person2_birth_minute: int = Field(
        default=0, ge=0, le=59, description="Second person birth minute"
    )
    person2_birth_timezone: Optional[str] = Field(
        default=None, description="Second person birth timezone"
    )
    person2_birth_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Second person birth longitude"
    )
    person2_use_true_solar_time: bool = Field(
        default=True,
        description="Enable true solar time for second person (八字 default on)",
    )
    relationship_type: Literal[
        "general", "marriage", "friendship", "business", "family"
    ] = Field(
        default="general",
        description=(
            "关系类型：general / marriage / friendship / business / family。"
            "用户未说明关系时保留 general；不能因两人性别或‘我们两个人’推断为婚姻。"
        ),
    )


class SukuyoCompatibilityRequest(_DeferredModel):
    """T1299望日定宿及三九法；宿主历法另选，经纬度不定宿。"""

    calendar_basis: SukuyoCalendarBasis = Field(
        default="chinese_hko_utc08",
        description="双方共用一套宿主历法，独立于各自出生时区与配宿档案；默认现代中国农历UTC+08。japanese_hutime_1002_1_utc09为1872-02-09至2031-01-22的HuTime冻结逐日参考、固定UTC+09，2015起属出版方参考推算，非历史地方时或逐年神宫刊本验收；范围外不回退中国历。japanese_naoj_historical_utc09为公元0001-01-01至1872-12-31的NAOJ历史月朔参考、固定UTC+09；早期纪年属重建，改历末月仅两天，保留跨出版方异日，非历史地方时或全部颁历验收。",
    )

    person1_textual_pada: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
        strict=True,
        description="第一人仅按历日宿名查原典分足表的显式足序；不表示已排得出生足位，省略保留四足",
    )
    person2_textual_pada: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
        strict=True,
        description="第二人仅按历日宿名查原典分足表的显式足序；不表示已排得出生足位，省略保留四足",
    )

    calendar_profile: Literal["t1299_fullmoon27", "hinoo_t1299_host27"] = Field(
        default="t1299_fullmoon27",
        description="默认T1299下卷望日逆顺及生日加十三法；Hinoo研究档案应用T2465闰月和小月分宿规则，宿主历法由calendar_basis另选",
    )
    person1_calendar_day_part: Optional[Literal["first_half", "second_half"]] = Field(
        default=None,
        description="Hinoo档案下第一人的已确定原典日序前/后半；不按民用钟时猜测",
    )
    person2_calendar_day_part: Optional[Literal["first_half", "second_half"]] = Field(
        default=None,
        description="Hinoo档案下第二人的已确定原典日序前/后半；不按民用钟时猜测",
    )

    leap_month_policy: Literal["unresolved", "repeat_month"] = Field(
        default="unresolved",
        description="闰月默认仅返回候选；repeat_month显式约定沿用同名月，不宣称原典唯一算法",
    )
    person1_name: str = Field(default="甲方", description="First person name / label")
    person1_date: str = Field(description="First person birth date, e.g. 1990-06-15")
    person1_time: Optional[str] = Field(
        default=None,
        description="已知出生时间；未知可省略，按当地日期保留所选宿主历法的全部可能日期，不猜生时",
    )
    person1_zone: Optional[str] = Field(
        default="+08:00",
        description="第一人出生时区，默认+08:00；按calendar_basis转换，不因日本参考自动改成东京",
    )
    person2_name: str = Field(default="乙方", description="Second person name / label")
    person2_date: str = Field(description="Second person birth date")
    person2_time: Optional[str] = Field(
        default=None,
        description="已知出生时间；未知可省略，按当地日期保留所选宿主历法的全部可能日期，不猜生时",
    )
    person2_zone: Optional[str] = Field(
        default="+08:00",
        description="第二人出生时区，默认+08:00；按calendar_basis转换，不因日本参考自动改成东京",
    )

    @model_validator(mode="after")
    def day_part_requires_hinoo(self) -> "SukuyoCompatibilityRequest":
        if self.calendar_profile != "hinoo_t1299_host27" and any(
            p is not None
            for p in (self.person1_calendar_day_part, self.person2_calendar_day_part)
        ):
            raise ValueError("原典日序半日只适用于明确选择的Hinoo研究档案")
        return self
