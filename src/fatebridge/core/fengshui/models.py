"""Consolidated Feng Shui Pydantic request and compact per-tool response models."""

from __future__ import annotations

import math
import re
import types
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from numbers import Integral, Real
from typing import Annotated, Any, Literal, cast, get_args, get_origin

from dateutil.tz import datetime_exists
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from fatebridge.core.fengshui.calendar import year_context
from fatebridge.core.fengshui.directions import (
    MOUNTAIN_BY_NAME,
    sitting_from_mountain,
    sitting_support,
)
from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.core.response_models import (
    Object,
    PartialOutput,
    ProjectedOutput,
    RunMetadata,
)
from fatebridge.utils.timezones import parse_timezone_name

Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
Trigram = Literal["坎", "艮", "震", "巽", "离", "坤", "兑", "乾"]
NorthReference = Literal["magnetic", "true"]
Basis = Literal["measured", "user_confirmed"]
BazhaiRuleset = Literal["bazhai_sitting_v1"]
JinsuoRuleset = Literal["jinsuo_basic_fixed_v1"]
AnnualRuleset = Literal["annual_zibai_lichun_v1"]
Method = Literal["bazhai", "jinsuo", "annual_stars", "monthly_stars", "xuankong_natal"]
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
Year = int

UNION_ORIGINS = (types.UnionType, get_origin(Annotated[int, "u"] | None))


def _unwrap(annotation: Any) -> Any:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _kind(annotation: Any) -> str | None:
    annotation = _unwrap(annotation)
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal and args and all(type(v) in (int, float) for v in args):
        return "number" if any(type(v) is float for v in args) else "integer"
    if origin in UNION_ORIGINS:
        kinds = [_kind(arg) for arg in args if arg is not type(None)]
        if kinds and all(kinds):
            return "number" if "number" in kinds else "integer"
    return None


def _temporal_kind(annotation: Any) -> str | None:
    annotation = _unwrap(annotation)
    if annotation is datetime:
        return "datetime"
    if annotation is date:
        return "date"
    if get_origin(annotation) in UNION_ORIGINS:
        kinds = [_temporal_kind(a) for a in get_args(annotation) if a is not type(None)]
        if kinds and len(set(kinds)) == 1:
            return kinds[0]
    return None


def _contains_number(annotation: Any) -> bool:
    annotation = _unwrap(annotation)
    if _kind(annotation) is not None or _temporal_kind(annotation) is not None:
        return True
    return any(_contains_number(a) for a in get_args(annotation) if a is not Ellipsis)


def _allows_bool(annotation: Any, value: bool) -> bool:
    annotation = _unwrap(annotation)
    if annotation is bool:
        return True
    if get_origin(annotation) is Literal:
        return any(type(arg) is bool and arg is value for arg in get_args(annotation))
    if get_origin(annotation) in UNION_ORIGINS:
        return any(_allows_bool(arg, value) for arg in get_args(annotation))
    return False


def _finite(value: Any) -> bool:
    if isinstance(value, (Integral, Fraction)):
        return True
    if isinstance(value, Decimal):
        return value.is_finite()
    return math.isfinite(value)


