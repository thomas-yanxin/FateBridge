"""Projection-safe source readings, explicitly separate from adjudicated facts."""

from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from fatebridge.core.output_base import PartialOutput


class RelativeSourceTiming(PartialOutput):
    statement_kind: Optional[Literal["relative_solar_term_day_statement"]] = None
    source_term: Optional[str] = None
    source_elapsed_days: Optional[int] = Field(default=None, ge=0)
    source_duty_stem: Optional[
        Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    ] = None
    reading_excerpt: Optional[str] = None
    calendar_instant_reconstructed: Optional[Literal[False]] = None
    day_count_convention: Optional[Literal["not_adjudicated"]] = None
    effective_duty_assigned: Optional[Literal[False]] = None

    @field_validator("source_elapsed_days", mode="before")
    @classmethod
    def exact_integer_fact(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("原文相对天数必须保留JSON整数类型")
        return value

    @field_validator(
        "calendar_instant_reconstructed", "effective_duty_assigned", mode="before"
    )
    @classmethod
    def exact_boolean_facts(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("相对时序不能以数值冒充是否已推算出生瞬间或司令")
        return value


class SourcePageAnchor(PartialOutput):
    pdf_page: Optional[int] = Field(default=None, ge=1)
    image_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("pdf_page", mode="before")
    @classmethod
    def exact_page(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("原页页码必须保留JSON整数类型")
        return value


class SourceConditionProvenance(PartialOutput):
    method_id: Optional[Literal["registered_source_conditions_v1"]] = None
    condition_layer_sha256: Optional[str] = None


class SourceConditionReview(PartialOutput):
    review_id: Optional[str] = None
    case_id: Optional[str] = None
    pillars: Optional[List[str]] = None
    review_kind: Optional[Literal["same_developer_primary_image_reading"]] = None
    claim_shape: Optional[
        Literal[
            "conditional_category_with_named_example",
            "contextual_semantic_mapping_needs_expert_adjudication",
            "explicit_body_and_seal_separately",
            "explicit_body_context_with_source_transformation_claim",
            "explicit_body_weakness_despite_seal",
            "explicit_day_master_strength",
            "explicit_day_master_strength_and_no_transformation",
            "explicit_day_master_strength_in_paired_contrast",
            "explicit_day_master_strength_with_passage_conditions",
            "explicit_day_master_strength_with_relative_duty_statement",
            "explicit_day_master_strength_with_roots",
            "explicit_day_master_weakness_and_damaged_seal",
            "explicit_fire_extreme_strength",
            "explicit_fire_weakness_with_early_season",
            "explicit_later_example_backreference",
            "shared_paragraph_named_example",
        ]
    ] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_url: Optional[str] = None
    source_page_anchors: Optional[List[SourcePageAnchor]] = None
    reading_excerpt: Optional[str] = None
    excerpt_kind: Optional[Literal["developer_transcription_for_scope"]] = None
    body_seal_conditions: Optional[str] = None
    passage_conditions: Optional[str] = None
    relative_timing_statements: Optional[List[RelativeSourceTiming]] = None
    independent_expert_review: Optional[Literal["not_completed"]] = None
    effective_force_adjudication: Optional[Literal["not_adjudicated"]] = None
    effective_passage_adjudication: Optional[Literal["not_adjudicated"]] = None
    strength_annotation_assigned_or_regraded: Optional[Literal[False]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None
    calculation_effect: Optional[Literal["none"]] = None
    provenance: Optional[SourceConditionProvenance] = None

    @field_validator("new_independent_validation_credit", mode="before")
    @classmethod
    def exact_credit(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("校读信用必须为整数0，不可借布尔值改变证据类型")
        return value

    @field_validator("strength_annotation_assigned_or_regraded", mode="before")
    @classmethod
    def exact_boolean_fact(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("校读不重判等级的事实必须保留JSON布尔类型")
        return value

    @model_validator(mode="after")
    def preserve_known_registered_reading(self) -> "SourceConditionReview":
        if self.review_id is not None:
            from fatebridge.core.source_conditions import validate_known_review

            validate_known_review(
                self.model_dump(exclude_unset=True, exclude_none=True)
            )
        return self
