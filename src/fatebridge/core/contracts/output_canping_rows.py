"""Canping interval rows and text witnesses."""

from pydantic import model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_canping_reading import (
    CanpingPairResolution,
    CanpingTextSelection,
)
from fatebridge.core.contracts.output_canping_solar import (
    CanpingInterval,
    CanpingSolarBoundary,
)
from fatebridge.utils.civil_time import ZonedCalendar


class CanpingVerses(PartialOutput):
    statusShun: str | None = None
    statusNi: str | None = None
    numNi: int | None = None
    numShun: int | None = None
    textNi: str | None = None
    textShun: str | None = None
    selectionShun: CanpingTextSelection | None = None
    selectionNi: CanpingTextSelection | None = None
    pair_resolution: CanpingPairResolution | None = None


class CanpingRow(CanpingInterval):
    year_start_boundary: CanpingSolarBoundary | None = None
    year_end_boundary: CanpingSolarBoundary | None = None
    age: int | None = None
    ageEnd: int | None = None
    ageStart: int | None = None
    branch: str | None = None
    index: int | None = None
    ni: int | None = None
    numNi: int | None = None
    numShun: int | None = None
    shun: int | None = None
    ziRound: int | None = None
    verses: CanpingVerses | None = None
    dayunBranch: str | None = None
    dayunRange: str | None = None
    ganzhi: str | None = None
    taisuiBranch: str | None = None
    year: int | None = None
    at: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    status: str | None = None
    pillar: str | None = None
    dayun_index: int | None = None
    dayun_pillar: str | None = None
    segments: list["CanpingRow"] | None = None

    @model_validator(mode="after")
    def coherent_dated_row(self) -> "CanpingRow":
        if self.status == "not_started" and any(
            value is not None
            for value in (
                self.dayun_index,
                self.dayunBranch,
                self.dayun_pillar,
                self.numNi,
                self.numShun,
                self.verses,
            )
        ):
            raise ValueError("未起运区间不能附活动大运或条文。")
        at = (
            ZonedCalendar.from_isoformat(self.at).utc.julian_day_exact()
            if self.at is not None
            else None
        )
        start = (
            ZonedCalendar.from_isoformat(self.start_at).utc.julian_day_exact()
            if self.start_at is not None
            else None
        )
        end = (
            ZonedCalendar.from_isoformat(self.end_at).utc.julian_day_exact()
            if self.end_at is not None
            else None
        )
        if at is not None and (
            (start is not None and at < start) or (end is not None and at >= end)
        ):
            raise ValueError("查询时刻不在所选半开区间。")
        for boundary, ending in (
            (self.year_start_boundary, False),
            (self.year_end_boundary, True),
        ):
            if boundary is None:
                continue
            if self.year is not None and boundary.year is not None:
                if boundary.year != self.year + int(ending):
                    raise ValueError("所选年与实际立春边界年份不一致。")
        return self
