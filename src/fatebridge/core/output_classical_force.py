"""Typed, projection-compatible contracts for distinct body and seal evidence."""

from fractions import Fraction
from typing import List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.energy_provenance import ROLES
from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_classical_roots import ClassicalRoot
from fatebridge.core.output_energy_provenance import EnergyProvenance, bind_part, close
from fatebridge.core.output_root_ledger import HiddenStemLedgerEntry


class ForceSource(PartialOutput):
    id: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    edition: Optional[str] = None
    url: Optional[str] = None
    pdf_pages: Optional[List[int]] = None
    printed_pages: Optional[List[int]] = None
    source_sha256: Optional[str] = None


class ForceRoot(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stem: Optional[str] = None
    hidden_rank: Optional[int] = Field(default=None, ge=0, le=2)


class ForceComponent(PartialOutput):
    element: Optional[str] = None
    ten_gods: Optional[List[str]] = None
    physical_hidden_roots: Optional[List[ForceRoot]] = None
    remaining_hidden_roots: Optional[List[HiddenStemLedgerEntry]] = None
    revealed_positions: Optional[List[str]] = None
    source_star_refs: Optional[List[str]] = None
    engineering_energy: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    engineering_energy_unrounded: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )


class ForceComponents(PartialOutput):
    body: Optional[ForceComponent] = None
    seal: Optional[ForceComponent] = None
    output: Optional[ForceComponent] = None
    wealth: Optional[ForceComponent] = None
    officer_killer: Optional[ForceComponent] = None


class EngineeringForceComposition(PartialOutput):
    status: Optional[Literal["supplied_calculation", "not_supplied"]] = None
    ratio_basis: Optional[
        Literal[
            "unrounded_same_assessment", "rounded_legacy_assessment", "not_supplied"
        ]
    ] = None
    strength_method_id: Optional[str] = None
    strength_level: Optional[str] = None
    support_share: Optional[float] = Field(default=None, ge=0, le=1)
    body_within_support_share: Optional[float] = Field(default=None, ge=0, le=1)
    body_seal_energy_relation: Optional[
        Literal["body_greater", "seal_greater", "equal", "not_supplied"]
    ] = None
    comparison_basis: Optional[
        Literal[
            "exact_rational_same_assessment",
            "unrounded_same_assessment",
            "rounded_legacy_assessment",
            "not_supplied",
        ]
    ] = None
    legacy_float_body_seal_energy_relation: Optional[
        Literal["body_greater", "seal_greater", "equal", "not_supplied"]
    ] = None
    body_energy_exact: Optional[str] = None
    seal_energy_exact: Optional[str] = None
    body_within_support_exact: Optional[str] = None
    quantity_kind: Optional[Literal["uncalibrated_engineering_energy"]] = None

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


class ClassicalForceAdjudication(PartialOutput):
    body_strength: Optional[Literal["not_adjudicated"]] = None
    seal_weight: Optional[Literal["not_adjudicated"]] = None
    body_seal_relation: Optional[Literal["not_adjudicated"]] = None


class ForceStemRootObservation(PartialOutput):
    stem: Optional[str] = None
    role: Optional[Literal["body", "seal", "output", "wealth", "officer_killer"]] = None
    is_day_master: Optional[bool] = None
    visible_positions: Optional[List[str]] = None
    roots: Optional[List[ClassicalRoot]] = None
    force_status: Optional[Literal["not_adjudicated"]] = None


class ForceSourceRootObservations(PartialOutput):
    method_id: Optional[Literal["observed_stem_root_categories_v1"]] = None
    life_stage_profile_id: Optional[str] = None
    source: Optional[ForceSource] = None
    stems: Optional[List[ForceStemRootObservation]] = None
    scope: Optional[str] = None


class ClassicalForceComponents(PartialOutput):
    method_id: Optional[Literal["body_seal_force_components_v1"]] = None
    source: Optional[ForceSource] = None
    components: Optional[ForceComponents] = None
    energy_provenance: Optional[EnergyProvenance] = None
    source_root_observations: Optional[ForceSourceRootObservations] = None
    engineering_composition: Optional[EngineeringForceComposition] = None
    classical_adjudication: Optional[ClassicalForceAdjudication] = None
    scope: Optional[str] = None
    limitations: Optional[List[str]] = None

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
            "rounded_legacy_assessment": "engineering_energy",
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
            composition.legacy_float_body_seal_energy_relation is not None
            and composition.legacy_float_body_seal_energy_relation != expected_relation
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
