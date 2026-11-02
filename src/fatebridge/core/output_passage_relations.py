"""Partial-safe same-receipt links, separate from the legacy passage schema."""

from typing import List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_branch_candidates import (
    BranchCombinationCandidates,
    validate_effect_links,
)
from fatebridge.core.output_classical_passage import PassageNode, Pillar
from fatebridge.core.passage_relations import relation_plane


class RelationReceipt(PartialOutput):
    kind: Optional[str] = None
    positions: Optional[List[Pillar]] = None
    status: Optional[str] = None


class PassageRelationEvent(PartialOutput):
    id: Optional[str] = Field(default=None, pattern=r"^assessment\.relations:\d+$")
    plane: Optional[Literal["stem", "branch", "unclassified"]] = None
    receipt: Optional[RelationReceipt] = None

    @model_validator(mode="after")
    def preserve_plane(self) -> "PassageRelationEvent":
        if self.receipt is not None and self.receipt.kind is not None:
            if self.plane is not None and self.plane != relation_plane(
                self.receipt.kind
            ):
                raise ValueError("关系层必须忠于实际关系种类，未知种类不猜层")
        return self


class PassageRelationNode(PartialOutput):
    node_id: Optional[str] = None
    visible_relation_refs: Optional[List[str]] = None
    root_carrier_scope: Optional[
        Literal[
            "physical_hidden_branch", "supplied_element_root_ledger", "not_supplied"
        ]
    ] = None
    root_carrier_positions: Optional[List[Pillar]] = None
    root_relation_refs: Optional[List[str]] = None
    potential_branch_candidate_refs: Optional[List[str]] = None

    @model_validator(mode="after")
    def preserve_carrier(self) -> "PassageRelationNode":
        if self.node_id is None:
            return self
        PassageNode.model_validate({"id": self.node_id})
        pillar, plane, _ = self.node_id.split(":")
        if plane == "hidden":
            if (
                self.root_carrier_positions is not None
                and self.root_carrier_positions != [pillar]
            ):
                raise ValueError("藏干关系只能连接其实际物理载体支")
            if self.visible_relation_refs:
                raise ValueError("不能把透干合直接套给同柱藏干")
            expected_scope = "physical_hidden_branch"
        else:
            if "root_carrier_positions" not in self.model_fields_set:
                return self
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
        if self.root_carrier_positions is not None and len(
            set(self.root_carrier_positions)
        ) != len(self.root_carrier_positions):
            raise ValueError("根载体柱不能重复计入")
        return self


class PassageRelationContext(PartialOutput):
    method_id: Optional[Literal["same_assessment_passage_relations_v1"]] = None
    passage_source_id: Optional[str] = None
    relations_status: Optional[Literal["supplied", "not_supplied"]] = None
    source_relation_count: Optional[int] = Field(default=None, ge=0)
    events: Optional[List[PassageRelationEvent]] = None
    unclassified_event_refs: Optional[List[str]] = None
    nodes: Optional[List[PassageRelationNode]] = None
    effective_passage: Optional[Literal["not_adjudicated"]] = None
    calculation_effect: Optional[Literal["none"]] = None
    scope: Optional[str] = None
    branch_combination_candidates: Optional[BranchCombinationCandidates] = None

    @model_validator(mode="after")
    def preserve_candidate_links(self) -> "PassageRelationContext":
        inventory = self.branch_combination_candidates
        if inventory is None:
            if "branch_combination_candidates" in self.model_fields_set and any(
                n.potential_branch_candidate_refs is not None for n in self.nodes or []
            ):
                raise ValueError("未给候选清单不能宣称已核对候选引用")
            return self
        if (
            self.source_relation_count is not None
            and inventory.source_relation_count is not None
            and self.source_relation_count != inventory.source_relation_count
        ):
            raise ValueError("候选与节点必须沿用同次关系数量")
        if (
            self.relations_status is not None
            and inventory.effects_status is not None
            and self.relations_status != inventory.effects_status
        ):
            raise ValueError("候选与节点必须沿用同次回执提供状态")
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
        rows = inventory.candidates
        if rows is None or not all(r.id is not None for r in rows):
            return self
        for node in self.nodes or []:
            if node.potential_branch_candidate_refs is None:
                continue
            if "root_carrier_positions" not in node.model_fields_set:
                continue
            if node.root_carrier_positions is None:
                raise ValueError("缺少根载体不能伪作已核对无候选")
            if not all(r.known_identity()[2] is not None for r in rows):
                continue
            expected = [
                r.id
                for r in rows
                if set(node.root_carrier_positions) & set(r.known_identity()[2] or [])
            ]
            if node.potential_branch_candidate_refs != expected:
                raise ValueError("节点候选引用须保留同次物理载体涉及的全部候选")
        return self

    @model_validator(mode="after")
    def preserve_same_receipt_links(self) -> "PassageRelationContext":
        if self.relations_status == "not_supplied" and (
            self.events is not None or self.source_relation_count is not None
        ):
            raise ValueError("未提供关系回执不能改成已核对空列表")
        events = {e.id: e for e in self.events or [] if e.id is not None}
        if len(events) != sum(e.id is not None for e in self.events or []):
            raise ValueError("同一来源关系回执不能重复计入")
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
            if complete and set(events) != {
                f"assessment.relations:{i}" for i in range(self.source_relation_count)
            }:
                raise ValueError("来源关系序号不能跳过或替换原事件")
        nodes = [n.node_id for n in self.nodes or [] if n.node_id is not None]
        if len(nodes) != len(set(nodes)):
            raise ValueError("同一通关节点的关系上下文不能重复")
        if not complete:
            return self
        if (
            self.unclassified_event_refs is not None
            and self.unclassified_event_refs
            != [e.id for e in self.events or [] if e.plane == "unclassified"]
        ):
            raise ValueError("未分类关系必须保留未知，不能伪作条件全清")
        for node in self.nodes or []:
            if node.node_id is None:
                continue
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
            if node.root_relation_refs is not None:
                if "root_carrier_positions" not in node.model_fields_set:
                    continue
                if node.root_carrier_positions is None:
                    raise ValueError("缺少根载体回执不能伪作已核对无支关系")
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
        return self
