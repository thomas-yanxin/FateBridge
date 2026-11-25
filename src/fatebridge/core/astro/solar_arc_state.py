"""Same-run solar displacement, before its public float projection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from typing import TypedDict

from fatebridge.core.astro.sensitivity_timing import SpecialtySampleTime
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.civil_time import utc_calendar

YEAR_DAYS = 365.25
MAX_KEY_YEARS = 150.0
KEY_POLICY = (
    "1 TT ephemeris day per 365.25 UTC calendar days; calendar subtraction "
    "ignores leap seconds; symbolic convention, not a measured event clock"
)


class SolarArcSampleUnavailable(ValueError):
    reason_code: str


class SolarArcCalendarUnavailable(SolarArcSampleUnavailable):
    reason_code = "sample_nominal_utc_calendar_unavailable"


class SolarArcTimeRangeError(SolarArcSampleUnavailable):
    """A stated symbolic key range, distinct from ephemeris/configuration faults."""

    def __init__(self, key_years: float, *, before_birth: bool = False) -> None:
        super().__init__(
            "Solar arc supports target instants 0..150 Julian key years after birth"
        )
        self.key_years = key_years
        self.reason_code = (
            "target_before_birth_time_sample"
            if key_years < 0 or before_birth
            else "target_after_supported_key_range_for_sample"
        )


class SolarArcRecord(TypedDict):
    analysis_utc: str
    birth_effective_utc: str
    elapsed_calendar_days: float
    year_days: float
    key_years: float
    birth_julian_day_tt: float
    progressed_julian_day_tt: float
    julian_day_resolution_seconds: float
    natal_tropical_sun: float
    progressed_tropical_sun: float
    solar_arc_degrees: float
    one_degree_per_year_degrees: float
    difference_from_one_degree_per_year: float
    sun_ephemeris_models: list[str]
    sun_observation_indices: list[int]
    key_policy: str


@dataclass(frozen=True)
class SolarArcState:
    analysis_utc: datetime
    birth_effective_utc: datetime | None
    elapsed_calendar_days: float
    key_years: float
    birth_julian_day_tt: float
    progressed_julian_day_tt: float
    natal_tropical_sun: float
    progressed_tropical_sun: float
    sun_ephemeris_models: tuple[str, str]
    sun_observation_indices: tuple[int, int]

    retained_birth_label: str | None = None

    @property
    def birth_label(self) -> str:
        if self.retained_birth_label is not None:
            return self.retained_birth_label
        else:
            pass
        assert (
            self.birth_effective_utc is not None
        )  # Computed requires a calendar point.
        return self.birth_effective_utc.isoformat()

    @property
    def arc(self) -> Fraction:
        return (
            Fraction(self.progressed_tropical_sun) - Fraction(self.natal_tropical_sun)
        ) % 360

    def to_record(self) -> SolarArcRecord:
        arc = float(self.arc)
        return {
            "analysis_utc": self.analysis_utc.isoformat(),
            "birth_effective_utc": self.birth_label,
            "elapsed_calendar_days": self.elapsed_calendar_days,
            "year_days": YEAR_DAYS,
            "key_years": self.key_years,
            "birth_julian_day_tt": self.birth_julian_day_tt,
            "progressed_julian_day_tt": self.progressed_julian_day_tt,
            "julian_day_resolution_seconds": math.ulp(self.birth_julian_day_tt) * 86400,
            "natal_tropical_sun": self.natal_tropical_sun,
            "progressed_tropical_sun": self.progressed_tropical_sun,
            "solar_arc_degrees": arc,
            "one_degree_per_year_degrees": self.key_years,
            "difference_from_one_degree_per_year": arc - self.key_years,
            "sun_ephemeris_models": list(self.sun_ephemeris_models),
            "sun_observation_indices": list(self.sun_observation_indices),
            "key_policy": KEY_POLICY,
        }


@dataclass(frozen=True)
class RetainedSolarArcTiming:
    elapsed_calendar_days: float
    key_years: float
    progressed_julian_day_tt: float


def exact_solar_arc_timing(
    birth_tt: TTInstant,
    birth_calendar_day: Fraction,
    analysis: datetime,
    *,
    analysis_tt: TTInstant | None = None,
) -> RetainedSolarArcTiming:
    """Apply the nominal calendar key, rounding only at the Swiss TT boundary."""
    interval = utc_calendar(analysis).julian_day_exact() - birth_calendar_day
    exact_key = interval / Fraction(YEAR_DAYS)
    # The published day and key values keep their display rounding.
    elapsed_days = float(interval * 86400) / 86400
    key = elapsed_days / YEAR_DAYS
    before_birth = analysis_tt is not None and analysis_tt.days < birth_tt.days
    if before_birth or not 0 <= exact_key <= MAX_KEY_YEARS:
        raise SolarArcTimeRangeError(key, before_birth=before_birth or exact_key < 0)
    else:
        pass
    return RetainedSolarArcTiming(
        elapsed_days, key, birth_tt.shifted_by(exact_key).as_float()
    )


def retained_solar_arc_timing(
    clock: SpecialtySampleTime, analysis: datetime, analysis_tt: TTInstant
) -> RetainedSolarArcTiming:
    """Apply the nominal calendar key to the exact effective TT."""
    calendar = clock.effective_calendar
    if calendar is None:
        raise SolarArcCalendarUnavailable(
            "Sample has no defined nominal UTC calendar coordinate"
        )
    else:
        pass
    birth_tt = clock.effective.time.tt
    assert birth_tt is not None  # PhysicalEpoch owns exact TT.
    return exact_solar_arc_timing(
        birth_tt, calendar.day, analysis, analysis_tt=analysis_tt
    )


def resolve_solar_arc_state(
    birth_utc: datetime | None,
    birth_jd_tt: float,
    analysis_datetime: datetime,
    *,
    batch: SolarEphemerisBatch,
    clock: SpecialtySampleTime | None = None,
    birth_tt: TTInstant | None = None,
    analysis_tt: TTInstant | None = None,
) -> SolarArcState:
    """Resolve the original source facts under the caller's active Sun batch."""
    retained_label = None
    if analysis_datetime.utcoffset() is None:
        raise ValueError("Solar-arc instants require explicit timezone offsets")
    else:
        pass
    analysis_datetime = analysis_datetime.astimezone(timezone.utc)
    if clock is not None:
        assert (
            analysis_tt is not None
        )  # Bound by the same target as its Sun observation.
        timing = retained_solar_arc_timing(clock, analysis_datetime, analysis_tt)
        elapsed_days = timing.elapsed_calendar_days
        key_years = timing.key_years
        progressed_jd = timing.progressed_julian_day_tt
        birth_utc = clock.effective.utc_datetime
        retained_label = clock.effective.utc_label
    else:
        if birth_utc is None or birth_utc.utcoffset() is None:
            raise ValueError("Solar-arc instants require explicit timezone offsets")
        else:
            pass
        birth_utc = birth_utc.astimezone(timezone.utc)
        if birth_tt is None:
            elapsed_days = (analysis_datetime - birth_utc).total_seconds() / 86400
            key_years = elapsed_days / YEAR_DAYS
            if not 0 <= key_years <= MAX_KEY_YEARS:
                raise SolarArcTimeRangeError(key_years)
            else:
                pass
            progressed_jd = birth_jd_tt + key_years
        else:
            timing = exact_solar_arc_timing(
                birth_tt, utc_calendar(birth_utc).julian_day_exact(), analysis_datetime
            )
            elapsed_days = timing.elapsed_calendar_days
            key_years = timing.key_years
            progressed_jd = timing.progressed_julian_day_tt
    natal, progressed = [batch.sun(jd) for jd in (birth_jd_tt, progressed_jd)]
    return SolarArcState(
        analysis_utc=analysis_datetime,
        birth_effective_utc=birth_utc,
        elapsed_calendar_days=elapsed_days,
        key_years=key_years,
        birth_julian_day_tt=birth_jd_tt,
        progressed_julian_day_tt=progressed_jd,
        natal_tropical_sun=natal["longitude"],
        progressed_tropical_sun=progressed["longitude"],
        sun_ephemeris_models=(natal["model"], progressed["model"]),
        sun_observation_indices=(natal["index"], progressed["index"]),
        retained_birth_label=retained_label,
    )
