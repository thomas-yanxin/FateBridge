"""Typed branch-star facts, same-board anchors and complete-service guards."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_comparison import compare_present
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.jinkou.patterns import (
    MONTH_STAR_TARGETS as MONTH_TARGETS,
)
from fatebridge.core.metaphysics.jinkou.patterns import MONTHS_ORDER as MONTHS
from fatebridge.core.metaphysics.jinkou.patterns import TIANSHE_TARGETS, branch_stars
from fatebridge.utils.data import EARTHLY_BRANCHES as BRANCHES

POSITIONS = ("贵神", "将神", "地分")

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Position = Literal["贵神", "将神", "地分"]


class JinkouBranchStarCheck(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: Literal["tianxi", "tianma", "yima", "sangche", "sangmen", "diaoke", "tianshe"]
    name: str
    category: Literal["month_building", "year_branch", "season_and_day"]
    target_kind: Literal["branch", "day_ganzhi"]
    target: str
    matched_positions: list[Position]
    matched_day: StrictBool | None
    original_pdf_page: Literal[118, 119, 120] | None = None

    @model_validator(mode="after")
    def whole_item(self) -> JinkouBranchStarCheck:
        day = self.id == "tianshe"
        if (
            self.target_kind != ("day_ganzhi" if day else "branch")
            or (day and (self.matched_positions or type(self.matched_day) is not bool))
            or (not day and self.matched_day is not None)
            or self.matched_positions
            != [p for p in POSITIONS if p in self.matched_positions]
        ):
            raise ValueError("京本神煞条目的目标、匹配范围或位置重复不一致")
        # Independent of an omitted projection context, target roles and labels
        # are fixed by the published entry. No calendar is inferred here.
        names = dict(
            zip(
                ("tianxi", "tianma", "yima", "sangche", "sangmen", "diaoke", "tianshe"),
                ("天喜", "天马", "驿马", "丧车", "丧门", "吊客", "天赦"),
            )
        )
        category = (
            "season_and_day"
            if day
            else "year_branch" if self.id in {"sangmen", "diaoke"} else "month_building"
        )
        page = (
            118
            if self.id in {"tianxi", "tianshe"}
            else 119 if self.id in {"tianma", "yima"} else 120
        )
        if (
            self.name != names[self.id]
            or self.category != category
            or (self.original_pdf_page is not None and self.original_pdf_page != page)
        ):
            raise ValueError("京本神煞条目的名称、来源页或锚点类别不一致")

        if (day and self.target not in SEXAGENARY_INDEX) or (
            not day and (len(self.target) != 1 or self.target not in BRANCHES)
        ):
            raise ValueError("京本神煞目标需要有效支或完整日干支")
        allowed = (
            set(TIANSHE_TARGETS)
            if day
            else (
                set(MONTH_TARGETS[self.id])
                if self.id in MONTH_TARGETS
                else set(BRANCHES)
            )
        )
        if self.target not in allowed:
            raise ValueError("京本所选条目不存在该目标")
        return self


class JinkouBranchStars(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_branch_stars_v1"] | None = None
    original_pdf_pages: list[int] | None = None
    year_branch: Branch | None = None
    month_building_branch: Branch | None = None
    day_ganzhi: str | None = None
    nominal_month: int | None = None
    season_partition: Literal["春", "夏", "秋", "冬"] | None = None
    month_profile: Literal["declared_term_month_ordinal_v1"] | None = None
    input_branches: dict[Position, Branch] | None = None
    checks: list[JinkouBranchStarCheck] | None = None
    yima_anchor: Literal["month_building_branch"] | None = None
    comprehensive_effect: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_false_certification(cls, v: object) -> bool | None:
        return v if v is None or type(v) is bool else False

    @model_validator(mode="after")
    def compatible_facts(self) -> JinkouBranchStars:

        if self.day_ganzhi is not None and self.day_ganzhi not in SEXAGENARY_INDEX:
            raise ValueError("神煞日序须为有效六十甲子")
        if self.month_building_branch is not None:
            i = MONTHS.index(self.month_building_branch)
            if self.nominal_month is not None and self.nominal_month != i + 1:
                raise ValueError("神煞名义月序须对应实际月建")
            if (
                self.season_partition is not None
                and self.season_partition != "春夏秋冬"[i // 3]
            ):
                raise ValueError("本节四季按三个月序分组，不借用土旺月五态分组")
        if self.checks is not None:
            if [c.id for c in self.checks] != [
                "tianxi",
                "tianma",
                "yima",
                "sangche",
                "sangmen",
                "diaoke",
                "tianshe",
            ]:
                raise ValueError("京本所选七项神煞须完整有序")
            for c in self.checks:
                if c.target_kind == "branch" and self.input_branches is not None:
                    for p, b in self.input_branches.items():
                        if (p in c.matched_positions) != (b == c.target):
                            raise ValueError("神煞匹配位置与实际本支不一致")
                if (
                    c.target_kind == "day_ganzhi"
                    and self.day_ganzhi is not None
                    and c.matched_day != (self.day_ganzhi == c.target)
                ):
                    raise ValueError("天赦须与实际占日完整干支核对")
        if (
            self.year_branch is not None
            and self.month_building_branch is not None
            and self.day_ganzhi is not None
            and self.input_branches is not None
            and set(self.input_branches) == set(POSITIONS)
        ):
            inputs: dict[str, str] = {}
            for position, branch in self.input_branches.items():
                inputs[position] = branch
            expected = branch_stars(
                year_branch=self.year_branch,
                month_branch=self.month_building_branch,
                day_ganzhi=self.day_ganzhi,
                input_branches=inputs,
            )
            compare_present(self.model_dump(exclude_unset=True), expected)
        return self


def align_branch_stars(board: dict[str, Any]) -> None:
    value = board.get("branch_stars")
    if not isinstance(value, dict):
        return
    for row in board.get("rows") or []:
        p = row.get("label")
        inputs = value.get("input_branches") or {}
        if p in inputs and "content" in row and inputs[p] != row["content"]:
            raise ValueError("京本神煞须使用同课贵神、将神、地分本支")


def require_complete_branch_stars(board: dict[str, Any]) -> None:
    value = board.get("branch_stars")
    if not isinstance(value, dict):
        raise ValueError("完整金口诀须保留京本神煞定位依据")
    JinkouBranchStars.model_validate(value)
    try:
        expected = branch_stars(
            year_branch=value["year_branch"],
            month_branch=value["month_building_branch"],
            day_ganzhi=value["day_ganzhi"],
            input_branches=value["input_branches"],
        )
    except KeyError as exc:
        raise ValueError("完整京本神煞定位缺少同次输入") from exc
    if value != expected:
        raise ValueError("完整京本神煞定位须保留全部计算事实")
    align_branch_stars(board)
