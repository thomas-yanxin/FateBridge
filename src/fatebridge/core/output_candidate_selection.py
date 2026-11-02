"""Projection-compatible source-path prerequisites, without an acceptance label."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class OriginalMonthQi(PartialOutput):
    stem: Optional[str] = None
    ten_god: Optional[str] = None


class CandidateMonth(PartialOutput):
    branch: Optional[str] = None
    label: Optional[str] = None
    stem: Optional[str] = None
    ten_god: Optional[str] = None
    selection_rule: Optional[str] = None
    selection_method: Optional[str] = None
    original_main_qi: Optional[OriginalMonthQi] = None
    basis_status: Optional[Literal["original_and_selected_differ", "same_ten_god"]] = (
        None
    )


class CandidateObservation(PartialOutput):
    id: Optional[str] = None
    status: Optional[Literal["matched", "not_matched"]] = None
    star_refs: Optional[List[str]] = None
    positions: Optional[List[str]] = None
    scope: Optional[str] = None


class CandidateForceCondition(PartialOutput):
    condition: Optional[str] = None
    status: Optional[Literal["unknown"]] = None


class CandidateSourceCaution(PartialOutput):
    id: Optional[str] = None
    status: Optional[Literal["matched", "not_matched"]] = None
    star_refs: Optional[List[str]] = None
    effect: Optional[Literal["source_caution_only"]] = None
    scope: Optional[str] = None


class SourceCandidatePath(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    month_anchor_basis: Optional[List[Literal["selected", "original_main_qi"]]] = None
    status: Optional[
        Literal["requires_force_adjudication", "observable_prerequisite_not_met"]
    ] = None
    observed_conditions: Optional[List[CandidateObservation]] = None
    source_cautions: Optional[List[CandidateSourceCaution]] = None
    force_conditions: Optional[List[CandidateForceCondition]] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None
    source_ref: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_observable_failures(self) -> "SourceCandidatePath":
        if self.status == "requires_force_adjudication" and any(
            c.status == "not_matched" for c in self.observed_conditions or []
        ):
            raise ValueError("可观察前提未满足时不能冒称已进入纯力量裁定")
        return self


class CandidateSelection(PartialOutput):
    method_id: Optional[
        Literal[
            "month_path_conditions_v1",
            "month_path_conditions_v2",
            "month_path_conditions_v3",
        ]
    ] = None
    source: Optional[Dict[str, Any]] = None
    selected_month: Optional[CandidateMonth] = None
    paths: Optional[List[SourceCandidatePath]] = None
    chosen_path_id: None = None
    adjudication_status: Optional[Literal["not_adjudicated"]] = None
    selection_status: Optional[
        Literal[
            "requires_force_adjudication",
            "observable_prerequisites_not_met",
            "source_paths_not_modeled",
        ]
    ] = None
    scope: Optional[str] = None


class MonthStructureReference(PartialOutput):
    key: Optional[Literal["selected_month_reference"]] = None
    label: Optional[str] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None
    reason: Optional[str] = None
    useful_elements: Optional[List[str]] = Field(default=None, max_length=0)
    avoid_elements: Optional[List[str]] = Field(default=None, max_length=0)
    useful_ten_gods: Optional[List[str]] = Field(default=None, max_length=0)
