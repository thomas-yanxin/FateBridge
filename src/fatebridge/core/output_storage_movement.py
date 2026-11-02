"""Projection-compatible contracts for actual storage-earth root receipts."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class StorageRootEffect(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stem: Optional[str] = None
    element: Optional[str] = None
    ten_god: Optional[str] = None
    event_retention_multiplier: Optional[float] = Field(default=None, ge=0, le=1)
    combined_loss_multiplier: Optional[float] = Field(default=None, ge=0, le=1)
    remaining_hidden_mass: Optional[float] = Field(default=None, ge=0)
    basis: Optional[str] = None

    @model_validator(mode="after")
    def preserve_event_scope(self) -> "StorageRootEffect":
        if (
            self.element is not None
            and self.element != "水"
            and self.event_retention_multiplier is not None
            and self.event_retention_multiplier != 1
        ):
            raise ValueError("四墓土冲动事件不能虚构其他藏干的统一减损或增量")
        if (
            self.combined_loss_multiplier is not None
            and self.event_retention_multiplier is not None
            and self.combined_loss_multiplier > self.event_retention_multiplier
        ):
            raise ValueError("最终损耗因子不能撤销本事件已经记录的减损")
        return self


class StorageMovementEffect(PartialOutput):
    method_id: Optional[Literal["ziping_storage_movement_v1"]] = None
    movement_kind: Optional[Literal["same_element_earth_movement"]] = None
    root_effects: Optional[List[StorageRootEffect]] = None
    earth_energy_bonus: Optional[float] = Field(default=None, ge=0, le=0)
    water_retention_policy: Optional[float] = Field(default=None, ge=0, le=1)
    numeric_magnitude_origin: Optional[
        Literal["engineering_policy_not_classical_coefficient"]
    ] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None
    source: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_policy_factor(self) -> "StorageMovementEffect":
        if self.water_retention_policy is not None:
            for root in self.root_effects or []:
                if (
                    root.element == "水"
                    and root.event_retention_multiplier is not None
                    and root.event_retention_multiplier != self.water_retention_policy
                ):
                    raise ValueError("水根事件因子与实际记录的工程政策不一致")
        return self


class StorageMovementEvent(PartialOutput):
    kind: Optional[Literal["六冲", "刑"]] = None
    positions: Optional[List[str]] = None
    status: Optional[Literal["active"]] = None
    clash_mode: Optional[Literal["storage_earth_movement"]] = None
    storage_effect: Optional[StorageMovementEffect] = None
    source_id: Optional[str] = None
