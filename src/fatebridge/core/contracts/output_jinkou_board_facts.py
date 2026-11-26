"""Jinkou position, strength and structural facts."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import BranchName
from fatebridge.core.contracts.output_jinkou_natal import JinkouNatalAbsolute
from fatebridge.core.contracts.output_jinkou_qi_models import JinkouInternalRelation
from fatebridge.core.contracts.output_jinkou_relations import (
    validate_absolute_row,
    validate_calendar_row,
    validate_defeat_row,
    validate_queue,
    validate_relations,
)
from fatebridge.core.contracts.output_jinkou_sources import (
    JinkouStrengthSource,
    JinkouUseSource,
)
from fatebridge.core.contracts.output_liuren_board import RenDiurnalEvidence


class JinkouGuishen(BranchName):
    start_branch: str | None = None
    earth_branch: str | None = None
    intrinsic_ganzhi: str | None = None
    direction: str | None = None


class JinkouOverview(PartialOutput):
    board_style: str | None = None
    board_style_detail: str | None = None
    di_fen: str | None = None
    gender: str | None = None
    guishen: JinkouGuishen | None = None
    kongwang: str | None = None
    month_general: BranchName | None = Field(
        default=None,
        description="依民用瞬间中气确定的月将本位，未移到地分；yuejiang另记落地分后的将神。",
    )
    si_da_kong: str | None = None
    transmission_method: str | None = None
    use_position: str | None = None
    use_position_basis: str | None = None
    yuejiang: BranchName | None = Field(
        default=None,
        description="月将加时后落在地分的将神，对应将神行；与month_general月将本位分开。",
    )
    di_fen_source: str | None = None
    xun_head: str | None = None
    power_basis: str | None = None
    diurnal_basis: str | None = None
    is_diurnal: bool | None = None
    diurnal_evidence: RenDiurnalEvidence | None = None


class JinkouRow(PartialOutput):
    content: str | None = None
    element: str | None = None
    label: str | None = None
    seasonal_power: str | None = Field(
        default=None, description="按月建约定的四季旺衰，与位内旺衰分开。"
    )
    internal_power: str | None = Field(
        default=None,
        description="按四位课内旺神所得旺衰；多个旺神候选未裁定时为 null。",
    )
    shenjiang: str | None = None
    polarity: str | None = None
    dun_stem: str | None = None
    intrinsic_ganzhi: str | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None
    month_break: bool | None = None
    is_use: bool | None = None


class JinkouMotion(PartialOutput):
    name: str | None = None
    source_position: str | None = None
    target_position: str | None = None
    relation: str | None = None
    source_section: str | None = None
    basis: str | None = None
    empty_positions: list[str] | None = None


class JinkouInternalStrength(PartialOutput):
    method: str | None = None
    status: str | None = None
    anchor_element: str | None = None
    candidate_elements: list[str] | None = None
    candidate_positions: list[str] | None = None
    has_control: bool | None = None
    relations: list[JinkouInternalRelation] | None = None
    powers: dict[str, str | None] | None = None
    basis: str | None = None
    source_evidence: JinkouStrengthSource | None = None
    scope: str | None = None


class JinkouUseEvidence(PartialOutput):
    polarity_position: str | None = None
    subject_position: str | None = None
    controlled_by: list[str] | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None
    month_break: bool | None = None
    seasonal_power: str | None = None
    internal_power: str | None = None
    no_control_principle_applies: bool | None = None
    internal_strength_candidates: list[str] | None = None
    comprehensive_position: None = None
    source_evidence: JinkouUseSource | None = None
    status: str | None = None
    basis: str | None = None
    scope: str | None = None


class JinkouJueCheck(PartialOutput):
    left_position: str | None = None
    right_position: str | None = None
    left_branch: str | None = None
    right_branch: str | None = None
    element: str | None = None
    classification: str | None = None
    matched: bool | None = None
    status: str | None = None
    reason: str | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def named_pair_matches_facts(self) -> "JinkouJueCheck":

        validate_absolute_row(self.model_dump(exclude_unset=True))
        return self


class JinkouJue(PartialOutput):
    checks: list[JinkouJueCheck] | None = None
    natal: JinkouNatalAbsolute | None = None
    unavailable: list[JinkouJueCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_selected_pair_catalog(self) -> "JinkouJue":

        validate_queue(self.model_dump(exclude_unset=True), "si_jue")
        return self

    @model_validator(mode="after")
    def missing_natal_is_not_a_false_or_unavailable_known_branch(self) -> "JinkouJue":
        if self.natal is None or self.unavailable is None:
            return self
        if "right_branch" not in self.natal.model_fields_set:
            return self
        if self.natal.right_branch is not None:
            if self.unavailable:
                raise ValueError("明确本命支的大绝不能仍列为缺失本命支")
        elif len(self.unavailable) != 1 or any(
            r.matched is not None or r.status != "missing_birth_branch"
            for r in self.unavailable
        ):
            raise ValueError("本命支缺失时大绝必须保留未算状态")
        return self


class JinkouBaiCheck(PartialOutput):
    position: str | None = None
    element: str | None = None
    seat_branch: str | None = None
    bai_branch: str | None = None
    matched: bool | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def selected_phase_matches_seat(self) -> "JinkouBaiCheck":

        validate_defeat_row(self.model_dump(exclude_unset=True))
        return self


class JinkouBai(PartialOutput):
    checks: list[JinkouBaiCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_selected_defeat_catalog(self) -> "JinkouBai":

        validate_queue(self.model_dump(exclude_unset=True), "si_bai")
        return self


class JinkouCalendarCheck(PartialOutput):
    rule_id: str | None = None
    name: str | None = None
    position: str | None = None
    branch: str | None = None
    reference_branch: str | None = None
    matched: bool | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def year_day_rule_matches_facts(self) -> "JinkouCalendarCheck":

        validate_calendar_row(self.model_dump(exclude_unset=True))
        return self


class JinkouCalendarRelations(PartialOutput):
    year_branch: str | None = None
    day_branch: str | None = None
    checks: list[JinkouCalendarCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def year_day_references_are_coherent(self) -> "JinkouCalendarRelations":

        validate_relations({"calendar": self.model_dump(exclude_unset=True)})
        return self


class JinkouRelationVariant(PartialOutput):
    branches: list[str] | None = None
    scan_element: str | None = None
    transcription_element: str | None = None
    original_pdf_page: int | None = None


class JinkouRelations(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    transcription_url: str | None = None
    source_sha256: str | None = None
    source_section: str | None = None
    si_jue: JinkouJue | None = None
    si_bai: JinkouBai | None = None
    calendar: JinkouCalendarRelations | None = None
    transcription_variants: list[JinkouRelationVariant] | None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_unearned_full_conformance(cls, value: object) -> Literal[False]:
        if value is not False:
            raise ValueError("所选京本结构关系不能宣称完整原典认证")
        return value

    @model_validator(mode="after")
    def source_and_selected_facts_agree(self) -> "JinkouRelations":

        validate_relations(self.model_dump(exclude_unset=True))
        return self


class LabelValue(PartialOutput):
    label: str | None = None
    value: str | None = None


class JinkouTrineMember(PartialOutput):
    position: str | None = None
    branch: str | None = None
    day_clash: bool | None = None
    month_break: bool | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None


class JinkouTrineStem(PartialOutput):
    position: str | None = None
    stem: str | None = None
    element: str | None = None
    trine_element: str | None = None
    explicit_fire_clause: bool | None = None


class JinkouTrine(PartialOutput):
    name: str | None = None
    partial_name: str | None = None
    element: str | None = None
    branches: list[str] | None = None
    present_branches: list[str] | None = None
    missing_branches: list[str] | None = None
    structural_status: str | None = None
    human_stem_relation: str | None = None
    member_conditions: list[JinkouTrineMember] | None = None
    controlling_dun_stems: list[JinkouTrineStem] | None = None
    source_listed_disruptors: list[str] | None = None
    disruptor_application: str | None = None
    du_he: None = None
    transformation_confirmed: None = None
    waiting_branch: str | None = None
    calendar_candidates: None = None
    original_pdf_pages: list[int] | None = None
    basis: str | None = None


class JinkouTrineVariant(PartialOutput):
    original_pdf_page: int | None = None
    scan_reading: str | None = None
    transcription_reading: str | None = None


class JinkouCombinations(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_section: str | None = None
    day_branch: str | None = None
    month_branch: str | None = None
    trines: list[JinkouTrine] | None = None
    textual_variants: list[JinkouTrineVariant] | None = None
    scope: str | None = None
