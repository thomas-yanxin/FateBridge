"""Explicit geodetic inputs for a dated magnetic reference, never a site survey."""

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import ConfigDict, Field, StrictFloat, field_validator, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel


class GeomagneticReference(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {
                    "required": [selected],
                    "properties": {selected: {"not": {"type": "null"}}},
                    "not": {
                        "required": [other],
                        "properties": {other: {"not": {"type": "null"}}},
                    },
                }
                for selected, other in (
                    ("model_date", "decimal_year"),
                    ("decimal_year", "model_date"),
                )
            ]
        }
    )
    model_id: Literal["wmm2025_v1"] = "wmm2025_v1"
    latitude: StrictFloat = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: StrictFloat = Field(ge=-180, le=180, allow_inf_nan=False)
    height_km_wgs84: StrictFloat = Field(
        ge=-1,
        le=850,
        allow_inf_nan=False,
        description="WGS84椭球高，单位km；必须明确提供，海拔/MSL高不可直接代替",
    )
    model_date: Optional[date] = Field(
        default=None,
        ge=date(2025, 1, 1),
        lt=date(2030, 1, 1),
        json_schema_extra={"pattern": r"^202[5-9]-\d{2}-\d{2}$"},
        description="UTC参考日期，按当日00:00换算小数年；与decimal_year二选一，不推断测量时刻",
    )
    decimal_year: Optional[StrictFloat] = Field(
        default=None, ge=2025, lt=2030, allow_inf_nan=False
    )
    evidence: str = Field(
        min_length=1,
        pattern=r"\S",
        description="地点、椭球高和参考日期来源；虚构测试需明确标注",
    )

    @field_validator("model_date", mode="before")
    @classmethod
    def explicit_date(cls, value: object) -> object:
        if value is None or (
            isinstance(value, date) and not isinstance(value, datetime)
        ):
            return value
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        raise ValueError("model_date须为明确的YYYY-MM-DD日期，不能以时间戳或时刻代替")

    @model_validator(mode="after")
    def exactly_one_time(self) -> "GeomagneticReference":
        if (self.model_date is None) == (self.decimal_year is None):
            raise ValueError("model_date和decimal_year须且只能提供一项")
        return self

    def year_value(self) -> float:
        if self.decimal_year is not None:
            return self.decimal_year
        assert self.model_date is not None
        year = self.model_date.year
        return (
            year
            + (self.model_date - date(year, 1, 1)).days
            / (date(year + 1, 1, 1) - date(year, 1, 1)).days
        )
