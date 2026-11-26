"""Same-board evidence for selected 探原 empty/nonempty clauses."""

from typing import Any, Literal

from pydantic import StrictBool, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.common import (
    SEXAGENARY_INDEX,
    kongwang_for_ganzhi,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.liureng_emptiness import (
    apply_year_fate_emptiness,
    emptiness_evidence,
)
from fatebridge.core.metaphysics.liureng_transmissions import STEM_HOUSES
from fatebridge.utils.data import EARTHLY_BRANCHES

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
AuthorityRole = Literal["太岁", "月建", "月将"]


class LiurenEmptyRow(PartialOutput):
    earth_branch: Branch
    sky_branch: Branch
    sky_xun_kong: StrictBool
    earth_xun_kong: StrictBool
    earth_is_day_stem_house: StrictBool
    earth_stem_house_exception: StrictBool
    sky_authority_roles: list[AuthorityRole]
    sky_authority_xunkong_exception: StrictBool
    earth_year_fate_roles: list[Literal["natal", "annual"]] | None = None
    earth_year_fate_xunkong_exception: StrictBool | None = None
    earth_xunkong_after_seat_and_year_fate: StrictBool | None = None
    effective_empty: None = None

    @model_validator(mode="after")
    def seat_exception_is_local(self) -> "LiurenEmptyRow":
        if self.earth_stem_house_exception != (
            self.earth_xun_kong and self.earth_is_day_stem_house
        ):
            raise ValueError("地盘日干寄宫空亡例外的条件不一致")
        return self


class LiurenEmptyRole(PartialOutput):
    role: AuthorityRole
    branch: Branch
    branch_xun_kong: StrictBool
    xunkong_exception_applies: StrictBool


class LiurenYearFateEarthBranches(PartialOutput):
    natal: Branch | None = None
    annual: Branch | None = None


class LiurenEmptinessEvidence(PartialOutput):
    ruleset_id: Literal["liuren_tanyuan_empty_scope_v3"] | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_title: str | None = None
    original_pdf_pages: list[int] | None = None
    year_fate_placement_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    xun_head: str | None = None
    empty_branches: list[Branch] | None = None
    day_stem_house: Branch | None = None
    year_branch: Branch | None = None
    month_building_branch: Branch | None = None
    month_general_branch: Branch | None = None
    hour_branch: Branch | None = None
    hour_branch_xun_kong: StrictBool | None = None
    role_conditions: list[LiurenEmptyRole] | None = None
    rows: list[LiurenEmptyRow] | None = None
    year_fate_earth_branches: LiurenYearFateEarthBranches | None = None
    nianming_status: Literal["calculated", "partial", "inputs_not_available"] | None = (
        None
    )
    seasonal_true_half_empty_status: Literal["not_adjudicated"] | None = None
    filling_clashing_status: Literal["role_exceptions_only"] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def empty_facts_match_context(self) -> "LiurenEmptinessEvidence":

        if self.rows is not None and [r.earth_branch for r in self.rows] != list(
            EARTHLY_BRANCHES
        ):
            raise ValueError("六壬空亡依据必须保留十二地盘位，不得删减或调序")
        if self.rows is not None and {r.sky_branch for r in self.rows} != set(
            EARTHLY_BRANCHES
        ):
            raise ValueError("六壬空亡依据的天盘须含十二个不同支位")
        if self.role_conditions is not None and [
            r.role for r in self.role_conditions
        ] != ["太岁", "月建", "月将"]:
            raise ValueError("六壬空亡角色条件不得删减、合并或调序")
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("六壬空亡依据需要有效日干支")
            empty = kongwang_for_ganzhi(self.day_ganzhi)[:2]
            if self.xun_head is not None and self.xun_head != xun_head_for_ganzhi(
                self.day_ganzhi
            ):
                raise ValueError("六壬空亡旬首与占日不一致")
            if self.empty_branches is not None and self.empty_branches != list(empty):
                raise ValueError("六壬空亡两支与占日不一致")
            house = STEM_HOUSES[self.day_ganzhi[0]]
            if self.day_stem_house is not None and self.day_stem_house != house:
                raise ValueError("六壬空亡依据的日干寄宫不一致")
            for row in self.rows or []:
                if (
                    row.sky_xun_kong != (row.sky_branch in empty)
                    or row.earth_xun_kong != (row.earth_branch in empty)
                    or row.earth_is_day_stem_house != (row.earth_branch == house)
                ):
                    raise ValueError("天盘本空、地盘本空或日干地盘位与占日不一致")
            for role in self.role_conditions or []:
                if role.branch_xun_kong != (role.branch in empty):
                    raise ValueError("六壬空亡角色的本空事实与占日不一致")
            if (
                self.hour_branch is not None
                and self.hour_branch_xun_kong is not None
                and self.hour_branch_xun_kong != (self.hour_branch in empty)
            ):
                raise ValueError("六壬占时本空与占日旬空不一致")
        role_branches = {
            "太岁": self.year_branch,
            "月建": self.month_building_branch,
            "月将": self.month_general_branch,
        }
        for role in self.role_conditions or []:
            branch = role_branches[role.role]
            if branch is not None and role.branch != branch:
                raise ValueError("六壬空亡角色支位与本次依据不一致")
        if all(
            v is not None
            for v in (
                self.day_ganzhi,
                self.year_branch,
                self.month_building_branch,
                self.month_general_branch,
                self.hour_branch,
                self.rows,
            )
        ):
            assert self.day_ganzhi is not None
            assert self.year_branch is not None
            assert self.month_building_branch is not None
            assert self.month_general_branch is not None
            assert self.hour_branch is not None
            expected = emptiness_evidence(
                day_ganzhi=self.day_ganzhi,
                year_branch=self.year_branch,
                month_branch=self.month_building_branch,
                month_general_branch=self.month_general_branch,
                hour_branch=self.hour_branch,
                sky_by_earth={r.earth_branch: r.sky_branch for r in self.rows or []},
            )
            placements = self.year_fate_earth_branches
            if (
                placements is not None
                and {"natal", "annual"} <= placements.model_fields_set
            ):
                apply_year_fate_emptiness(
                    expected, natal=placements.natal, annual=placements.annual
                )
            else:
                # A projection can select rows without selecting the two placement inputs.
                for key in ("year_fate_earth_branches", "nianming_status"):
                    expected.pop(key)
                for row in expected["rows"]:
                    for key in (
                        "earth_year_fate_roles",
                        "earth_year_fate_xunkong_exception",
                        "earth_xunkong_after_seat_and_year_fate",
                    ):
                        row.pop(key)
            compare_present_empty(self.model_dump(exclude_unset=True), expected)
        return self


def compare_present_empty(actual: Any, expected: Any) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key, value in actual.items():
            if key in expected:
                compare_present_empty(value, expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("六壬空亡依据队列与本课不一致")
        for left, right in zip(actual, expected):
            compare_present_empty(left, right)
    elif actual != expected:
        raise ValueError("六壬空亡依据与本课四柱、月将或天地盘不一致")


def require_complete_emptiness(
    board: dict[str, Any], *, natal: str | None = None, annual: str | None = None
) -> None:

    evidence = board.get("emptiness_evidence")
    required = (
        "day_ganzhi",
        "year_branch",
        "month_building_branch",
        "month_general_branch",
        "hour_branch",
        "rows",
    )
    if not isinstance(evidence, dict) or any(evidence.get(k) is None for k in required):
        raise ValueError("完整六壬输出缺少空亡计算依据")
    expected = emptiness_evidence(
        day_ganzhi=evidence["day_ganzhi"],
        year_branch=evidence["year_branch"],
        month_branch=evidence["month_building_branch"],
        month_general_branch=evidence["month_general_branch"],
        hour_branch=evidence["hour_branch"],
        sky_by_earth={r["earth_branch"]: r["sky_branch"] for r in evidence["rows"]},
    )
    if natal is not None or annual is not None:
        apply_year_fate_emptiness(expected, natal=natal, annual=annual)
    if evidence != expected:
        raise ValueError("完整六壬输出的空亡依据缺项或与计算条件不一致")