def _normalize(annotation: Any, value: Any) -> Any:
    annotation = _unwrap(annotation)
    if value is None:
        return value
    temporal = _temporal_kind(annotation)
    if temporal == "date":
        if (isinstance(value, date) and not isinstance(value, datetime)) or (
            isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        ):
            return value
        raise PydanticCustomError(
            "date_type", "Input should be an ISO calendar date (YYYY-MM-DD)"
        )
    if temporal == "datetime":
        if isinstance(value, datetime) or (
            isinstance(value, str)
            and re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}", value)
        ):
            return value
        raise PydanticCustomError(
            "datetime_type", "Input should be an explicit ISO date and clock"
        )
    kind = _kind(annotation)
    if isinstance(value, bool) and _contains_number(annotation):
        if _allows_bool(annotation, value):
            return value
        raise PydanticCustomError(
            "int_type" if kind == "integer" else "float_type",
            (
                "Input should be a valid integer"
                if kind == "integer"
                else "Input should be a valid number"
            ),
        )
    if kind is not None:
        if not isinstance(value, (Real, Decimal)):
            raise PydanticCustomError(
                "int_type" if kind == "integer" else "float_type",
                (
                    "Input should be a valid integer"
                    if kind == "integer"
                    else "Input should be a valid number"
                ),
            )
        if not _finite(value):
            raise PydanticCustomError(
                "finite_number", "Input should be a finite number"
            )
        if kind == "integer":
            integer = int(math.trunc(value))
            if value == integer:
                return integer
        return value
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in UNION_ORIGINS:
        choices = [arg for arg in args if arg is not type(None)]
        if len(choices) == 1:
            return _normalize(choices[0], value)
    if origin is list and isinstance(value, list) and args:
        return [_normalize(args[0], item) for item in value]
    if origin is dict and isinstance(value, dict) and len(args) == 2:
        return {key: _normalize(args[1], item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class _NumericGuard:
    annotation: Any

    def __call__(self, value: Any) -> Any:
        return _normalize(self.annotation, value)


class FengshuiInput(FateBridgeBaseRequest):
    """Attach strict numeric/calendar guards to nested and flattened fields."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        changed = False
        for info in cls.model_fields.values():
            if _contains_number(info.annotation):
                info.metadata = [
                    item
                    for item in info.metadata
                    if not (
                        isinstance(item, BeforeValidator)
                        and isinstance(item.func, _NumericGuard)
                    )
                ] + [BeforeValidator(_NumericGuard(info.annotation))]
                changed = True
        if changed and cls.__pydantic_complete__:
            cls.model_rebuild(force=True)


class TimeInput(FengshuiInput):
    timezone_name: str = Field(
        default="Asia/Shanghai", description="IANA 时区或 UTC 偏移；用于对应历法边界"
    )

    @field_validator("timezone_name")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        parse_timezone_name(value)
        return value

    @field_validator("birth_at", "query_at", "event_at", check_fields=False)
    @classmethod
    def existing_aware_clock(cls, value: datetime | None) -> datetime | None:
        if (
            value is not None
            and value.utcoffset() is not None
            and not datetime_exists(value)
        ):
            raise ValueError("nonexistent local time：该地区时区不存在此钟时")
        return value


class GeomagneticReference(FengshuiInput):
    """Geodetic coordinates & epoch for WMM2025 (2025-2030) or IGRF-14 (1900-2030)."""

    model_id: Literal["auto", "wmm2025_v1", "igrf14_v1"] = Field(
        default="auto",
        description="地磁模型：auto（2025-2030用WMM2025，1900-2025用IGRF-14）、wmm2025_v1 或 igrf14_v1",
    )
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    height_km_wgs84: float = Field(
        default=0.0, ge=-1, le=850, allow_inf_nan=False, description="WGS84椭球高(km)"
    )
    model_date: date | None = Field(
        default=None,
        ge=date(1900, 1, 1),
        le=date(2030, 1, 1),
        description="UTC参考日期(YYYY-MM-DD)；与decimal_year二选一",
    )
    decimal_year: float | None = Field(
        default=None, ge=1900, le=2030, allow_inf_nan=False
    )
    evidence: str | None = Field(
        default=None, min_length=1, pattern=r"\S", description="地点与参考日期来源"
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
        raise ValueError("model_date须为YYYY-MM-DD日期")

    @model_validator(mode="after")
    def validate_time_and_model(self) -> "GeomagneticReference":
        if (self.model_date is None) == (self.decimal_year is None):
            raise ValueError("model_date和decimal_year须且只能提供一项")
        year = self.year_value()
        if self.model_id == "wmm2025_v1" and not (2025.0 <= year <= 2030.0):
            raise ValueError(
                "wmm2025_v1 仅支持 [2025.0, 2030.0]；历史年份请用 auto 或 igrf14_v1"
            )
        if not (1900.0 <= year <= 2030.0):
            raise ValueError("地磁模型仅支持 1900.0–2030.0")
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


class DirectionsRequest(FengshuiInput):
    geomagnetic_reference: GeomagneticReference | None = Field(
        default=None,
        description="可选地磁参考（WMM2025/IGRF-14）；只给换算候选，不自动修改宅盘朝向",
    )
    bearing_degrees: float | None = Field(
        default=None,
        ge=0,
        le=360,
        allow_inf_nan=False,
        description="实际方位角，0°北、顺时针，360°归一为0°",
    )
    north_reference: NorthReference | None = Field(
        default=None, description="角度参考北：magnetic 或 true；提供角度时必填"
    )
    ruleset_id: Literal["houtian_directions_v1"] = "houtian_directions_v1"

    @model_validator(mode="after")
    def validate_reference(self) -> "DirectionsRequest":
        if self.bearing_degrees is not None and self.north_reference is None:
            raise ValueError("角度输入必须明确 north_reference")
        return self


class MingguaRequest(TimeInput):
    birth_date: date | None = Field(
        default=None, description="公历出生日期；与有效生年/出生时刻三选一"
    )
    birth_year: Year | None = Field(
        default=None, ge=1800, le=2199, description="已确认换年后的有效生年"
    )
    birth_at: datetime | None = Field(default=None, description="含时区的 ISO 出生时刻")
    gender: Literal["male", "female"] | None = Field(
        default=None, description="传统男女起算法；未知时返回两个候选"
    )
    year_boundary: Literal["lichun", "january_1"] = Field(
        default="lichun", description="命卦换年约定"
    )
    ruleset_id: BazhaiRuleset = "bazhai_sitting_v1"

    @model_validator(mode="after")
    def validate_birth(self) -> "MingguaRequest":
        if (
            sum(
                v is not None
                for v in (self.birth_year, self.birth_at, self.birth_date)
            )
            > 1
        ):
            raise ValueError("birth_year、birth_at、birth_date 只能提供一项")
        if self.birth_date is not None and not 1801 <= self.birth_date.year <= 2199:
            raise ValueError("birth_date 支持 1801–2199 年")
        if self.birth_at is not None:
            if self.birth_at.tzinfo is None or self.birth_at.utcoffset() is None:
                raise ValueError("birth_at 必须包含时区")
            if not 1801 <= self.birth_at.year <= 2199:
                raise ValueError("birth_at 支持 1801–2199 年")
        return self


class Occupant(MingguaRequest):
    subject_id: str | None = Field(
        default=None, min_length=1, max_length=100, description="住户稳定标识"
    )


class House(FengshuiInput):
    object_id: str = Field(default="house", min_length=1, max_length=100)
    sitting_trigram: Trigram | None = Field(
        default=None, description="已确认住宅坐山卦"
    )
    facing_degrees: float | None = Field(
        default=None,
        ge=0,
        le=360,
        allow_inf_nan=False,
        description="宅向角度，0°北顺时针",
    )
    facing_mountain: Mountain | None = Field(
        default=None, description="已确认住宅朝向二十四山（未提供 facing_degrees 时可选）"
    )
    bearing_uncertainty_degrees: float | None = Field(
        default=None,
        ge=0,
        le=180,
        allow_inf_nan=False,
        description="宅向测量误差半径（度）",
    )
    north_reference: NorthReference | None = Field(
        default=None, description="参考北：magnetic 或 true；提供角度时默认 magnetic"
    )
    orientation_basis: Basis = "user_confirmed"
    division_method: Literal["confirmed_angular_sectors"] = "confirmed_angular_sectors"

    @model_validator(mode="after")
    def bearing_reference(self) -> "House":
        if self.facing_degrees is not None and self.facing_mountain is not None:
            raise ValueError("facing_degrees 与 facing_mountain 不能同时提供")
        if self.bearing_uncertainty_degrees is not None and self.facing_degrees is None:
            raise ValueError("宅向误差半径须同时提供 facing_degrees")
        if self.facing_degrees is not None and self.north_reference is None:
            self.north_reference = "magnetic"
        self.check_sitting_trigram(self.bearing_uncertainty_degrees or 0.0)
        return self

    def check_sitting_trigram(self, radius: float) -> None:
        if self.facing_degrees is not None and self.sitting_trigram is not None:
            assert self.north_reference is not None
            supported = sitting_support(
                self.facing_degrees, radius, self.north_reference
            )
            if self.sitting_trigram not in {c["sitting_trigram"] for c in supported}:
                raise ValueError("宅向推导的坐山与 sitting_trigram 不一致")
        if self.facing_mountain is not None and self.sitting_trigram is not None:
            derived = sitting_from_mountain(self.facing_mountain)["trigram"]
            if self.sitting_trigram != derived:
                raise ValueError("facing_mountain 推导的坐山与 sitting_trigram 不一致")


PLACEMENT_FACING_ROLES = {
    "door": "door_facing",
    "bed": "headboard",
    "desk": "desk_facing",
    "stove": "fire_mouth",
}

PLACEMENT_SCHEMA_CONSTRAINTS: dict[str, Any] = {
    "allOf": [
        {
            "anyOf": [
                {"required": [f], "properties": {f: {"type": "string"}}}
                for f in ("location_direction", "facing_direction")
            ]
        },
        {
            "anyOf": [
                {
                    "required": ["facing_direction"],
                    "properties": {"facing_direction": {"type": "string"}},
                },
                {"properties": {"facing_role": {"type": "null"}}},
            ]
        },
        *[
            {
                "if": {"properties": {"purpose": {"const": p}}},
                "then": {"properties": {"facing_role": {"enum": [None, r]}}},
            }
            for p, r in PLACEMENT_FACING_ROLES.items()
        ],
        {
            "anyOf": [
                {"properties": {"subject_id": {"type": "null"}}},
                {"properties": {"subject_ids": {"type": "null"}}},
            ]
        },
    ]
}


class Placement(FengshuiInput):
    """门床桌灶已确认方位。至少提供位置或朝向；提供朝向时可省略 facing_role 自动匹配。"""

    model_config = ConfigDict(json_schema_extra=PLACEMENT_SCHEMA_CONSTRAINTS)

    object_id: str | None = Field(default=None, min_length=1, max_length=100)
    purpose: Literal["door", "bed", "desk", "stove"]
    location_direction: Direction | None = Field(default=None, description="已确认落宫")
    facing_direction: Direction | None = Field(default=None, description="已确认朝向")
    facing_role: (
        Literal["door_facing", "headboard", "desk_facing", "fire_mouth"] | None
    ) = None
    subject_id: str | None = None
    subject_ids: list[str] | None = Field(default=None, min_length=1, max_length=50)
    observation_basis: Basis = "user_confirmed"

    def applies_to_occupant(self, subject_id: str) -> bool:
        if self.subject_ids is not None:
            return subject_id in self.subject_ids
        return self.subject_id is None or self.subject_id == subject_id

    @model_validator(mode="after")
    def facing_semantics(self) -> "Placement":
        if self.subject_id is not None and self.subject_ids is not None:
            raise ValueError("subject_id 和 subject_ids 只能提供一项")
        if self.subject_ids is not None and len(set(self.subject_ids)) != len(
            self.subject_ids
        ):
            raise ValueError("对象共用住户 subject_ids 必须唯一")
        if self.location_direction is None and self.facing_direction is None:
            raise ValueError("布局对象至少提供位置或朝向")
        if self.facing_direction is None and self.facing_role is not None:
            raise ValueError("无 facing_direction 时不得单独提供 facing_role")
        expected_role = PLACEMENT_FACING_ROLES[self.purpose]
        if self.facing_direction is not None and self.facing_role is None:
            self.facing_role = cast(
                Literal["door_facing", "headboard", "desk_facing", "fire_mouth"],
                expected_role,
            )
        if self.facing_role is not None and self.facing_role != expected_role:
            raise ValueError("facing_role 与 purpose 不匹配")
        return self


def _next_auto_id(prefix: str, used: set[str]) -> str:
    idx = 1
    while f"{prefix}_{idx}" in used:
        idx += 1
    candidate = f"{prefix}_{idx}"
    used.add(candidate)
    return candidate


class BazhaiRequest(FengshuiInput):
    house: House | None = None
    occupants: list[Occupant] = Field(default_factory=list, max_length=50)
    placements: list[Placement] = Field(default_factory=list, max_length=200)
    ruleset_id: BazhaiRuleset = "bazhai_sitting_v1"

    @model_validator(mode="after")
    def unique_ids(self) -> "BazhaiRequest":
        if self.house is not None:
            self.house.check_sitting_trigram(
                self.house.bearing_uncertainty_degrees or 0
            )
        used_subjects = {o.subject_id for o in self.occupants if o.subject_id is not None}
        if self.house is not None:
            used_subjects.add(self.house.object_id)
        for o in self.occupants:
            if o.subject_id is None:
                o.subject_id = _next_auto_id("occupant", used_subjects)

        used_objects = {p.object_id for p in self.placements if p.object_id is not None}
        if self.house is not None:
            used_objects.add(self.house.object_id)
        for p in self.placements:
            if p.object_id is None:
                p.object_id = _next_auto_id("placement", used_objects)

        ids = [cast(str, o.subject_id) for o in self.occupants]
        objects = [cast(str, p.object_id) for p in self.placements]
        if len(set(ids)) != len(ids) or len(set(objects)) != len(objects):
            raise ValueError("住户及布局对象 ID 必须分别唯一")
        if self.house is not None and self.house.object_id in ids:
            raise ValueError("住宅 ID 不得与住户 ID 重复")
        if self.house is not None and self.house.object_id in objects:
            raise ValueError("布局对象 ID 不得与住宅 ID 重复")
        known_subjects = set(ids)
        if any(
            ref not in known_subjects
            for p in self.placements
            for ref in (
                p.subject_ids
                if p.subject_ids is not None
                else [p.subject_id] if p.subject_id is not None else []
            )
        ):
            raise ValueError("布局对象引用了未提供的住户")
        return self


class EnvironmentFeature(FengshuiInput):
    object_id: str | None = Field(default=None, min_length=1, max_length=100)
    direction: Direction | None = Field(default=None, description="已确认八宫方位")
    mountain: Mountain | None = Field(default=None, description="已确认二十四山位")
    classification: Literal["sand", "water", "mixed", "unknown"]
    classification_basis: Basis = "user_confirmed"
    evidence: str | None = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )
    label: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def resolve_sector_and_mountain(self) -> "EnvironmentFeature":
        if self.direction is None and self.mountain is None:
            raise ValueError("环境特征须提供 direction 或 mountain")
        if self.mountain is not None:
            m_dir = MOUNTAIN_BY_NAME[self.mountain]["direction"]
            if self.direction is not None and self.direction != m_dir:
                raise ValueError(
                    f"mountain {self.mountain} 属 {m_dir} 宫，与 direction={self.direction} 冲突"
                )
            self.direction = cast(Direction, m_dir)
        return self


def _assign_feature_ids(features: list[EnvironmentFeature]) -> None:
    used = {f.object_id for f in features if f.object_id is not None}
    for f in features:
        if f.object_id is None:
            f.object_id = _next_auto_id("feature", used)


class JinsuoRequest(FengshuiInput):
    features: list[EnvironmentFeature] = Field(default_factory=list, max_length=500)
    ruleset_id: JinsuoRuleset = "jinsuo_basic_fixed_v1"

    @model_validator(mode="after")
    def unique_features(self) -> "JinsuoRequest":
        _assign_feature_ids(self.features)
        ids = [cast(str, f.object_id) for f in self.features]
        if len(set(ids)) != len(ids):
            raise ValueError("环境特征 object_id 必须唯一")
        return self


class AnnualRequest(TimeInput):
    effective_year: Year | None = Field(default=None, ge=1800, le=2199)
    query_at: datetime | None = None
    ruleset_id: AnnualRuleset = "annual_zibai_lichun_v1"

    @model_validator(mode="after")
    def validate_query(self) -> "AnnualRequest":
        if self.effective_year is not None and self.query_at is not None:
            raise ValueError("effective_year 与 query_at 不能同时提供")
        if self.query_at is not None:
            if self.query_at.tzinfo is None or self.query_at.utcoffset() is None:
                raise ValueError("query_at 必须包含时区")
            if not 1801 <= self.query_at.year <= 2199:
                raise ValueError("query_at 支持 1801–2199 年")
        return self


class MonthlyRequest(TimeInput):
    query_at: datetime | None = Field(
        default=None, description="含时区的查询时刻；按十二节换月、同时计算日/时紫白"
    )
    effective_solar_year: StrictInt | None = Field(default=None, ge=1800, le=2199)
    solar_month_number: StrictInt | None = Field(default=None, ge=1, le=12)
    include_daily_hourly: StrictBool = Field(
        default=True, description="传入 query_at 时同步计算日紫白与时紫白"
    )
    ruleset_id: Literal["monthly_zibai_jie_v1"] = "monthly_zibai_jie_v1"

    @model_validator(mode="after")
    def selected_month_clock(self) -> "MonthlyRequest":
        if (self.effective_solar_year is None) != (self.solar_month_number is None):
            raise ValueError("effective_solar_year与solar_month_number必须成对")
        if self.query_at is not None:
            if self.effective_solar_year is not None:
                raise ValueError("query_at与已确认有效年/节月不能同时提供")
            if self.query_at.tzinfo is None or self.query_at.utcoffset() is None:
                raise ValueError("query_at必须包含时区")
            if not 1801 <= self.query_at.year <= 2199:
                raise ValueError("query_at支持1801–2199年")
        return self


class HousePeriod(TimeInput):
    basis: (
        Literal[
            "construction_completion",
            "first_occupancy",
            "confirmed_major_renovation",
            "expert_confirmed",
        ]
        | None
    ) = None
    evidence: str | None = Field(
        default=None, min_length=1, max_length=2000, pattern=r"\S"
    )
    period_number: int | None = Field(default=None, ge=1, le=9)
    event_year: int | None = Field(default=None, ge=1800, le=2199)
    event_at: datetime | None = None
    qualifies_for_period_reset: bool | None = None

    @model_validator(mode="after")
    def selected_event(self) -> "HousePeriod":
        if (
            sum(
                x is not None
                for x in (self.period_number, self.event_year, self.event_at)
            )
            != 1
        ):
            raise ValueError(
                "定运需且仅需 period_number、event_year、event_at 之一"
            )
        if self.basis is None:
            self.basis = (
                "expert_confirmed"
                if self.period_number is not None
                else "construction_completion"
            )
        if self.event_at is not None:
            AnnualRequest(query_at=self.event_at, timezone_name=self.timezone_name)
        if self.basis == "expert_confirmed" and self.period_number is None:
            raise ValueError("expert_confirmed 必须显式确认 period_number")
        if self.basis == "confirmed_major_renovation":
            if self.qualifies_for_period_reset is None:
                self.qualifies_for_period_reset = True
            elif self.qualifies_for_period_reset is not True:
                raise ValueError("大修换运须明确 qualifies_for_period_reset=true")
        elif self.qualifies_for_period_reset is not None:
            raise ValueError("qualifies_for_period_reset 仅用于已确认的大修换运")
        return self


class CityGateObservation(FengshuiInput):
    mountain: Mountain
    observation_basis: Literal["measured", "user_confirmed", "image_observed"] = (
        "user_confirmed"
    )
    evidence: str | None = Field(
        default=None, min_length=1, max_length=2000, pattern=r"\S"
    )
    water_present: StrictBool | None = None
    multiple_openings_present: StrictBool | None = None
    encircling_form_present: StrictBool | None = None
    sole_opening_with_water: StrictBool | None = None
    three_way_water_junction_present: StrictBool | None = None
    water_reflects_towards_site: StrictBool | None = None

    @model_validator(mode="after")
    def coherent_observation(self) -> "CityGateObservation":
        fields = (
            "water_present",
            "multiple_openings_present",
            "encircling_form_present",
            "sole_opening_with_water",
            "three_way_water_junction_present",
            "water_reflects_towards_site",
        )
        if not any(getattr(self, k) is not None for k in fields):
            raise ValueError("城门观察须至少提供一项明确形势事实")
        if self.water_present is False and any(
            getattr(self, k) is True
            for k in (
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


class CityGateRequest(FengshuiInput):
    ruleset_id: Literal["shen_city_gate_v1"] = "shen_city_gate_v1"
    reference_period_number: StrictInt | None = Field(default=None, ge=1, le=9)
    period_evidence: str | None = Field(
        default=None, min_length=1, max_length=2000, pattern=r"\S"
    )
    observations: list[CityGateObservation] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def unique_mountains(self) -> "CityGateRequest":
        values = [o.mountain for o in self.observations]
        if len(values) != len(set(values)):
            raise ValueError("同一城门山位不可重复")
        return self


class LingzhengObservation(FengshuiInput):
    direction: Direction
    high_solid_terrain_present: StrictBool | None = None
    low_lying_terrain_present: StrictBool | None = None
    river_water_present: StrictBool | None = None
    observation_basis: Literal["measured", "user_confirmed", "image_observed"] = (
        "user_confirmed"
    )
    evidence: str | None = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )

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


class FixedLingzhengRequest(FengshuiInput):
    ruleset_id: Literal["shen_fixed_lingzheng_v1"] = "shen_fixed_lingzheng_v1"
    five_period_half: Literal["first_decade", "second_decade"] | None = None
    half_evidence: str | None = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )
    observations: list[LingzhengObservation] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def explicit_half_and_unique_directions(self) -> "FixedLingzhengRequest":
        if self.five_period_half is None and self.half_evidence is not None:
            raise ValueError("未指定五运分段时不得单独提供 half_evidence")
        if len({o.direction for o in self.observations}) != len(self.observations):
            raise ValueError("零正外局同一方向不可重复")
        return self


class ExternalFormObservation(FengshuiInput):
    direction: Direction
    mountain_present: StrictBool | None = None
    water_present: StrictBool | None = None
    observation_basis: Literal["measured", "user_confirmed", "image_observed"] = (
        "user_confirmed"
    )
    evidence: str | None = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )

    @model_validator(mode="after")
    def explicit_observation(self) -> "ExternalFormObservation":
        if self.mountain_present is None and self.water_present is None:
            raise ValueError("外局须至少明确山形或水形的一项观察")
        return self


class XuankongInterpretationRequest(FengshuiInput):
    ruleset_id: Literal["xuankong_conditioned_v1"] = "xuankong_conditioned_v1"
    timeliness_ruleset_id: Literal["wang_zhongzhou_timeliness_v1"] | None = None
    host_guest_ruleset_id: Literal["shen_2011_host_guest_v1"] | None = None
    fixed_lingzheng: FixedLingzhengRequest | None = None
    current_period_number: StrictInt | None = Field(default=None, ge=1, le=9)
    period_evidence: str | None = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )
    external_forms: list[ExternalFormObservation] = Field(
        default_factory=list, max_length=8
    )

    @model_validator(mode="after")
    def distinct_confirmed_facts(self) -> "XuankongInterpretationRequest":
        if self.fixed_lingzheng is not None:
            if (
                self.fixed_lingzheng.five_period_half is not None
                and self.current_period_number is not None
                and self.current_period_number != 5
            ):
                raise ValueError("零正五运分段仅可用于明确评价五运")
            old_water = {o.direction: o.water_present for o in self.external_forms}
            for obs in self.fixed_lingzheng.observations:
                if (
                    obs.river_water_present is True
                    and old_water.get(obs.direction) is False
                ):
                    raise ValueError(
                        "同一全宅方向的有水事实不能在飞星与固定零正观察中冲突"
                    )
        directions = [o.direction for o in self.external_forms]
        if len(set(directions)) != len(directions):
            raise ValueError("同一全宅外局方向不能重复")
        return self


class XuankongRequest(FengshuiInput):
    house: House | None = None
    period: HousePeriod | None = None
    current_period_number: StrictInt | None = Field(
        default=None, ge=1, le=9, description="可选当前评价运，计算当令分布与令星入囚"
    )
    ruleset_id: Literal["xuankong_zhongzhou_v1"] = "xuankong_zhongzhou_v1"
    interpretation: XuankongInterpretationRequest | None = None
    city_gate: CityGateRequest | None = None

    @model_validator(mode="after")
    def magnetic_reference(self) -> "XuankongRequest":
        if (
            self.house is not None
            and self.house.bearing_uncertainty_degrees is not None
        ):
            if self.house.bearing_uncertainty_degrees > 7.5:
                raise ValueError("本玄空版本的宅向误差半径最多支持7.5度")
        if self.house is not None:
            self.house.check_sitting_trigram(self.effective_bearing_uncertainty)
        if self.house is not None and (
            (
                self.house.facing_degrees is not None
                and self.house.north_reference != "magnetic"
            )
            or (
                self.house.facing_mountain is not None
                and self.house.north_reference == "true"
            )
        ):
            raise ValueError("本玄空版本使用磁北宅向；真北需先完成磁偏角校正")
        if (
            self.current_period_number is not None
            and self.interpretation is not None
            and self.interpretation.current_period_number is not None
            and self.current_period_number != self.interpretation.current_period_number
        ):
            raise ValueError(
                "current_period_number 与 interpretation.current_period_number 不一致"
            )
        if self.current_period_number is not None:
            if (
                self.interpretation is not None
                and self.interpretation.current_period_number is None
            ):
                self.interpretation.current_period_number = self.current_period_number
            if (
                self.city_gate is not None
                and self.city_gate.reference_period_number is None
            ):
                self.city_gate.reference_period_number = self.current_period_number
        if (
            self.interpretation is not None
            and self.interpretation.fixed_lingzheng is not None
            and self.interpretation.fixed_lingzheng.five_period_half is not None
            and self.interpretation.current_period_number is not None
            and self.interpretation.current_period_number != 5
        ):
            raise ValueError("零正五运分段仅可用于明确评价五运")
        return self

    @property
    def effective_bearing_uncertainty(self) -> float:
        if (
            self.house is not None
            and self.house.bearing_uncertainty_degrees is not None
        ):
            return self.house.bearing_uncertainty_degrees
        return 0.0


class AssessRequest(BazhaiRequest):
    """Multi-layer assessment decoupled from AnnualRequest mutual exclusion."""

    analyze_layout: bool | None = Field(
        default=None, description="是否计算跨层布局落宫与四层叠盘；默认有 placements 时自动启用"
    )
    features: list[EnvironmentFeature] = Field(default_factory=list, max_length=500)
    effective_year: Year | None = Field(
        default=None,
        ge=1800,
        le=2199,
        description="显式有效年覆盖（可与 query_at 并用）",
    )
    query_at: datetime | None = Field(
        default=None, description="含时区查询时刻，用于月/日/时紫白及默认年星"
    )
    timezone_name: str = Field(default="Asia/Shanghai")
    built_year: Year | None = Field(
        default=None,
        ge=1800,
        le=2199,
        description="住宅建成或换运有效年份（扁平简写，等效于 xuankong.period.event_year）",
    )
    period_number: int | None = Field(
        default=None,
        ge=1,
        le=9,
        description="住宅元运 1–9（扁平简写，等效于 xuankong.period.period_number）",
    )
    methods: list[Method] | None = None
    jinsuo_ruleset_id: JinsuoRuleset = "jinsuo_basic_fixed_v1"
    annual_ruleset_id: AnnualRuleset = "annual_zibai_lichun_v1"
    xuankong: XuankongRequest | None = None
    monthly: MonthlyRequest | None = None

    @field_validator("timezone_name")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        parse_timezone_name(value)
        return value

    @field_validator("query_at")
    @classmethod
    def valid_query_clock(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.utcoffset() is not None and not datetime_exists(value):
                raise ValueError("nonexistent local time：该地区时区不存在此钟时")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("query_at 必须包含时区")
            if not 1801 <= value.year <= 2199:
                raise ValueError("query_at 支持 1801–2199 年")
        return value

    @property
    def selected_methods(self) -> list[Method]:
        if self.methods is not None:
            return self.methods
        selected: list[Method] = []
        if (
            self.xuankong is not None
            or self.built_year is not None
            or self.period_number is not None
        ):
            selected.append("xuankong_natal")
        if self.effective_year is not None or self.query_at is not None:
            selected.append("annual_stars")
        if self.monthly is not None or self.query_at is not None:
            selected.append("monthly_stars")
        if self.features:
            selected.append("jinsuo")
        if self.house is not None or self.occupants:
            selected.append("bazhai")
        return selected

    def _inferred_current_period(self) -> int | None:
        eval_year = self.effective_year
        if eval_year is None and self.query_at is not None:
            eval_year = year_context(
                None, self.query_at, self.timezone_name, resolve_interval=False
            ).get("effective_year")
        if eval_year is None:
            return None
        return ((eval_year - 1864) // 20) % 9 + 1

    @model_validator(mode="after")
    def validate_layers(self) -> "AssessRequest":
        if self.analyze_layout is None:
            self.analyze_layout = bool(self.placements)
        if self.built_year is not None and self.period_number is not None:
            raise ValueError("built_year 与 period_number 不能同时提供")
        if not self.selected_methods:
            raise ValueError("至少选择一层计算")
        if len(set(self.selected_methods)) != len(self.selected_methods):
            raise ValueError("methods 不得重复")
        _assign_feature_ids(self.features)
        JinsuoRequest(features=self.features, ruleset_id=self.jinsuo_ruleset_id)
        flat_period: HousePeriod | None = None
        if self.built_year is not None or self.period_number is not None:
            if self.xuankong is not None and self.xuankong.period is not None:
                raise ValueError("顶层 built_year/period_number 不能与 xuankong.period 同时提供")
            flat_period = HousePeriod(
                event_year=self.built_year,
                period_number=self.period_number,
                timezone_name=self.timezone_name,
            )
        if (
            self.xuankong is not None or flat_period is not None
        ) and "xuankong_natal" not in self.selected_methods:
            raise ValueError("提供 xuankong/built_year/period_number 时须在 methods 中选择 xuankong_natal")
        if "xuankong_natal" in self.selected_methods:
            natal = self.xuankong or XuankongRequest()
            if self.house is not None and natal.house is not None:
                if self.house.model_dump() != natal.house.model_dump():
                    raise ValueError("合参顶层 house 与 xuankong.house 必须一致")
            inferred_period = self._inferred_current_period()
            current_period = natal.current_period_number
            if current_period is None and inferred_period is not None:
                if (
                    natal.interpretation is None
                    or natal.interpretation.current_period_number is None
                ):
                    current_period = inferred_period
            city_gate_data = (
                natal.city_gate.model_dump() if natal.city_gate is not None else None
            )
            if (
                city_gate_data is not None
                and city_gate_data["reference_period_number"] is None
                and (current_period or inferred_period) is not None
            ):
                city_gate_data["reference_period_number"] = (
                    current_period or inferred_period
                )
            resolved_natal = XuankongRequest.model_validate(
                {
                    **natal.model_dump(),
                    "house": natal.house or self.house,
                    "period": natal.period or flat_period,
                    "current_period_number": current_period,
                    "city_gate": city_gate_data,
                }
            )
            if self.xuankong is not None or flat_period is not None:
                self.xuankong = resolved_natal
        return self


# --- Compact Per-Tool Projection-Compatible Output Models (<6 KB schemas) ---


class Coverage(PartialOutput):
    implemented_layers: list[str] | None = None
    missing_inputs: list[str] | None = None
    unavailable_layers: list[str] | None = None
    not_requested_layers: list[str] | None = None


class BaseFengshuiOutput(ProjectedOutput):
    analysis_type: str | None = None
    engine: str | None = None
    status: Literal["complete", "partial"] | None = None
    layers: dict[str, Object] | None = None
    coverage: Coverage | None = None
    conflicts: list[Object] | None = None
    summary: str | None = None
    run_metadata: RunMetadata | None = None


class DirectionsOutput(BaseFengshuiOutput):
    pass


class MingguaOutput(BaseFengshuiOutput):
    pass


class BazhaiOutput(BaseFengshuiOutput):
    pass


class JinsuoOutput(BaseFengshuiOutput):
    pass


class AnnualStarsOutput(BaseFengshuiOutput):
    pass


class MonthlyStarsOutput(BaseFengshuiOutput):
    pass


class XuankongOutput(BaseFengshuiOutput):
    pass


class AssessOutput(BaseFengshuiOutput):
    palace_overlay: dict[str, Object] | None = None
    layout_analysis: Object | None = None


class FengshuiOutput(AssessOutput):
    @model_validator(mode="after")
    def require_declared_layers(self, info: ValidationInfo) -> "FengshuiOutput":
        if info.context and info.context.get("full_result") and self.coverage:
            actual = {n for n, v in (self.layers or {}).items() if v is not None}
            if set(self.coverage.implemented_layers or []) - actual:
                raise ValueError("完整风水结果缺少已声明计算的图层")
        return self
