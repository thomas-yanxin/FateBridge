"""Explicit authored uses, observed relationships and execution facts."""

from typing import Any, List, Literal, Optional

from pydantic import ConfigDict, Field, StrictBool, StrictInt, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel


class ObservedCondition(_DeferredModel):
    value: Optional[StrictBool]
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class WorkstationActivity(_DeferredModel):
    ruleset_id: Literal["workstation_activity_authored_v1"]
    object_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    activity: Literal["work", "study", "meditation", "storage", "mixed", "unknown"]
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    space_mixed_use: Optional[ObservedCondition] = Field(
        default=None,
        description="空间是否同时办公/睡眠等混用，独立于这张桌实际活动；未知不推定",
    )


class EntryBarrier(_DeferredModel):
    ruleset_id: Literal["afsi_entry_barrier_v1"]
    relation_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    entrance_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    desk_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    barrier_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    barrier_kind: Literal["plant", "screen"]
    operation: Literal["retain", "relocate", "add"]
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    entry_line_through_user: ObservedCondition
    barrier_between_entry_and_user: ObservedCondition
    # These are engineering execution facts, not additional traditional rules.
    entrance_view_maintained: Optional[ObservedCondition] = None
    circulation_clear: Optional[ObservedCondition] = None
    operating_space_clear: Optional[ObservedCondition] = None
    physically_feasible: Optional[ObservedCondition] = None

    @model_validator(mode="after")
    def distinct_objects(self) -> "EntryBarrier":
        if len({self.entrance_id, self.desk_id, self.barrier_id}) != 3:
            raise ValueError("入口、书桌与隔挡须为三个不同实际对象")
        return self


class EvaluationPeriod(_DeferredModel):
    number: StrictInt = Field(ge=1, le=9)
    evidence: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class WorkstationReview(_DeferredModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"required": [key], "properties": {key: {"minItems": 1}}}
                for key in ("activities", "entry_barriers")
            ]
        }
    )
    activities: List[WorkstationActivity] = Field(default_factory=list, max_length=100)
    entry_barriers: List[EntryBarrier] = Field(default_factory=list, max_length=100)
    evaluation_period: Optional[EvaluationPeriod] = Field(
        default=None,
        description="本次活动参考的显式评价运；不从宅运、年星或系统日期补齐",
    )

    @model_validator(mode="after")
    def unique_requests(self) -> "WorkstationReview":
        if not self.activities and not self.entry_barriers:
            raise ValueError("工位作者审查至少提供活动或入口隔挡关系")
        for records, field in (
            (self.activities, "object_id"),
            (self.entry_barriers, "relation_id"),
        ):
            ids = [getattr(item, field) for item in records]
            if len(ids) != len(set(ids)):
                raise ValueError("工位作者审查 ID 不能重复")
        triples = [
            (r.entrance_id, r.desk_id, r.barrier_id) for r in self.entry_barriers
        ]
        if len(triples) != len(set(triples)):
            raise ValueError("同一入口/坐者/隔挡关系不能重复")
        return self


class MaterialApplication(_DeferredModel):
    ruleset_id: Literal["afsi_application_conditions_v1"]
    target_request_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"\S",
        description="可选关联本轮明确 element_adjustments.request_id；绑定不证明物件已在目标宫位",
    )
    water_clean: Optional[ObservedCondition] = None
    water_moving: Optional[ObservedCondition] = None
    metal_exposed: Optional[ObservedCondition] = None
    proportionate_to_space: Optional[ObservedCondition] = Field(
        default=None,
        description="署名作者的定性尺度核对；不是引擎算出的剂量/重量阈值",
    )
    plant_healthy: Optional[ObservedCondition] = None


def validate_review(
    review: WorkstationReview,
    placements: List[Any],
    forms: List[Any],
    context: Any,
    known_context: Any = None,
) -> None:
    """Registration establishes identity/use, never position or observed relations."""
    purposes = {p.object_id: p.purpose for p in [*placements, *forms]}
    objects = {o.object_id: o for o in known_context.objects} if known_context else {}
    objects.update({o.object_id: o for o in context.objects} if context else {})
    for obj in objects.values():
        purpose = obj.purpose or (
            obj.role if obj.role in {"door", "desk", "bed", "stove"} else None
        )
        if obj.role == "main_entry_door":
            purpose = "door"
        if purpose:
            purposes.setdefault(obj.object_id, purpose)
    for activity in review.activities:
        if purposes.get(activity.object_id) != "desk":
            raise ValueError("工位活动须关联明确的书桌对象")
    for relation in review.entry_barriers:
        entrance = objects.get(relation.entrance_id)
        if purposes.get(relation.entrance_id) != "door" or (
            entrance and entrance.role == "bathroom_door"
        ):
            raise ValueError("隔挡须关联明确的实际入口门，不能由通道或厕门代替")
        if purposes.get(relation.desk_id) != "desk":
            raise ValueError("隔挡目标须为明确书桌坐者")
        barrier = objects.get(relation.barrier_id)
        if barrier is None or barrier.kind not in {
            "material_object",
            "furniture",
            "garden_feature",
        }:
            raise ValueError("隔挡须独立登记实际植物/屏风对象")
        if barrier.purpose is not None or barrier.role is not None:
            raise ValueError("隔挡不能同时伪装成门床桌灶或其他已声明角色")
        form = next((f for f in forms if f.object_id == relation.desk_id), None)
        if (
            form
            and form.entrance_direct_line is not None
            and form.observation_basis != "image_observed"
            and relation.entry_line_through_user.observation_basis != "image_observed"
            and relation.entry_line_through_user.value is not None
            and form.entrance_direct_line != relation.entry_line_through_user.value
        ):
            raise ValueError("同一工位入口直线事实不得互相矛盾")
