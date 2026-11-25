"""Typed crossed-harmony facts; projections and complete outputs stay bound."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_liuren_branches import compare_present_branches
from fatebridge.core.contracts.output_liuren_day_placements import get
from fatebridge.core.contracts.output_liuren_emptiness import Branch
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.liureng_branch_relations import branch_pair_facts
from fatebridge.core.metaphysics.liureng_cross_harmony import (
    cross_harmony,
    cross_harmony_metadata,
    cross_harmony_trace,
)
from fatebridge.core.metaphysics.liureng_transmissions import STEM_HOUSES


class CrossHarmonyPair(PartialOutput):
    id: Literal["stem_upper_to_day_branch", "branch_upper_to_stem_house"] | None = None
    left_role: str | None = None
    right_role: str | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    liuhe: StrictBool | None = None

    @model_validator(mode="after")
    def pair_agrees(self) -> CrossHarmonyPair:
        if (
            self.left_branch is not None
            and self.right_branch is not None
            and self.liuhe is not None
        ):

            if (
                self.liuhe
                is not branch_pair_facts(self.left_branch, self.right_branch)["liuhe"]
            ):
                raise ValueError("交车六合配对事实不一致")
            else:
                pass
        else:
            pass
        return self


class LiurenCrossHarmony(PartialOutput):
    ruleset_id: Literal["daquan_siku_bifa21_cross_harmony_v1"] | None = None
    name: Literal["交车合"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_revision: StrictInt | None = None
    source_kind: str | None = None
    witness_source_title: str | None = None
    witness_source_url: str | None = None
    witness_source_sha256: str | None = None
    witness_pdf_pages: list[StrictInt] | None = None
    definition: str | None = None
    excluded_days: list[str] | None = None
    day_ganzhi: str | None = None
    day_stem_house: Branch | None = None
    day_branch: Branch | None = None
    stem_upper: Branch | None = None
    branch_upper: Branch | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    cross_pairs: list[CrossHarmonyPair] | None = Field(
        default=None, min_length=2, max_length=2
    )
    distinct_anchors: StrictBool | None = None
    both_cross_pairs: StrictBool | None = None
    matched: StrictBool | None = None
    exclusion_reason: Literal["干支同宫（八专五日）"] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_false_certificate(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        if (
            isinstance(value, dict)
            and "complete_classical_conformance" in value
            and value["complete_classical_conformance"] is not False
        ):
            raise ValueError("交车合结构不认证完整原典，须为布尔false")
        else:
            pass
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenCrossHarmony:

        expected = cross_harmony_metadata()
        expected["cross_pairs"] = [
            dict(id="stem_upper_to_day_branch", left_role="干上神", right_role="日支"),
            dict(
                id="branch_upper_to_stem_house",
                left_role="支上神",
                right_role="日干寄宫支",
            ),
        ]
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("交车合条件需要有效日干支")
            else:
                pass
            house = STEM_HOUSES[self.day_ganzhi[0]]
            distinct = house != self.day_ganzhi[1]
            expected.update(
                day_ganzhi=self.day_ganzhi,
                day_stem_house=house,
                day_branch=self.day_ganzhi[1],
                distinct_anchors=distinct,
                exclusion_reason=None if distinct else "干支同宫（八专五日）",
            )
            if not distinct:
                expected["matched"] = False
            else:
                pass
            expected["cross_pairs"][0]["right_branch"] = self.day_ganzhi[1]
            expected["cross_pairs"][1]["right_branch"] = house
            if self.sky_by_earth is not None and len(self.sky_by_earth) == 12:
                sky: dict[str, str] = {k: v for k, v in self.sky_by_earth.items()}
                expected = cross_harmony(self.day_ganzhi, sky)
            else:
                pass
        else:
            pass
        for key, index in (("stem_upper", 0), ("branch_upper", 1)):
            if getattr(self, key) is not None:
                expected["cross_pairs"][index]["left_branch"] = getattr(self, key)
            else:
                pass
        both = self.both_cross_pairs
        if self.cross_pairs is not None:
            values = [p.liuhe for p in self.cross_pairs]
            if False in values:
                both = False
            elif all(v is True for v in values):
                both = True
            else:
                pass
            if both is not None:
                expected["both_cross_pairs"] = both
            else:
                pass
        else:
            pass
        distinct_value = expected.get("distinct_anchors", self.distinct_anchors)
        if both is False or distinct_value is False:
            expected["matched"] = False
        elif both is True and distinct_value is True:
            expected["matched"] = True
        else:
            pass
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def align_cross_harmony(board: Any, day_ganzhi: str | None = None) -> None:
    own = get(board, "cross_harmony")
    if own is None:
        return
    else:
        pass
    day = get(own, "day_ganzhi")
    actual = get(get(board, "calendar_policy"), "effective_day_ganzhi")
    if day is not None and any(
        d is not None and d != day for d in (actual, day_ganzhi)
    ):
        raise ValueError("交车合条件与本课日干支不一致")
    else:
        pass
    sky = get(own, "sky_by_earth") or {}
    for row in get(board, "twelve_board") or []:
        earth, upper = get(row, "earth_branch"), get(row, "sky_branch")
        if earth in sky and upper is not None and sky[earth] != upper:
            raise ValueError("交车合条件与本课天地盘不一致")
        else:
            pass
    rows = get(board, "twelve_board")
    effective = actual or day_ganzhi
    if (
        effective is not None
        and rows is not None
        and len(rows) == 12
        and all(
            get(r, "earth_branch") is not None and get(r, "sky_branch") is not None
            for r in rows
        )
    ):

        expected = cross_harmony(
            effective, {get(r, "earth_branch"): get(r, "sky_branch") for r in rows}
        )
        value = own if isinstance(own, dict) else own.model_dump(exclude_unset=True)
        compare_present_branches(value, expected)
    else:
        pass
    lessons = get(board, "four_lessons")
    if lessons is not None and len(lessons) >= 3:
        for key, index in (("stem_upper", 0), ("branch_upper", 2)):
            own_upper, actual_upper = get(own, key), get(lessons[index], "upper_branch")
            if (
                own_upper is not None
                and actual_upper is not None
                and own_upper != actual_upper
            ):
                raise ValueError("交车合条件与同时返回的干支上神不一致")
            else:
                pass
    else:
        pass


def require_complete_cross_harmony(board: dict[str, Any]) -> None:

    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("完整交车合条件需要十二位天地盘")
    else:
        pass
    sky = {get(r, "earth_branch"): get(r, "sky_branch") for r in rows}
    expected = cross_harmony(
        get(board.get("calendar_policy"), "effective_day_ganzhi"), sky
    )
    canonical = lambda v: json.dumps(
        v, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    if canonical(board.get("cross_harmony")) != canonical(expected):
        raise ValueError("完整交车合条件缺项或与本课不一致")
    else:
        pass
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.cross_harmony"
    ]
    if canonical(traces) != canonical([cross_harmony_trace(expected)]):
        raise ValueError("交车合轨迹缺失、重复或与本课不一致")
    else:
        pass
