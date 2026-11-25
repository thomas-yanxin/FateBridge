"""Request contracts for calendar."""

from __future__ import annotations

from pydantic import Field

from fatebridge.core.requests.base import _DeferredModel


class JieqiYearRequest(_DeferredModel):
    """Request model for annual jieqi helper output."""

    year: int = Field(description="Target year, e.g. 2028")
    zone: str | None = Field(default="Asia/Shanghai", description="Timezone spec")
    lat: str | None = Field(default=None, description="Latitude text hint")
    lon: str | None = Field(default=None, description="Longitude text hint")
    gps_lat: float | None = Field(default=None, description="GPS latitude")
    gps_lon: float | None = Field(default=None, description="GPS longitude")
    jieqis: list[str] = Field(
        default_factory=list, description="Optional focused jieqi names"
    )
    selected_sections: list[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class NongliTimeRequest(_DeferredModel):
    """Request model for nongli-time helper output."""

    date: str = Field(description="Date string, e.g. 2028-04-01")
    time: str = Field(description="Time string, e.g. 09:00:00")
    zone: str | None = Field(default="Asia/Shanghai", description="Timezone spec")
    analysis_utc_offset: str | None = Field(
        default=None,
        description="已确认的民用 UTC 偏移，格式 ±HH:MM 或 ±HH:MM:SS，用于消歧重复钟时",
    )
    lat: str | None = Field(default=None, description="Latitude text hint")
    lon: str | None = Field(default=None, description="Longitude text hint")
    gps_lat: float | None = Field(default=None, description="GPS latitude")
    gps_lon: float | None = Field(default=None, description="GPS longitude")
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
    selected_sections: list[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
