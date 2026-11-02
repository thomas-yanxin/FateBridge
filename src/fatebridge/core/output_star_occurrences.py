"""Typed physical counts retain their unit and visible/hidden distinction."""

from typing import Dict, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class StarOccurrenceCount(PartialOutput):
    visible_count: Optional[int] = Field(default=None, ge=0)
    hidden_count: Optional[int] = Field(default=None, ge=0)
    total_count: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def retain_physical_sum(self) -> "StarOccurrenceCount":
        if (
            self.visible_count is not None
            and self.hidden_count is not None
            and self.total_count is not None
            and self.total_count != self.visible_count + self.hidden_count
        ):
            raise ValueError("星位实数总量必须等于透干与藏干项数之和")
        return self


class StarOccurrences(PartialOutput):
    method_id: Optional[Literal["physical_ten_god_occurrences_v1"]] = None
    quantity_kind: Optional[
        Literal["physical_occurrences_not_force_or_weighted_score"]
    ] = None
    day_stem_counted_as_support: Optional[Literal[False]] = None
    status: Optional[Literal["complete_star_categories", "partial_star_categories"]] = (
        None
    )
    gods: Optional[Dict[str, StarOccurrenceCount]] = None
    scope: Optional[str] = None
