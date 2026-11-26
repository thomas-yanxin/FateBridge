"""Exact recorded coordinates for a finite birth-time sensitivity grid."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.birth_clock import resolve_solar_epoch
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import utc_clock, utc_point_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.civil_time import CivilPoint, UTCCalendar, utc_calendar

SECOND = Fraction(1, 86400)
CADENCE = 30 * SECOND


@dataclass(frozen=True)
class RecordedBirthSample:
    """The physical point on the recorded axis, before any legacy rebase."""

    epoch: PhysicalEpoch

    @property
    def tt(self) -> TTInstant:
        point = self.epoch.time.tt
        assert point is not None  # PhysicalEpoch requires TT.
        return point

    @property
    def nominal_calendar(self) -> CivilPoint | None:
        """A symbolic key coordinate, separate from physical identity."""
        if self.epoch.source_calendar is not None:
            return self.epoch.source_calendar
        label = self.epoch.utc_label
        if label is None:
            return None
        if self.epoch.utc_is_leap_second:
            # Both sides of an insertion share this nominal limit. The
            # continuous nondecreasing extension holds it for all of :60.
            following_ordinal = date.fromisoformat(label[:10]).toordinal() + 1
            return CivilPoint(UTCCalendar(following_ordinal, 0).julian_day_exact())
        return utc_point_from_tt(self.tt)


@dataclass(frozen=True)
class RecordedBirthGrid:
    samples: tuple[RecordedBirthSample, ...]
    nominal_index: int


def sampling_radius(minutes: float) -> timedelta:
    """Keep the established timedelta microsecond quantization of the input."""
    if not math.isfinite(minutes) or not 0 <= minutes <= 120:
        raise ValueError("birth_time_uncertainty_minutes must be finite and in [0,120]")
    return timedelta(minutes=minutes)


def civil_recorded_sample(moment: datetime | UTCCalendar) -> RecordedBirthSample:
    return RecordedBirthSample(PhysicalEpoch.from_civil(moment))


def shift_civil_recorded_sample(
    center: RecordedBirthSample, offset: timedelta
) -> RecordedBirthSample:
    """Apply an elapsed SI offset, preserving an exactly matching civil label."""
    if not offset:
        return center
    delta = Fraction(
        (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds,
        86_400_000_000,
    )
    tt = center.tt.shifted_by(delta)
    if center.epoch.utc_datetime is not None:
        label = utc_calendar(center.epoch.utc_datetime).shifted(offset)
    else:
        source = center.epoch.source_calendar
        assert source is not None  # A forward civil center has a source calendar.
        label = source.as_calendar().shifted(offset)
    if label.ordinal >= date(1972, 1, 1).toordinal() and utc_clock(label).tt == tt:
        return civil_recorded_sample(label)
    return RecordedBirthSample(PhysicalEpoch.from_tt(tt))


def recorded_birth_grid(
    birth: AstroBirthInfo, uncertainty_minutes: float
) -> RecordedBirthGrid:
    """Apply the input clock's interval before constructing an exact TT grid.

    Civil radius is elapsed TT around the recorded center. Solar radius is
    applied to the supplied solar clock; its solved TT and UT1 own the bounds.
    Historical TT follows the selected source, including modeled pre-UTC UT1.
    """
    radius = sampling_radius(uncertainty_minutes)
    conversion = birth.clock_conversion
    if birth.native_epoch is not None:
        nominal = RecordedBirthSample(birth.native_epoch)
    else:
        moment = (birth.recorded_datetime or birth.local_datetime).astimezone(
            timezone.utc
        )
        nominal = civil_recorded_sample(moment)
    if not radius:
        return RecordedBirthGrid((nominal,), 0)

    if conversion is None:
        lower = shift_civil_recorded_sample(nominal, -radius)
        upper = shift_civil_recorded_sample(nominal, radius)
    else:
        wall = datetime.fromisoformat(conversion["input_wall_datetime"])
        basis = conversion["input_clock_basis"]
        policy = conversion["solar_ephemeris_policy"]
        lower, upper = (
            RecordedBirthSample(
                resolve_solar_epoch(
                    wall + offset, birth.longitude, basis, ephemeris_policy=policy
                )[0]
            )
            for offset in (-radius, radius)
        )

    start, center, stop = lower.tt.days, nominal.tt.days, upper.tt.days
    if not start <= center <= stop:
        raise ValueError(
            "Solar clock interval must contain its nominal physical instant"
        )
    points = {start: lower, stop: upper, center: nominal}
    anchor = lower.epoch.utc_datetime
    for index in range(1, math.ceil((stop - start) / CADENCE)):
        if anchor is not None and anchor.year >= 1972:
            ordinary = anchor + timedelta(seconds=30 * index)
            ordinary_tt = utc_clock(ordinary).tt
            assert ordinary_tt is not None  # From a modern ordinary UTC label.
            if (
                start < ordinary_tt.days < stop
                and ordinary != nominal.epoch.utc_datetime
            ):
                points[ordinary_tt.days] = civil_recorded_sample(ordinary)
        else:
            point = start + index * CADENCE
            if point != center:
                points[point] = RecordedBirthSample(
                    PhysicalEpoch.from_tt(TTInstant(point))
                )

    # The start-anchored modern label schedule can cross a +1 second
    # insertion. Optional subdivision points can move within that pair to
    # avoid requiring a :60 sample solely to satisfy the cadence cap.
    ordered = sorted(points)
    for left, right in zip(ordered, ordered[1:]):
        if right - left <= CADENCE:
            continue
        middle = (left + right) / 2
        sample = RecordedBirthSample(PhysicalEpoch.from_tt(TTInstant(middle)))
        if sample.epoch.utc_is_leap_second:
            middle -= SECOND
            sample = RecordedBirthSample(PhysicalEpoch.from_tt(TTInstant(middle)))
        points[middle] = sample
    ordered = sorted(points)
    return RecordedBirthGrid(
        tuple(points[point] for point in ordered), ordered.index(center)
    )
