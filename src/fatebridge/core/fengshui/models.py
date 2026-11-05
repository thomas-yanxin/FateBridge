"""Residential inputs: location, facing and observed form stay distinct."""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, cast

from dateutil.tz import datetime_exists
from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from fatebridge.utils.timezones import parse_timezone_name

from .city_gate_inputs import CityGateRequest
from .context_inputs import EnvironmentalContext
from .geomagnetic_inputs import GeomagneticReference
from .layout_inputs import ElementAdjustment, FormObservation
from .lingzheng_inputs import FixedLingzhengRequest
from .numeric_inputs import FengshuiInput as _DeferredModel
from .spatial_request import WorkstationLayoutInput
from .surface_inputs import SurfaceConstraints, SurfaceLayout
from .workstation_inputs import validate_review

Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
Trigram = Literal["坎", "艮", "震", "巽", "离", "坤", "兑", "乾"]
NorthReference = Literal["magnetic", "true"]
Basis = Literal["measured", "user_confirmed"]
BazhaiRuleset = Literal["bazhai_sitting_v1"]
JinsuoRuleset = Literal["jinsuo_basic_fixed_v1"]
AnnualRuleset = Literal["annual_zibai_lichun_v1"]
Method = Literal["bazhai", "jinsuo", "annual_stars", "monthly_stars", "xuankong_natal"]
Year = int


class TimeInput(_DeferredModel):
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
    def existing_aware_clock(cls, value: Optional[datetime]) -> Optional[datetime]:
        # Python callers can supply a cached dateutil/ZoneInfo tzinfo object.
        # astimezone(same_tzinfo) then preserves even an impossible local clock.
        # Fixed-offset ISO instants remain valid and convert normally.
        if (
            value is not None
            and value.utcoffset() is not None
            and not datetime_exists(value)
        ):
            raise ValueError(
                "nonexistent local time：该地区时区不存在此钟时；请提供有效当地钟时或明确UTC偏移。"
            )
        # A valid aware datetime already identifies a fold through its UTC
        # offset/fold flag. Preserve that explicit instant instead of rejecting
        # an otherwise valid repeated wall clock.
        return value


class MingguaRequest(TimeInput):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "anyOf": [
                        {"properties": {left: {"type": "null"}}},
                        {"properties": {right: {"type": "null"}}},
                    ]
                }
                for left, right in [
                    ("birth_date", "birth_at"),
                    ("birth_date", "effective_birth_year"),
                    ("birth_at", "effective_birth_year"),
                ]
            ]
        }
    )
    birth_date: Optional[date] = Field(
        default=None,
        description="公历出生日期；非立春当日无需出生时刻，与有效生年/出生时刻三选一",
    )
    effective_birth_year: Optional[Year] = Field(
        default=None,
        ge=1800,
        le=2199,
        description="已确认换年后的有效生年；与 birth_at 二选一",
    )
    birth_at: Optional[datetime] = Field(
        default=None, description="含时区的 ISO 出生时刻；不使用真太阳时"
    )
    gender_convention: Optional[Literal["male", "female"]] = Field(
        default=None, description="传统男女起算法；未知时返回两个候选，不默认男"
    )
    year_boundary: Literal["lichun", "january_1"] = Field(
        default="lichun", description="选定命卦换年约定；非所有古本统一规则"
    )
    ruleset_id: BazhaiRuleset = Field(
        default="bazhai_sitting_v1", description="八宅坐山与命卦规则版本；不是八字喜用"
    )

    @model_validator(mode="after")
    def validate_birth(self) -> "MingguaRequest":
        if (
            sum(
                v is not None
                for v in (self.effective_birth_year, self.birth_at, self.birth_date)
            )
            > 1
        ):
            raise ValueError("effective_birth_year、birth_at、birth_date 只能提供一项")
        if self.birth_date is not None and not 1801 <= self.birth_date.year <= 2199:
            raise ValueError("birth_date 支持 1801–2199 年")
        if self.birth_at is not None:
            if self.birth_at.tzinfo is None or self.birth_at.utcoffset() is None:
                raise ValueError("birth_at 必须包含时区")
            if not 1801 <= self.birth_at.year <= 2199:
                raise ValueError("birth_at 支持 1801–2199 年")
        return self


class Occupant(MingguaRequest):
    subject_id: str = Field(
        min_length=1,
        max_length=100,
        description="已确认住户的稳定标识，用于关联实际使用对象",
    )


class House(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "required": ["bearing_uncertainty_degrees"],
                        "properties": {
                            "bearing_uncertainty_degrees": {"type": "number"}
                        },
                    },
                    "then": {
                        "required": ["facing_degrees"],
                        "properties": {"facing_degrees": {"type": "number"}},
                    },
                }
            ]
        }
    )
    object_id: str = Field(
        default="house",
        min_length=1,
        max_length=100,
        description="住宅标识，不与住户或家具标识混用",
    )
    sitting_trigram: Optional[Trigram] = Field(
        default=None, description="已确认的住宅坐山卦；不是家具朝向或个人命卦"
    )
    facing_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        le=360,
        allow_inf_nan=False,
        description="宅向角度，0°北、顺时针；360°归一为0°",
    )
    bearing_uncertainty_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        le=180,
        strict=True,
        allow_inf_nan=False,
        description="同一宅向已知的测量误差半径，供八宅及玄空共同读取；须有facing_degrees。只接受调用方独立提供的有界区间，不把WMM标准差当误差上界。省略沿用点方位约定，不证明现场误差为零；玄空最多支持7.5度。",
    )
    north_reference: Optional[NorthReference] = Field(
        default=None,
        description="角度的参考北：magnetic 磁北或 true 真北；有角度时必填，不猜参考系",
    )
    orientation_basis: Basis = Field(
        default="user_confirmed",
        description="宅向事实来源：实测或用户明确确认；照片不自动定向",
    )
    division_method: Literal["confirmed_angular_sectors"] = Field(
        default="confirmed_angular_sectors",
        description="已确认的八宫角区分法，不自动识别户型立极",
    )

    @model_validator(mode="after")
    def bearing_reference(self) -> "House":
        if self.bearing_uncertainty_degrees is not None and self.facing_degrees is None:
            raise ValueError("宅向误差半径须同时提供 facing_degrees")
        if self.facing_degrees is not None and self.north_reference is None:
            raise ValueError("角度输入必须明确 north_reference")
        if self.bearing_uncertainty_degrees is not None:
            self.check_sitting_trigram(self.bearing_uncertainty_degrees)
        return self

    def check_sitting_trigram(self, radius: float) -> None:
        if self.facing_degrees is not None and self.sitting_trigram is not None:
            assert self.north_reference is not None
            from .bearing_support import sitting_support

            supported = sitting_support(
                self.facing_degrees,
                radius,
                self.north_reference,
            )
            if self.sitting_trigram not in {c["sitting_trigram"] for c in supported}:
                raise ValueError("宅向推导的坐山与 sitting_trigram 不一致")


_PLACEMENT_FACING_ROLES = {
    "door": "door_facing",
    "bed": "headboard",
    "desk": "desk_facing",
    "stove": "fire_mouth",
}


