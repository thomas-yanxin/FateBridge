"""Request contracts for base."""

from __future__ import annotations

import types
from datetime import datetime
from typing import Annotated, Literal, Union, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from fatebridge.core.civil_calendar import gregorian_date
from fatebridge.core.consultation_policy import POLICY_ID, restricted_intent_path
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.utils.house_systems import (
    GAUQUELIN_UNSUPPORTED_MESSAGE,
    INVALID_HOUSE_CODE_MESSAGE,
    INVALID_HOUSE_SYSTEM_MESSAGE,
    TWELVE_HOUSE_SYSTEM_NOTE,
    InvalidHouseCodeError,
    InvalidHouseSystemError,
    UnsupportedGauquelinError,
    normalize_house_system,
    normalize_zodiac_type,
    parse_house_code,
    resolve_offline_house_code,
)


def _allows_none(annotation: object) -> bool:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _allows_none(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        return any(_allows_none(arg) for arg in get_args(annotation))
    return annotation is type(None)


class FateBridgeBaseRequest(BaseModel):
    """Build request schemas on first use and reject undeclared fields."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _validate_consultation_scope(cls, data: object) -> object:
        if isinstance(data, dict):
            path = restricted_intent_path(data)
            if path:
                raise PydanticCustomError(
                    "consultation_restricted",
                    "此请求超出允许的咨询范围",
                    {"policy": POLICY_ID, "path": path},
                )
        return data

    @model_validator(mode="after")
    def _validate_calendar_dates(self) -> "FateBridgeBaseRequest":
        # note (civil date): Component ranges alone cannot reject February 30.
        errors: list[InitErrorDetails] = []
        for prefix in (
            "birth_",
            "person1_birth_",
            "person2_birth_",
            "analysis_",
            "candidate_",
            "question_",
            "inner_birth_",
            "outer_birth_",
        ):
            year: int | None = getattr(self, prefix + "year", None)
            month: int | None = getattr(self, prefix + "month", None)
            day: int | None = getattr(self, prefix + "day", None)
            if year is not None and month is not None and day is not None:
                if (
                    prefix in {"candidate_", "question_"}
                    and getattr(self, prefix + "hour_origin", None) == "noon"
                ):
                    try:
                        event_wall_datetime(
                            year,
                            month,
                            day,
                            getattr(self, prefix + "hour"),
                            getattr(self, prefix + "minute", 0),
                            getattr(self, prefix + "calendar", "proleptic_gregorian"),
                            "noon",
                            second=getattr(self, prefix + "second", 0),
                        )
                    except (ValueError, TypeError):
                        raise PydanticCustomError(
                            "invalid_clock_origin_datetime",
                            "无效的正午起算日期／小时标签，或最终钟面超出支持范围",
                            {"path": prefix + "datetime"},
                        ) from None
                    continue
                if getattr(self, prefix + "calendar", None) == "julian":
                    try:
                        gregorian_date(
                            year,
                            month,
                            day,
                            calendar="julian",
                        )
                    except (ValueError, TypeError):
                        raise PydanticCustomError(
                            "invalid_calendar_date",
                            "无效的儒略历日期或换算结果超出支持范围",
                            {"path": prefix + "date"},
                        ) from None
                    continue
                try:
                    datetime(year, month, day)
                except (ValueError, TypeError):
                    errors.append(
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "invalid_calendar_date",
                                "无效的公历日期，请核对年、月、日及闰年。",
                                {"path": prefix + "date"},
                            ),
                            loc=(),
                            input=[year, month, day],
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(type(self).__name__, errors)
        return self


class AstroHouseValidatorMixin:
    """Mixin for Western request models that accept house_system and zodiac_type."""

    @field_validator("house_system", mode="before", check_fields=False)
    @classmethod
    def _validate_house_system_selection(cls, value: object) -> object:
        try:
            if value is None:
                raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE)
            normalize_house_system(value)
        except UnsupportedGauquelinError:
            raise PydanticCustomError(
                "unsupported_house_system",
                GAUQUELIN_UNSUPPORTED_MESSAGE,
                {"system": "Gauquelin", "sector_count": 36},
            ) from None
        except InvalidHouseSystemError:
            raise PydanticCustomError(
                "invalid_house_system", INVALID_HOUSE_SYSTEM_MESSAGE
            ) from None
        return value

    @field_validator("zodiac_type", mode="before", check_fields=False)
    @classmethod
    def _normalize_zodiac_type_selection(cls, value: object) -> object:
        return normalize_zodiac_type(value)


class OfflineHouseValidatorMixin:
    """Mixin for offline chart models restricted to house codes 0..8 and Tropic/Sidereal."""

    @field_validator("house_system", mode="before", check_fields=False)
    @classmethod
    def _validate_offline_house_system(cls, value: object) -> object:
        if value is None:
            field = (
                cls.model_fields.get("house_system")
                if issubclass(cls, BaseModel)
                else None
            )
            if field is not None and _allows_none(field.annotation):
                return None
            raise PydanticCustomError("invalid_house_code", INVALID_HOUSE_CODE_MESSAGE)
        try:
            resolve_offline_house_code(value)
        except UnsupportedGauquelinError:
            raise PydanticCustomError(
                "unsupported_house_system",
                GAUQUELIN_UNSUPPORTED_MESSAGE,
                {"system": "Gauquelin", "sector_count": 36},
            ) from None
        except InvalidHouseCodeError:
            raise PydanticCustomError(
                "invalid_house_code", INVALID_HOUSE_CODE_MESSAGE
            ) from None
        return value

    @field_validator("zodiac_type", mode="before", check_fields=False)
    @classmethod
    def _normalize_offline_zodiac_type(cls, value: object) -> object:
        return normalize_zodiac_type(value)


class AnalysisDateFields(BaseModel):
    """Shared optional analysis calendar date fields (year, month, day)."""

    analysis_year: int | None = Field(default=None, description="Analysis year")
    analysis_month: int | None = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: int | None = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )


class OptionalAnalysisClockFields(AnalysisDateFields):
    """Shared optional analysis clock fields (year, month, day, hour, minute)."""

    analysis_hour: int | None = Field(
        default=None, ge=0, le=23, description="Analysis hour (0-23)"
    )
    analysis_minute: int | None = Field(
        default=None, ge=0, le=59, description="Analysis minute (0-59)"
    )


class RequiredAnalysisClockFields(BaseModel):
    """Shared required analysis clock fields for metaphysics engines."""

    analysis_year: int = Field(description="Analysis year, e.g., 2026")
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: int = Field(
        default=0, ge=0, le=59, description="Analysis minute (0-59)"
    )
    analysis_second: int = Field(
        default=0, ge=0, le=59, description="Analysis second (0-59)"
    )
    analysis_timezone: str | None = Field(
        default=None, description="Analysis timezone (IANA name or UTC offset)"
    )
    analysis_utc_offset: str | None = Field(
        default=None,
        description="已确认的民用 UTC 偏移，格式 ±HH:MM 或 ±HH:MM:SS，用于消歧重复钟时。",
    )
    analysis_longitude: float | None = Field(
        default=None, ge=-180, le=180, description="Analysis longitude"
    )


class WesternChartSystemFields(BaseModel):
    """Shared Western chart house-system and zodiac fields."""

    house_system: int | str = Field(
        default="P",
        description="House system, any convention: SE letter ('P'=Placidus, "
        "'R'=Regiomontanus, 'W'=whole sign, 'D'=equal_mc), key ('placidus', "
        "'equal_mc'), or integer code 0..8 (3=Placidus, 8=equal_mc)."
        + TWELVE_HOUSE_SYSTEM_NOTE,
    )
    zodiac_type: Literal["Tropic", "Sidereal"] = Field(
        default="Tropic", description="Zodiac type: Tropic or Sidereal"
    )

    @field_validator("zodiac_type", mode="before")
    @classmethod
    def _normalize_zodiac_type(cls, value: object) -> object:
        return normalize_zodiac_type(value)
