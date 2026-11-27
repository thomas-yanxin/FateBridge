"""Request contracts for calendar."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

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
    place: str | None = Field(
        default=None,
        description="地点名称（支持离线地名库自动补全 longitude / latitude / timezone）",
    )

    @field_validator("latitude", mode="before")
    @classmethod
    def _parse_local_latitude(cls, value: object) -> float | None:
        return parse_geo_coordinate(value, axis="latitude")

    @field_validator("longitude", mode="before")
    @classmethod
    def _parse_local_longitude(cls, value: object) -> float | None:
        return parse_geo_coordinate(value, axis="longitude")

    @model_validator(mode="after")
    def _resolve_local_place(self) -> "LocalLocationFields":
        place_text = (self.place or "").strip()
        if not place_text or place_text == "未提供":
            return self
        need_lon = self.longitude is None or "longitude" not in self.model_fields_set
        need_lat = self.latitude is None or "latitude" not in self.model_fields_set
        need_tz = self.timezone is None or "timezone" not in self.model_fields_set
        if not (need_lon or need_lat or need_tz):
            return self
        from fatebridge.utils.places import resolve_place_location

        resolved = resolve_place_location(place_text, place_field="place")
        if need_lon:
            self.longitude = resolved.longitude
        if need_lat:
            self.latitude = resolved.latitude
        if need_tz and resolved.timezone is not None:
            self.timezone = resolved.timezone
        return self

    def service_inputs(self) -> dict[str, object]:
        return self.model_dump(exclude={"place"})


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
