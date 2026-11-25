"""Partial-safe branch geometry, screening and same-receipt references."""

from typing import Any, Literal, Mapping

from pydantic import Field, model_validator

from fatebridge.core.branch_candidates import (
    KNOWN_SCREEN_METHODS,
    ORDER,
    geometric_candidates,
)
from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_classical_passage import Pillar
from fatebridge.core.punishment_resolution import (
    CURRENT_STRENGTH_METHODS as CURRENT_PUNISHMENT_METHODS,
)
from fatebridge.core.punishment_resolution import (
    MONTH_OFFICER_CLASH_RESOLVED,
    MONTH_OFFICER_SOURCE,
    REPEATED_PAIR_SOURCE,
    REPETITION_NO_PUNISHMENT,
    repeated_zi_mao_participants,
    zi_month_officer_clash_alternative,
)

Kind = Literal["三会", "三合", "六合", "半合"]
Target = Literal["木", "火", "土", "金", "水"]
Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Decision = Literal[
    "recorded_event",
    "outside_current_adjacency",
    "contained_in_complete_bureau",
    "suppressed_before_half_evaluation",
    "unclassified_unrecorded",
    "not_assessed",
]


def _identity(value: str) -> tuple[str, str, list[str]]:
    parts = value.split(":")
    if (
        len(parts) != 4
        or parts[0] != "bc1"
        or parts[1] not in {"三会", "三合", "六合", "半合"}
        or parts[2] not in {"木", "火", "土", "金", "水"}
    ):
        raise ValueError("候选标识须保留关系种类、目标与实际柱位")
    seats = parts[3].split("-")
    if (
        any(p not in ORDER for p in seats)
        or seats != [p for p in ORDER if p in seats]
        or not 2 <= len(seats) <= 4
    ):
        raise ValueError("候选柱位须有序且不重复")
    if parts[1] in {"六合", "半合"} and len(seats) != 2:
        raise ValueError("二支候选必须恰有两个物理柱位")
    if parts[1] in {"三会", "三合"} and len(seats) < 3:
        raise ValueError("完整三支候选至少有三个物理柱位")
    return parts[1], parts[2], seats


class BranchCombinationCandidate(PartialOutput):
    id: str | None = None
    kind: Kind | None = None
    target: Target | None = None
    positions: list[Pillar] | None = None
    branches: list[Branch] | None = None
    screen_decision: Decision | None = None
    actual_event_refs: list[str] | None = None
    current_statuses: list[str] | None = None
    claimed_blockers: list[Pillar] | None = None
    clashed_blockers: list[Pillar] | None = None
    contained_in_complete_candidate_ids: list[str] | None = None

    def known_identity(
        self,
    ) -> tuple[str | None, str | None, list[str] | None]:
        return (
            _identity(self.id)
            if self.id is not None
            else (
                self.kind,
                self.target,
                list(self.positions) if self.positions is not None else None,
            )
        )

    @model_validator(mode="after")
    def preserve_physical_identity(self) -> "BranchCombinationCandidate":
        kind, target, seats = self.known_identity()
        if self.id is not None:
            for supplied, derived in (
                (self.kind, kind),
                (self.target, target),
                (self.positions, seats),
            ):
                if supplied is not None and supplied != derived:
                    raise ValueError("候选标识不能与已给的关系种类、目标或柱位矛盾")
        if seats is not None:
            if seats != [p for p in ORDER if p in seats] or len(set(seats)) != len(
                seats
            ):
                raise ValueError("候选柱位须有序且不重复")
            if self.branches is not None and len(self.branches) != len(seats):
                raise ValueError("候选支须逐位对应物理柱位")
            for blockers in (self.claimed_blockers, self.clashed_blockers):
                if blockers is not None and blockers != [
                    p for p in seats if p in blockers
                ]:
                    raise ValueError("筛选阻位只能来自候选自身的有序柱位")
        if self.actual_event_refs is not None:
            if len(set(self.actual_event_refs)) != len(self.actual_event_refs):
                raise ValueError("候选不能重复引用同一实际事件")
            for ref in self.actual_event_refs:
                if (
                    not ref.startswith("assessment.relations:")
                    or not ref.removeprefix("assessment.relations:").isdigit()
                ):
                    raise ValueError("候选事件引用须指向同次实际关系序号")
            if self.current_statuses is not None and len(self.current_statuses) != len(
                self.actual_event_refs
            ):
                raise ValueError("候选状态须逐项对应实际事件")
            if self.screen_decision == "recorded_event" and not self.actual_event_refs:
                raise ValueError("没有实际事件不能标为已有事件")
            if (
                self.screen_decision not in {None, "recorded_event"}
                and self.actual_event_refs
            ):
                raise ValueError("已有实际事件不能被写成未记录候选")
        return self


