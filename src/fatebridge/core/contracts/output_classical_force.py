"""Typed, projection-compatible contracts for distinct body and seal evidence."""

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PRESENT_FACT, PartialOutput
from fatebridge.core.contracts.output_classical_roots import ClassicalRoot
from fatebridge.core.contracts.output_energy_provenance import (
    EnergyProvenance,
    bind_part,
    close,
)
from fatebridge.core.contracts.output_root_ledger import HiddenStemLedgerEntry
from fatebridge.core.energy_provenance import ROLES


class ForceSource(PartialOutput):
    id: str | None = None
    author: str | None = None
    title: str | None = None
    edition: str | None = None
    url: str | None = None
    pdf_pages: list[int] | None = None
    printed_pages: list[int] | None = None
    source_sha256: str | None = None


class ForceRoot(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    stem: str | None = None
    hidden_rank: int | None = Field(default=None, ge=0, le=2)


class ForceComponent(PartialOutput):
    element: str | None = None
    ten_gods: list[str] | None = None
    physical_hidden_roots: list[ForceRoot] | None = None
    remaining_hidden_roots: list[HiddenStemLedgerEntry] | None = None
    revealed_positions: list[str] | None = None
    source_star_refs: list[str] | None = None
    engineering_energy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    engineering_energy_unrounded: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )


class ForceComponents(PartialOutput):
    body: ForceComponent | None = None
    seal: ForceComponent | None = None
    output: ForceComponent | None = None
    wealth: ForceComponent | None = None
    officer_killer: ForceComponent | None = None


class EngineeringForceComposition(PartialOutput):
    status: Literal["supplied_calculation", "not_supplied"] | None = None
    ratio_basis: Literal["unrounded_same_assessment", "not_supplied"] | None = None
    strength_method_id: str | None = None
    strength_level: str | None = None
    support_share: float | None = Field(default=None, ge=0, le=1)
    body_within_support_share: float | None = Field(default=None, ge=0, le=1)
    body_seal_energy_relation: (
        Literal["body_greater", "seal_greater", "equal", "not_supplied"] | None
    ) = None
    comparison_basis: (
        Literal[
            "exact_rational_same_assessment",
            "unrounded_same_assessment",
            "not_supplied",
        ]
        | None
    ) = None
    float_body_seal_energy_relation: (
        Literal["body_greater", "seal_greater", "equal", "not_supplied"] | None
    ) = None
    body_energy_exact: str | None = None
    seal_energy_exact: str | None = None
    body_within_support_exact: str | None = None
    quantity_kind: Literal["uncalibrated_engineering_energy"] | None = None

    @model_validator(mode="after")
    def coherent_exact_comparison(self) -> "EngineeringForceComposition":
        values = {}
        for field in (
            "body_energy_exact",
            "seal_energy_exact",
            "body_within_support_exact",
        ):
            raw = getattr(self, field)
            if raw is not None:
                try:
                    value = Fraction(raw)
                except (ValueError, ZeroDivisionError) as error:
                    raise ValueError("身印精确回执须为有限分数") from error
                if value < 0 or (field == "body_within_support_exact" and value > 1):
                    raise ValueError("身印精确回执范围不符")
                values[field] = value
        if "body_energy_exact" in values and "seal_energy_exact" in values:
            body, seal = values["body_energy_exact"], values["seal_energy_exact"]
            expected = (
                "body_greater"
                if body > seal
                else "seal_greater" if seal > body else "equal"
            )
            if (
                self.body_seal_energy_relation is not None
                and self.body_seal_energy_relation != expected
            ):
                raise ValueError("身印比较与精确分量不符")
            if (
                body + seal
                and "body_within_support_exact" in values
                and values["body_within_support_exact"] != body / (body + seal)
            ):
                raise ValueError("身印精确占比与分量不符")
            if not body + seal and "body_within_support_exact" in values:
                raise ValueError("身印工程总量为零时占比未定义，不能伪造0/0的值")
        return self


class EngineeringStrengthIndex(PartialOutput):
    method_id: Annotated[str | None, FULL_FACT] = None
    quantity_kind: Annotated[
        Literal["uncalibrated_strength_policy_index"] | None, FULL_FACT
    ] = None
    strength_level: Annotated[Literal["强", "中和", "弱"] | None, FULL_FACT] = None
    numerical_strength_level: Annotated[
        Literal["强", "中和", "弱"] | None, FULL_FACT
    ] = None
    support_share: Annotated[float | None, FULL_FACT] = Field(default=None, ge=0, le=1)
    source_adjudication_used: Annotated[Literal[False] | None, FULL_FACT] = None
    scope: Annotated[str | None, FULL_FACT] = None


