"""Request contracts for birth."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from fatebridge.core.requests.base import _DeferredModel
from fatebridge.utils.birth_input import MAX_PERSON_BIRTH_YEAR, MIN_PERSON_BIRTH_YEAR


class FateBridgeRequest(_DeferredModel):
    """Request model for individual destiny analysis"""

    name: Optional[str] = Field(
        default="未提供",
        description="姓名（可选，仅用于结果快照中的标识，不参与计算）",
    )
    gender: Optional[str] = Field(
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
    birth_month: int = Field(ge=1, le=12, description="Birth month (1-12)")
    birth_day: int = Field(ge=1, le=31, description="Birth day (1-31)")
    birth_hour: int = Field(ge=0, le=23, description="Birth hour (0-23)")
    birth_minute: int = Field(default=0, ge=0, le=59, description="Birth minute (0-59)")
    birth_place: Optional[str] = Field(
        default="未提供", description="Birth place (optional)"
    )
    birth_timezone: Optional[str] = Field(
        default=None, description="Birth timezone (IANA name or UTC offset)"
    )
    birth_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Birth longitude (optional)"
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

    birth_utc_offset: Optional[str] = Field(
        default=None,
        strict=True,
        description=(
            "已确认的出生民用UTC偏移，格式±HH:MM或±HH:MM:SS；用于消歧重复钟时。"
            "必须与解析出的birth_timezone在该钟时的规则一致；不据此猜测时区，"
            "不替未知的重复小时选边，不能使跳过的钟时有效。保留原IANA时区用于"
            "后续交运边界；不认证出生记录精度。未知请省略或传null。"
        ),
    )

    birth_second: Optional[int] = Field(
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

    @model_validator(mode="after")
    def seconds_require_minute(self) -> BaziClockRequest:
        if (
            self.birth_second is not None
            and "birth_minute" not in self.model_fields_set
        ):
            raise ValueError("birth_second需要显式提供birth_minute；不能替未知分钟填0")
        return self


class AstroBirthRequest(_DeferredModel):
    """Base birth request model for offline astrology endpoints."""

    name: Optional[str] = Field(default="未提供", description="Name (optional)")
    birth_year: int = Field(description="Birth year, e.g., 1990")
    birth_month: int = Field(ge=1, le=12, description="Birth month (1-12)")
    birth_day: int = Field(ge=1, le=31, description="Birth day (1-31)")
    birth_hour: int = Field(ge=0, le=23, description="Birth hour (0-23)")
    birth_minute: int = Field(default=0, ge=0, le=59, description="Birth minute (0-59)")
    birth_timezone: Optional[str] = Field(
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
    birth_longitude: float = Field(ge=-180, le=180, description="Birth longitude")
    birth_latitude: float = Field(ge=-90, le=90, description="Birth latitude")
    birth_place: Optional[str] = Field(default="未提供", description="Birth place")