_PLACEMENT_SCHEMA_CONSTRAINTS: Dict[str, Any] = {
    "allOf": [
        {
            "anyOf": [
                {
                    "required": [field],
                    "properties": {field: {"type": "string"}},
                }
                for field in ("location_direction", "facing_direction")
            ]
        },
        {
            "anyOf": [
                {
                    "properties": {
                        field: {"type": "null"}
                        for field in ("facing_direction", "facing_role")
                    }
                },
                {
                    "required": ["facing_direction", "facing_role"],
                    "properties": {
                        field: {"type": "string"}
                        for field in ("facing_direction", "facing_role")
                    },
                },
            ]
        },
        *[
            {
                "if": {"properties": {"purpose": {"const": purpose}}},
                "then": {"properties": {"facing_role": {"enum": [None, role]}}},
            }
            for purpose, role in _PLACEMENT_FACING_ROLES.items()
        ],
        {
            "anyOf": [
                {"properties": {"subject_id": {"type": "null"}}},
                {"properties": {"subject_ids": {"type": "null"}}},
            ]
        },
    ]
}


class Placement(_DeferredModel):
    """门床桌灶的已确认方位。至少提供位置或朝向；两者均未知时省略本对象，
    可在 form_observations 中独立提供形态。朝向和对应 facing_role 必须成对。
    """

    # Publish the same cross-field constraints that facing_semantics enforces.
    # Optional fields may be omitted or explicitly null; neither is a bearing.
    model_config = ConfigDict(json_schema_extra=_PLACEMENT_SCHEMA_CONSTRAINTS)

    object_id: str = Field(min_length=1, max_length=100)
    purpose: Literal["door", "bed", "desk", "stove"]
    location_direction: Optional[Direction] = Field(
        default=None,
        description="已确认落宫，默认相对全宅中心；显式关联楼层时使用该层独立确认的中心与图纸方向，统一宅/年盘不代表自动定各层宅运。未知省略，不由朝向推断",
    )
    facing_direction: Optional[Direction] = Field(
        default=None,
        description="门朝向、床头、书桌朝向或已确认的灶火门，独立于位置；提供时必须同时提供对应 facing_role",
    )
    facing_role: Optional[
        Literal["door_facing", "headboard", "desk_facing", "fire_mouth"]
    ] = Field(
        default=None,
        description="与 facing_direction 成对：door=door_facing、bed=headboard、desk=desk_facing、stove=fire_mouth",
    )
    subject_id: Optional[str] = Field(
        default=None,
        description="单人使用；与 subject_ids 互斥，两者省略时应用全部已提供住户",
    )
    subject_ids: Optional[List[str]] = Field(
        default=None,
        min_length=1,
        max_length=50,
        json_schema_extra={"uniqueItems": True},
        description="对象实际共用住户 ID 集合；与 subject_id 互斥，不纳入其他住户，宅盘仍单独保留",
    )
    observation_basis: Basis = "user_confirmed"

    def applies_to_occupant(self, subject_id: str) -> bool:
        """Use one scope predicate for findings and inverse direction options."""
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
            raise ValueError("布局对象至少提供位置或朝向，不猜测缺失位置")
        if (self.facing_direction is None) != (self.facing_role is None):
            raise ValueError("facing_direction 和 facing_role 必须一起提供")
        if (
            self.facing_role is not None
            and self.facing_role != _PLACEMENT_FACING_ROLES[self.purpose]
        ):
            raise ValueError("facing_role 与 purpose 不匹配")
        return self


class BazhaiRequest(_DeferredModel):
    house: Optional[House] = Field(
        default=None,
        description="已确认的住宅坐向；未知可省略保留其他可算层，不用桌朝向补宅向",
    )
    occupants: List[Occupant] = Field(
        default_factory=list,
        max_length=50,
        description="独立命卦住户资料；同住不代表共用家具，不由八字喜忌补出",
    )
    placements: List[Placement] = Field(
        default_factory=list,
        max_length=200,
        description="门床桌灶已确认的位置、朝向和使用人；位置与朝向分别核对，未知不补宫",
    )
    ruleset_id: BazhaiRuleset = Field(
        default="bazhai_sitting_v1",
        description="八宅坐山规则版本；不表示其他流派均已覆盖",
    )

    @model_validator(mode="after")
    def unique_ids(self) -> "BazhaiRequest":
        if self.house is not None:
            self.house.check_sitting_trigram(
                self.house.bearing_uncertainty_degrees or 0
            )
        ids = [o.subject_id for o in self.occupants]
        context = getattr(self, "environmental_context", None)
        known_subjects = set(ids) | (
            {m.subject_id for m in context.household_members} if context else set()
        )
        objects = [p.object_id for p in self.placements]
        if len(set(ids)) != len(ids) or len(set(objects)) != len(objects):
            raise ValueError("住户及布局对象 ID 必须分别唯一")
        if self.house is not None and self.house.object_id in ids:
            raise ValueError("住宅 ID 不得与住户 ID 重复")
        if self.house is not None and self.house.object_id in objects:
            raise ValueError("布局对象 ID 不得与住宅 ID 重复")
        if any(
            referenced not in known_subjects
            for p in self.placements
            for referenced in (
                p.subject_ids
                if p.subject_ids is not None
                else [p.subject_id] if p.subject_id is not None else []
            )
        ):
            raise ValueError("布局对象引用了未提供的住户")
        return self


class EnvironmentFeature(_DeferredModel):
    object_id: str = Field(min_length=1, max_length=100)
    direction: Direction = Field(
        description="已确认特征落宫，默认以全宅中心为准；若environmental_context.floors将对象关联楼层，则必须相对该层独立确认中心及对齐后的方位，不由全宅中心自动投射。"
    )
    classification: Literal["sand", "water", "mixed", "unknown"]
    classification_basis: Basis
    evidence: str = Field(
        min_length=1,
        max_length=1000,
        description="用户确认或测量的分类依据；不按物品名称自动猜测砂水",
    )
    label: Optional[str] = Field(default=None, max_length=100)


class JinsuoRequest(_DeferredModel):
    features: List[EnvironmentFeature] = Field(
        default_factory=list,
        max_length=500,
        description="已确认方位、砂水分类及来源的环境特征，不按物件名称猜分类",
    )
    ruleset_id: JinsuoRuleset = Field(
        default="jinsuo_basic_fixed_v1", description="金锁八宫固定砂水偏好规则版本"
    )

    @model_validator(mode="after")
    def unique_features(self) -> "JinsuoRequest":
        ids = [f.object_id for f in self.features]
        if len(set(ids)) != len(ids):
            raise ValueError("环境特征 object_id 必须唯一")
        return self


