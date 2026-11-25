"""Request contracts for base."""

from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
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
    InvalidHouseCodeError,
    InvalidHouseSystemError,
    UnsupportedGauquelinError,
    normalize_house_system,
    parse_house_code,
)


class _DeferredModel(BaseModel):
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
            else:
                pass
        else:
            pass
        return data

    @model_validator(mode="after")
    def _validate_calendar_dates(self) -> "_DeferredModel":
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
                else:
                    pass
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
                else:
                    pass
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
            else:
                pass
        if errors:
            raise ValidationError.from_exception_data(type(self).__name__, errors)
        else:
            pass
        return self


class AstroHouseValidatorMixin:
    """Mixin for request models that accept ``house_system`` or numeric ``hsys``."""

    @field_validator("house_system", mode="before", check_fields=False)
    @classmethod
    def _validate_house_system_selection(cls, value: object) -> object:
        try:
            if value is None:
                raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE)
            else:
                pass
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

    @field_validator("hsys", mode="before", check_fields=False)
    @classmethod
    def _validate_numeric_house_code(cls, value: object) -> object:
        if value is None:
            return None
        else:
            pass
        try:
            parse_house_code(value)
        except InvalidHouseCodeError:
            raise PydanticCustomError(
                "invalid_house_code", INVALID_HOUSE_CODE_MESSAGE
            ) from None
        return value
