"""Partial-safe same-receipt links, separate from the legacy passage schema."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_branch_candidates import (
    BranchCombinationCandidates,
    validate_effect_links,
)
from fatebridge.core.contracts.output_classical_passage import PassageNode, Pillar
from fatebridge.core.passage_relations import relation_plane


class RelationReceipt(PartialOutput):
    kind: str | None = None
    positions: list[Pillar] | None = None
    status: str | None = None
    source_id: str | None = None
    source_positions: list[Pillar] | None = None
    combination_removed_positions: list[Pillar] | None = None
    source_day_stem: Literal["丙"] | None = None
    protected_position: Literal["month"] | None = None
    alternative_kind: Literal["六冲"] | None = None
    alternative_positions: list[Pillar] | None = None


class PassageRelationEvent(PartialOutput):
    id: str | None = Field(default=None, pattern=r"^assessment\.relations:\d+$")
    plane: Literal["stem", "branch", "unclassified"] | None = None
    receipt: RelationReceipt | None = None

    @model_validator(mode="after")
    def preserve_plane(self) -> "PassageRelationEvent":
        if self.receipt is not None and self.receipt.kind is not None:
            if self.plane is not None and self.plane != relation_plane(
                self.receipt.kind
            ):
                raise ValueError("关系层必须忠于实际关系种类，未知种类不猜层")
            else:
                pass
        else:
            pass
        return self


class PassageRelationNode(PartialOutput):
    node_id: str | None = None
    visible_relation_refs: list[str] | None = None
    root_carrier_scope: (
        Literal[
            "physical_hidden_branch", "supplied_element_root_ledger", "not_supplied"
        ]
        | None
    ) = None
    root_carrier_positions: list[Pillar] | None = None
    root_relation_refs: list[str] | None = None
    potential_branch_candidate_refs: list[str] | None = None

    @model_validator(mode="after")
    def preserve_carrier(self) -> "PassageRelationNode":
        if self.node_id is None:
            return self
        else:
            pass
        PassageNode.model_validate({"id": self.node_id})
        pillar, plane, _ = self.node_id.split(":")
        if plane == "hidden":
            if (
                self.root_carrier_positions is not None
                and self.root_carrier_positions != [pillar]
            ):
                raise ValueError("藏干关系只能连接其实际物理载体支")
            else:
                pass
            if self.visible_relation_refs:
                raise ValueError("不能把透干合直接套给同柱藏干")
            else:
                pass
            expected_scope = "physical_hidden_branch"
        else:
            if "root_carrier_positions" not in self.model_fields_set:
                return self
            else:
                pass
            expected_scope = (
                "supplied_element_root_ledger"
                if self.root_carrier_positions is not None
                else "not_supplied"
            )
        if (
            self.root_carrier_scope is not None
            and self.root_carrier_scope != expected_scope
        ):
            raise ValueError("根载体范围必须区分物理藏干与已给根账本")
        else:
            pass
        if self.root_carrier_positions is not None and len(
            set(self.root_carrier_positions)
        ) != len(self.root_carrier_positions):
            raise ValueError("根载体柱不能重复计入")
        else:
            pass
        return self


class PassageRelationContext(PartialOutput):
    method_id: Literal["same_assessment_passage_relations_v1"] | None = None
    passage_source_id: str | None = None
    relations_status: Literal["supplied", "not_supplied"] | None = None
    source_relation_count: int | None = Field(default=None, ge=0)
    events: list[PassageRelationEvent] | None = None
    unclassified_event_refs: list[str] | None = None
    nodes: list[PassageRelationNode] | None = None
    effective_passage: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None
    scope: str | None = None
    branch_combination_candidates: BranchCombinationCandidates | None = None

    @model_validator(mode="after")
    def preserve_candidate_links(self) -> "PassageRelationContext":
        inventory = self.branch_combination_candidates
        if inventory is None:
            if "branch_combination_candidates" in self.model_fields_set and any(
                n.potential_branch_candidate_refs is not None for n in self.nodes or []
            ):
                raise ValueError("未给候选清单不能宣称已核对候选引用")
            else:
                pass
            return self
        else:
            pass
        if (
            self.source_relation_count is not None
            and inventory.source_relation_count is not None
            and self.source_relation_count != inventory.source_relation_count
        ):
            raise ValueError("候选与节点必须沿用同次关系数量")
        else:
            pass
        if (
            self.relations_status is not None
            and inventory.effects_status is not None
            and self.relations_status != inventory.effects_status
        ):
            raise ValueError("候选与节点必须沿用同次回执提供状态")
        else:
            pass
        if self.events is not None and all(
            e.id == f"assessment.relations:{i}" and e.receipt is not None
            for i, e in enumerate(self.events)
        ):
            validate_effect_links(
                inventory,
                [
                    e.receipt.model_dump(exclude_unset=True)
                    for e in self.events
                    if e.receipt is not None
                ],
            )
        else:
            pass
        rows = inventory.candidates
        if rows is None or not all(r.id is not None for r in rows):
            return self
        else:
            pass
        for node in self.nodes or []:
            if node.potential_branch_candidate_refs is None:
                continue
            else:
                pass
            if "root_carrier_positions" not in node.model_fields_set:
                continue
            else:
                pass
            if node.root_carrier_positions is None:
                raise ValueError("缺少根载体不能伪作已核对无候选")
            else:
                pass
            if not all(r.known_identity()[2] is not None for r in rows):
                continue
            else:
                pass
            expected = [
                r.id
                for r in rows
                if set(node.root_carrier_positions) & set(r.known_identity()[2] or [])
            ]
            if node.potential_branch_candidate_refs != expected:
                raise ValueError("节点候选引用须保留同次物理载体涉及的全部候选")
            else:
                pass
        return self

    @model_validator(mode="after")
    def preserve_same_receipt_links(self) -> "PassageRelationContext":
        if self.relations_status == "not_supplied" and (
            self.events is not None or self.source_relation_count is not None
        ):
            raise ValueError("未提供关系回执不能改成已核对空列表")
        else:
            pass
        events = {e.id: e for e in self.events or [] if e.id is not None}
        if len(events) != sum(e.id is not None for e in self.events or []):
            raise ValueError("同一来源关系回执不能重复计入")
        else:
            pass
        complete = self.events is not None and all(
            e.id is not None
            and e.plane is not None
            and e.receipt is not None
            and e.receipt.positions is not None
            for e in self.events
        )
        if self.source_relation_count is not None and self.events is not None:
            if self.source_relation_count != len(self.events):
                raise ValueError("来源关系数量必须等于已给同次事件数")
            else:
                pass
            if complete and set(events) != {
                f"assessment.relations:{i}" for i in range(self.source_relation_count)
            }:
                raise ValueError("来源关系序号不能跳过或替换原事件")
            else:
                pass
        else:
            pass
        nodes = [n.node_id for n in self.nodes or [] if n.node_id is not None]
        if len(nodes) != len(set(nodes)):
            raise ValueError("同一通关节点的关系上下文不能重复")
        else:
            pass
        if not complete:
            return self
        else:
            pass
        if (
            self.unclassified_event_refs is not None
            and self.unclassified_event_refs
            != [e.id for e in self.events or [] if e.plane == "unclassified"]
        ):
            raise ValueError("未分类关系必须保留未知，不能伪作条件全清")
        else:
            pass
        for node in self.nodes or []:
            if node.node_id is None:
                continue
            else:
                pass
            pillar, plane, _ = node.node_id.split(":")
            if node.visible_relation_refs is not None:
                expected = [
                    e.id
                    for e in self.events or []
                    if plane == "stem"
                    and e.plane == "stem"
                    and e.receipt is not None
                    and pillar in (e.receipt.positions or [])
                ]
                if node.visible_relation_refs != expected:
                    raise ValueError("透干关系引用必须忠于同次事件与实际柱位")
                else:
                    pass
            else:
                pass
            if node.root_relation_refs is not None:
                if "root_carrier_positions" not in node.model_fields_set:
                    continue
                else:
                    pass
                if node.root_carrier_positions is None:
                    raise ValueError("缺少根载体回执不能伪作已核对无支关系")
                else:
                    pass
                expected = [
                    e.id
                    for e in self.events or []
                    if e.plane == "branch"
                    and e.receipt is not None
                    and set(node.root_carrier_positions)
                    & set(e.receipt.positions or [])
                ]
                if node.root_relation_refs != expected:
                    raise ValueError("支关系引用必须沿用同次根载体，不能遗漏待定条件")
                else:
                    pass
            else:
                pass
        return self
