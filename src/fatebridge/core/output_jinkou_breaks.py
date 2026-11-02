"""Bind printed pair facts to their own course, including partial projections."""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import Field, StrictBool, StrictInt, model_validator

from .metaphysics.jinkou_branch_breaks import (
    CONTEXTS,
    POSITIONS,
    RULE,
    branch_breaks,
    branch_breaks_trace,
    metadata,
    pair_facts,
)
from .output_base import PartialOutput
from .output_jinkou_break_witnesses import BreakPairWitnessEvidence
from .output_liuren_emptiness import Branch


def compare(actual: Any, expected: Any, *, complete: bool = False) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or (
            complete and expected.keys() - actual.keys()
        ):
            raise ValueError("完整破支事实缺少原文或同课依据")
        for key in actual.keys() & expected.keys():
            compare(actual[key], expected[key], complete=complete)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("破支事实须保留所列完整队列")
        for a, b in zip(actual, expected):
            compare(a, b, complete=complete)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("破支事实与所选原文或本课本支不一致")


class JinkouBreakPair(PartialOutput):
    id: Literal["god_general", "god_ground", "general_ground"] | None = None
    left_position: str | None = None
    right_position: str | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    source_pair_present: StrictBool | None = None
    source_written_pair: list[Branch] | None = Field(
        default=None, min_length=2, max_length=2
    )
    source_order: Literal["left_then_right", "right_then_left"] | None = None
    effective_break: None = None
    effect_direction: None = None

    @model_validator(mode="after")
    def present_facts_agree(self) -> JinkouBreakPair:
        value = self.model_dump(exclude_unset=True)
        if self.id is not None:
            _, i, j = next(c for c in CONTEXTS if c[0] == self.id)
            compare(
                value, dict(left_position=POSITIONS[i], right_position=POSITIONS[j])
            )
        if self.left_branch is not None and self.right_branch is not None:
            compare(value, pair_facts(self.left_branch, self.right_branch))
        elif any(
            k in value and value[k] is None for k in ("left_branch", "right_branch")
        ):
            if self.source_pair_present is not None:
                raise ValueError("明确未知的本支不能判定破支配对")
        return self


class JinkouBranchBreaks(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_printed_break_pairs_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_page: StrictInt | None = None
    written_pairs: list[list[Branch]] | None = None
    transcription_url: str | None = None
    transcription_written_pairs: list[list[Branch]] | None = None
    scan_extra_pairs: list[list[Branch]] | None = None
    extra_pair_author_intent: None = None
    witness_evidence: BreakPairWitnessEvidence | None = None
    membership_policy: str | None = None
    rows: list[JinkouBreakPair] | None = Field(default=None, min_length=3, max_length=3)
    effect_direction: None = None
    effective_break: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def same_source_and_queue(self) -> JinkouBranchBreaks:
        value = self.model_dump(exclude_unset=True)
        compare(value, metadata())
        if self.rows is not None:
            compare(
                value["rows"],
                [
                    dict(
                        id=identifier,
                        left_position=POSITIONS[i],
                        right_position=POSITIONS[j],
                    )
                    for identifier, i, j in CONTEXTS
                ],
            )
        return self


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else value.model_dump(exclude_unset=True)


def align_branch_breaks(value: Any, *, complete: bool = False) -> None:
    board = as_dict(value)
    rows = board.get("rows")
    expected = None
    if isinstance(rows, list):
        by_role = {
            r.get("label"): r.get("content") for r in rows if isinstance(r, dict)
        }
        if all(by_role.get(p) is not None for p in POSITIONS):
            expected = branch_breaks(*(cast(str, by_role[p]) for p in POSITIONS))
    block = board.get("branch_breaks")
    traces = [t for t in board.get("rule_trace") or [] if t.get("rule_id") == RULE]
    if len(traces) > 1:
        raise ValueError("破支事实的规则轨迹不可重复")
    for trace in traces:
        if trace.get("result") is not None:
            JinkouBranchBreaks.model_validate(trace["result"])
    if complete:
        if expected is None or block is None or len(traces) != 1:
            raise ValueError("完整金口诀须保留三组破支事实及唯一同课轨迹")
        compare(block, expected, complete=True)
        compare(traces[0], branch_breaks_trace(expected), complete=True)
    else:
        if expected is not None:
            if block is not None:
                compare(block, expected)
            if traces and "result" in traces[0]:
                compare(traces[0]["result"], expected)
        if block is not None and traces and "result" in traces[0]:
            compare(traces[0]["result"], block)
