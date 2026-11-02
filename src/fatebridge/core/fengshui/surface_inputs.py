"""A seated desktop is a separate authored reference frame, never a house palace."""

from typing import List, Literal, Optional

from pydantic import ConfigDict, Field, StrictBool, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel

SurfaceZone = Literal[
    "near_left",
    "near_center",
    "near_right",
    "middle_left",
    "middle_center",
    "middle_right",
    "far_left",
    "far_center",
    "far_right",
]
Representation = Literal[
    "living_plant", "fresh_flowers", "water_image", "dark_accessory", "other", "unknown"
]


class SurfaceItem(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {
                    "properties": {
                        "zone": {"type": "null"},
                        "zone_observation_basis": {"type": "null"},
                    }
                },
                {
                    "required": ["zone", "zone_observation_basis"],
                    "properties": {
                        "zone": {"type": "string"},
                        "zone_observation_basis": {"type": "string"},
                    },
                },
            ]
        }
    )
    object_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    representation: Representation = Field(
        description="已确认的作者规则代表物；手机、饮料瓶、普通玩偶不自动当火、水或土",
    )
    zone: Optional[SurfaceZone] = Field(
        default=None,
        description="near靠身体的桌沿，far是远离身体的桌沿；near_right为右前近沿，far_left为左后远沿。未知位置省略/null；只确认左右不补近远",
    )
    zone_observation_basis: Optional[
        Literal["measured", "user_confirmed", "image_observed"]
    ] = Field(
        default=None,
        description="位置的独立证据；确认是真植物不等于确认其九格位置，照片估计用image_observed",
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def meaningful_evidence(self) -> "SurfaceItem":
        if not self.label.strip() or not self.evidence.strip():
            raise ValueError("物件名称与观察依据不能空白")
        if (self.zone is None) != (self.zone_observation_basis is None):
            raise ValueError("zone与zone_observation_basis必须成对，未知位置两者省略")
        return self


class SurfaceLayout(_DeferredModel):
    object_id: str = Field(min_length=1, max_length=100)
    ruleset_id: Literal["desktop_bagua_btb_v1"]
    shape: Literal["rectangular"]
    anchor: Literal["seated_near_edge"] = Field(
        description="坐着使用的桌沿为近侧；远左不是东南宫，不与罗盘或年星混用"
    )
    goal: Literal["career", "abundance"] = Field(
        description="用户确认的目标；当前作者处方覆盖事业与丰盛，不由生辰推断"
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000)
    items: List[SurfaceItem] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def surface_evidence(self) -> "SurfaceLayout":
        if not self.evidence.strip():
            raise ValueError("桌面边界与使用参考系需观察依据")
        ids = [item.object_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("同一桌面的物件 ID 不能重复")
        return self


class SurfaceConstraints(_DeferredModel):
    """Action permissions and confirmed feasibility, not observations of qi."""

    object_id: str = Field(min_length=1, max_length=100)
    can_move_items: Optional[StrictBool] = None
    can_add_items: Optional[StrictBool] = None
    locked_item_ids: List[str] = Field(default_factory=list, max_length=100)
    unavailable_zones: List[SurfaceZone] = Field(default_factory=list, max_length=9)
    feasible_zones: List[SurfaceZone] = Field(
        default_factory=list,
        max_length=9,
        description="只列用户逐区明确确认能容纳对象且保留入口视野的区域；照片空白、材质确认或移动许可不能证明其他区域可行",
    )
    evidence: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def separate_feasibility(self) -> "SurfaceConstraints":
        if not self.evidence.strip():
            raise ValueError("动作约束需用户依据")
        for values in (
            self.locked_item_ids,
            self.unavailable_zones,
            self.feasible_zones,
        ):
            if len(values) != len(set(values)):
                raise ValueError("动作约束不能重复")
        if set(self.unavailable_zones) & set(self.feasible_zones):
            raise ValueError("同一区域不能同时可行与不可用")
        return self
