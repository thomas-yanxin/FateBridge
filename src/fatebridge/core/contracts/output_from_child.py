"""Structured facts for the source-scoped from-child review path."""

from typing import Any, Literal

from pydantic import ConfigDict, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class FromChildOccurrence(PartialOutput):
    id: str | None = None
    position: Literal["year", "month", "day", "hour"] | None = None
    location: Literal["visible", "hidden"] | None = None
    stem: str | None = None
    branch: str | None = None
    hidden_rank: int | None = None
    role: Literal["peer", "output", "wealth", "seal", "officer"] | None = None
    ten_god: str | None = None


class FromChildObservation(PartialOutput):
    id: str | None = None
    matched: bool | None = None
    occurrence_ids: list[str] | None = None


def _from_child_policy_schema(schema: dict[str, Any]) -> None:
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
    method_id: Literal["ditian_from_child_presence_screen_v1"] | None = None
    status: (
        Literal[
            "requires_force_adjudication",
            "observable_obstruction",
            "observable_prerequisite_not_met",
        ]
        | None
    ) = None
    formation_status: Literal["not_adjudicated"] | None = None
    ordinary_fuyi_requires_review: bool | None = None
    strength_requirement: Literal["not_a_prerequisite"] | None = None
    day_stem: str | None = None
    occurrences: list[FromChildOccurrence] | None = None
    observed_conditions: list[FromChildObservation] | None = None
    output_positions: list[str] | None = None
    visible_obstructions: list[str] | None = None
    hidden_obstructions: list[str] | None = None
    conditional_direction: dict[str, OpenJsonValue] | None = None
    pending_conditions: list[str] | None = None
    source: dict[str, OpenJsonValue] | None = None
    scope: str | None = None

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
        else:
            pass
        if self.ordinary_fuyi_requires_review is True and self.status in {
            "observable_obstruction",
            "observable_prerequisite_not_met",
        }:
            raise ValueError("从儿审查标记与可观察状态不一致")
        else:
            pass
        if (
            self.status == "requires_force_adjudication"
            and self.ordinary_fuyi_requires_review is False
        ):
            raise ValueError("从儿审查标记与可观察状态不一致")
        else:
            pass
        return self