class AnnualRequest(TimeInput):
    effective_year: Optional[Year] = Field(
        default=None,
        ge=1800,
        le=2199,
        description="已确认立春后的有效年；与 query_at 二选一",
    )
    query_at: Optional[datetime] = Field(
        default=None, description="含时区的查询时刻，以立春交节换年"
    )
    ruleset_id: AnnualRuleset = Field(
        default="annual_zibai_lichun_v1",
        description="立春换年九宫紫白规则版本；非历史山向宅盘",
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "anyOf": [
                        {
                            "properties": {
                                "effective_solar_year": {"type": "null"},
                                "solar_month_number": {"type": "null"},
                            }
                        },
                        {
                            "required": ["effective_solar_year", "solar_month_number"],
                            "properties": {
                                "effective_solar_year": {"type": "integer"},
                                "solar_month_number": {"type": "integer"},
                            },
                        },
                    ]
                },
                {
                    "anyOf": [
                        {"properties": {"query_at": {"type": "null"}}},
                        {
                            "properties": {
                                "effective_solar_year": {"type": "null"},
                                "solar_month_number": {"type": "null"},
                            }
                        },
                    ]
                },
            ],
        }
    )
    query_at: Optional[datetime] = Field(
        default=None,
        json_schema_extra={"pattern": r"(?:[zZ]|[+-]\d{2}:?\d{2})$"},
        description="含时区的实际查询时刻；以十二个节的交节瞬间换月，以立春换有效年，不是农历初一或公历月首",
    )
    effective_solar_year: Optional[StrictInt] = Field(
        default=None,
        ge=1800,
        le=2199,
        description="已独立确认的立春后有效年；与solar_month_number成对，与query_at互斥。一月公历日期不能直接当作本年",
    )
    solar_month_number: Optional[StrictInt] = Field(
        default=None,
        ge=1,
        le=12,
        description="已确认节月：1=立春寅月，11=大雪子月，12=下一公历年的小寒丑月；不是农历月、闰月或公历月",
    )
    ruleset_id: Literal["monthly_zibai_jie_v1"] = Field(
        default="monthly_zibai_jie_v1",
        description="Monthly Zi Bai rule profile using the declared solar year and solar-term month boundaries.",
    )

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
    """One explicitly selected historical event, never the query date."""

    basis: Literal[
        "construction_completion",
        "first_occupancy",
        "confirmed_major_renovation",
        "expert_confirmed",
    ]
    evidence: str = Field(min_length=1, max_length=2000)
    period_number: Optional[int] = Field(default=None, ge=1, le=9)
    effective_event_year: Optional[int] = Field(default=None, ge=1800, le=2199)
    event_at: Optional[datetime] = None
    qualifies_for_period_reset: Optional[bool] = None

    @model_validator(mode="after")
    def selected_event(self) -> "HousePeriod":
        if (
            sum(
                x is not None
                for x in (self.period_number, self.effective_event_year, self.event_at)
            )
            != 1
        ):
            raise ValueError(
                "定运需且仅需 period_number、effective_event_year、event_at 之一"
            )
        if not self.evidence.strip():
            raise ValueError("定运 evidence 不得为空白")
        if self.event_at is not None:
            AnnualRequest(query_at=self.event_at, timezone_name=self.timezone_name)
        if self.basis == "expert_confirmed" and self.period_number is None:
            raise ValueError("expert_confirmed 必须显式确认 period_number")
        if self.basis == "confirmed_major_renovation":
            if self.qualifies_for_period_reset is not True:
                raise ValueError(
                    "大修换运须明确 qualifies_for_period_reset=true 并记录依据"
                )
        elif self.qualifies_for_period_reset is not None:
            raise ValueError("qualifies_for_period_reset 仅用于已确认的大修换运")
        return self


class ExternalFormObservation(_DeferredModel):
    """Confirmed external forms in house-centred sectors, not indoor backing."""

    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"properties": {key: {"type": "boolean"}}, "required": [key]}
                for key in ("mountain_present", "water_present")
            ]
        }
    )
    direction: Direction
    mountain_present: Optional[StrictBool] = None
    water_present: Optional[StrictBool] = None
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")

    @model_validator(mode="after")
    def explicit_observation(self) -> "ExternalFormObservation":
        if self.mountain_present is None and self.water_present is None:
            raise ValueError("外局须至少明确山形或水形的一项存在/不存在观察")
        if not self.evidence.strip():
            raise ValueError("外局 evidence 不得为空白")
        return self


