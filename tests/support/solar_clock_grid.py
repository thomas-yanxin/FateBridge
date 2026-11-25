"""Checks shared by the fixed 0, 30 and 60 second solar rebase cohorts."""

from datetime import datetime, timedelta
from fractions import Fraction

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.sensitivity_timing import specialty_sample_times


def civil_solar_birth(moment: datetime) -> AstroBirthInfo:
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=True,
    )


def verify_recorded_grid_solar_reset(
    birth: AstroBirthInfo,
    target: datetime,
    offset_seconds: int,
    reference_tt_days: str,
    reference_eot_seconds: float,
    tolerance_seconds: float,
) -> datetime:
    radius = abs(offset_seconds)
    interval = specialty_sample_times(birth, radius / 60)
    center = interval.samples[interval.nominal_index].recorded
    assert center.epoch.require_datetime() == target - timedelta(seconds=offset_seconds)
    assert tuple(
        (sample.recorded.tt.days - center.tt.days) * 86400
        for sample in interval.samples
    ) == tuple(range(-radius, radius + 1, 30))
    sample = interval.samples[-1 if offset_seconds > 0 else 0]

    # A fixed historical label denotes modeled UT1, while a grid offset is in
    # SI seconds. Run the same reset at the reference label to test its EOT.
    fixed = (
        specialty_sample_times(civil_solar_birth(target), 0).samples[0]
        if offset_seconds
        else sample
    )
    assert fixed.recorded.epoch.require_datetime() == target
    assert fixed.recorded.tt.days == Fraction(reference_tt_days)
    fixed_seconds = (fixed.effective.require_datetime() - target).total_seconds()
    assert abs(fixed_seconds - reference_eot_seconds) <= tolerance_seconds

    # All fixed modern dates lie away from UTC leap insertions.
    if target.year >= 1972:
        assert sample.recorded.epoch.require_datetime() == target
    else:
        pass
    return sample.effective.require_datetime()
