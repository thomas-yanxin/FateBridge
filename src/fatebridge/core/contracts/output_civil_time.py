"""Exact nominal Gregorian coordinates shared by projected solar evidence."""

from datetime import timedelta
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PRESENT_FACT, PartialOutput
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar


class CivilRationalEvidence(PartialOutput):
    numerator: Annotated[str | None, FULL_FACT] = Field(
        None, pattern=r"^-?(0|[1-9][0-9]*)$"
    )
    denominator: Annotated[str | None, FULL_FACT] = Field(
        None, pattern=r"^[1-9][0-9]*$"
    )

    def known_day(self) -> Fraction | None:
        """Read a projected coordinate only when both decimal integers exist."""
        if self.numerator is None or self.denominator is None:
            return None
        return Fraction(int(self.numerator), int(self.denominator))


class CivilPointEvidence(CivilRationalEvidence):
    unit: Annotated[Literal["nominal_gregorian_day"] | None, FULL_FACT] = None
    excluded_before: Annotated[CivilRationalEvidence | None, PRESENT_FACT] = None

    def known_point(self) -> CivilPoint | None:
        """A missing projected cap is unknown, distinct from explicit null."""
        day = self.known_day()
        if day is None or "excluded_before" not in self.model_fields_set:
            return None
        if self.excluded_before is None:
            return CivilPoint(day)
        cap = self.excluded_before.known_day()
        return CivilPoint(day, cap) if cap is not None else None

    @model_validator(mode="after")
    def preserve_qualified_interval(self) -> "CivilPointEvidence":
        point = self.known_point()
        if (
            point is not None
            and point.excluded_before is not None
            and point.day >= point.excluded_before
        ):
            raise ValueError("民用时刻必须早于其已限定的排除端点")
        return self


class CivilPointLabelEvidence(PartialOutput):
    """A retained coordinate and its display, shared by source receipts."""

    civil_point: CivilPointEvidence | None = None
    datetime_with_offset: str | None = None
    datetime_utc: str | None = Field(
        None,
        description="当地钟时未定义时的带零偏移UTC显示，沿用名义日期及排除端点政策",
    )
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None

    @property
    def display_with_offset(self) -> str | None:
        if self.datetime_utc is not None:
            return self.datetime_utc
        return self.datetime_with_offset

    @model_validator(mode="after")
    def point_matches_display(self, info: ValidationInfo) -> "CivilPointLabelEvidence":
        point = self.civil_point.known_point() if self.civil_point is not None else None
        display = self.display_with_offset
        if (
            info.context
            and info.context.get("full_result")
            and self.comparison_policy == "retained_nominal_civil_point_v1"
            and (point is None or display is None)
        ):
            raise ValueError("完整的精确民用比较回执须保留主点和显示标签")
        if self.datetime_utc is not None and self.datetime_with_offset is not None:
            raise ValueError("当地钟时未定义时不能同时声明当地带偏移时间")
        if display is not None and (point is not None or self.datetime_utc is not None):
            clock = ZonedCalendar.from_isoformat(display)
            if self.datetime_utc is not None and clock.offset != timedelta(0):
                raise ValueError("节气UTC显示须采用零偏移")
            if point is not None and point.as_calendar() != clock.utc:
                raise ValueError("精确民用主点与显示时间不一致")
        return self