class BranchCombinationCandidates(PartialOutput):
    method_id: Literal["branch_combination_candidate_inventory_v1"] | None = None
    strength_method_id: str | None = None
    effects_status: Literal["supplied", "not_supplied"] | None = None
    source_relation_count: int | None = Field(default=None, ge=0)
    screen_status: Literal["reconstructed_v8", "not_identified"] | None = None
    pre_half_claimed_positions: list[Pillar] | None = None
    pre_half_clashed_positions: list[Pillar] | None = None
    branches_by_position: Mapping[Pillar, Branch] | None = None
    candidates: list[BranchCombinationCandidate] | None = None
    effective_combination: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None
    scope: str | None = None

    def known_branches(self) -> dict[str, str]:
        return {str(p): str(b) for p, b in (self.branches_by_position or {}).items()}

    @model_validator(mode="after")
    def preserve_catalogue_and_known_screen(self) -> "BranchCombinationCandidates":
        if (
            self.screen_status == "reconstructed_v8"
            and self.strength_method_id is not None
            and self.strength_method_id not in KNOWN_SCREEN_METHODS
        ):
            raise ValueError("未知旺衰方法不能沿用v8筛选状态")
        sets = (self.pre_half_claimed_positions, self.pre_half_clashed_positions)
        for stage_positions in sets:
            if stage_positions is not None and stage_positions != [
                p for p in ORDER if p in stage_positions
            ]:
                raise ValueError("筛选柱位须有序且不重复")
        if self.effects_status == "not_supplied" and (
            self.source_relation_count is not None or any(s is not None for s in sets)
        ):
            raise ValueError("未给关系回执不能伪作已核对筛选")
        if self.screen_status == "not_identified" and any(s is not None for s in sets):
            raise ValueError("未识别筛选方法不能宣称已知阻位")
        rows = self.candidates or []
        ids = [r.id for r in rows if r.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("同一候选不能重复列入")
        shapes = None
        if self.branches_by_position is not None and all(
            p in self.branches_by_position for p in ORDER
        ):
            shapes = geometric_candidates(self.known_branches())
            if self.candidates is not None and all(r.id is not None for r in rows):
                if ids != [s["id"] for s in shapes]:
                    raise ValueError("完整四支候选清单不能遗漏被筛掉的候选或改变顺序")
        for row in rows:
            kind, target, seats = row.known_identity()
            if (
                seats is not None
                and self.branches_by_position is not None
                and row.branches is not None
            ):
                for p, branch in zip(seats, row.branches):
                    if (
                        p in self.branches_by_position
                        and self.known_branches()[p] != branch
                    ):
                        raise ValueError("候选支与同次四支不符")
            if (
                shapes is not None
                and kind is not None
                and target is not None
                and seats is not None
            ):
                shape = next(
                    (
                        s
                        for s in shapes
                        if (s["kind"], s["target"], s["positions"])
                        == (kind, target, seats)
                    ),
                    None,
                )
                if (
                    shape is None
                    or row.branches is not None
                    and row.branches != shape["branches"]
                ):
                    raise ValueError("候选必须符合已给四支的字面图形")
                if row.contained_in_complete_candidate_ids is not None:
                    expected = [
                        s["id"]
                        for s in shapes
                        if s["kind"] in {"三会", "三合"}
                        and kind in {"六合", "半合"}
                        and set(seats) <= set(s["positions"])
                    ]
                    if row.contained_in_complete_candidate_ids != expected:
                        raise ValueError("完整局包含关系必须保留全部物理候选")
            if seats is not None:
                for supplied, stage in (
                    (row.claimed_blockers, self.pre_half_claimed_positions),
                    (row.clashed_blockers, self.pre_half_clashed_positions),
                ):
                    if (
                        supplied is not None
                        and stage is not None
                        and supplied
                        != ([p for p in seats if p in stage] if kind == "半合" else [])
                    ):
                        raise ValueError("候选阻位必须忠于半合筛选前的同次位置")
            if self.effects_status == "not_supplied" and (
                row.actual_event_refs is not None or row.current_statuses is not None
            ):
                raise ValueError("未给关系回执不能伪作已核对无实际事件")
            if self.screen_status == "not_identified" and (
                row.claimed_blockers is not None or row.clashed_blockers is not None
            ):
                raise ValueError("未知筛选不能伪作无阻位")
            if (
                self.screen_status == "reconstructed_v8"
                and row.actual_event_refs == []
                and seats is not None
            ):
                if (
                    kind == "六合"
                    and abs(ORDER.index(seats[0]) - ORDER.index(seats[1])) != 1
                ):
                    expected_decision = "outside_current_adjacency"
                elif kind == "六合" and row.contained_in_complete_candidate_ids:
                    expected_decision = "contained_in_complete_bureau"
                elif kind == "半合" and (
                    row.claimed_blockers
                    or row.clashed_blockers
                    or set(seats) & set(self.pre_half_claimed_positions or [])
                    or set(seats) & set(self.pre_half_clashed_positions or [])
                ):
                    expected_decision = "suppressed_before_half_evaluation"
                else:
                    expected_decision = None
                if expected_decision is not None and row.screen_decision not in {
                    None,
                    expected_decision,
                }:
                    raise ValueError("筛选说明不能背离已知邻接、包含或阻位条件")
        return self


def validate_effect_links(
    inventory: BranchCombinationCandidates, relations: list[Any]
) -> None:
    """Compare co-known receipts; never manufacture a missing event or field."""
    validate_punishment_resolution(
        inventory.strength_method_id, relations, inventory.known_branches()
    )
    if inventory.effects_status == "not_supplied":
        raise ValueError("已有实际关系不能声称未给回执")
    if (
        inventory.source_relation_count is not None
        and inventory.source_relation_count != len(relations)
    ):
        raise ValueError("候选清单的来源数量必须忠于同次关系")
    for row in inventory.candidates or []:
        kind, target, seats = row.known_identity()
        if (
            kind is not None
            and target is not None
            and seats is not None
            and all(
                isinstance(e, dict)
                and "kind" in e
                and (
                    e["kind"] != kind
                    or all(k in e for k in ("positions", "target", "status"))
                )
                for e in relations
            )
        ):
            matching = [
                i
                for i, e in enumerate(relations)
                if e["kind"] == kind
                and (e["target"], e["positions"]) == (target, seats)
            ]
            if row.actual_event_refs is not None and row.actual_event_refs != [
                f"assessment.relations:{i}" for i in matching
            ]:
                raise ValueError("候选引用不能遗漏或替换同次实际事件")
            if row.current_statuses is not None and row.current_statuses != [
                relations[i]["status"] for i in matching
            ]:
                raise ValueError("候选状态必须忠于同次实际关系")
    if all(
        isinstance(e, dict) and all(k in e for k in ("kind", "status", "positions"))
        for e in relations
    ):
        claimed = {
            p
            for e in relations
            if e["kind"] in {"三会", "三合", "六合"}
            and e["status"] in {"binding", "conditioned_transformation"}
            for p in e["positions"]
        }
        clashed = {
            p
            for e in relations
            if e["kind"] == "六冲" and e["status"] == "active"
            for p in e["positions"]
        }
        if inventory.screen_status == "reconstructed_v8":
            for supplied, actual in (
                (inventory.pre_half_claimed_positions, claimed),
                (inventory.pre_half_clashed_positions, clashed),
            ):
                if supplied is not None and supplied != [
                    p for p in ORDER if p in actual
                ]:
                    raise ValueError("候选筛选前位置必须忠于同次完整关系回执")


def physical_branch_mapping(rows: list[Any]) -> dict[str, str]:
    """Read co-known physical branch facts without inventing missing pillars."""
    branches: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        p, branch = row.get("pillar"), row.get("branch")
        if p in ORDER and isinstance(branch, str):
            if p in branches and branches[p] != branch:
                raise ValueError("同次物理根账本不能为同柱给出不同支")
            branches[p] = branch
    return branches


def validate_punishment_resolution(
    method: str | None,
    relations: list[Any],
    branches: Mapping[str, str] | None = None,
) -> None:
    """Check co-known covering combinations even without a candidate sidecar."""
    if method not in CURRENT_PUNISHMENT_METHODS:
        return
    cover = set()
    for event in relations:
        if not isinstance(event, dict) or "kind" not in event:
            return
        if event["kind"] not in {"三会", "三合", "六合"}:
            continue
        status = event.get("status")
        if status in {"binding", "conditioned_transformation"}:
            if not isinstance(event.get("positions"), list):
                return
            cover.update(event["positions"])
        elif status not in {"contested_or_clashed", "same_target_affiliation_only"}:
            return
    complete_branches = branches is not None and all(p in branches for p in ORDER)
    physical_pair = (
        [p for p in ORDER if branches[p] in {"子", "卯"}]
        if complete_branches and branches is not None
        else None
    )
    repeated = (
        repeated_zi_mao_participants(physical_pair, branches, cover)
        if physical_pair is not None and branches is not None
        else None
    )
    clashes_known = all(
        event.get("kind") != "六冲"
        or (
            event.get("status") is not None and isinstance(event.get("positions"), list)
        )
        for event in relations
    )
    active_clashes = [
        event["positions"]
        for event in relations
        if event.get("kind") == "六冲"
        and event.get("status") == "active"
        and isinstance(event.get("positions"), list)
    ]
    for event in relations:
        if event.get("kind") != "刑" or not isinstance(event.get("positions"), list):
            continue
        seats, status = event["positions"], event.get("status")
        if status == MONTH_OFFICER_CLASH_RESOLVED:
            for key, expected in (
                ("source_id", MONTH_OFFICER_SOURCE["id"]),
                ("source_day_stem", "丙"),
                ("protected_position", "month"),
                ("alternative_kind", "六冲"),
            ):
                if key in event and event[key] != expected:
                    raise ValueError("月官别位冲解刑须保留丙子源角色与实际替代关系")
            if physical_pair is not None and branches is not None and clashes_known:
                alternative = zi_month_officer_clash_alternative(
                    seats, branches, cover, active_clashes, day_stem="丙"
                )
                if alternative is None or seats != physical_pair:
                    raise ValueError("月官别位冲解刑须有唯一子卯酉与同次活动卯酉冲")
                if (
                    "alternative_positions" in event
                    and event["alternative_positions"] != alternative
                ):
                    raise ValueError("解刑替代位置须忠于同次实际活动冲")
            continue
        if repeated is not None and physical_pair is not None:
            expected_status = "active" if repeated else REPETITION_NO_PUNISHMENT
            expected_positions = repeated or physical_pair
            if status != expected_status or seats != expected_positions:
                raise ValueError("一子二卯须按同次会合后的实体数与实际余对裁定刑")
            expected_removed = [p for p in physical_pair if p in cover]
            for key, expected in (
                ("source_positions", physical_pair),
                ("combination_removed_positions", expected_removed),
                ("source_id", REPEATED_PAIR_SOURCE["id"]),
            ):
                if key in event and event[key] != expected:
                    raise ValueError("子卯重见来源实体须忠于同次物理支与已成会合")
            continue
        if status == REPETITION_NO_PUNISHMENT and physical_pair is not None:
            raise ValueError("一子二卯原文规则不能外推其他实体数")
        full_cover = all(p in cover for p in seats)
        unique_pair = None
        if physical_pair is not None and branches is not None:
            unique_pair = (
                len(physical_pair) == 2
                and {branches[p] for p in physical_pair} == {"子", "卯"}
                and seats == physical_pair
            )
        expected_resolved = full_cover or bool(
            unique_pair and any(p in cover for p in seats)
        )
        impossible = not any(p in cover for p in seats) or (
            not full_cover and (len(seats) != 2 or unique_pair is False)
        )
        if status == "resolved_by_combination" and impossible:
            raise ValueError("当前解刑须有实际会合覆盖；单端条件只适用唯一实体子卯对")
        if status == "active" and expected_resolved:
            raise ValueError("当前算法不能遗漏同次成立会合对唯一子卯对的解刑条件")