class XuankongInterpretationRequest(_DeferredModel):
    """An opt-in, limited rule layer; current period never resets natal age."""

    model_config = ConfigDict(
        json_schema_extra=cast(
            Dict[str, Any],
            {
                "allOf": [
                    {
                        "if": {
                            "required": ["fixed_lingzheng"],
                            "properties": {
                                "fixed_lingzheng": {
                                    "type": "object",
                                    "required": ["five_period_half"],
                                    "properties": {
                                        "five_period_half": {"type": "string"}
                                    },
                                }
                            },
                        },
                        "then": {
                            "required": ["current_period_number"],
                            "properties": {"current_period_number": {"const": 5}},
                        },
                    },
                    *[
                        {
                            "not": {
                                "required": ["external_forms", "fixed_lingzheng"],
                                "properties": {
                                    "external_forms": {
                                        "contains": {
                                            "required": ["direction", "water_present"],
                                            "properties": {
                                                "direction": {"const": direction},
                                                "water_present": {"const": water},
                                            },
                                        }
                                    },
                                    "fixed_lingzheng": {
                                        "type": "object",
                                        "required": ["observations"],
                                        "properties": {
                                            "observations": {
                                                "contains": {
                                                    "required": [
                                                        "direction",
                                                        "river_water_present",
                                                    ],
                                                    "properties": {
                                                        "direction": {
                                                            "const": direction
                                                        },
                                                        "river_water_present": {
                                                            "const": True
                                                        },
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                            }
                        }
                        for direction in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
                        for water in (False,)
                    ],
                ],
                "anyOf": [
                    {
                        "properties": {
                            "current_period_number": {"type": "null"},
                            "period_evidence": {"type": "null"},
                        }
                    },
                    {
                        "properties": {
                            "current_period_number": {"type": "integer"},
                            "period_evidence": {"type": "string"},
                        },
                        "required": ["current_period_number", "period_evidence"],
                    },
                ],
            },
        )
    )
    ruleset_id: Literal["xuankong_conditioned_v1"] = "xuankong_conditioned_v1"
    include_calculation_reading: StrictBool = Field(
        default=True,
        description="已请求解释时默认返回带完整上下文引用的玄空固定中文释义；可显式关闭，不验证任意模型正文或现实预测",
    )
    timeliness_ruleset_id: Optional[Literal["wang_zhongzhou_timeliness_v1"]] = Field(
        default=None,
        description="显式选择王亭之上卷基本旺生衰死与互用数字参考；不扩充当令外局条件或产生综合吉凶",
    )
    host_guest_ruleset_id: Optional[Literal["shen_2011_host_guest_v1"]] = Field(
        default=None,
        description="显式选择沈氏2011整理本所收主客定义：坐山宫山主、向首宫向主及地运山向盘层比较；保留216条下卦关系词差异，不合并原书异说或推导吉凶、81对专属断语",
    )
    fixed_lingzheng: Optional[FixedLingzhengRequest] = Field(
        default=None,
        description="显式选择沈氏固定零正与五运分段；不替代山向飞星或自动合成现场吉凶",
    )
    current_period_number: Optional[StrictInt] = Field(
        default=None,
        ge=1,
        le=9,
        description="明确确认的评价时运，与历史宅运分开；不从宅运或年星数字推断",
    )
    period_evidence: Optional[str] = Field(
        default=None, min_length=1, max_length=1000, pattern=r"\S"
    )
    external_forms: List[ExternalFormObservation] = Field(
        default_factory=list,
        max_length=8,
        json_schema_extra={
            "allOf": [
                {
                    "contains": {
                        "type": "object",
                        "properties": {"direction": {"const": direction}},
                        "required": ["direction"],
                    },
                    "minContains": 0,
                    "maxContains": 1,
                }
                for direction in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
            ]
        },
        description="以全宅中心八宫记录外部山形/水形；不沿用金锁砂水、室内靠背或摆件分类",
    )

    @model_validator(mode="after")
    def distinct_confirmed_facts(self) -> "XuankongInterpretationRequest":
        if self.fixed_lingzheng is not None:
            if (
                self.fixed_lingzheng.five_period_half is not None
                and self.current_period_number != 5
            ):
                raise ValueError("零正五运分段仅可用于明确评价五运")
            old_water = {o.direction: o.water_present for o in self.external_forms}
            for observation in self.fixed_lingzheng.observations:
                old = old_water.get(observation.direction)
                if observation.river_water_present is True and old is False:
                    raise ValueError(
                        "同一全宅方向的有水事实不能在飞星与固定零正观察中冲突"
                    )
        if (self.current_period_number is None) != (self.period_evidence is None):
            raise ValueError("current_period_number 与 period_evidence 必须一起提供")
        if self.period_evidence is not None and not self.period_evidence.strip():
            raise ValueError("period_evidence 不得为空白")
        directions = [o.direction for o in self.external_forms]
        if len(set(directions)) != len(directions):
            raise ValueError("同一全宅外局方向不能重复或互相覆盖")
        return self


class XuankongRequest(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "properties": {
                        "house": {
                            "properties": {
                                "bearing_uncertainty_degrees": {
                                    "anyOf": [
                                        {"type": "number", "maximum": 7.5},
                                        {"type": "null"},
                                    ]
                                }
                            }
                        }
                    }
                }
            ]
        }
    )
    house: Optional[House] = Field(
        default=None, description="已确认的住宅磁北宅向；不是家具朝向，不由年盘补出"
    )
    period: Optional[HousePeriod] = Field(
        default=None,
        description="历史建成、入住或合资格大修定运的独立依据；查询日期不能代替",
    )
    ruleset_id: Literal["xuankong_zhongzhou_v1"] = Field(
        default="xuankong_zhongzhou_v1",
        description="中州派玄空规则版本，误差跨边界保留候选",
    )
    interpretation: Optional[XuankongInterpretationRequest] = Field(
        default=None,
        description="显式启用有限星组合五行、当令外局与床/门取用条件；不等于完整81组合断法或全宅勘察",
    )
    city_gate: Optional[CityGateRequest] = Field(
        default=None,
        description="独立选择沈氏城门运盘与同元龙水形条件；参考运显式提供，不重置历史宅盘。仅算门位时无需历史定运或现场水形。",
    )

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
        if (
            self.house is not None
            and self.house.facing_degrees is not None
            and self.house.north_reference != "magnetic"
        ):
            raise ValueError("本玄空版本使用磁北宅向；真北需先由用户完成磁偏角校正")
        return self

    @property
    def effective_bearing_uncertainty(self) -> float:
        if (
            self.house is not None
            and self.house.bearing_uncertainty_degrees is not None
        ):
            return self.house.bearing_uncertainty_degrees
        return 0.0


class LayoutConstraint(_DeferredModel):
    """Action permissions, never evidence of a layout's physical properties."""

    object_id: str = Field(min_length=1, max_length=100)
    can_relocate: Optional[StrictBool] = None
    can_rotate: Optional[StrictBool] = None
    can_add_items: Optional[StrictBool] = None
    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def nonblank_evidence(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("动作约束依据不得为空白")
        return value


class LayoutAlternative(_DeferredModel):
    """A user-supplied proposal, independently observed at its new position.

    A move within the same compass sector is still a move. Explicit changes
    therefore cannot be inferred solely from the two directional labels.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": [field], "properties": {field: {"type": "object"}}}
                for field in ("placement", "form_observation", "environmental_context")
            ]
        }
    )

    candidate_id: str = Field(min_length=1, max_length=100)
    object_id: str = Field(min_length=1, max_length=100)
    changes: List[Literal["location", "facing"]] = Field(
        min_length=1, max_length=2, json_schema_extra={"uniqueItems": True}
    )
    placement: Optional[Placement] = None
    form_observation: Optional[FormObservation] = None
    features: List[EnvironmentFeature] = Field(
        default_factory=list,
        max_length=1,
        description="候选对象在新位置/朝向下独立确认的砂水特征；仅限本候选object_id，不继承搬转前分类与落宫，须选择jinsuo",
    )
    environmental_context: Optional[EnvironmentalContext] = Field(
        default=None,
        description="候选位置独立确认的楼层/环境事实；搬转后不继承现状楼层归属及环境观察，人物身份不得改变",
    )
    physically_feasible: Optional[StrictBool] = Field(
        default=None,
        description="逐方案确认能容纳家具、保持操作空间与通行；允许移动不等于此项为真",
    )
    evidence: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def consistent_candidate(self) -> "LayoutAlternative":
        if not self.evidence.strip() or len(set(self.changes)) != len(self.changes):
            raise ValueError("候选依据不得空白，changes 不得重复")
        observations = [self.placement, self.form_observation]
        supplied = [o for o in observations if o is not None]
        related = self.environmental_context is not None and any(
            self.object_id in (r.source_object_id, r.target_object_id)
            for r in self.environmental_context.interior_relations
        )
        review = (
            self.environmental_context.workstation_review
            if self.environmental_context
            else None
        )
        if review:
            related = (
                related
                or any(a.object_id == self.object_id for a in review.activities)
                or any(
                    self.object_id in (r.entrance_id, r.desk_id, r.barrier_id)
                    for r in review.entry_barriers
                )
            )
        if (not supplied and not related) or any(
            o.object_id != self.object_id for o in supplied
        ):
            raise ValueError("候选需独立位置或形态观察，且 object_id 必须一致")
        if supplied and len({o.purpose for o in supplied}) != 1:
            raise ValueError("候选位置与形态用途必须一致")
        JinsuoRequest(features=self.features)
        if any(feature.object_id != self.object_id for feature in self.features):
            raise ValueError("候选砂水只能引用本候选 object_id")
        if self.placement is not None and self.placement.location_direction is not None:
            if any(
                feature.direction != self.placement.location_direction
                for feature in self.features
            ):
                raise ValueError("同一候选对象的砂水方向与已确认位置必须一致")
        return self


def _validate_floor_sector_assignments(
    context: EnvironmentalContext, location_object_ids: set[str]
) -> None:
    for floor in context.floors:
        if not set(floor.object_ids) & location_object_ids:
            continue
        if (
            context.orientation is None
            or not context.orientation.ready_for_sectors()
            or floor.uses_shared_orientation is not True
            or floor.center_confirmed is not True
            or floor.floorplan_alignment_confirmed is not True
        ):
            raise ValueError(
                f"楼层 {floor.floor_id} 的共用方向、独立中心及户型偏移未确认，不能提交该层实际落宫"
            )


def _validate_floor_user_assignments(
    context: EnvironmentalContext, placements: List[Placement]
) -> None:
    for floor in context.floors:
        if not floor.usage_confirmed:
            continue
        for placement in placements:
            if placement.object_id not in floor.object_ids:
                continue
            explicit_users = placement.subject_ids or (
                [placement.subject_id] if placement.subject_id is not None else []
            )
            if set(explicit_users) - set(floor.subject_ids):
                raise ValueError(
                    f"楼层 {floor.floor_id} 的完整使用名单与对象 {placement.object_id} 明确使用人矛盾"
                )


def _validate_static_floor_frames(
    current: Optional[EnvironmentalContext],
    proposed: EnvironmentalContext,
    target_id: str,
    static_feature_ids: set[str],
    changes: set[str],
) -> None:
    if (
        current is not None
        and current.orientation is not None
        and proposed.orientation is not None
        and current.orientation.north_reference is not None
        and proposed.orientation.north_reference is not None
        and current.orientation.north_reference != proposed.orientation.north_reference
    ):
        raise ValueError("家具候选不得改变已确认的全局 north_reference")
    original_floors = {f.floor_id: f for f in current.floors} if current else {}
    original_objects = {
        object_id: floor
        for floor in original_floors.values()
        for object_id in floor.object_ids
    }
    frame_fields = (
        "floor_id",
        "level",
        "space_kind",
        "uses_shared_orientation",
        "center_confirmed",
        "floorplan_alignment_confirmed",
    )
    old_target = original_objects.get(target_id)
    new_target = next(
        (floor for floor in proposed.floors if target_id in floor.object_ids), None
    )
    if (
        old_target is not None
        and new_target is not None
        and "location" not in changes
        and any(
            getattr(old_target, field) != getattr(new_target, field)
            for field in ("floor_id", "level", "space_kind")
        )
    ):
        raise ValueError("候选楼层或空间归属变化必须声明location搬位并核对搬位许可")
    for floor in proposed.floors:
        previous = original_floors.get(floor.floor_id)
        if previous is not None and any(
            getattr(previous, field) != getattr(floor, field) for field in frame_fields
        ):
            raise ValueError("家具候选不得改写已有楼层的身份或坐标参考系")
        for object_id in set(floor.object_ids) - {target_id}:
            before = original_objects.get(object_id)
            if before is None:
                if object_id in static_feature_ids:
                    raise ValueError("候选不得将未移动的既有砂水特征改为新的楼层坐标")
                continue
            if any(
                getattr(before, field) != getattr(floor, field)
                for field in frame_fields
            ):
                raise ValueError("候选不得改变未移动对象的楼层或坐标参考系")


def _context_roles(context: Optional[EnvironmentalContext]) -> Dict[str, set[str]]:
    return (
        {
            obj.object_id: {
                value for value in (obj.role, obj.purpose) if value is not None
            }
            | ({"sharp_corner"} if obj.role == "pillar_corner" else set())
            for obj in context.objects
        }
        if context is not None
        else {}
    )


class AssessRequest(BazhaiRequest):
    workstation_layout: Optional[WorkstationLayoutInput] = Field(
        default=None,
        description="带米制尺寸与显式参考系的工位几何、传统条件解释及有限候选搜索；单独输出workstation_layout_analysis，不默认开启桌面流派。照片/误差保持候选，动作沿用layout_constraints。",
    )
    scene: Optional[Literal["workstation", "shared_rental", "home"]] = Field(
        default=None,
        description="工位/合租/家居场景；局部按九宫飞星、金锁优先审查，八宅命卦独立。未指定 methods 时按已有事实选层，显式列表优先。",
    )
    environmental_context: Optional[EnvironmentalContext] = Field(
        default=None,
        description="专家口径的方向与户型确认、家庭辈分/排行、多楼层/院落、无方位环境事实；独立于八字紫微与八宅命卦，不按身份或命盘补方向。",
    )
    layout_constraints: List[LayoutConstraint] = Field(
        default_factory=list,
        max_length=200,
        description="已确认对象的搬动、转向或新增许可；不证明位置、容纳和通行可行，不阻塞普通解释",
    )
    layout_alternatives: List[LayoutAlternative] = Field(
        default_factory=list,
        max_length=50,
        description="用户实际提出的候选变化；新位置、现场关系与物理可行性独立确认，原关系任一端移动需重核",
    )
    surface_layouts: List[SurfaceLayout] = Field(
        default_factory=list,
        max_length=100,
        description="显式选择作者规则的矩形桌面物件；near 靠坐者、far 远离坐者，不等于罗盘方位",
    )
    surface_constraints: List[SurfaceConstraints] = Field(
        default_factory=list,
        max_length=100,
        description="已提交桌面的物件许可、固定项和逐区确认的可容纳范围；不从照片空白推可行区",
    )
    form_observations: List[FormObservation] = Field(
        default_factory=list,
        max_length=200,
        description="入口可见、直冲、实体背靠等独立形态观察；照片保留候选，无方位或生辰也可独立分析",
    )
    form_ruleset_id: Literal["indoor_command_authored_v1"] = Field(
        default="indoor_command_authored_v1",
        description="室内形态作者规则版本，保留实际来源与覆盖范围",
    )
    element_adjustments: List[ElementAdjustment] = Field(
        default_factory=list,
        max_length=100,
        description="对已算星角色的有限五行调节请求；不是个人喜用、材料资格、剂量或现实效力保证",
    )
    element_ruleset_id: Literal["afsi_element_balance_v1"] = Field(
        default="afsi_element_balance_v1",
        description="有限五行关系作者版本；各方法不能相互抵消",
    )
    annual_remedy_ruleset_id: Optional[Literal["pang_2026_annual_v1"]] = Field(
        default=None,
        description="显式选择作者2026年盘的有限调节规则；不外推年份或全宅结论",
    )
    analyze_layout: bool = Field(
        default=False,
        description="对布局对象计算跨层落宫、位置/朝向调整方位及五行关系；通用于门床桌灶。原始盘与本分析的完成状态分别保留。",
    )
    features: List[EnvironmentFeature] = Field(
        default_factory=list,
        max_length=500,
        description="实际确认方位和砂水分类的金锁环境特征；物件名称不自动推分类，候选新位置须重核",
    )
    effective_year: Optional[Year] = Field(
        default=None,
        ge=1800,
        le=2199,
        description="已确认的年星有效年；不代替玄空历史宅运",
    )
    query_at: Optional[datetime] = Field(
        default=None,
        description="含时区的实际年度查询时刻；按立春边界推有效年，不用于补宅运",
    )
    timezone_name: str = Field(
        default="Asia/Shanghai",
        description="年度查询的 IANA 时区或 UTC 偏移；与参考北分别核对",
    )
    methods: Optional[List[Method]] = Field(
        default=None,
        description="null/省略表示自动选法；场景/作者输入按事实选择，旧无场景无作者请求使用三法。显式列表（含空列表）优先。",
    )
    jinsuo_ruleset_id: JinsuoRuleset = Field(
        default="jinsuo_basic_fixed_v1", description="金锁八宫固定砂水规则版本"
    )
    annual_ruleset_id: AnnualRuleset = Field(
        default="annual_zibai_lichun_v1",
        description="立春换年九宫紫白版本；年盘不是历史宅盘",
    )
    xuankong: Optional[XuankongRequest] = Field(
        default=None,
        description="显式启用宅盘时的历史定运和宅向；可继承顶层 house，年星不继承宅运",
    )
    monthly: Optional[MonthlyRequest] = Field(
        default=None,
        description="独立月紫白输入；提供时自动选月层，显式methods仍优先。显式选择monthly_stars而省略本项时只继承顶层query_at/timezone_name，不以effective_year猜节月。月星不替代年星或宅盘，不生成布局处方。",
    )

    @property
    def workstation_review(self) -> Any:
        return (
            self.environmental_context.workstation_review
            if self.environmental_context
            else None
        )

    @property
    def selected_methods(self) -> List[Method]:
        # Keep null in the public input model so validation/dump/binding does
        # not turn automatic selection into an explicit caller choice.
        if self.methods is not None:
            return self.methods
        from typing import cast

        from .method_policy import select_methods

        return cast(List[Method], select_methods(self.model_dump()))

    @model_validator(mode="after")
    def validate_layers(self) -> "AssessRequest":
        if (
            not self.selected_methods
            and not self.form_observations
            and not self.surface_layouts
            and self.environmental_context is None
            and self.workstation_layout is None
            and self.scene is None
        ):
            raise ValueError(
                "至少选择一层计算；独立形态/桌面作者计算可用 methods=[] 并提供相应观察"
            )
        surfaces = {s.object_id: s for s in self.surface_layouts}
        if len(surfaces) != len(self.surface_layouts):
            raise ValueError("桌面对象不能重复")
        constraints = {c.object_id: c for c in self.surface_constraints}
        if len(constraints) != len(self.surface_constraints):
            raise ValueError("同一桌面的动作约束不能重复")
        if set(constraints) - set(surfaces):
            raise ValueError("桌面约束必须关联已提供桌面")
        for constraint in self.surface_constraints:
            item_ids = {i.object_id for i in surfaces[constraint.object_id].items}
            if set(constraint.locked_item_ids) - item_ids:
                raise ValueError("固定物件必须属于关联桌面")
        for placement in self.placements:
            if placement.object_id in surfaces and placement.purpose != "desk":
                raise ValueError("桌面作者规则只能关联实际书桌，不能套用其他家具")
        if any(
            a.target_method not in self.selected_methods
            for a in self.element_adjustments
        ):
            raise ValueError("元素目标须属于本次选中的计算方法")
        forms = {o.object_id: o for o in self.form_observations}
        if len(forms) != len(self.form_observations):
            raise ValueError("同一对象形态观察不能重复或互相覆盖")
        for object_id in set(forms) & set(surfaces):
            if forms[object_id].purpose != "desk":
                raise ValueError(
                    "同一对象的桌面与形态用途不一致；桌面作者规则只能用于书桌"
                )
        for placement in self.placements:
            if (
                placement.object_id in forms
                and placement.purpose != forms[placement.object_id].purpose
            ):
                raise ValueError("同一对象的形态用途与布局用途不一致")
            if placement.location_direction is not None and any(
                feature.object_id == placement.object_id
                and feature.direction != placement.location_direction
                for feature in self.features
            ):
                raise ValueError("同一对象的砂水方向与已确认位置必须一致")
        request_ids = [a.request_id for a in self.element_adjustments]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("元素调节请求 ID 必须唯一")
        objects = {p.object_id for p in self.placements}
        known = objects | set(forms)
        if self.workstation_layout is not None:
            spatial = self.workstation_layout
            scene = spatial.scene
            desk_ids = {s.desk_id for s in scene.seats}
            occupant_ids = {occupant.subject_id for occupant in self.occupants}
            if any(
                seat.subject_ids is not None and set(seat.subject_ids) - occupant_ids
                for seat in scene.seats
            ):
                raise ValueError("实测工位subject_ids须引用本次明确提供的使用人")
            desktop_ids = {s.desk_id for s in scene.desktops}
            if desk_ids & (objects | set(forms)) or desktop_ids & set(surfaces):
                raise ValueError(
                    "实测工位的位置/形态/桌面由空间层负责；同一对象不能同时提交另一份位置或形态"
                )
            geometry_ids = {b.object_id for b in scene.bodies}
            geometry_ids.update(o.object_id for o in scene.openings)
            geometry_ids.update(i.object_id for d in scene.desktops for i in d.items)
            if geometry_ids & (objects | set(forms)):
                raise ValueError(
                    "实测场景对象不能同时提交另一份位置/形态；候选关系须由自己的新几何重算"
                )
            known.update(geometry_ids)
            if any(f.object_id in geometry_ids for f in self.features):
                raise ValueError(
                    "实测对象砂水分类用scene.bodies[].sand_water，方区由所选实测参考系计算，不重复提交features"
                )
            if any(c.object_id in geometry_ids for c in self.layout_alternatives):
                raise ValueError(
                    "实测对象候选通过workstation_layout.search提供，避免旧关系与新几何混用"
                )
            if self.environmental_context:
                if any(
                    set(floor.object_ids) & geometry_ids
                    for floor in self.environmental_context.floors
                ):
                    raise ValueError(
                        "实测对象的参考层级与中心由scene.compass独立确认，不叠加另一份floors坐标绑定"
                    )
                if any(
                    observation.object_id in geometry_ids
                    for observation in self.environmental_context.observations
                ):
                    raise ValueError(
                        "实测对象的形态由场景重算，不继承旧environmental_context.observations"
                    )
                if {
                    obj.object_id for obj in self.environmental_context.objects
                } & geometry_ids:
                    raise ValueError(
                        "实测空间对象身份由scene负责，不同时提交environmental_context.objects中的另一份身份"
                    )
                if any(
                    {r.source_object_id, r.target_object_id} & geometry_ids
                    for r in self.environmental_context.interior_relations
                ):
                    raise ValueError(
                        "实测对象的室内关系由空间层重算，不同时接受另一份关系判断"
                    )
                review = self.workstation_review
                if review and (
                    any(a.object_id in desk_ids for a in review.activities)
                    or any(
                        {r.entrance_id, r.desk_id, r.barrier_id} & geometry_ids
                        for r in review.entry_barriers
                    )
                ):
                    raise ValueError(
                        "实测工位活动/入口关系由空间层负责，不重复提交作者观察"
                    )
            interpretation = self.xuankong.interpretation if self.xuankong else None
            if (
                interpretation
                and spatial.evaluation_period is not None
                and interpretation.current_period_number is not None
                and spatial.evaluation_period != interpretation.current_period_number
            ):
                raise ValueError("工位评价运与明确的玄空评价运不得矛盾")
            if scene.compass and scene.compass.chart_binding_confirmed:
                for house in (
                    self.house,
                    self.xuankong.house if self.xuankong else None,
                ):
                    if (
                        house
                        and house.north_reference
                        and house.north_reference != scene.compass.north_reference
                    ):
                        raise ValueError(
                            "已绑定宅盘的图纸北基准须与宅向一致，不自动换算"
                        )
        if self.environmental_context is not None:
            self.environmental_context.validate_references(
                known | set(surfaces) | {f.object_id for f in self.features},
                [o.subject_id for o in self.occupants],
                {p.object_id: p.purpose for p in self.placements}
                | {o.object_id: o.purpose for o in self.form_observations}
                | {s.object_id: "desk" for s in self.surface_layouts},
            )
            known.update(obj.object_id for obj in self.environmental_context.objects)
            _validate_floor_user_assignments(
                self.environmental_context, self.placements
            )
            _validate_floor_sector_assignments(
                self.environmental_context,
                {
                    p.object_id
                    for p in self.placements
                    if p.location_direction is not None
                }
                | {f.object_id for f in self.features}
                | {
                    f.object_id
                    for c in self.layout_alternatives
                    if c.environmental_context is None
                    for f in c.features
                },
            )
            orientation = self.environmental_context.orientation
            if orientation is not None:
                proposals = [
                    c.placement
                    for c in self.layout_alternatives
                    if c.placement and c.environmental_context is None
                ]
                placements = [*self.placements, *proposals]
                proposal_features = [
                    feature
                    for candidate in self.layout_alternatives
                    if candidate.environmental_context is None
                    for feature in candidate.features
                ]
                external_forms = bool(
                    self.xuankong
                    and (
                        (
                            self.xuankong.interpretation
                            and self.xuankong.interpretation.external_forms
                        )
                        or (
                            self.xuankong.city_gate
                            and self.xuankong.city_gate.observations
                        )
                    )
                )
                if not orientation.ready_for_sectors() and (
                    any(p.location_direction is not None for p in placements)
                    or self.features
                    or proposal_features
                    or external_forms
                ):
                    raise ValueError(
                        "户型方位、偏移及中心未确认，不能同时提交实际落宫、砂水分宫或外局分宫；原始盘与独立形态仍可计算"
                    )
                if not orientation.direction_confirmed and any(
                    p.facing_direction is not None for p in placements
                ):
                    raise ValueError("方位未确认，不能同时提交已确认家具朝向")
                for house in (
                    self.house,
                    self.xuankong.house if self.xuankong else None,
                ):
                    if (
                        house is not None
                        and house.north_reference is not None
                        and orientation.north_reference is not None
                        and house.north_reference != orientation.north_reference
                    ):
                        raise ValueError("环境方位与宅向的 north_reference 不一致")
        constraint_ids = [c.object_id for c in self.layout_constraints]
        if (
            len(set(constraint_ids)) != len(constraint_ids)
            or set(constraint_ids) - known
        ):
            raise ValueError("家具动作约束须唯一且引用已提供对象")
        for furniture_constraint in self.layout_constraints:
            surface_constraint = constraints.get(furniture_constraint.object_id)
            if (
                surface_constraint is not None
                and furniture_constraint.can_add_items is not None
                and surface_constraint.can_add_items is not None
                and furniture_constraint.can_add_items
                != surface_constraint.can_add_items
            ):
                raise ValueError("同一对象的家具与桌面新增许可不得冲突")
        candidates = [c.candidate_id for c in self.layout_alternatives]
        if len(set(candidates)) != len(candidates):
            raise ValueError("布局候选 candidate_id 必须唯一")
        current = {p.object_id: p for p in self.placements}
        for candidate in self.layout_alternatives:
            if candidate.features and "jinsuo" not in self.selected_methods:
                raise ValueError("候选砂水特征须在 methods 中选择 jinsuo")
            if candidate.object_id not in known:
                raise ValueError("布局候选须引用已有位置或形态对象")
            base = current.get(candidate.object_id) or forms.get(candidate.object_id)
            base_purpose = (
                base.purpose
                if base is not None
                else next(
                    (
                        role
                        for role in _context_roles(self.environmental_context).get(
                            candidate.object_id, set()
                        )
                        if role in {"bed", "desk", "stove", "door"}
                    ),
                    None,
                )
            )
            for obs in (candidate.placement, candidate.form_observation):
                if obs is not None and obs.purpose != base_purpose:
                    raise ValueError("候选不得改变对象用途")
            proposal = candidate.placement
            candidate_context = candidate.environmental_context
            if candidate_context is not None:
                current_definitions = (
                    {obj.object_id: obj for obj in self.environmental_context.objects}
                    if self.environmental_context is not None
                    else {}
                )
                for obj in candidate_context.objects:
                    prior = current_definitions.get(obj.object_id)
                    if prior is not None and any(
                        getattr(prior, field) != getattr(obj, field)
                        for field in ("kind", "purpose", "role")
                    ):
                        raise ValueError("候选不得更换已确认物件的类型或角色")
                prior_uses = (
                    {
                        fact.object_id: fact.element_use
                        for fact in self.environmental_context.material_facts
                        if fact.element_use is not None
                    }
                    if self.environmental_context is not None
                    else {}
                )
                for fact in candidate_context.material_facts:
                    if fact.object_id in prior_uses and fact.element_use not in (
                        None,
                        prior_uses[fact.object_id],
                    ):
                        raise ValueError("搬转候选不得更换已明确的元素代表物用途问题")
                    for old_fact in (
                        self.environmental_context.material_facts
                        if self.environmental_context is not None
                        else []
                    ):
                        if (
                            old_fact.object_id != fact.object_id
                            or old_fact.observation_basis == "image_observed"
                        ):
                            continue
                        if (
                            old_fact.application
                            and fact.application
                            and old_fact.application.target_request_id is not None
                            and old_fact.application.target_request_id
                            != fact.application.target_request_id
                        ):
                            raise ValueError("搬转候选不得更换已绑定的材料调节目标")
                        for attribute in ("material", "shape", "colour", "plant_alive"):
                            previous_value, new_value = getattr(
                                old_fact, attribute
                            ), getattr(fact, attribute)
                            if previous_value not in (
                                None,
                                "unknown",
                            ) and new_value not in (None, "unknown", previous_value):
                                raise ValueError(
                                    "搬位/转向候选不得改写同一物件已确认的材质、器形、颜色或存活状态"
                                )
                current_members = (
                    {
                        m.subject_id: m
                        for m in self.environmental_context.household_members
                    }
                    if self.environmental_context
                    else {}
                )
                for member in candidate_context.household_members:
                    if (
                        member.subject_id not in current_members
                        or member.model_dump()
                        != current_members[member.subject_id].model_dump()
                    ):
                        raise ValueError("候选不得新增或更换家庭人物身份")
                candidate_context.validate_references(
                    known
                    | set(surfaces)
                    | {f.object_id for f in self.features}
                    | {f.object_id for f in candidate.features},
                    {o.subject_id for o in self.occupants} | set(current_members),
                    {p.object_id: p.purpose for p in self.placements}
                    | {o.object_id: o.purpose for o in self.form_observations},
                    _context_roles(self.environmental_context),
                    {
                        object_id: floor
                        for floor in (
                            self.environmental_context.floors
                            if self.environmental_context is not None
                            else []
                        )
                        for object_id in floor.object_ids
                        if object_id != candidate.object_id
                    },
                )
                _validate_static_floor_frames(
                    self.environmental_context,
                    candidate_context,
                    candidate.object_id,
                    {
                        f.object_id
                        for f in self.features
                        if f.object_id != candidate.object_id
                    },
                    set(candidate.changes),
                )
                _validate_floor_user_assignments(
                    candidate_context, [proposal] if proposal is not None else []
                )
                _validate_floor_sector_assignments(
                    candidate_context,
                    (
                        {proposal.object_id}
                        if proposal is not None
                        and proposal.location_direction is not None
                        else set()
                    )
                    | {feature.object_id for feature in candidate.features},
                )
                orientation = candidate_context.orientation
                if (
                    orientation is None
                    and self.environmental_context is not None
                    and self.environmental_context.orientation is not None
                ):
                    # A proposal cannot erase an explicitly known uncertainty.
                    orientation = self.environmental_context.orientation
                if orientation is not None:
                    if (
                        (
                            bool(candidate.features)
                            or (
                                proposal is not None
                                and proposal.location_direction is not None
                            )
                        )
                        and not orientation.ready_for_sectors()
                    ) or (
                        proposal is not None
                        and proposal.facing_direction is not None
                        and not orientation.direction_confirmed
                    ):
                        raise ValueError("候选环境方位未确认，不能提交已确认位置或朝向")
                    for house in (
                        self.house,
                        self.xuankong.house if self.xuankong else None,
                    ):
                        if (
                            house is not None
                            and house.north_reference is not None
                            and orientation.north_reference is not None
                            and house.north_reference != orientation.north_reference
                        ):
                            raise ValueError("候选环境与宅向的 north_reference 不一致")
            if proposal is not None:
                known_subjects = {o.subject_id for o in self.occupants} | (
                    {m.subject_id for m in self.environmental_context.household_members}
                    if self.environmental_context
                    else set()
                )
                referenced = proposal.subject_ids or (
                    [proposal.subject_id] if proposal.subject_id else []
                )
                if set(referenced) - known_subjects:
                    raise ValueError("候选引用了未提供的住户")
                before = current.get(candidate.object_id)
                if before is not None:
                    if any(
                        before.applies_to_occupant(subject_id)
                        != proposal.applies_to_occupant(subject_id)
                        for subject_id in known_subjects
                    ):
                        raise ValueError("候选不得更换对象使用人范围")
                    for aspect in ("location", "facing"):
                        old = getattr(before, f"{aspect}_direction")
                        new = getattr(proposal, f"{aspect}_direction")
                        if (
                            old is not None
                            and new is not None
                            and old != new
                            and aspect not in candidate.changes
                        ):
                            raise ValueError("候选方向变化必须在 changes 中明确声明")
        if any(a.object_id not in objects for a in self.element_adjustments):
            raise ValueError("元素调节须引用已提供的布局对象")
        if (
            self.annual_remedy_ruleset_id is not None
            and "annual_stars" not in self.selected_methods
        ):
            raise ValueError("作者年度调节规则须显式选择 annual_stars")
        if len(set(self.selected_methods)) != len(self.selected_methods):
            raise ValueError("methods 不得重复")
        AnnualRequest(
            effective_year=self.effective_year,
            query_at=self.query_at,
            timezone_name=self.timezone_name,
            ruleset_id=self.annual_ruleset_id,
        )
        JinsuoRequest(features=self.features, ruleset_id=self.jinsuo_ruleset_id)
        if self.xuankong is not None and "xuankong_natal" not in self.selected_methods:
            raise ValueError("提供 xuankong 时须在 methods 中选择 xuankong_natal")
        if "xuankong_natal" in self.selected_methods:
            natal = self.xuankong or XuankongRequest()
            if self.house is not None and natal.house is not None:
                if self.house.model_dump() != natal.house.model_dump():
                    raise ValueError("合参顶层 house 与 xuankong.house 必须一致")
            XuankongRequest.model_validate(
                {**natal.model_dump(), "house": natal.house or self.house}
            )
        contexts = [(self.environmental_context, None)] + [
            (c.environmental_context, c) for c in self.layout_alternatives
        ]
        target_ids = {a.request_id for a in self.element_adjustments}
        for review_context, review_candidate in contexts:
            if review_context is None:
                continue
            for fact in review_context.material_facts:
                if (
                    fact.application
                    and fact.application.target_request_id is not None
                    and fact.application.target_request_id not in target_ids
                ):
                    raise ValueError("材料施用引用未知 element_adjustments.request_id")
            if review_context.workstation_review:
                evaluation = review_context.workstation_review.evaluation_period
                original_evaluation = (
                    self.workstation_review.evaluation_period
                    if self.workstation_review
                    else None
                )
                natal_interpretation = (
                    self.xuankong.interpretation if self.xuankong else None
                )
                if (
                    evaluation
                    and natal_interpretation
                    and natal_interpretation.current_period_number is not None
                    and evaluation.number != natal_interpretation.current_period_number
                ):
                    raise ValueError("同次活动与玄空解释的评价运不得矛盾")
                if (
                    review_candidate
                    and evaluation
                    and original_evaluation
                    and evaluation.number != original_evaluation.number
                ):
                    raise ValueError("搬转候选不得更换本次评价运")
                if review_candidate and self.workstation_review:
                    old_activities = {
                        a.object_id: a for a in self.workstation_review.activities
                    }
                    for activity in review_context.workstation_review.activities:
                        previous = old_activities.get(activity.object_id)
                        if (
                            previous
                            and previous.observation_basis != "image_observed"
                            and previous.activity != "unknown"
                            and previous.activity != activity.activity
                        ):
                            raise ValueError(
                                "搬转候选不得改写已确认的实际活动；事实更正先更新现状"
                            )
                    old_barriers = {
                        r.barrier_id: r for r in self.workstation_review.entry_barriers
                    }
                    for relation in review_context.workstation_review.entry_barriers:
                        previous_barrier = old_barriers.get(relation.barrier_id)
                        if (
                            previous_barrier
                            and previous_barrier.observation_basis != "image_observed"
                            and previous_barrier.barrier_kind != relation.barrier_kind
                        ):
                            raise ValueError("搬转候选不得改写隔挡物件种类")
                placements = [
                    p
                    for p in self.placements
                    if not review_candidate or p.object_id != review_candidate.object_id
                ]
                review_forms = [
                    f
                    for f in self.form_observations
                    if not review_candidate or f.object_id != review_candidate.object_id
                ]
                if review_candidate and review_candidate.placement:
                    placements.append(review_candidate.placement)
                if review_candidate and review_candidate.form_observation:
                    review_forms.append(review_candidate.form_observation)
                validate_review(
                    review_context.workstation_review,
                    placements,
                    review_forms,
                    review_context,
                    self.environmental_context,
                )
        return self


class DirectionsRequest(_DeferredModel):
    geomagnetic_reference: Optional[GeomagneticReference] = Field(
        default=None,
        description="可选WMM2025地磁参考；明确地点、WGS84椭球高及日期，仅给换算候选，不自动确认或修改宅盘朝向",
    )
    bearing_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        le=360,
        allow_inf_nan=False,
        description="实际方位角，0°北、顺时针，360°归一为0°；省略时仅返回通用方向表",
    )
    north_reference: Optional[NorthReference] = Field(
        default=None,
        description="角度参考北：magnetic 磁北或 true 真北；提供角度时必须确认",
    )
    ruleset_id: Literal["houtian_directions_v1"] = Field(
        default="houtian_directions_v1",
        description="后天八卦通用方向索引版本，不代表实际空间已定宫",
    )

    @model_validator(mode="after")
    def validate_reference(self) -> "DirectionsRequest":
        if self.bearing_degrees is not None and self.north_reference is None:
            raise ValueError("角度输入必须明确 north_reference")
        return self
