"""Request contracts for birth."""

from __future__ import annotations

from datetime import MAXYEAR, MINYEAR
from typing import Annotated, Literal

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from fatebridge.core.bazi.policies import (
    ChangshengSchool,
    DutyProfile,
    ZiHourPolicy,
)
from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.utils.birth_input import MAX_PERSON_BIRTH_YEAR, MIN_PERSON_BIRTH_YEAR


class BirthClockBase(FateBridgeBaseRequest):
    """Shared birth clock and optional place/longitude fields across domains."""

    name: str | None = Field(
        default="未提供",
        description="姓名（可选，仅用于结果标识，不参与计算）",
    )
    birth_year: int = Field(description="Birth year")
    birth_month: int = Field(ge=1, le=12, description="Birth month (1-12)")
    birth_day: int = Field(ge=1, le=31, description="Birth day (1-31)")
    birth_hour: int = Field(ge=0, le=23, description="Birth hour (0-23)")
    birth_minute: int = Field(default=0, ge=0, le=59, description="Birth minute (0-59)")
    birth_place: str | None = Field(
        default="未提供", description="Birth place (optional)"
    )
    birth_timezone: str | None = Field(
        default=None, description="Birth timezone (IANA name or UTC offset)"
    )
    birth_longitude: float | None = Field(
        default=None, ge=-180, le=180, description="Birth longitude (optional)"
    )


class FateBridgeRequest(BirthClockBase):
    """Request model for individual destiny analysis"""

    gender: str | None = Field(
        default="未知",
        description=(
            "性别（可选但建议提供：影响大运顺逆排布与部分六亲判断）。"
            "接受 男/女、male/female/m/f、阳/阴、乾/坤 等写法。"
        ),
    )
    birth_year: int = Field(
        ge=MIN_PERSON_BIRTH_YEAR,
        le=MAX_PERSON_BIRTH_YEAR,
        description="Birth year (1900–2100, the existing individual-birth service range)",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description=(
            "Rebase the birth clock onto true solar time (longitude + equation of "
            "time). Default on in the current software policy; this option does "
            "not certify a classical text's clock rule. Set false for the raw civil clock."
        ),
    )


class BaziClockRequest(FateBridgeRequest):
    """Known clock components and explicit civil-offset selection for BaZi."""

    birth_utc_offset: str | None = Field(
        default=None,
        strict=True,
        description=(
            "已确认的出生民用UTC偏移，格式±HH:MM或±HH:MM:SS；用于消歧重复钟时。"
            "必须与解析出的birth_timezone在该钟时的规则一致；不据此猜测时区，"
            "不替未知的重复小时选边，不能使跳过的钟时有效。保留原IANA时区用于"
            "后续交运边界；不认证出生记录精度。未知请省略或传null。"
        ),
    )

    birth_second: int | None = Field(
        default=None,
        ge=0,
        le=59,
        strict=True,
        description=(
            "已知出生秒数0–59；提供时必须显式提供birth_minute。"
            "未知请省略或传null；沿用00秒作为兼容计算参考，并返回省略分量说明，"
            "不代表已知出生在整分、不推定误差区间或记录精度。不接受闰秒60。"
        ),
    )
    zi_hour_policy: ZiHourPolicy = Field(
        default="day_rollover_at_23",
        description=(
            "早晚子时（23:00–23:59）流派：day_rollover_at_23（sect=1，23时换日柱，五鼠遁按次日干）"
            " | night_zi_same_day_next_hour_stem（sect=2，夜子时日柱不换，时干按次日五鼠遁）"
            " | night_zi_same_day_same_hour_stem（夜子时日柱不换，时干按当日五鼠遁）。"
        ),
    )
    changsheng_school: ChangshengSchool = Field(
        default="fire_earth_same_palace",
        description=(
            "十二长生流派：fire_earth_same_palace（火土同宫，戊随丙、己随丁）"
            " | water_earth_same_palace（水土同宫，戊随壬、己随癸）"
            " | five_element_same_stage（五行同生同死）。"
        ),
    )
    duty_profile: DutyProfile = Field(
        default="sanming",
        description="人元司令分野分日表：sanming（三命通会）| yuanhai（渊海子平）| 6tail | ditian（滴天髓）。",
    )

    @model_validator(mode="after")
    def seconds_require_minute(self) -> BaziClockRequest:
        if (
            self.birth_second is not None
            and "birth_minute" not in self.model_fields_set
        ):
            raise PydanticCustomError(
                "birth_second_requires_minute",
                "birth_second需要显式提供birth_minute；不能替未知分钟填0",
                {"path": "birth_minute", "required_with": "birth_second"},
            )
        return self


AstroBirthYear = Annotated[int, Field(ge=MINYEAR, le=MAXYEAR)]


class AstroBirthBase(BirthClockBase):
    """Shared astrology birth request with optional coordinates."""

    name: str | None = Field(default="未提供", description="Name (optional)")
    birth_year: AstroBirthYear = Field(description="Birth year, e.g., 1990")
    birth_timezone: str | None = Field(
        default=None,
        description=(
            "Birth timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from a supported birth_place. Western "
            "charts and timing reject an unresolved civil timezone; coordinates "
            "alone do not establish a zone. Supply UTC explicitly when that is "
            "the confirmed recorded basis. Place inference does not certify "
            "historical clock accuracy."
        ),
    )
    birth_latitude: float | None = Field(
        default=None, ge=-90, le=90, description="Birth latitude (optional)"
    )
    birth_place: str | None = Field(default="未提供", description="Birth place")


class AstroBirthRequest(AstroBirthBase):
    """Base birth request model accepting coordinates or a supported birth_place."""

    gender: str | None = Field(
        default=None,
        description="性别（可选，用于批量/跨工具参数对称；西方推运计算不使用性别）。",
    )
    birth_second: int | None = Field(
        default=None,
        ge=0,
        le=59,
        description="出生秒数（0-59，可选，用于跨工具参数对称）。",
    )
    birth_utc_offset: str | None = Field(
        default=None,
        description="已确认的出生民用UTC偏移（±HH:MM或±HH:MM:SS，可选，用于跨工具参数对称）。",
    )
    birth_place: str | None = Field(
        default=None,
        description="Birth place (optional; when coordinates/timezone are omitted, resolved lazily via supported city catalog)",
    )
    birth_longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="Birth longitude (optional when birth_place is given)",
    )
    birth_latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="Birth latitude (optional when birth_place is given)",
    )

    @model_validator(mode="after")
    def _require_coordinates_or_place(self) -> AstroBirthRequest:
        if self.birth_longitude is None or self.birth_latitude is None:
            place = (self.birth_place or "").strip()
            if not place or place == "未提供":
                missing_path = (
                    "birth_longitude"
                    if self.birth_longitude is None
                    else "birth_latitude"
                )
                raise PydanticCustomError(
                    "missing_coordinates",
                    "需要 birth_longitude / birth_latitude，或提供 FateBridge 支持的 birth_place 以补全坐标",
                    {"path": missing_path},
                )
        return self

    def service_inputs(self) -> dict[str, object]:
        from fatebridge.core.astro.birth import resolve_astro_birth_request_inputs

        return resolve_astro_birth_request_inputs(self.model_dump())
