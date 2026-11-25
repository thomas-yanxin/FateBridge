"""Projection-compatible, internally checked contracts for occurrence planes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_classical_force import ForceSource
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, Element

ElementName = Literal["木", "火", "土", "金", "水"]


class PresenceOccurrence(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    pillar: Literal["year", "month", "day", "hour"]
    stem: str = Field(pattern="^[甲乙丙丁戊己庚辛壬癸]$")
    element: ElementName
    branch: str | None = Field(default=None, pattern="^[子丑寅卯辰巳午未申酉戌亥]$")
    hidden_rank: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="after")
    def preserve_stem_and_hidden_rank(self) -> "PresenceOccurrence":
        if self.element != STEM_ELEMENTS[self.stem][0].value:
            raise ValueError("五行须与原录干字相符")
        else:
            pass
        if (self.branch is None) != (self.hidden_rank is None):
            raise ValueError("藏干须同时保留地支和藏干次序")
        else:
            pass
        if self.branch is not None and self.hidden_rank is not None:
            hidden = BRANCH_HIDDEN_STEMS[self.branch]
            if self.hidden_rank >= len(hidden) or hidden[self.hidden_rank] != self.stem:
                raise ValueError("藏干须符合该支的实际藏干及次序")
            else:
                pass
        else:
            pass
        return self


class PresencePlane(PartialOutput):
    occurrences: list[PresenceOccurrence] | None = None
    present_elements: list[ElementName] | None = None
    absent_elements: list[ElementName] | None = None

    @model_validator(mode="after")
    def preserve_presence_complement(self) -> "PresencePlane":
        if self.present_elements is not None and len(set(self.present_elements)) != len(
            self.present_elements
        ):
            raise ValueError("出现五行不得重复")
        else:
            pass
        if self.absent_elements is not None and len(set(self.absent_elements)) != len(
            self.absent_elements
        ):
            raise ValueError("未出现五行不得重复")
        else:
            pass
        if self.occurrences is not None:
            positions = [(o.pillar, o.hidden_rank) for o in self.occurrences]
            if len(set(positions)) != len(positions):
                raise ValueError("同一实物字位不得重复列入该层")
            else:
                pass
            found = {o.element for o in self.occurrences}
            if (
                self.present_elements is not None
                and set(self.present_elements) != found
            ):
                raise ValueError("出现五行须忠于该层实际字位")
            else:
                pass
            if (
                self.absent_elements is not None
                and set(self.absent_elements) != {e.value for e in Element} - found
            ):
                raise ValueError("该层未出现五行须为实际出现的补集")
            else:
                pass
        else:
            pass
        if self.present_elements is not None and self.absent_elements is not None:
            if set(self.present_elements) & set(self.absent_elements) or set(
                self.present_elements + self.absent_elements
            ) != {e.value for e in Element}:
                raise ValueError("出现与未出现须完整互斥")
            else:
                pass
        else:
            pass
        return self


class ElementPresence(PartialOutput):
    method_id: Literal["physical_element_presence_planes_v1"] | None = None
    source: ForceSource | None = None
    visible_stems: PresencePlane | None = None
    principal_hidden_stems: PresencePlane | None = None
    all_hidden_stems: PresencePlane | None = None
    all_listed_elements: list[ElementName] | None = None
    absent_from_all_listed: list[ElementName] | None = None
    source_phrase_scope: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_plane_identity(self) -> "ElementPresence":
        for plane, hidden in (
            (self.visible_stems, False),
            (self.all_hidden_stems, True),
        ):
            if plane is not None and plane.occurrences is not None:
                if any(
                    (o.hidden_rank is not None) != hidden for o in plane.occurrences
                ):
                    raise ValueError("天干与藏干层不得互换")
                else:
                    pass
                if {o.pillar for o in plane.occurrences} != {
                    "year",
                    "month",
                    "day",
                    "hour",
                }:
                    raise ValueError("完整实物层须保留四柱字位")
                else:
                    pass
            else:
                pass
        principal = self.principal_hidden_stems
        if principal is not None and principal.occurrences is not None:
            if {o.pillar for o in principal.occurrences} != {
                "year",
                "month",
                "day",
                "hour",
            }:
                raise ValueError("完整本气层须保留四柱字位")
            else:
                pass
            if any(o.hidden_rank != 0 for o in principal.occurrences):
                raise ValueError("地支本气层只含实际第一藏干")
            else:
                pass
            if (
                self.all_hidden_stems is not None
                and self.all_hidden_stems.occurrences is not None
            ):
                expected = [
                    o for o in self.all_hidden_stems.occurrences if o.hidden_rank == 0
                ]
                if principal.occurrences != expected:
                    raise ValueError("本气须为全部藏干的实际子集")
                else:
                    pass
            else:
                pass
        else:
            pass
        if self.visible_stems is not None and self.all_hidden_stems is not None:
            visible, hidden_plane = (
                self.visible_stems.present_elements,
                self.all_hidden_stems.present_elements,
            )
            if visible is not None and hidden_plane is not None:
                found = set(visible + hidden_plane)
                if (
                    self.all_listed_elements is not None
                    and set(self.all_listed_elements) != found
                ):
                    raise ValueError("全局出现须为天干与全部藏干的并集")
                else:
                    pass
                if (
                    self.absent_from_all_listed is not None
                    and set(self.absent_from_all_listed)
                    != {e.value for e in Element} - found
                ):
                    raise ValueError("全局未出现须为实际并集的补集")
                else:
                    pass
            else:
                pass
        else:
            pass
        return self