class ClassicalForceAdjudication(PartialOutput):
    method_id: Annotated[Literal["classical_force_conditions_v1"] | None, FULL_FACT] = (
        None
    )
    status: Annotated[
        Literal["not_adjudicated", "conditional", "adjudicated"] | None, FULL_FACT
    ] = None
    body_strength: Annotated[Literal["强", "中和", "弱"] | None, PRESENT_FACT] = None
    seal_weight: Annotated[Literal["重", "轻"] | None, PRESENT_FACT] = None
    body_seal_relation: Annotated[str | None, PRESENT_FACT] = None
    ordinary_fuyi_applicable: Annotated[bool | None, PRESENT_FACT] = None
    observed_body_root_positions: Annotated[list[str] | None, FULL_FACT] = None
    observed_seal_root_positions: Annotated[list[str] | None, FULL_FACT] = None
    source_refs: Annotated[list[str] | None, FULL_FACT] = None
    pending_conditions: Annotated[list[str] | None, FULL_FACT] = None
    scope: Annotated[str | None, FULL_FACT] = None

    @model_validator(mode="after")
    def unresolved_has_no_force_grade(self) -> "ClassicalForceAdjudication":
        if self.status == "not_adjudicated" and any(
            value is not None
            for value in (
                self.body_strength,
                self.seal_weight,
                self.body_seal_relation,
                self.ordinary_fuyi_applicable,
            )
        ):
            raise ValueError("原典力量未裁定时不能交付强弱、身印关系或普通扶抑适用结论")
        return self


class ForceStemRootObservation(PartialOutput):
    stem: str | None = None
    role: Literal["body", "seal", "output", "wealth", "officer_killer"] | None = None
    is_day_master: bool | None = None
    visible_positions: list[str] | None = None
    roots: list[ClassicalRoot] | None = None
    force_status: Literal["not_adjudicated"] | None = None


class ForceSourceRootObservations(PartialOutput):
    method_id: Literal["observed_stem_root_categories_v1"] | None = None
    life_stage_profile_id: str | None = None
    source: ForceSource | None = None
    stems: list[ForceStemRootObservation] | None = None
    scope: str | None = None


class ClassicalForceComponents(PartialOutput):
    method_id: Literal["body_seal_force_components_v1"] | None = None
    source: ForceSource | None = None
    components: ForceComponents | None = None
    energy_provenance: EnergyProvenance | None = None
    source_root_observations: ForceSourceRootObservations | None = None
    engineering_composition: EngineeringForceComposition | None = None
    classical_adjudication: Annotated[ClassicalForceAdjudication | None, FULL_FACT] = (
        None
    )
    scope: str | None = None
    limitations: list[str] | None = None

    @model_validator(mode="after")
    def preserve_native_energy_sources(self) -> "ClassicalForceComponents":
        provenance = self.energy_provenance
        if provenance is None:
            return self
        composition = self.engineering_composition
        if (
            composition is not None
            and composition.strength_method_id is not None
            and provenance.strength_method_id is not None
            and composition.strength_method_id != provenance.strength_method_id
        ):
            raise ValueError("身印能量来源与计算方法须为同次回执")
        for role in ROLES:
            front = (
                getattr(provenance.fronts, role)
                if provenance.fronts is not None
                else None
            )
            component = (
                getattr(self.components, role) if self.components is not None else None
            )
            if front is None or component is None:
                continue
            if (
                front.element is not None
                and component.element is not None
                and front.element != component.element
            ):
                raise ValueError("分项能量五行须忠于对应身印等角色")
            if (
                front.total_energy_unrounded is not None
                and component.engineering_energy_unrounded is not None
                and not close(
                    front.total_energy_unrounded, component.engineering_energy_unrounded
                )
            ):
                raise ValueError("归因总量须忠于对应同次未舍入分量")
            if component.remaining_hidden_roots is not None:
                bind_part(
                    front,
                    "physical_hidden",
                    [
                        r.model_dump(exclude_unset=True)
                        for r in component.remaining_hidden_roots
                    ],
                )
        return self

    @model_validator(mode="after")
    def preserve_recorded_float_composition(self) -> "ClassicalForceComponents":
        components, composition = self.components, self.engineering_composition
        if components is None or composition is None:
            return self
        fields = {
            "unrounded_same_assessment": "engineering_energy_unrounded",
        }
        key = fields.get(composition.ratio_basis or "")
        if key is None or components.body is None or components.seal is None:
            return self
        body = getattr(components.body, key)
        seal = getattr(components.seal, key)
        if body is None or seal is None:
            return self
        expected_relation = (
            "body_greater"
            if body > seal
            else "seal_greater" if seal > body else "equal"
        )
        if (
            composition.float_body_seal_energy_relation is not None
            and composition.float_body_seal_energy_relation != expected_relation
        ):
            raise ValueError("浮点身印比较必须忠于同次已给分量")
        # Exact arithmetic can legitimately disagree at a float boundary.
        # Only a declared FLOAT comparison is compared with these floats.
        if (
            composition.comparison_basis == composition.ratio_basis
            and composition.body_seal_energy_relation is not None
            and composition.body_seal_energy_relation != expected_relation
        ):
            raise ValueError("同基准身印比较与已给分量不符")
        share = composition.body_within_support_share
        if share is not None:
            if not body + seal:
                raise ValueError("身印工程总量为零时浮点占比未定义")
            if share != body / (body + seal):
                raise ValueError("身印浮点占比必须忠于同次已给未舍入或旧展示分量")
        return self
