"""Explicit native root clock conversion; a solved root cannot become linear."""

from datetime import datetime
from typing import Any, Dict

from fatebridge.core.astro.time_scales import datetime_from_tt_point, ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.errors import EphemerisSourceError


class SolarTermClockError(EphemerisSourceError):
    """Bounded clock failure on an already selected physical-time root."""

    MESSAGES = {
        "solar_root_civil_unrepresentable": "Selected TT solar crossing has no unique representable civil datetime under the configured time policy",
        "solar_root_clock_unavailable": "Selected TT solar crossing clock conversion is unavailable under the configured clock data",
    }

    def as_result(self) -> Dict[str, Any]:
        result = super().as_result()
        result["issues"] = [{"path": "runtime.solar_term_clock", "code": self.reason}]
        return result


def native_solar_root_datetime(jd_tt: float) -> datetime:
    """Keep IEEE point intent and distinguish a clock failure from no root."""
    try:
        return datetime_from_tt_point(TTInstant.from_float(jd_tt))
    except EphemerisSourceError:
        raise
    except (ValueError, OverflowError) as error:
        raise SolarTermClockError("solar_root_civil_unrepresentable") from error
    except Exception as error:
        raise SolarTermClockError("solar_root_clock_unavailable") from error


def native_solar_root_time_policy(moment: datetime) -> Dict[str, Any]:
    """Qualify a native civil label under the actual configured clock policy.

    A Gregorian UTC-shaped label before atomic UTC represents modeled UT1;
    a future label can depend on an expired leap-second table. Neither is a
    measured civil UTC claim, even when its TT root is numerically precise.
    """
    try:
        clock = ephemeris_time(moment)
    except EphemerisSourceError:
        raise
    except (ValueError, OverflowError) as error:
        raise SolarTermClockError("solar_root_civil_unrepresentable") from error
    except Exception as error:
        raise SolarTermClockError("solar_root_clock_unavailable") from error
    return {
        "civil_time_policy": clock.method,
        "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
        "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
    }
