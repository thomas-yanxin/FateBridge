"""Projection-compatible source-path prerequisites, without an acceptance label."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_month_use import MonthUseMatch, MonthUseResolution


class OriginalMonthQi(PartialOutput):
    stem: str | None = None
    ten_god: str | None = None


class CandidateMonth(PartialOutput):
    branch: str | None = None
    label: str | None = None
    stem: str | None = None
    ten_god: str | None = None
    selection_rule: str | None = None
    selection_method: str | None = None
    reference_scope: str | None = None
    original_main_qi: OriginalMonthQi | None = None
    basis_status: Literal["original_and_selected_differ", "same_ten_god"] | None = None


class CandidateObservation(PartialOutput):
    id: str | None = None
    status: Literal["matched", "not_matched"] | None = None
    star_refs: list[str] | None = None
    positions: list[str] | None = None
    scope: str | None = None


class CandidateForceCondition(PartialOutput):
    condition: str | None = None
    status: Literal["unknown"] | None = None


class CandidateSourceCaution(PartialOutput):
    id: str | None = None
    status: Literal["matched", "not_matched"] | None = None
    star_refs: list[str] | None = None
    effect: Literal["source_caution_only"] | None = None
    scope: str | None = None


class SourceCandidatePath(PartialOutput):
    id: str | None = None
    label: str | None = None
    month_anchor_basis: list[str] | None = None
    month_use_match: Annotated[MonthUseMatch | None, FULL_FACT] = None
    status: (
        Literal[
            "requires_force_adjudication",
            "requires_identity_adjudication",
            "observable_prerequisite_not_met",
        ]
        | None
    ) = None
    observed_conditions: list[CandidateObservation] | None = None
    source_cautions: list[CandidateSourceCaution] | None = None
    force_conditions: list[CandidateForceCondition] | None = None
    formation_status: Literal["not_adjudicated"] | None = None
    source_ref: str | None = None
    source_pdf_pages: list[int] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_observable_failures(self) -> "SourceCandidatePath":
        if self.status in (
            "requires_force_adjudication",
            "requires_identity_adjudication",
        ) and any(c.status == "not_matched" for c in self.observed_conditions or []):
            raise ValueError("可观察前提未满足时不能冒称已进入纯力量裁定")
        return self


class CandidateSelection(PartialOutput):
    method_id: (
        Literal[
            "month_path_conditions_v1",
            "month_path_conditions_v2",
            "month_path_conditions_v3",
            "month_path_conditions_v4",
            "month_path_conditions_v5",
        ]
        | None
    ) = None
    source: dict[str, OpenJsonValue] | None = None
    selected_month: CandidateMonth | None = None
    month_use_resolution: Annotated[MonthUseResolution | None, FULL_FACT] = None
    paths: list[SourceCandidatePath] | None = None
    chosen_path_id: None = None
    adjudication_status: Literal["not_adjudicated"] | None = None
    selection_status: (
        Literal[
            "requires_force_adjudication",
            "observable_prerequisites_not_met",
            "requires_identity_adjudication",
            "source_paths_not_modeled",
        ]
        | None
    ) = None
    scope: str | None = None


class MonthStructureReference(PartialOutput):
    key: Literal["selected_month_reference", "month_use_reference"] | None = None
    label: str | None = None
    formation_status: Literal["not_adjudicated"] | None = None
    reason: str | None = None
    useful_elements: list[str] | None = Field(default=None, max_length=0)
    avoid_elements: list[str] | None = Field(default=None, max_length=0)
    useful_ten_gods: list[str] | None = Field(default=None, max_length=0)
