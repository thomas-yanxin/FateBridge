"""Observed attributes and an optional representation-use question, not natal needs."""

from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from fatebridge.core.fengshui.numeric_inputs import FengshuiInput as _DeferredModel
from fatebridge.core.fengshui.workstation_inputs import MaterialApplication

Material = Literal[
    "wood",
    "processed_wood",
    "living_plant",
    "metal",
    "stone",
    "ceramic",
    "glass",
    "plastic",
    "textile",
    "water",
    "mixed",
    "unknown",
]
Shape = Literal[
    "columnar", "triangular", "square", "round", "wavy", "irregular", "unknown"
]
Colour = Literal[
    "green",
    "red",
    "tan",
    "brown",
    "beige",
    "yellow",
    "white",
    "gold",
    "blue",
    "black",
    "other",
    "mixed",
    "unknown",
]
ElementUse = Literal[
    "wood_remedy", "fire_remedy", "earth_remedy", "metal_remedy", "water_remedy"
]


class MaterialShapeFact(_DeferredModel):
    fact_id: str = Field(min_length=1, max_length=100)
    object_id: str = Field(min_length=1, max_length=100)
    material: Material | None = None
    shape: Shape | None = None
    colour: Colour | None = None
    element_use: ElementUse | None = Field(
        default=None,
        description="用户明确询问该物可否充当某元素代表物；不是所需/喜用元素，不证明任意宫位需要它或可立即摆放",
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000)
    plant_alive: StrictBool | None = Field(
        default=None,
        description="仅living_plant的存活状态；不得由绿色/照片外观补为确认存活",
    )
    application: MaterialApplication | None = Field(
        default=None,
        description="显式选AFSI附加条件；属性资格与尺度/运行/目标绑定分开，不认证摆位或效力",
    )

    @field_validator("fact_id", "object_id", "evidence")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("材质器形事实的ID与依据不能为空白")
        else:
            pass
        return value

    @model_validator(mode="after")
    def observed_attributes(self) -> "MaterialShapeFact":
        if self.material is None and self.shape is None and self.colour is None:
            raise ValueError(
                "材质器形事实至少提供一种实际属性；未知用unknown，不以目标代替观察"
            )
        else:
            pass
        if self.plant_alive is not None and self.material != "living_plant":
            raise ValueError("plant_alive只用于明确的living_plant")
        else:
            pass
        if self.application is not None:
            if self.element_use is None:
                raise ValueError("材料施用条件须有明确 element_use 问题")
            else:
                pass
            allowed = {
                "water_clean": "water",
                "water_moving": "water",
                "metal_exposed": "metal",
                "plant_healthy": "living_plant",
            }
            for field, material in allowed.items():
                if (
                    getattr(self.application, field) is not None
                    and self.material != material
                ):
                    raise ValueError("施用观察须与独立确认的实际材质一致")
                else:
                    pass
            if (
                self.application.proportionate_to_space is not None
                and self.material
                not in {"metal", "water", "stone", "ceramic", "living_plant"}
            ):
                raise ValueError("尺度条件仅用于已登记的实际代表物材质")
            else:
                pass
            healthy = self.application.plant_healthy
            if (
                healthy
                and healthy.value is True
                and healthy.observation_basis != "image_observed"
                and self.plant_alive is False
                and self.observation_basis != "image_observed"
            ):
                raise ValueError("已确认死亡植物不能同时确认健康存活")
            else:
                pass
        else:
            pass
        return self
