"""Partial projection of the explicitly supplied 将命 大绝 relation."""

from typing import Literal, Optional

from pydantic import model_validator

from .output_base import PartialOutput

NatalBranch = Literal[
    "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"
]


class JinkouNatalAbsolute(PartialOutput):
    left_position: Optional[Literal["将神"]] = None
    right_position: Optional[Literal["命支"]] = None
    left_branch: Optional[NatalBranch] = None
    right_branch: Optional[NatalBranch] = None
    classification: Optional[Literal["大绝"]] = None
    matched: Optional[bool] = None
    element: Optional[Literal["木", "火", "金", "水"]] = None
    status: Optional[Literal["computed", "missing_birth_branch"]] = None
    input_source: Optional[
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "not_provided"]
    ] = None
    original_pdf_page: Optional[Literal[109]] = None
    basis: Optional[str] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def declared_natal_branch_controls_knownness(self) -> "JinkouNatalAbsolute":
        if "right_branch" not in self.model_fields_set:
            return self
        provided = self.right_branch is not None
        allowed_sources = (
            {"explicit_natal_branch", "explicit_birth_year_ganzhi"}
            if provided
            else {"not_provided"}
        )
        if (
            "input_source" in self.model_fields_set
            and self.input_source not in allowed_sources
        ):
            raise ValueError("本命年支的明确来源与已知状态不一致")
        source = self.input_source or (
            "explicit_natal_branch" if provided else "not_provided"
        )
        known: dict[str, object] = {
            "status": "computed" if provided else "missing_birth_branch",
            "input_source": source,
        }
        if not provided:
            known.update(matched=None, element=None)
        if self.left_branch is not None:
            from .metaphysics.jinkou_relations import natal_absolute

            known.update(
                natal_absolute(self.left_branch, self.right_branch, input_source=source)
            )
        actual = self.model_dump(exclude_unset=True)
        if any(actual[k] != value for k, value in known.items() if k in actual):
            raise ValueError("将命大绝与本命支、京本配对或未知状态不一致")
        return self
