"""Selected Shen fixed-ground zero/regular deity and independently observed forms."""

from typing import List, Literal, Optional

from pydantic import ConfigDict, Field, StrictBool, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel


class LingzhengObservation(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": [key], "properties": {key: {"type": "boolean"}}}
                for key in (
                    "high_solid_terrain_present",
                    "low_lying_terrain_present",
                    "river_water_present",
                )
            ]
        }
    )
    direction: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    high_solid_terrain_present: Optional[StrictBool] = None
    low_lying_terrain_present: Optional[StrictBool] = None
    river_water_present: Optional[StrictBool] = Field(
        default=None,
        description="原按语河流的外部水体存在事实；一般有水、室内水杯、水景或摆件不能直接代替河流",
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")

    @model_validator(mode="after")
    def observed_facts(self) -> "LingzhengObservation":
        if all(
            getattr(self, name) is None
            for name in (
                "high_solid_terrain_present",
                "low_lying_terrain_present",
                "river_water_present",
            )
        ):
            raise ValueError("零正形势须至少有一项明确存在或不存在的事实")
        return self


class FixedLingzhengRequest(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {
                    "properties": {
                        "five_period_half": {"type": "null"},
                        "half_evidence": {"type": "null"},
                    }
                },
                {
                    "required": ["five_period_half", "half_evidence"],
                    "properties": {
                        "five_period_half": {"type": "string"},
                        "half_evidence": {"type": "string"},
                    },
                },
            ]
        }
    )
    ruleset_id: Literal["shen_fixed_lingzheng_v1"] = "shen_fixed_lingzheng_v1"
    five_period_half: Optional[Literal["first_decade", "second_decade"]] = Field(
        default=None,
        description="仅明确评价五运时确认前十年或后十年，不从历史宅运或系统日期推断",
    )
    half_evidence: Optional[str] = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )
    observations: List[LingzhengObservation] = Field(
        default_factory=list,
        max_length=8,
        json_schema_extra={
            "allOf": [
                {
                    "contains": {
                        "type": "object",
                        "properties": {"direction": {"const": d}},
                        "required": ["direction"],
                    },
                    "minContains": 0,
                    "maxContains": 1,
                }
                for d in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
            ]
        },
        description="全宅中心磁北八宫的高实、低洼及外部河流事实分别确认；互不以否定或摆件名推定",
    )

    @model_validator(mode="after")
    def explicit_half_and_unique_directions(self) -> "FixedLingzhengRequest":
        if (self.five_period_half is None) != (self.half_evidence is None):
            raise ValueError("五运分段与half_evidence必须一起提供")
        if len({o.direction for o in self.observations}) != len(self.observations):
            raise ValueError("零正外局同一方向不可重复")
        return self
