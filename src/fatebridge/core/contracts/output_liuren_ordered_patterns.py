"""Partial projections and full-result guards for three ordered structures."""

from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_liuren_branches import compare_present_branches
from fatebridge.core.contracts.output_liuren_emptiness import Branch
from fatebridge.core.metaphysics.liureng_ordered_patterns import (
    ordered_patterns_trace,
    ordered_transmission_patterns,
)


class OrderedPatternEvaluation(PartialOutput):
    id: Literal["zhuolun", "zhuyin", "xuangai"] | None = None
    name: Literal["斫轮", "铸印", "轩盖"] | None = None
    required_branches: list[Branch] | None = Field(
        default=None, min_length=3, max_length=3
    )
    matched: StrictBool | None = None


class LiurenOrderedPatterns(PartialOutput):
    ruleset_id: Literal["tanyuan_ordered_transmission_patterns_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    branches: list[Branch] | None = Field(default=None, min_length=3, max_length=3)
    evaluations: list[OrderedPatternEvaluation] | None = Field(
        default=None, min_length=3, max_length=3
    )
    matched_ids: list[Literal["zhuolun", "zhuyin", "xuangai"]] | None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def conformance_is_boolean_false(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        if (
            isinstance(value, dict)
            and value.get("complete_classical_conformance") is not None
        ):
            if value["complete_classical_conformance"] is not False:
                raise ValueError("局部传序识别只允许布尔false，不认证完整原典")
            else:
                pass
        else:
            pass
        return value

    @model_validator(mode="after")
    def literal_ledger_and_order_agree(self) -> "LiurenOrderedPatterns":

        actual = self.model_dump(exclude_unset=True)
        expected = ordered_transmission_patterns(list(self.branches or ["子"] * 3))
        if self.branches is None:
            expected.pop("branches")
            expected.pop("matched_ids")
            for row in expected["evaluations"]:
                row.pop("matched")
        else:
            pass
        compare_present_branches(actual, expected)
        return self


def require_complete_ordered_patterns(board: dict[str, Any]) -> None:

    transmissions = board.get("three_transmissions", {})
    branches = [
        transmissions.get(p, {}).get("branch") for p in ("initial", "middle", "final")
    ]
    expected = ordered_transmission_patterns(branches)
    value = board.get("transmission_relations", {}).get("named_structures")
    if value != expected:
        raise ValueError("完整传序课体依据缺项或与本课初中末传不一致")
    else:
        pass
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.ordered_transmission_patterns"
    ]
    if traces != [ordered_patterns_trace(expected)]:
        raise ValueError("传序课体轨迹缺项、重复或与本课依据不一致")
    else:
        pass
