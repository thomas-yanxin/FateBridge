"""Birth coordinates and civil/solar-time normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

if TYPE_CHECKING:
    from fatebridge.core.astro.physical_epoch import PhysicalEpoch

from fatebridge.utils.civil_time import UTCCalendar, utc_calendar
from fatebridge.utils.places import resolve_birth_place_context
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    calculate_solar_time_adjustment,
)
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock


def require_resolved_birth_timezone(source: str) -> None:
    """Do not turn an unresolved civil clock into an asserted UTC instant."""
    if source not in ("birth_timezone", "birth_place", "solar_clock_conversion"):
        raise ValueError(
            "未知出生时区不能默认为UTC；请提供明确 birth_timezone"
            "（IANA名称或UTC偏移），或可唯一识别时区的 birth_place。坐标不能代替民用时区。"
        )


@dataclass(frozen=True)
class AstroBirthInfo:
    name: str
    birth_place: str
    timezone: str
    longitude: float
    latitude: float
    local_datetime: datetime
    utc_datetime: Optional[datetime]
    applied_true_solar: bool = False
    solar_correction_minutes: float = 0.0
    solar_datetime: Optional[datetime] = None
    recorded_datetime: Optional[datetime] = None
    clock_conversion: Optional[Dict[str, Any]] = None
    solar_time_reference: Optional[Dict[str, Any]] = None
    timezone_source: Literal[
        "birth_timezone", "birth_place", "default_utc", "solar_clock_conversion"
    ] = "birth_timezone"

    @property
    def physical_datetime(self) -> datetime:
        """The same physical instant in any representable aware civil zone."""
        return (
            self.utc_datetime if self.utc_datetime is not None else self.local_datetime
        )

    @property
    def utc_calendar(self) -> UTCCalendar:
        return utc_calendar(self.physical_datetime)

    @property
    def utc_isoformat(self) -> str:
        return self.utc_calendar.isoformat()

    @property
    def require_utc_datetime(self) -> datetime:
        """Guard algorithms that specifically require a Python UTC datetime."""
        if self.utc_datetime is None:
            raise ValueError(
                "This algorithm requires a representable UTC datetime; "
                f"the unchanged physical instant has UTC label {self.utc_isoformat}"
            )
        return self.utc_datetime


@dataclass(frozen=True, kw_only=True)
class NativeSolarBirthInfo(AstroBirthInfo):
    """Opt-in primary TT/UT1, with an ordinal solar-label reference only.

    local_datetime is an aware label reference, not the physical instant.
    Legacy consumers must not turn that label into a fabricated UTC epoch.
    A target replacement clears native_epoch before using a real datetime.
    """

    native_epoch: Optional[PhysicalEpoch] = None

    def __post_init__(self) -> None:
        if self.native_epoch is None:
            return
        if (
            self.native_epoch.utc_datetime is not None
            or self.utc_datetime is not None
            or self.recorded_datetime is not None
            or self.clock_conversion is None
            or self.timezone_source != "solar_clock_conversion"
        ):
            raise ValueError("Native solar epoch cannot also contain a civil instant")
        label = datetime.fromisoformat(self.clock_conversion["input_wall_datetime"])
        if (
            label.tzinfo is not None
            or self.local_datetime.utcoffset() != timedelta(0)
            or self.local_datetime.replace(tzinfo=None) != label
        ):
            raise ValueError(
                "Native birth label reference must preserve the solar input"
            )

    @property
    def physical_datetime(self) -> datetime:
        if self.native_epoch is not None and self.native_epoch.utc_datetime is None:
            raise ValueError("Physical TT/UT1 epoch has no UTC datetime carrier")
        return super().physical_datetime


def build_astro_birth_info(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int = 0,
    birth_second: int = 0,
    birth_microsecond: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: Optional[str] = None,
    birth_longitude: Optional[float] = None,
    birth_latitude: Optional[float] = None,
    name: Optional[str] = None,
    birth_place: Optional[str] = None,
    use_true_solar_time: bool = False,
    preserve_instant: bool = False,
    solar_clock_ephemeris_policy: str = "auto",
    require_resolved_timezone: bool = False,
    allow_native_solar_epoch: bool = False,
) -> AstroBirthInfo:
    place_context = resolve_birth_place_context(birth_place)
    timezone_name = birth_timezone or place_context.timezone or "UTC"
    timezone_source: Literal["birth_timezone", "birth_place", "default_utc"] = (
        "birth_timezone"
        if birth_timezone
        else "birth_place" if place_context.timezone else "default_utc"
    )
    if require_resolved_timezone and birth_clock_basis == "civil":
        require_resolved_birth_timezone(timezone_source)
    effective_longitude = (
        birth_longitude if birth_longitude is not None else place_context.longitude
    )
    effective_latitude = (
        birth_latitude if birth_latitude is not None else place_context.latitude
    )
    if effective_longitude is None or effective_latitude is None:
        raise ValueError(
            "核心星盘需要 birth_longitude / birth_latitude，或提供 FateBridge 支持的 birth_place 以自动补全坐标。"
        )
    if birth_clock_basis != "civil":
        from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock

        if birth_timezone is not None or use_true_solar_time:
            raise ValueError(
                "Local solar birth clocks require birth_timezone omitted and use_true_solar_time=false"
            )
        wall = datetime(
            birth_year,
            birth_month,
            birth_day,
            birth_hour,
            birth_minute,
            birth_second,
            birth_microsecond,
        )
        if allow_native_solar_epoch:
            from fatebridge.core.astro.birth_clock import resolve_solar_epoch

            epoch, conversion = resolve_solar_epoch(
                wall,
                effective_longitude,
                birth_clock_basis,
                ephemeris_policy=solar_clock_ephemeris_policy,
            )
            if epoch.utc_datetime is None:
                return NativeSolarBirthInfo(
                    name=(name or "未提供").strip() or "未提供",
                    birth_place=(birth_place or "未提供").strip() or "未提供",
                    timezone="UTC",
                    longitude=effective_longitude,
                    latitude=effective_latitude,
                    local_datetime=wall.replace(tzinfo=timezone.utc),
                    utc_datetime=None,
                    recorded_datetime=None,
                    clock_conversion=conversion,
                    timezone_source="solar_clock_conversion",
                    native_epoch=epoch,
                )
            moment = epoch.utc_datetime
        else:
            moment, conversion = resolve_solar_birth_clock(
                wall,
                effective_longitude,
                birth_clock_basis,
                ephemeris_policy=solar_clock_ephemeris_policy,
            )
        return AstroBirthInfo(
            name=(name or "未提供").strip() or "未提供",
            birth_place=(birth_place or "未提供").strip() or "未提供",
            timezone="UTC",
            longitude=effective_longitude,
            latitude=effective_latitude,
            local_datetime=moment,
            utc_datetime=moment,
            recorded_datetime=moment,
            clock_conversion=conversion,
            timezone_source="solar_clock_conversion",
        )
    tzinfo = parse_timezone_name(timezone_name)
    local_datetime = datetime(
        birth_year,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
        birth_second,
        birth_microsecond,
        tzinfo=tzinfo,
    )
    validate_local_clock(local_datetime)
    recorded_datetime = local_datetime
    # Legacy callers rebase onto the apparent Sun (longitude + equation of
    # time). Physical-epoch callers preserve the civil instant and use
    # solar_datetime only as a wall-clock label, never a new zone timestamp.
    correction_minutes = 0.0
    solar_datetime = None
    solar_time_reference = None
    if use_true_solar_time:
        if not preserve_instant:
            from fatebridge.core.astro.solar_rebase import (
                rebase_solar_datetime,
                solar_rebase_adjustment,
            )

            adjustment, solar_time_reference = solar_rebase_adjustment(
                local_datetime, timezone_name, effective_longitude
            )
        else:
            adjustment = calculate_solar_time_adjustment(
                datetime(
                    birth_year,
                    birth_month,
                    birth_day,
                    birth_hour,
                    birth_minute,
                    birth_second,
                    birth_microsecond,
                ),
                timezone_name,
                effective_longitude,
                strategy=SOLAR_TIME_STRATEGY_APPARENT,
            )
        correction_minutes = adjustment["total_correction_minutes"]
        solar_delta = timedelta(minutes=correction_minutes)
        try:
            solar_datetime = (
                local_datetime + solar_delta
                if preserve_instant
                else rebase_solar_datetime(local_datetime, correction_minutes)
            )
        except OverflowError:
            # A valid physical instant can have a solar wall label outside
            # Python's year1..9999 representation. Presentation must not move
            # or invalidate that instant; legacy rebasing still rejects it.
            if not preserve_instant:
                raise
            solar_datetime = None
        if not preserve_instant:
            assert solar_datetime is not None
            local_datetime = solar_datetime
    utc_datetime = utc_calendar(local_datetime).as_datetime()
    return AstroBirthInfo(
        name=(name or "未提供").strip() or "未提供",
        birth_place=(birth_place or "未提供").strip() or "未提供",
        timezone=timezone_name,
        longitude=effective_longitude,
        latitude=effective_latitude,
        local_datetime=local_datetime,
        utc_datetime=utc_datetime,
        applied_true_solar=use_true_solar_time,
        solar_correction_minutes=round(correction_minutes, 4),
        solar_datetime=solar_datetime,
        solar_time_reference=solar_time_reference,
        recorded_datetime=recorded_datetime,
        timezone_source=timezone_source,
    )
