"""Compose scene inputs and resolved search domains at the request boundary."""

from typing import Literal

from pydantic import Field, PrivateAttr, model_validator

from .numeric_inputs import FengshuiInput
from .spatial_domains import resolve_search_domains
from .spatial_inputs import Evidence, ResolvedMoveDomain, SpatialScene, SpatialSearch


class WorkstationLayoutInput(FengshuiInput):
    _resolved_domains: list[ResolvedMoveDomain] = PrivateAttr(default_factory=list)
    ruleset_id: Literal["workstation_layout_v1"] = "workstation_layout_v1"
    scene: SpatialScene
    search: SpatialSearch | None = None
    evaluation_period: int | None = Field(default=None, ge=1, le=9)
    evaluation_period_evidence: Evidence | None = None
    timeliness_ruleset_id: Literal["wang_zhongzhou_timeliness_v1"] | None = None

    @model_validator(mode="after")
    def scope(self) -> "WorkstationLayoutInput":
        if (self.evaluation_period is None) != (
            self.evaluation_period_evidence is None
        ):
            raise ValueError("评价运及其依据须成对，不从宅运/查询日期补值")
        if self.search:
            movable = {
                b.object_id
                for b in self.scene.bodies
                if b.kind in {"desk", "furniture", "screen", "plant"}
            }
            movable.update(
                item.object_id for d in self.scene.desktops for item in d.items
            )
            if any(d.object_id not in movable for d in self.search.domains):
                raise ValueError(
                    "搜索只能移动已登记家具/物件；不移动门窗、梁柱和空间边界"
                )
            self._resolved_domains = resolve_search_domains(self.scene, self.search)
        return self

    @property
    def resolved_domains(self) -> list[ResolvedMoveDomain]:
        return self._resolved_domains
