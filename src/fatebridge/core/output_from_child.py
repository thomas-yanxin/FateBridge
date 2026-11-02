"""Structured facts for the source-scoped from-child review path."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import ConfigDict, model_validator

from fatebridge.core.output_base import PartialOutput


class FromChildOccurrence(PartialOutput):
    id: Optional[str] = None
    position: Optional[Literal["year", "month", "day", "hour"]] = None
    location: Optional[Literal["visible", "hidden"]] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    hidden_rank: Optional[int] = None
    role: Optional[Literal["peer", "output", "wealth", "seal", "officer"]] = None
    ten_god: Optional[str] = None


class FromChildObservation(PartialOutput):
    id: Optional[str] = None
    matched: Optional[bool] = None
    occurrence_ids: Optional[List[str]] = None


def _from_child_policy_schema(schema: Dict[str, Any]) -> None:
    schema.setdefault("allOf", []).append(
        {
            "if": {
                "anyOf": [
                    {
                        "properties": {
                            "ordinary_fuyi_requires_review": {"const": True}
                        },
                        "required": ["ordinary_fuyi_requires_review"],
                    },
                    {
                        "properties": {
                            "status": {"const": "requires_force_adjudication"}
                        },
                        "required": ["status"],
                    },
                ]
            },
            "then": {
                "properties": {
                    "status": {"enum": ["requires_force_adjudication", None]},
                    "ordinary_fuyi_requires_review": {"enum": [True, None]},
                    "visible_obstructions": {"maxItems": 0},
                    "observed_conditions": {
                        "items": {"properties": {"matched": {"enum": [True, None]}}}
                    },
                }
            },
        }
    )


class FromChildReference(PartialOutput):
    model_config = ConfigDict(json_schema_extra=_from_child_policy_schema)
    method_id: Optional[Literal["ditian_from_child_presence_screen_v1"]] = None
    status: Optional[
        Literal[
            "requires_force_adjudication",
            "observable_obstruction",
            "observable_prerequisite_not_met",
        ]
    ] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None
    ordinary_fuyi_requires_review: Optional[bool] = None
    strength_requirement: Optional[Literal["not_a_prerequisite"]] = None
    day_stem: Optional[str] = None
    occurrences: Optional[List[FromChildOccurrence]] = None
    observed_conditions: Optional[List[FromChildObservation]] = None
    output_positions: Optional[List[str]] = None
    visible_obstructions: Optional[List[str]] = None
    hidden_obstructions: Optional[List[str]] = None
    conditional_direction: Optional[Dict[str, Any]] = None
    pending_conditions: Optional[List[str]] = None
    source: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_review_conditions(self) -> "FromChildReference":
        reviewing = self.ordinary_fuyi_requires_review is True or (
            self.status == "requires_force_adjudication"
        )
        if reviewing and (
            self.visible_obstructions
            or any(r.matched is False for r in self.observed_conditions or [])
        ):
            raise ValueError("从儿可观察前提或透干阻碍不能被改写为已满足")
        if self.ordinary_fuyi_requires_review is True and self.status in {
            "observable_obstruction",
            "observable_prerequisite_not_met",
        }:
            raise ValueError("从儿审查标记与可观察状态不一致")
        if (
            self.status == "requires_force_adjudication"
            and self.ordinary_fuyi_requires_review is False
        ):
            raise ValueError("从儿审查标记与可观察状态不一致")
        return self
