"""Shared wall-clock cells for the Dayun inverse probes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Protocol

from fatebridge.core.almanac import SolarTerm
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.solar_time import NormalizedBirthTime

MICROSECOND = timedelta(microseconds=1)


class BirthClockAtInstant(Protocol):
    def __call__(self, birth_instant_utc: datetime, /) -> NormalizedBirthTime: ...


@dataclass(frozen=True, kw_only=True)
class DayunWallCell:
    lower: datetime
    upper: datetime
    last: datetime
    first_wall: datetime
    last_wall: datetime
    slope: int
    is_forward: bool
    reference_term: SolarTerm
    is_affine: bool

    @property
    def reference_timestamp(self) -> str:
        if self.reference_term.has_defined_local_clock:
            return self.reference_term.calendar.isoformat()
        else:
            return self.reference_term.calendar.utc.isoformat()

    @property
    def wall_range(self) -> tuple[datetime, datetime]:
        low, high = sorted((self.first_wall, self.last_wall))
        return low, high

    def inverse(self, target: datetime) -> tuple[datetime, datetime] | None:
        """Enclose the target on the microsecond grid of a qualified cell."""
        low, high = self.wall_range
        if not low <= target <= high:
            return None
        delta = (target - self.first_wall) // MICROSECOND
        quotient, remainder = divmod(delta, self.slope)
        lower = self.lower + quotient * MICROSECOND
        return lower, lower + bool(remainder) * MICROSECOND


def build_dayun_wall_cells(
    timezone_name: str,
    gender: str | None,
    cuts: set[datetime],
    high: datetime,
    clock_at: BirthClockAtInstant,
) -> tuple[DayunWallCell, ...]:
    ordered = sorted(cuts)
    intervals = [
        (left, right, right - MICROSECOND) for left, right in pairwise(ordered)
    ]
    # note (dayun): A cut at the inclusive endpoint owns a singleton final cell.
    intervals.append((ordered[-1], high, high))
    cells = []
    for left, right, last in intervals:
        start = TimingAnalysis.resolve_dayun_start(
            clock_at(left).input_datetime, gender, timezone_name
        )
        initial_wall, calendar_offset = start.calendar_wall_offset()
        reference_term = start.target_term
        is_forward = start.forward_direction
        # note (dayun): One elapsed second changes the nominal offset by 120 seconds.
        slope = -119 if is_forward else 121
        final_wall = initial_wall
        is_affine = True
        if left != last:
            end = TimingAnalysis.resolve_dayun_start(
                clock_at(last).input_datetime, gender, timezone_name
            )
            final_wall, final_offset = end.calendar_wall_offset()
            final_reference_term = end.target_term
            reference_point = reference_term.civil_point
            final_reference_point = final_reference_term.civil_point
            if reference_point is None and final_reference_point is None:
                has_same_reference = (
                    reference_term.has_defined_local_clock
                    and reference_term.calendar.isoformat()
                ) == (
                    final_reference_term.has_defined_local_clock
                    and final_reference_term.calendar.isoformat()
                )
            else:
                has_same_reference = reference_point == final_reference_point
            is_affine = (
                end.forward_direction == is_forward
                and has_same_reference
                and end.birth.date() == start.birth.date()
                and end.birth.utcoffset() == start.birth.utcoffset()
                and (final_offset["years"], final_offset["months"])
                == (calendar_offset["years"], calendar_offset["months"])
                and final_wall - initial_wall == slope * (last - left)
            )
        cells.append(
            DayunWallCell(
                lower=left,
                upper=right,
                last=last,
                first_wall=initial_wall,
                last_wall=final_wall,
                slope=slope,
                is_forward=is_forward,
                reference_term=reference_term,
                is_affine=is_affine,
            )
        )
    return tuple(cells)
