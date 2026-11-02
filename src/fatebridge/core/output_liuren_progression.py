"""Projection-aware same-calculation constraints for transmission progressions."""

from typing import Any, List, Literal, Optional

from pydantic import StrictBool, StrictInt, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches
from .output_liuren_emptiness import Branch


class LiurenProgression(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_transmission_progression_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[StrictInt]] = None
    day_ganzhi: Optional[str] = None
    branches: Optional[List[Branch]] = None
    steps: Optional[List[StrictInt]] = None
    kind: Optional[Literal["连茹", "间断"]] = None
    structure_matched: Optional[StrictBool] = None
    sequence_direction: Optional[Literal["进", "退"]] = None
    empty_branches: Optional[List[Branch]] = None
    branch_xun_kong: Optional[List[StrictBool]] = None
    raw_branch_empty_conditional_reading: Optional[
        Literal[
            "初空进退受阻",
            "末空以退论",
            "末空以进言",
            "按支序进读",
            "按支序退读",
            "见空不拘原进退说",
            "前进多阻",
            "后退有妨",
        ]
    ] = None
    raw_branch_empty_conditional_direction: Optional[Literal["进", "退"]] = None
    empty_assumption: Optional[str] = None
    effective_direction: None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def boolean_false_conformance(cls, value: Any) -> Any:
        if isinstance(value, dict):
            flag = value.get("complete_classical_conformance")
            if flag is not None and flag is not False:
                raise ValueError("三传局部条件只允许布尔false，不认证完整原典")
        return value

    @model_validator(mode="after")
    def consistent_progression(self) -> "LiurenProgression":
        for name, size in [
            ("branches", 3),
            ("steps", 2),
            ("empty_branches", 2),
            ("branch_xun_kong", 3),
        ]:
            value = getattr(self, name)
            if value is not None and len(value) != size:
                raise ValueError("三传进退依据队列长度不符")
        if self.day_ganzhi is not None and self.branches is not None:
            from .metaphysics.liureng_progression import transmission_progression

            compare_present_branches(
                self.model_dump(exclude_unset=True),
                transmission_progression(self.day_ganzhi, list(self.branches)),
            )
        return self


def get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def align_progression(board: Any, pillars: Any = None) -> None:
    evidence = get(board, "transmission_progression")
    if evidence is None:
        return
    day = get(evidence, "day_ganzhi")
    if pillars is not None:
        a, b = get(get(pillars, "day"), "stem"), get(get(pillars, "day"), "branch")
        if a is not None and b is not None and day is not None and day != a + b:
            raise ValueError("三传进退与同次四柱日干支不符")
    for name in [
        "calendar_policy",
        "emptiness_evidence",
        "branch_relations",
        "transmission_relations",
    ]:
        own = get(
            get(board, name),
            "effective_day_ganzhi" if name == "calendar_policy" else "day_ganzhi",
        )
        if day is not None and own is not None and day != own:
            raise ValueError("三传进退日干支与本课其他依据不符")
    branches = get(evidence, "branches")
    flags = get(evidence, "branch_xun_kong")
    trans = get(board, "three_transmissions")
    for i, name in enumerate(["initial", "middle", "final"]):
        item = get(trans, name)
        branch, empty = get(item, "branch"), get(item, "xun_kong")
        if branches is not None and branch is not None and branches[i] != branch:
            raise ValueError("三传进退支序与本课三传不符")
        if flags is not None and empty is not None and flags[i] != empty:
            raise ValueError("三传进退本空与本课三传不符")


def require_complete_progression(board: dict[str, Any]) -> None:
    from .metaphysics.liureng_progression import (
        progression_trace,
        transmission_progression,
    )

    value = board.get("transmission_progression")
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("branches"), list)
        or value.get("day_ganzhi") is None
    ):
        raise ValueError("完整六壬输出缺少三传进退依据")
    expected = transmission_progression(value["day_ganzhi"], value["branches"])
    if value != expected:
        raise ValueError("完整三传进退依据缺项或与同次计算不符")
    align_progression(board)
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.transmission_progression"
    ]
    if traces != [progression_trace(expected)]:
        raise ValueError("三传进退轨迹缺项、重复或与依据不符")
