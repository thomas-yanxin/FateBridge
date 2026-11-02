"""Request contracts for base."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError


class _DeferredModel(BaseModel):
    """所有请求模型的公共基类。

    ``defer_build=True`` 把 Pydantic 的核心 schema / validator 编译从「类定义时」
    推迟到「首次实例化时」，从而把 import 期（CLI 冷启动）逐个编译模型的开销移出
    关键路径——大量请求模型不再在导入时一次性编译。

    对计算结果与校验行为**零影响**：defer_build 仅改变 schema 的构建时机，不改变
    schema 内容；首次实例化时按需构建并缓存，后续调用与原先完全一致。子类自带的
    ``model_config`` 会与本配置合并，不会丢失。
    """

    model_config = ConfigDict(defer_build=True, extra="forbid")

    @field_validator("house_system", mode="before", check_fields=False)
    @classmethod
    def _validate_house_system_selection(cls, value: object) -> object:
        from fatebridge.utils.house_systems import (
            GAUQUELIN_UNSUPPORTED_MESSAGE,
            INVALID_HOUSE_SYSTEM_MESSAGE,
            InvalidHouseSystemError,
            UnsupportedGauquelinError,
            normalize_house_system,
        )

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

    @field_validator("hsys", mode="before", check_fields=False)
    @classmethod
    def _validate_numeric_house_code(cls, value: object) -> object:
        from fatebridge.utils.house_systems import (
            INVALID_HOUSE_CODE_MESSAGE,
            InvalidHouseCodeError,
            parse_house_code,
        )

        if value is None:
            return None
        try:
            parse_house_code(value)
        except InvalidHouseCodeError:
            raise PydanticCustomError(
                "invalid_house_code", INVALID_HOUSE_CODE_MESSAGE
            ) from None
        # Preserve the original value so a domain's StrictInt can still reject
        # digit strings rather than being bypassed by this shared guard.
        return value

    @model_validator(mode="before")
    @classmethod
    def _validate_consultation_scope(cls, data: object) -> object:
        from fatebridge.core.consultation_policy import (
            POLICY_ID,
            restricted_intent_path,
        )

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
    def _validate_calendar_dates(self) -> "_DeferredModel":
        # Bounds such as day<=31 cannot reject February 30. Validate complete
        # civil dates before binding on every transport, including pair inputs.
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
            date = [
                getattr(self, prefix + part, None) for part in ("year", "month", "day")
            ]
            if all(value is not None for value in date):
                if (
                    prefix in {"candidate_", "question_"}
                    and getattr(self, prefix + "hour_origin", None) == "noon"
                ):
                    from fatebridge.core.western_clock_origin import event_wall_datetime

                    try:
                        event_wall_datetime(
                            cast(int, date[0]),
                            cast(int, date[1]),
                            cast(int, date[2]),
                            getattr(self, prefix + "hour"),
                            getattr(self, prefix + "minute", 0),
                            getattr(self, prefix + "calendar", "proleptic_gregorian"),
                            "noon",
                        )
                    except (ValueError, TypeError):
                        raise PydanticCustomError(
                            "invalid_clock_origin_datetime",
                            "无效的正午起算日期／小时标签，或最终钟面超出支持范围",
                            {"prefix": prefix, "hour_origin": "noon"},
                        ) from None
                    continue
                if getattr(self, prefix + "calendar", None) == "julian":
                    from fatebridge.core.civil_calendar import gregorian_date

                    try:
                        gregorian_date(
                            cast(int, date[0]),
                            cast(int, date[1]),
                            cast(int, date[2]),
                            calendar="julian",
                        )
                    except (ValueError, TypeError):
                        raise PydanticCustomError(
                            "invalid_calendar_date",
                            "无效的儒略历日期或换算结果超出支持范围",
                            {"prefix": prefix, "calendar": "julian"},
                        ) from None
                    continue
                try:
                    datetime(cast(int, date[0]), cast(int, date[1]), cast(int, date[2]))
                except (ValueError, TypeError):
                    raise PydanticCustomError(
                        "invalid_calendar_date", "无效的公历日期", {"prefix": prefix}
                    ) from None
        return self
