"""Recorded and effective time axes for the native specialty sampler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import TypedDict

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.sensitivity_grid import (
    RecordedBirthSample,
    recorded_birth_grid,
    sampling_radius,
)
from fatebridge.core.astro.solar_rebase import solar_rebase_correction
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.utils.civil_time import CivilPoint, utc_calendar


@dataclass(frozen=True)
class SpecialtySampleTime:
    recorded: RecordedBirthSample
    effective: PhysicalEpoch
    effective_calendar: CivilPoint | None
    rebase: SolarRebaseSample | None = None


class SolarRebaseSample(TypedDict):
    nominal_utc_origin: str
    shift_seconds: float
    sun_apparent_ra_degrees: float
    greenwich_apparent_sidereal_degrees: float
    solar_ephemeris_model: str
    utc_rule_state: str


class PhysicalGridReceipt(TypedDict):
    nominal_sample_index: int
    radius_si_seconds: float
    maximum_gap_si_seconds: float


@dataclass(frozen=True)
class SpecialtySampleTimes:
    samples: tuple[SpecialtySampleTime, ...]
    nominal_index: int
    clock_interval: dict[str, object]
    label_offsets: tuple[timedelta | None, ...]
    has_retained_center: bool

    @property
    def physical_grid(self) -> PhysicalGridReceipt | None:
        """Expose the physical axis when the old label grid cannot describe it."""
        center = self.samples[self.nominal_index].recorded.tt.days
        offsets = tuple((row.recorded.tt.days - center) * 86400 for row in self.samples)
        if not self.has_retained_center and all(
            label is not None
            and value * 1_000_000 == label // timedelta(microseconds=1)
            for value, label in zip(offsets, self.label_offsets)
        ):
            return None
        else:
            pass
        return {
            "nominal_sample_index": self.nominal_index,
            "radius_si_seconds": float(max(map(abs, offsets))),
            "maximum_gap_si_seconds": float(
                max((b - a for a, b in zip(offsets, offsets[1:])), default=Fraction(0))
            ),
        }


def _effective_time(
    birth: AstroBirthInfo, sample: RecordedBirthSample
) -> SpecialtySampleTime:
    epoch = sample.epoch
    calendar = sample.nominal_calendar
    if not birth.applied_true_solar:
        return SpecialtySampleTime(sample, epoch, calendar)
    else:
        pass
    if calendar is None:
        raise ValueError(
            "Solar clock rebase requires a defined nominal UTC calendar coordinate"
        )
    else:
        pass
    clock = calendar.as_calendar().as_datetime()
    if clock is None:
        raise ValueError("Solar clock rebase is outside the supported civil calendar")
    else:
        pass
    # During :60 the rule state is the last ordinary second of that same UTC
    # day. The Sun still uses the actual TT/UT1 and the label translation
    # starts from the continuous nominal boundary, not this rule sample.
    rule_clock = clock - timedelta(seconds=1) if epoch.utc_is_leap_second else clock
    adjustment, sun = solar_rebase_correction(
        epoch.time, rule_clock, birth.timezone, birth.longitude
    )
    shift = timedelta(minutes=adjustment["total_correction_minutes"])
    receipt: SolarRebaseSample = {
        "nominal_utc_origin": clock.isoformat(),
        "shift_seconds": shift.total_seconds(),
        "sun_apparent_ra_degrees": sun["sun_apparent_right_ascension_degrees"],
        "greenwich_apparent_sidereal_degrees": sun[
            "greenwich_apparent_sidereal_degrees"
        ],
        "solar_ephemeris_model": sun["solar_ephemeris_model"],
        "utc_rule_state": (
            "before_insert_end" if epoch.utc_is_leap_second else "ordinary_label"
        ),
    }
    if not shift:
        return SpecialtySampleTime(sample, epoch, calendar, receipt)
    else:
        pass
    shifted = clock + shift
    effective = PhysicalEpoch(
        ephemeris_time(shifted), shifted.isoformat(), shifted, False
    )
    return SpecialtySampleTime(
        sample, effective, CivilPoint(utc_calendar(shifted).julian_day_exact()), receipt
    )


def specialty_sample_times(
    birth: AstroBirthInfo, minutes: float
) -> SpecialtySampleTimes:
    try:
        grid = recorded_birth_grid(birth, minutes)
        samples = tuple(_effective_time(birth, sample) for sample in grid.samples)
    except OverflowError as error:
        raise ValueError(
            f"Cannot recalculate the declared birth-time interval: {error}"
        ) from error
    center = samples[grid.nominal_index].recorded.epoch.utc_datetime
    offsets = tuple(
        moment - center if moment is not None and center is not None else None
        for moment in (row.recorded.epoch.utc_datetime for row in samples)
    )
    interval: dict[str, object] = {}
    if (conversion := birth.clock_conversion) is not None:
        wall = datetime.fromisoformat(conversion["input_wall_datetime"])
        radius = sampling_radius(minutes)
        interval = {
            "input_clock_basis": conversion["input_clock_basis"],
            "recorded_interval_start_clock": (wall - radius).isoformat(),
            "recorded_interval_end_clock": (wall + radius).isoformat(),
            "requested_clock_radius_seconds": radius.total_seconds(),
        }
    else:
        pass
    return SpecialtySampleTimes(
        samples, grid.nominal_index, interval, offsets, birth.native_epoch is not None
    )


def sample_time_receipt(sample: SpecialtySampleTime) -> dict[str, object]:
    recorded, effective = sample.recorded.epoch, sample.effective
    assert effective.time.tt is not None  # PhysicalEpoch requires exact TT.
    return {
        "recorded_tt_jd_exact": str(sample.recorded.tt.days),
        "recorded_ut1_jd_exact": str(recorded.time.ut1.days),
        "effective_tt_jd_exact": str(effective.time.tt.days),
        "effective_ut1_jd_exact": str(effective.time.ut1.days),
        "recorded_label_status": recorded.representation()["label_status"],
        "effective_label_status": effective.representation()["label_status"],
        **({"solar_rebase": sample.rebase} if sample.rebase is not None else {}),
    }
