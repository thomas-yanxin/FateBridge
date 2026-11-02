"""Projection-aware contract and same-board binding for day placements."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches
from .output_liuren_emptiness import Branch

PhaseRelation = Literal[
    "branch_generates_stem",
    "stem_generates_branch",
    "branch_controls_stem",
    "stem_controls_branch",
    "same_element",
]
MatchedRuleId = Literal[
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"
]


class DayPlacementRule(PartialOutput):
    id: str | None = None
    name: str | None = None
    condition: str | None = None
    placement: Literal["stem_over_branch", "branch_over_stem"] | None = None
    relation: PhaseRelation | Literal["harmony_unadjudicated"] | None = None
    definition_adjudicated: StrictBool | None = None
    placement_matches: StrictBool | None = None
    relation_matches: StrictBool | None = None
    matched: StrictBool | None = None


class LiurenDayPlacements(PartialOutput):
    ruleset_id: Literal["tanyuan_day_placements_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    day_ganzhi: str | None = None
    day_stem_house: Branch | None = None
    day_stem_element: Literal["木", "火", "土", "金", "水"] | None = None
    day_branch_element: Literal["木", "火", "土", "金", "水"] | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    placements: (
        dict[Literal["stem_over_branch", "branch_over_stem"], StrictBool] | None
    ) = None
    element_relations: dict[PhaseRelation, StrictBool] | None = None
    evaluations: list[DayPlacementRule] | None = Field(
        default=None, min_length=12, max_length=12
    )
    evaluated_count: StrictInt | None = None
    unresolved_count: StrictInt | None = None
    matched_ids: list[MatchedRuleId] | None = None
    unresolved_ids: list[Literal["D11", "D12"]] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_false_conformance(cls, value: Any) -> Any:
        if isinstance(value, dict) and "complete_classical_conformance" in value:
            if value["complete_classical_conformance"] is not False:
                raise ValueError("干支加临条件不认证完整原典，须为布尔false")
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenDayPlacements:
        from .metaphysics.common import (
            SEXAGENARY_INDEX,
            branch_element_text,
            stem_element_text,
        )
        from .metaphysics.liureng_day_placements import (
            day_placement_patterns,
            placement_metadata,
        )
        from .metaphysics.liureng_transmissions import STEM_HOUSES

        expected = placement_metadata()
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("干支加临需要有效日干支")
            expected.update(
                day_ganzhi=self.day_ganzhi,
                day_stem_house=STEM_HOUSES[self.day_ganzhi[0]],
                day_stem_element=stem_element_text(self.day_ganzhi[0]),
                day_branch_element=branch_element_text(self.day_ganzhi[1]),
            )
            if self.sky_by_earth is not None and len(self.sky_by_earth) == 12:
                sky: dict[str, str] = {k: v for k, v in self.sky_by_earth.items()}
                expected = day_placement_patterns(self.day_ganzhi, sky)
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def align_day_placements(board: Any, day_ganzhi: str | None = None) -> None:
    evidence = get(board, "day_placement_patterns")
    if evidence is None:
        return
    day = get(evidence, "day_ganzhi")
    actual_day = get(get(board, "calendar_policy"), "effective_day_ganzhi")
    if day is not None and actual_day is not None and day != actual_day:
        raise ValueError("干支加临与本课日干支不一致")
    if day is not None and day_ganzhi is not None and day != day_ganzhi:
        raise ValueError("干支加临与同时返回的四柱不一致")
    sky = get(evidence, "sky_by_earth") or {}
    for row in get(board, "twelve_board") or []:
        earth, upper = get(row, "earth_branch"), get(row, "sky_branch")
        if earth in sky and upper is not None and sky[earth] != upper:
            raise ValueError("干支加临与同时返回的天地盘不一致")


def require_complete_day_placements(board: dict[str, Any]) -> None:
    from .metaphysics.liureng_day_placements import (
        day_placement_patterns,
        day_placements_trace,
    )

    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("完整干支加临条件需要十二位天地盘")
    sky = {get(r, "earth_branch"): get(r, "sky_branch") for r in rows}
    expected = day_placement_patterns(
        get(board.get("calendar_policy"), "effective_day_ganzhi"), sky
    )
    canonical = lambda v: json.dumps(
        v, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    if canonical(board.get("day_placement_patterns")) != canonical(expected):
        raise ValueError("完整干支加临条件缺项或与本课不一致")
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.day_placement_patterns"
    ]
    if canonical(traces) != canonical([day_placements_trace(expected)]):
        raise ValueError("干支加临轨迹缺失、重复或与本课不一致")
