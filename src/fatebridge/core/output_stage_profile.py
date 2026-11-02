"""Partial-safe provenance for the actual fixed twelve-stage lookup."""

import hashlib
import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


class StageAnchor(PartialOutput):
    growth_branch: Optional[Branch] = None
    direction: Optional[Literal[-1, 1]] = None


class LifeStageProfile(PartialOutput):
    profile_id: Optional[Literal["ten_stem_yang_forward_yin_reverse_fire_earth_v1"]] = (
        None
    )
    branch_cycle: Optional[List[Branch]] = Field(
        default=None, min_length=12, max_length=12
    )
    stage_cycle: Optional[List[str]] = Field(default=None, min_length=12, max_length=12)
    growth_starts: Optional[Dict[Stem, StageAnchor]] = None
    lookup_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    soil_convention: Optional[str] = None
    source_basis: Optional[
        Literal["implementation_lookup_with_selected_text_crosscheck"]
    ] = None
    sources: Optional[List[Dict[str, Any]]] = None
    independent_expert_review: Optional[Literal["not_completed"]] = None
    calculation_effect: Optional[Literal["none_existing_values_only"]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_lookup_digest(self) -> "LifeStageProfile":
        if self.branch_cycle is not None and len(set(self.branch_cycle)) != 12:
            raise ValueError("十二支查表顺序不能丢失或重复地支")
        if self.stage_cycle is not None and len(set(self.stage_cycle)) != 12:
            raise ValueError("十二阶段查表顺序不能丢失或重复阶段")
        if (
            self.lookup_sha256 is not None
            and self.branch_cycle is not None
            and self.stage_cycle is not None
            and self.growth_starts is not None
            and len(self.growth_starts) == 10
            and all(
                a.growth_branch is not None and a.direction is not None
                for a in self.growth_starts.values()
            )
        ):
            lookup = {
                "branch_cycle": self.branch_cycle,
                "stage_cycle": self.stage_cycle,
                "growth_starts": {
                    # The receipt hashes lookup inputs, not unrelated future
                    # annotations retained by the partial-output contract.
                    s: a.model_dump(
                        include={"growth_branch", "direction"}, exclude_none=True
                    )
                    for s, a in self.growth_starts.items()
                },
            }
            actual = hashlib.sha256(
                json.dumps(
                    lookup, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            if actual != self.lookup_sha256:
                raise ValueError("阶段查表参数必须与同次查表散列一致")
        return self
