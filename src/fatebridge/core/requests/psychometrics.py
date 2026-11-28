"""Request contracts for psychometric assessments."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator
from pydantic_core import PydanticCustomError

from fatebridge.core.psychometrics.ipip_big_five import TOTAL_ITEMS, BigFiveDomain
from fatebridge.core.requests.base import FateBridgeBaseRequest

LikertScore = Annotated[StrictInt, Field(ge=1, le=5)]


def _parse_item_id(key: object) -> int | None:
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        return key if 1 <= key <= TOTAL_ITEMS else None
    if isinstance(key, str) and key.isascii() and key.isdigit():
        item_id = int(key)
        if 1 <= item_id <= TOTAL_ITEMS and str(item_id) == key:
            return item_id
    return None


class IpipBigFiveRequest(FateBridgeBaseRequest):
    """Shared request contract for administering or scoring IPIP Big-Five 50."""

    action: Literal["score", "list_items"] = Field(
        default="score",
        description=(
            "操作模式：list_items 列出50道标准IPIP题项与计分方向；"
            "score 对1-5分整数作答进行确定性正反向计分。"
        ),
    )
    responses: dict[str, LikertScore | None] | None = Field(
        default=None,
        description=(
            "按题号（'1'..'50'）映射的1-5分整数作答（JSON对象，CLI支持 --responses '{\"1\":5,...}'）；"
            "缺题可省略或设为 null，不可与 ratings 同时提供。"
        ),
    )
    ratings: list[LikertScore | None] | None = Field(
        default=None,
        min_length=1,
        max_length=TOTAL_ITEMS,
        description=(
            "按第1..50题顺序提交的1-5分整数列表（CLI支持 --ratings 5 1 4 ...）；"
            "缺题可设为 null，不可与 responses 同时提供。"
        ),
    )
    domain: BigFiveDomain | None = Field(
        default=None,
        description=(
            "仅在 action=list_items 时可选筛选单个维度："
            "extraversion / agreeableness / conscientiousness / emotional_stability / intellect。"
        ),
    )
    include_item_breakdown: bool = Field(
        default=False,
        description="仅在 action=score 时为 true 返回逐题原始分、计分键与折算后分值明细。",
    )

    @field_validator("responses", mode="before")
    @classmethod
    def _normalize_response_keys(cls, value: object) -> object:
        if value is None or not isinstance(value, dict):
            return value
        normalized: dict[str, object] = {}
        for raw_key, raw_score in value.items():
            item_id = _parse_item_id(raw_key)
            if item_id is None:
                raise PydanticCustomError(
                    "invalid_item_id",
                    "题号必须为 '1' 到 '50' 的规范整数：{item_key}",
                    {"item_key": str(raw_key), "path": "responses"},
                )
            canonical_key = str(item_id)
            if canonical_key in normalized:
                raise PydanticCustomError(
                    "duplicate_item_id",
                    "存在重复题号：{item_id}",
                    {"item_id": item_id, "path": "responses"},
                )
            normalized[canonical_key] = raw_score
        return normalized

    def _answered_map(self) -> dict[int, int]:
        if self.responses is not None:
            return {
                int(key): score
                for key, score in self.responses.items()
                if score is not None
            }
        if self.ratings is not None:
            return {
                index + 1: score
                for index, score in enumerate(self.ratings)
                if score is not None
            }
        return {}

    @model_validator(mode="after")
    def _validate_mode_inputs(self) -> "IpipBigFiveRequest":
        if self.action == "list_items":
            if self.responses is not None or self.ratings is not None:
                raise PydanticCustomError(
                    "invalid_mode_parameters",
                    "action=list_items 时不应提供 responses 或 ratings",
                    {"path": "responses" if self.responses is not None else "ratings"},
                )
            return self
        if self.domain is not None:
            raise PydanticCustomError(
                "invalid_mode_parameters",
                "action=score 时不支持 domain 筛选参数",
                {"path": "domain"},
            )
        if self.responses is not None and self.ratings is not None:
            raise PydanticCustomError(
                "conflicting_inputs",
                "responses 与 ratings 不能同时提供，请二选一",
                {"path": "ratings"},
            )
        if self.responses is None and self.ratings is None:
            raise PydanticCustomError(
                "missing_responses",
                "action=score 时必须提供 responses 或 ratings",
                {"path": "responses"},
            )
        if not self._answered_map():
            raise PydanticCustomError(
                "empty_responses",
                "至少需要提供 1 道有效（1-5 整数）作答",
                {"path": "responses" if self.responses is not None else "ratings"},
            )
        return self

    def service_inputs(self) -> dict[str, str | bool | dict[int, int] | None]:
        if self.action == "list_items":
            return {"action": "list_items", "domain": self.domain}
        return {
            "action": "score",
            "answers": self._answered_map(),
            "include_item_breakdown": self.include_item_breakdown,
        }
