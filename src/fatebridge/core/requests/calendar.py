"""Request contracts for calendar."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationInfo, field_validator

from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.utils.coordinates import parse_geo_coordinate


class LocalLocationFields(FateBridgeBaseRequest):
    """Shared timezone and coordinate fields for local calendar and divination requests."""

    timezone: str | None = Field(
        default=None,
        description="Timezone spec (IANA name or UTC offset, e.g. Asia/Shanghai or +08:00)",
    )
    latitude: float | str | None = Field(
        default=None,
        validate_default=True,
        description="Latitude in decimal degrees or text (e.g. 31.23 or '31n13')",
    )
    longitude: float | str | None = Field(
        default=None,
        validate_default=True,
        description="Longitude in decimal degrees or text (e.g. 121.47 or '121e28')",
    )

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _parse_local_coordinate(
        cls, value: object, info: ValidationInfo
    ) -> float | None:
        axis: Literal["latitude", "longitude"] = (
            "latitude" if info.field_name == "latitude" else "longitude"
        )
        return parse_geo_coordinate(value, axis=axis)


class JieqiYearRequest(LocalLocationFields):
    """Request model for annual jieqi helper output."""

    year: int = Field(description="Target year, e.g. 2028")
    timezone: str | None = Field(default="Asia/Shanghai", description="Timezone spec")
    jieqis: list[str] = Field(
        default_factory=list, description="Optional focused jieqi names"
    )


class NongliTimeRequest(LocalLocationFields):
    """Request model for nongli-time helper output."""

    date: str = Field(description="Date string, e.g. 2028-04-01")
    time: str = Field(description="Time string, e.g. 09:00:00")
    timezone: str | None = Field(default="Asia/Shanghai", description="Timezone spec")
    analysis_utc_offset: str | None = Field(
        default=None,
        description="已确认的民用 UTC 偏移，格式 ±HH:MM 或 ±HH:MM:SS，用于消歧重复钟时",
    )
    gender: str | None = Field(
        default=None,
        description=(
            "性别（可选，仅作元数据透传回显，不参与农历/节气/干支计算）。"
            "接受 男/女、male/female/m/f 等写法；省略则不回显。"
        ),
    )
    time_alg: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Time algorithm: 0=true solar time (requires longitude), 1=direct clock time",
    )
    ad: int = Field(
        default=1,
        description="Common era flag; offline nongli conversion supports ad=1 only within 1900-01-01 to 2100-12-31",
    )
