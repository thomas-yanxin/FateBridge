"""Request contracts for base."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator
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

    @model_validator(mode="before")
    @classmethod
    def _validate_consultation_scope(cls, data: Any) -> Any:
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
                try:
                    datetime(cast(int, date[0]), cast(int, date[1]), cast(int, date[2]))
                except (ValueError, TypeError):
                    raise PydanticCustomError(
                        "invalid_calendar_date", "无效的公历日期", {"prefix": prefix}
                    ) from None
        return self
