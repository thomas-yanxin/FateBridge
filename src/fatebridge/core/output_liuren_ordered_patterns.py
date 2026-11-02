"""Partial projections and full-result guards for three ordered structures."""

from typing import Any, List, Literal, Optional

from pydantic import Field, StrictBool, StrictInt, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches
from .output_liuren_emptiness import Branch


class OrderedPatternEvaluation(PartialOutput):
    id: Optional[Literal["zhuolun", "zhuyin", "xuangai"]] = None
    name: Optional[Literal["斫轮", "铸印", "轩盖"]] = None
    required_branches: Optional[List[Branch]] = Field(
        default=None, min_length=3, max_length=3
    )
    matched: Optional[StrictBool] = None


class LiurenOrderedPatterns(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_ordered_transmission_patterns_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[StrictInt]] = None
    branches: Optional[List[Branch]] = Field(default=None, min_length=3, max_length=3)
    evaluations: Optional[List[OrderedPatternEvaluation]] = Field(
        default=None, min_length=3, max_length=3
    )
    matched_ids: Optional[List[Literal["zhuolun", "zhuyin", "xuangai"]]] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def conformance_is_boolean_false(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("complete_classical_conformance") is not None
        ):
            if value["complete_classical_conformance"] is not False:
                raise ValueError("局部传序识别只允许布尔false，不认证完整原典")
        return value

    @model_validator(mode="after")
    def literal_ledger_and_order_agree(self) -> "LiurenOrderedPatterns":
        from .metaphysics.liureng_ordered_patterns import ordered_transmission_patterns

        actual = self.model_dump(exclude_unset=True)
        expected = ordered_transmission_patterns(list(self.branches or ["子"] * 3))
        if self.branches is None:
            expected.pop("branches")
            expected.pop("matched_ids")
            for row in expected["evaluations"]:
                row.pop("matched")
        compare_present_branches(actual, expected)
        return self


def require_complete_ordered_patterns(board: dict[str, Any]) -> None:
    from .metaphysics.liureng_ordered_patterns import (
        ordered_patterns_trace,
        ordered_transmission_patterns,
    )

    transmissions = board.get("three_transmissions", {})
    branches = [
        transmissions.get(p, {}).get("branch") for p in ("initial", "middle", "final")
    ]
    expected = ordered_transmission_patterns(branches)
    value = board.get("transmission_relations", {}).get("named_structures")
    if value != expected:
        raise ValueError("完整传序课体依据缺项或与本课初中末传不一致")
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.ordered_transmission_patterns"
    ]
    if traces != [ordered_patterns_trace(expected)]:
        raise ValueError("传序课体轨迹缺项、重复或与本课依据不一致")
