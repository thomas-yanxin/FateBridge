"""Explicit period and observed water forms for the selected Shen city-gate rule."""

from typing import List, Literal, Optional, get_args

from pydantic import ConfigDict, Field, StrictBool, StrictInt, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel

Mountain = Literal[
    "子",
    "癸",
    "丑",
    "艮",
    "寅",
    "甲",
    "卯",
    "乙",
    "辰",
    "巽",
    "巳",
    "丙",
    "午",
    "丁",
    "未",
    "坤",
    "申",
    "庚",
    "酉",
    "辛",
    "戌",
    "乾",
    "亥",
    "壬",
]

_FACTS = (
    "water_present",
    "multiple_openings_present",
    "encircling_form_present",
    "sole_opening_with_water",
    "three_way_water_junction_present",
    "water_reflects_towards_site",
)


class CityGateObservation(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": [key], "properties": {key: {"type": "boolean"}}}
                for key in _FACTS
            ],
            "allOf": [
                {
                    "not": {
                        "required": [left, right],
                        "properties": {left: {"const": lv}, right: {"const": rv}},
                    }
                }
                for left, lv, right, rv in [
                    ("water_present", False, key, True)
                    for key in (
                        "sole_opening_with_water",
                        "three_way_water_junction_present",
                        "water_reflects_towards_site",
                    )
                ]
                + [("sole_opening_with_water", True, "multiple_openings_present", True)]
            ],
        }
    )
    mountain: Mountain = Field(
        description="相对全宅中心、磁北二十四山的实际水路山位；八宫名不能代替同元龙山位"
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    water_present: Optional[StrictBool] = None
    multiple_openings_present: Optional[StrictBool] = Field(
        default=None, description="四周是否存在多个缺口；原文将此列为排除条件"
    )
    encircling_form_present: Optional[StrictBool] = None
    sole_opening_with_water: Optional[StrictBool] = Field(
        default=None,
        description="已确认四周仅此缺口且水口在此；不是仅有一个水口而四周另有缺口",
    )
    three_way_water_junction_present: Optional[StrictBool] = None
    water_reflects_towards_site: Optional[StrictBool] = None

    @model_validator(mode="after")
    def coherent_observation(self) -> "CityGateObservation":
        if not any(getattr(self, key) is not None for key in _FACTS):
            raise ValueError("城门观察须至少提供一项明确形势事实")
        if self.water_present is False and any(
            getattr(self, key) is True
            for key in (
                "sole_opening_with_water",
                "three_way_water_junction_present",
                "water_reflects_towards_site",
            )
        ):
            raise ValueError("无水与明确水口/三叉水/水光事实不得冲突")
        if (
            self.sole_opening_with_water is True
            and self.multiple_openings_present is True
        ):
            raise ValueError("唯一缺口与多个缺口不得同时为真")
        return self


class CityGateRequest(_DeferredModel):
    ruleset_id: Literal["shen_city_gate_v1"] = "shen_city_gate_v1"
    reference_period_number: StrictInt = Field(
        ge=1,
        le=9,
        description="本次城门运盘的明确参考运；独立于历史宅运，不从当前日期、年星或宅运暗中补出",
    )
    period_evidence: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    observations: List[CityGateObservation] = Field(
        default_factory=list,
        max_length=24,
        json_schema_extra={
            "allOf": [
                {
                    "contains": {
                        "type": "object",
                        "properties": {"mountain": {"const": name}},
                        "required": ["mountain"],
                    },
                    "minContains": 0,
                    "maxContains": 1,
                }
                for name in get_args(Mountain)
            ]
        },
        description="按需核对的实际水形；不传时只计算数字门位，不追问现场资料，不把道路或摆件自动当水",
    )

    @model_validator(mode="after")
    def unique_mountains(self) -> "CityGateRequest":
        values = [o.mountain for o in self.observations]
        if len(values) != len(set(values)):
            raise ValueError("同一城门山位不可重复或覆盖观察")
        return self
