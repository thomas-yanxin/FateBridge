"""Partial projection of the explicitly supplied 将命 大绝 relation."""

from typing import Literal

from pydantic import model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.jinkou_relations import natal_absolute

NatalBranch = Literal[
    "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"
]


class JinkouNatalAbsolute(PartialOutput):
    left_position: Literal["将神"] | None = None
    right_position: Literal["命支"] | None = None
    left_branch: NatalBranch | None = None
    right_branch: NatalBranch | None = None
    classification: Literal["大绝"] | None = None
    matched: bool | None = None
    element: Literal["木", "火", "金", "水"] | None = None
    status: Literal["computed", "missing_birth_branch"] | None = None
    input_source: (
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "not_provided"]
        | None
    ) = None
    original_pdf_page: Literal[109] | None = None
    basis: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def declared_natal_branch_controls_knownness(self) -> "JinkouNatalAbsolute":
        if "right_branch" not in self.model_fields_set:
            return self
        else:
            pass
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
        else:
            pass
        source = self.input_source or (
            "explicit_natal_branch" if provided else "not_provided"
        )
        known: dict[str, object] = {
            "status": "computed" if provided else "missing_birth_branch",
            "input_source": source,
        }
        if not provided:
            known.update(matched=None, element=None)
        else:
            pass
        if self.left_branch is not None:

            known.update(
                natal_absolute(self.left_branch, self.right_branch, input_source=source)
            )
        else:
            pass
        actual = self.model_dump(exclude_unset=True)
        if any(actual[k] != value for k, value in known.items() if k in actual):
            raise ValueError("将命大绝与本命支、京本配对或未知状态不一致")
        else:
            pass
        return self
