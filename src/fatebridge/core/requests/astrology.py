"""Request contracts for astrology."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    Field,
    StrictInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from fatebridge.core.requests.base import (
    FateBridgeBaseRequest,
    OfflineHouseValidatorMixin,
)
from fatebridge.core.requests.birth import AstroBirthBase
from fatebridge.utils.house_systems import OFFLINE_HOUSE_CODE_NOTE

SUBMICROSECOND_TARGET = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}.[0-9]{2}:[0-9]{2}:[0-9]{2}[.,][0-9]{6}0*[1-9]"
)

NUMERIC_TARGET = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)


def _exact_target_datetime(
    value: object, validate: ValidatorFunctionWrapHandler
) -> datetime:
    # Match only a fractional tail in the original label after Pydantic has
    # accepted its syntax. The parser's minute offset cannot cancel that tail.
    moment: datetime = validate(value)
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str) and SUBMICROSECOND_TARGET.match(value):
        raise ValueError("Target datetime must be representable to the microsecond")
    if isinstance(value, float):
        timestamp = Decimal.from_float(value)
    elif isinstance(value, str) and NUMERIC_TARGET.fullmatch(value):
        try:
            timestamp = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("Invalid target timestamp") from error
    else:
        return moment

    # Keep Speedate's unit threshold, applied to the supplied value once.
    # The decimal tuple scales exactly, regardless of the caller's context.
    sign, digits, exponent = timestamp.as_tuple()
    if not isinstance(exponent, int):
        raise ValueError("Target timestamp must be finite")
    scale = 3 if timestamp.copy_abs() > 20_000_000_000 else 6
    microseconds = round(Decimal((sign, digits, exponent + scale)))
    try:
        return datetime(1970, 1, 1, tzinfo=moment.tzinfo) + timedelta(
            microseconds=microseconds
        )
    except OverflowError as error:
        raise ValueError("Target timestamp is outside datetime range") from error


_ExactTargetDatetime = Annotated[AwareDatetime, WrapValidator(_exact_target_datetime)]


class AstroChartRequest(OfflineHouseValidatorMixin, AstroBirthBase):
    """Request model for offline astrology chart generation."""

    gender: str | None = Field(
        default="未知",
        description=(
            "性别（可选，仅用于结果标识；西方星盘计算不使用性别）。接受此字段是为了让"
            "同一套出生信息可以原样喂给八字/紫微/星盘等工具，避免批量调用时'有的工具收、"
            "有的不收'造成的反复试错。"
        ),
    )
    house_system: int | str | None = Field(
        default=None,
        description=(
            "Optional offline house system override; if omitted, FateBridge keeps each "
            "chart variant's historical default. Accepts SE letters, keys, or integer "
            "codes 0..8 (0=whole_sign, 1=Alcabitus, 2=Regiomontanus, 3=Placidus, "
            "4=Koch, 5=Vehlow Equal, 6=Polich Page, 7=Sripati, 8=equal_mc)."
        )
        + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiac_type: Literal["Tropic", "Sidereal"] | None = Field(
        default=None,
        description=(
            "Optional offline zodiac override ('Tropic' or 'Sidereal'); if omitted, "
            "FateBridge keeps each chart variant's historical default."
        ),
    )
    use_true_solar_time: bool = Field(
        default=False,
        description=(
            "Rebase the birth clock onto true solar time (longitude + equation of "
            "time). Default OFF: western astrology conventionally casts on the "
            "recorded civil (zone) clock time. Set true to align the western chart "
            "with the BaZi engine's apparent-solar instant."
            " Guolao and Indian charts preserve the recorded civil instant and report the solar clock separately."
        ),
    )


class SolarBirthClockFields(AstroChartRequest):
    """Shared birth clock basis and seconds for Germany and 13-sector charts."""

    birth_clock_basis: Literal["civil", "local_mean_solar", "local_apparent_solar"] = (
        Field(
            default="civil",
            description=(
                "Confirmed basis of the supplied birth clock label: civil uses birth_timezone; "
                "local_mean_solar (LMT) or local_apparent_solar (LAT) uses longitude and modeled "
                "UT1/TT with birth_timezone omitted."
            ),
        )
    )
    birth_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description=(
            "Recorded birth second (0..59), if known. Omitted seconds use the start of the "
            "supplied minute; this does not certify exact recording precision. Leap-second labels "
            "are not represented."
        ),
    )

    @model_validator(mode="after")
    def _validate_solar_birth_timezone(self) -> "SolarBirthClockFields":
        if self.birth_clock_basis != "civil" and self.birth_timezone is not None:
            raise PydanticCustomError(
                "conflicting_solar_birth_timezone",
                "Explicit solar birth labels must omit birth_timezone",
                {"path": "birth_timezone"},
            )
        return self


class AstroSpecialtyRequest(SolarBirthClockFields):
    """Germany and equal13 charts with explicitly confirmed time uncertainty."""

    birth_time_uncertainty_minutes: float | None = Field(
        default=None,
        ge=0,
        le=120,
        allow_inf_nan=False,
        description="User-confirmed +/- minutes around the recorded birth instant. None means unknown, not exact. Recalculates factors and the published source pattern / equal13 assignments on a UTC grid no wider than 30 seconds; samples are not a continuous-interval proof or probabilities.",
    )

    @model_validator(mode="after")
    def _solar_birth_clock_scope(self) -> "AstroSpecialtyRequest":
        if self.birth_clock_basis != "civil" and self.use_true_solar_time:
            raise PydanticCustomError(
                "conflicting_solar_birth_clock",
                "Local solar birth clocks require birth_timezone omitted and use_true_solar_time=false",
                {"path": "use_true_solar_time"},
            )
        return self


class AstroGermanyRequest(AstroSpecialtyRequest):
    """Optional target instant enables the explicit true-solar-arc layer."""

    high_latitude_fallback: Literal["error", "porphyry", "whole_sign"] = Field(
        default="error",
        description="Fallback when quadrant houses fail at |lat| >= 66.5°: error (default), porphyry, or whole_sign.",
    )
    dial_degrees: Literal["90", "45", "22.5"] = Field(
        default="90",
        description="Primary dial modulus to summarize in compact output (90, 45, or 22.5).",
    )
    sensitive_point_query: str | None = Field(
        default=None,
        description="Optional sensitive point formula 'A+B-C' (e.g. 'Mars+Jupiter-Zeus') to evaluate against all chart factors.",
    )
    analysis_datetime: _ExactTargetDatetime | None = Field(
        default=None,
        description="Optional ISO target instant with timezone offset for true-solar-arc biwheel geometry and the explicitly named Witte-1924 ecliptic day-meridian equation. Uses a 365.25-day Julian symbolic year key, within 0..150 key years after effective birth. Omit for natal only. Symbolic directions/meridians are not physical target positions or event-success probabilities.",
    )


class AstroNatalChartRequest(AstroChartRequest):
    """Natal astrology chart request with optional apparent-solar position layer."""

    node_mode: Literal["mean", "true"] = Field(
        default="mean",
        description="Lunar node mode: 'mean' (default) or 'true' (osculating true node).",
    )
    high_latitude_fallback: Literal["error", "porphyry", "whole_sign"] = Field(
        default="error",
        description="Fallback when quadrant houses fail at high latitudes (|lat| >= 66.5°): error (default), porphyry, or whole_sign.",
    )
    include_minor_aspects: bool = Field(
        default=False,
        description="Include minor aspects (30° semisextile, 45° semisquare, 72° quintile, 135° sesquiquadrate, 150° quincunx).",
    )
    extra_bodies: list[
        Literal["Chiron", "Lilith", "Ceres", "Pallas", "Juno", "Vesta", "True Node"]
    ] = Field(
        default_factory=list,
        description="Optional additional bodies/points to compute alongside the 11 standard chart points.",
    )
    apparent_model: Literal["native", "opaque_solar"] = Field(
        default="native",
        description=(
            "native retains the native chart. opaque_solar additionally returns standalone "
            "geocentric apparent_model_positions, with finite-source solar deflection outside "
            "an opaque 695700 km Sun and zero deflection for intercepted rays. Requires local "
            "barycentric ephemeris files and the jpl extra. This position layer does not "
            "recompute native planets, speeds, houses, aspects or readings; its tropical "
            "IAU2006/2000A frame is explicit even for a sidereal native chart."
        ),
    )


class AstroRelativeFlatRequest(OfflineHouseValidatorMixin, FateBridgeBaseRequest):
    """Flat (non-nested) relative/synastry chart request for tool surfaces."""

    davison_variant: Literal["uncorrected", "corrected", "spherical"] = Field(
        default="uncorrected",
        description="TimeSpace/Marks variant: uncorrected, MC-axis corrected, or spherical geographic midpoint. UT1 arithmetic time mean; nondefault variants require TimeSpace or Marks.",
    )

    inner_use_true_solar_time: bool = Field(
        default=False, description="Use apparent solar time for the inner chart"
    )
    outer_use_true_solar_time: bool = Field(
        default=False, description="Use apparent solar time for the outer chart"
    )

    inner_birth_year: int = Field(ge=1, le=9999, description="Inner chart birth year")
    inner_birth_month: int = Field(ge=1, le=12, description="Inner chart birth month")
    inner_birth_day: int = Field(ge=1, le=31, description="Inner chart birth day")
    inner_birth_hour: int = Field(ge=0, le=23, description="Inner chart birth hour")
    inner_birth_longitude: float = Field(ge=-180, le=180, description="Inner longitude")
    inner_birth_latitude: float = Field(ge=-90, le=90, description="Inner latitude")
    outer_birth_year: int = Field(ge=1, le=9999, description="Outer chart birth year")
    outer_birth_month: int = Field(ge=1, le=12, description="Outer chart birth month")
    outer_birth_day: int = Field(ge=1, le=31, description="Outer chart birth day")
    outer_birth_hour: int = Field(ge=0, le=23, description="Outer chart birth hour")
    outer_birth_longitude: float = Field(ge=-180, le=180, description="Outer longitude")
    outer_birth_latitude: float = Field(ge=-90, le=90, description="Outer latitude")
    inner_name: str | None = Field(default="内盘", description="Inner chart name")
    outer_name: str | None = Field(default="外盘", description="Outer chart name")
    inner_birth_place: str | None = Field(
        default="未提供", description="Inner birth place"
    )
    outer_birth_place: str | None = Field(
        default="未提供", description="Outer birth place"
    )
    relative_mode: str | int | None = Field(
        default=None, description="Relative mode selector"
    )
    inner_birth_minute: int = Field(
        default=0, ge=0, le=59, description="Inner birth minute"
    )
    outer_birth_minute: int = Field(
        default=0, ge=0, le=59, description="Outer birth minute"
    )
    inner_birth_timezone: str | None = Field(
        default=None,
        description=(
            "Inner timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from supported inner_birth_place; no implicit "
            "UTC is selected when unresolved. A hardcoded 'UTC' default silently "
            "treated an eastern wall-clock time as UTC and rotated the chart."
        ),
    )
    outer_birth_timezone: str | None = Field(
        default=None,
        description=(
            "Outer timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from supported outer_birth_place; no implicit "
            "UTC is selected when unresolved. A hardcoded 'UTC' default silently "
            "treated an eastern wall-clock time as UTC and rotated the chart."
        ),
    )
    house_system: int | str = Field(
        default="P",
        description=(
            "House system identifier (0..8, SE letter, or key). Defaults to Placidus ('P') "
            "to match the natal chart."
        )
        + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiac_type: Literal["Tropic", "Sidereal"] = Field(
        default="Tropic", description="Zodiac type: Tropic or Sidereal"
    )
    relationship_focus: str | None = Field(
        default=None,
        description=(
            "Optional relationship intent lens: marriage/婚姻 or romance/恋爱; "
            "adds a focus block + intent-filtered synastry aspects. Default/unset "
            "is general (no filtering)."
        ),
    )
    composite_house_method: Literal["cusp_midpoints", "mc_latitude"] = Field(
        default="cusp_midpoints",
        description="Composite house cusp method: 'cusp_midpoints' (default short-arc cusp midpoints) or 'mc_latitude' (Composite MC + mean latitude derived houses).",
    )
    high_latitude_fallback: Literal["error", "porphyry", "whole_sign"] = Field(
        default="error",
        description="Fallback when quadrant houses fail at high latitudes: error (default), porphyry, or whole_sign.",
    )
