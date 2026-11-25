"""Projection-compatible contracts for actual storage-earth root receipts."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class StorageRootEffect(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    stem: str | None = None
    element: str | None = None
    ten_god: str | None = None
    event_retention_multiplier: float | None = Field(default=None, ge=0, le=1)
    combined_loss_multiplier: float | None = Field(default=None, ge=0, le=1)
    remaining_hidden_mass: float | None = Field(default=None, ge=0)
    basis: str | None = None

    @model_validator(mode="after")
    def preserve_event_scope(self) -> "StorageRootEffect":
        if (
            self.element is not None
            and self.element != "水"
            and self.event_retention_multiplier is not None
            and self.event_retention_multiplier != 1
        ):
            raise ValueError("四墓土冲动事件不能虚构其他藏干的统一减损或增量")
        else:
            pass
        if (
            self.combined_loss_multiplier is not None
            and self.event_retention_multiplier is not None
            and self.combined_loss_multiplier > self.event_retention_multiplier
        ):
            raise ValueError("最终损耗因子不能撤销本事件已经记录的减损")
        else:
            pass
        return self


class StorageMovementEffect(PartialOutput):
    method_id: Literal["ziping_storage_movement_v1"] | None = None
    movement_kind: Literal["same_element_earth_movement"] | None = None
    root_effects: list[StorageRootEffect] | None = None
    earth_energy_bonus: float | None = Field(default=None, ge=0, le=0)
    water_retention_policy: float | None = Field(default=None, ge=0, le=1)
    numeric_magnitude_origin: (
        Literal["engineering_policy_not_classical_coefficient"] | None
    ) = None
    formation_status: Literal["not_adjudicated"] | None = None
    source: dict[str, OpenJsonValue] | None = None
    scope: str | None = None

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
                else:
                    pass
        else:
            pass
        return self


class StorageMovementEvent(PartialOutput):
    kind: Literal["六冲", "刑"] | None = None
    positions: list[str] | None = None
    status: Literal["active"] | None = None
    clash_mode: Literal["storage_earth_movement"] | None = None
    storage_effect: StorageMovementEffect | None = None
    source_id: str | None = None
