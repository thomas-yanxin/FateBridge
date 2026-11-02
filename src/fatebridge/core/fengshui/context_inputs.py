"""Confirmed environmental facts, household roles and floor-use boundaries.

These inputs deliberately have no personal chart or favourable-element fields.
They describe the environment and the people using it, independently of Ba Zhai
birth inputs and independently of an actual flying-star calculation.
"""

from typing import Any, Iterable, List, Literal, Mapping, Optional, Set

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from .interior_inputs import (
    InteriorRelation,
    InteriorRole,
    validate_relation_references,
)
from .material_inputs import MaterialShapeFact
from .numeric_inputs import FengshuiInput as _DeferredModel
from .workstation_inputs import WorkstationReview

ContextBasis = Literal["measured", "user_confirmed"]
FamilyRole = Literal["parent", "eldest_child", "middle_child", "youngest_child"]
Zodiac = Literal["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# Query scope and object identities alone are not environmental observations.
# Share this list with the validator so schema publication cannot omit the
# aggregate fact gate or accidentally count a metadata-only context as facts.
_CONTEXT_FACT_LIST_FIELDS = (
    "household_members",
    "floors",
    "observations",
    "interior_relations",
    "material_facts",
)
_CONTEXT_FACT_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {
            "required": ["workstation_review"],
            "properties": {"workstation_review": {"type": "object"}},
        },
        {
            "required": ["orientation"],
            "properties": {"orientation": {"type": "object"}},
        },
        *[
            {
                "required": [field],
                "properties": {field: {"type": "array", "minItems": 1}},
            }
            for field in _CONTEXT_FACT_LIST_FIELDS
        ],
    ]
}


class ContextFact(_DeferredModel):
    observation_basis: ContextBasis = "user_confirmed"
    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def nonblank_evidence(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("环境事实依据不能为空白")
        return value

    @model_validator(mode="after")
    def nonblank_identifiers(self) -> "ContextFact":
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{name} 不能为空白")
            if name.endswith("_ids") and isinstance(value, list):
                if any(not item.strip() for item in value):
                    raise ValueError(f"{name} 不能含空白 ID")
        return self


class OrientationConfirmation(ContextFact):
    """A north reference alone does not confirm the plan centre or alignment."""

    north_reference: Optional[Literal["magnetic", "true"]] = None
    direction_confirmed: StrictBool = False
    floorplan_alignment_confirmed: StrictBool = False
    center_confirmed: StrictBool = False

    @model_validator(mode="after")
    def reference_for_confirmed_direction(self) -> "OrientationConfirmation":
        if self.direction_confirmed and self.north_reference is None:
            raise ValueError("确认方位须说明 north_reference，不能由命盘推定方位")
        return self

    def ready_for_sectors(self) -> bool:
        return (
            self.direction_confirmed
            and self.floorplan_alignment_confirmed
            and self.center_confirmed
        )


class HouseholdMember(ContextFact):
    subject_id: str = Field(min_length=1, max_length=100)
    gender_role: Literal["male", "female"] = Field(
        description="已确认本次传统家庭角色口径；不从姓名或生辰推断"
    )
    generation: StrictInt = Field(
        ge=0, le=20, description="同一家庭相对辈分；数值越小越长，不是决策权"
    )
    family_roles: List[FamilyRole] = Field(
        default_factory=list,
        max_length=2,
        json_schema_extra={"uniqueItems": True},
        description="本家庭已确认父母身份及子女排行；可同时有两种身份",
    )
    co_resident: StrictBool = True
    spouse_subject_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    follow_spouse_rank: StrictBool = Field(
        default=False,
        description="显式采用本次专家的妻随夫排行口径；不会自动按婚姻推定",
    )
    zodiac: Optional[Zodiac] = Field(
        default=None, description="用户明确确认的生肖，不从生日或命卦反推"
    )

    @model_validator(mode="after")
    def coherent_roles(self) -> "HouseholdMember":
        if len(set(self.family_roles)) != len(self.family_roles):
            raise ValueError("family_roles 不可重复")
        ranks = set(self.family_roles) - {"parent"}
        if len(ranks) > 1:
            raise ValueError("同一家庭不能同时提供多个子女排行")
        if self.spouse_subject_id == self.subject_id:
            raise ValueError("配偶不能是本人")
        if self.follow_spouse_rank and (
            self.gender_role != "female" or self.spouse_subject_id is None
        ):
            raise ValueError("妻随夫排行须明确女性角色及 spouse_subject_id")
        return self


class FloorSpace(ContextFact):
    floor_id: str = Field(min_length=1, max_length=100)
    level: StrictInt = Field(ge=-20, le=200)
    space_kind: Literal["interior", "courtyard"] = "interior"
    uses_shared_orientation: Optional[StrictBool] = Field(
        default=None, description="本层与全宅使用统一已确认方位；未知不默认相同"
    )
    center_confirmed: Optional[StrictBool] = Field(
        default=None, description="本层自身立极已确认；不继承全宅或其他层中心"
    )
    floorplan_alignment_confirmed: Optional[StrictBool] = Field(
        default=None, description="本层户型与统一方向对齐已确认；不继承其他层"
    )
    subject_ids: List[str] = Field(
        default_factory=list,
        max_length=50,
        json_schema_extra={"uniqueItems": True},
        description="已确认实际在本空间居住/使用的人；只有正向名单，省略某人不表示其不使用，不从家庭角色自动分配",
    )
    usage_confirmed: StrictBool = Field(
        default=False,
        description="本空间全部实际住用/日常活动范围已完整核对，subject_ids未列的人确不使用；不由居住楼层自动推定",
    )
    usage_evidence: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="实际住用名单及不使用范围的完整核对依据；与usage_confirmed=true成对",
    )
    object_ids: List[str] = Field(
        default_factory=list, max_length=500, json_schema_extra={"uniqueItems": True}
    )
    suitability: Literal["confirmed_suitable", "requires_review", "not_assessed"] = (
        "not_assessed"
    )
    suitability_evidence: Optional[str] = Field(
        default=None, min_length=1, max_length=1000
    )

    @model_validator(mode="after")
    def scoped_floor(self) -> "FloorSpace":
        if self.space_kind == "courtyard" and self.level != 1:
            raise ValueError("本次专家口径将院落归属于第一层，courtyard.level 必须为1")
        if len(set(self.subject_ids)) != len(self.subject_ids):
            raise ValueError("楼层 subject_ids 不可重复")
        if len(set(self.object_ids)) != len(self.object_ids):
            raise ValueError("楼层 object_ids 不可重复")
        if self.usage_confirmed != (self.usage_evidence is not None):
            raise ValueError("完整使用范围确认与 usage_evidence 必须成对")
        if (self.suitability != "not_assessed") != (
            self.suitability_evidence is not None
        ):
            raise ValueError("楼层适宜性确认与 suitability_evidence 必须成对")
        if (
            self.suitability_evidence is not None
            and not self.suitability_evidence.strip()
        ):
            raise ValueError("楼层适宜性依据不能为空白")
        return self

    def ready_for_sectors(self) -> bool:
        """Local prerequisites; the caller must also check global orientation."""
        return (
            self.uses_shared_orientation is True
            and self.center_confirmed is True
            and self.floorplan_alignment_confirmed is True
        )


class FloorInfluence(ContextFact):
    influence_id: str = Field(min_length=1, max_length=100)
    source_floor_id: str = Field(min_length=1, max_length=100)
    extent: Literal["floor_local_confirmed", "shared_confirmed", "unknown"]
    shared_floor_ids: List[str] = Field(
        default_factory=list, max_length=100, json_schema_extra={"uniqueItems": True}
    )

    @model_validator(mode="after")
    def scoped_influence(self) -> "FloorInfluence":
        if len(set(self.shared_floor_ids)) != len(self.shared_floor_ids):
            raise ValueError("shared_floor_ids 不可重复")
        if self.extent == "shared_confirmed" and not self.shared_floor_ids:
            raise ValueError("共同影响须明确 shared_floor_ids")
        if self.extent != "shared_confirmed" and self.shared_floor_ids:
            raise ValueError("只有共同影响能指定 shared_floor_ids")
        return self


class EnvironmentalObservation(ContextFact):
    observation_id: str = Field(min_length=1, max_length=100)
    object_id: str = Field(min_length=1, max_length=100)
    floor_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Literal["room_relationship", "material", "shape", "modern_design"]
    feature: Literal[
        "kitchen_bathroom_adjacent",
        "bathroom_door_faces_kitchen",
        "bathroom_door_faces_bedroom",
        "kitchen_bedroom_adjacent",
        "wood",
        "metal",
        "stone",
        "ceramic",
        "glass",
        "plastic",
        "mixed_material",
        "pointed",
        "round",
        "square",
        "arched_opening",
        "open_kitchen",
    ]
    present: StrictBool = True

    @model_validator(mode="after")
    def category_matches_feature(self) -> "EnvironmentalObservation":
        categories = {
            "room_relationship": {
                "kitchen_bathroom_adjacent",
                "bathroom_door_faces_kitchen",
                "bathroom_door_faces_bedroom",
                "kitchen_bedroom_adjacent",
            },
            "material": {
                "wood",
                "metal",
                "stone",
                "ceramic",
                "glass",
                "plastic",
                "mixed_material",
            },
            "shape": {"pointed", "round", "square"},
            "modern_design": {"arched_opening", "open_kitchen"},
        }
        if self.feature not in categories[self.category]:
            raise ValueError("feature 与 category 不一致")
        return self


class EnvironmentalObject(ContextFact):
    object_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["room", "furniture", "garden_feature", "material_object", "opening"]
    purpose: Optional[Literal["door", "bed", "desk", "stove"]] = None
    role: Optional[InteriorRole] = Field(
        default=None,
        description="明确功能/部件身份；pillar_corner仅实体柱角，toilet_wall仅便器所在侧的墙，不从名称或普通相邻推定",
    )

    @model_validator(mode="after")
    def kind_and_purpose(self) -> "EnvironmentalObject":
        if not self.label.strip():
            raise ValueError("环境对象 label 不能为空白")
        if self.purpose == "door" and self.kind != "opening":
            raise ValueError("门对象的 kind 须为 opening")
        if self.purpose in {"bed", "desk", "stove"} and self.kind != "furniture":
            raise ValueError("门床桌灶用途须与环境对象 kind 一致")
        if self.role in {"main_entry_door", "bathroom_door"} and self.kind != "opening":
            raise ValueError("主门/厕门角色必须为opening")
        if self.role in {"bed", "desk", "stove"} and self.kind != "furniture":
            raise ValueError("床桌灶角色必须为furniture")
        if self.role in {"bed", "desk", "stove"} and self.purpose not in (
            None,
            self.role,
        ):
            raise ValueError("明确角色与purpose不得矛盾")
        if (
            self.role in {"exposed_beam", "pipe", "toilet_wall", "pillar_corner"}
            and self.kind != "material_object"
        ):
            raise ValueError("梁、管、厕墙部件须以material_object明确记录")
        if self.role in {"mirror", "sharp_corner"} and self.kind == "room":
            raise ValueError("镜面/尖角源必须记录实际物件，不能把整个房间当部件")
        return self


class EnvironmentalContext(_DeferredModel):
    model_config = ConfigDict(json_schema_extra=_CONTEXT_FACT_SCHEMA)

    ruleset_id: Literal["expert_environment_2026_10_v1"] = (
        "expert_environment_2026_10_v1"
    )
    orientation: Optional[OrientationConfirmation] = None
    household_scope: Literal["environmental_binding", "symbolic_reference"] = Field(
        default="environmental_binding",
        description="家庭索引查询范围：environmental_binding核对实际环境方区；symbolic_reference仅解释家庭/生肖卦象，不绑定实际方向或追问罗盘，是工程查询范围而非新传统断法",
    )
    household_composition_confirmed: StrictBool = Field(
        default=False,
        description="同住家庭名单及辈分已完整确认；否则不能由名单最年长者推乾坤",
    )
    household_members: List[HouseholdMember] = Field(
        default_factory=list, max_length=50
    )
    objects: List[EnvironmentalObject] = Field(default_factory=list, max_length=500)
    floors: List[FloorSpace] = Field(default_factory=list, max_length=100)
    floor_influences: List[FloorInfluence] = Field(default_factory=list, max_length=100)
    observations: List[EnvironmentalObservation] = Field(
        default_factory=list, max_length=500
    )
    interior_relations: List[InteriorRelation] = Field(
        default_factory=list, max_length=500
    )
    material_facts: List[MaterialShapeFact] = Field(
        default_factory=list, max_length=500
    )
    workstation_review: Optional[WorkstationReview] = Field(
        default=None,
        description="显式作者工位活动/入口隔挡；不启用BTB或WOFS桌面摆位，事实与执行条件分开",
    )

    @model_validator(mode="after")
    def coherent_references(self) -> "EnvironmentalContext":
        if (
            self.orientation is None
            and self.workstation_review is None
            and not any(getattr(self, field) for field in _CONTEXT_FACT_LIST_FIELDS)
        ):
            raise ValueError(
                "环境上下文至少提供方向核对、家庭成员、楼层或具体观察；对象定义本身不是完成审查"
            )
        for values, attr in (
            (self.household_members, "subject_id"),
            (self.floors, "floor_id"),
            (self.floor_influences, "influence_id"),
            (self.observations, "observation_id"),
            (self.objects, "object_id"),
            (self.interior_relations, "relation_id"),
            (self.material_facts, "fact_id"),
        ):
            ids = [getattr(item, attr) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{attr} 不可重复")
        attributes = set()
        for fact in self.material_facts:
            for name in ("material", "shape", "colour", "application"):
                if getattr(fact, name) is None:
                    continue
                key = (fact.object_id, name)
                if key in attributes:
                    raise ValueError(
                        "同一物件属性须独立且只确认一次，不能重复或相互覆盖"
                    )
                attributes.add(key)
        uses: dict[str, str] = {}
        for fact in self.material_facts:
            if fact.element_use is not None:
                if fact.object_id in uses and uses[fact.object_id] != fact.element_use:
                    raise ValueError("同一物件本次代表物用途问题不得相互矛盾")
                uses[fact.object_id] = fact.element_use
        members = {m.subject_id: m for m in self.household_members}
        floors = {f.floor_id: f for f in self.floors}
        spouse_references = [
            m.spouse_subject_id
            for m in self.household_members
            if m.spouse_subject_id is not None
        ]
        if len(spouse_references) != len(set(spouse_references)):
            raise ValueError("同一成员不能同时被多个成员引用为配偶")
        for member in self.household_members:
            spouse_id = member.spouse_subject_id
            if spouse_id is None:
                continue
            if spouse_id not in members:
                raise ValueError(f"未知配偶 subject_id: {spouse_id}")
            spouse = members[spouse_id]
            if spouse.generation != member.generation:
                raise ValueError("同一家庭的配偶须使用相同辈分")
            if spouse.spouse_subject_id not in (None, member.subject_id):
                raise ValueError("配偶引用不一致")
            if member.follow_spouse_rank and (
                spouse.gender_role != "male"
                or not set(spouse.family_roles) - {"parent"}
            ):
                raise ValueError("妻随夫排行须已确认丈夫的男性角色与子女排行")
        for influence in self.floor_influences:
            for floor_id in [influence.source_floor_id, *influence.shared_floor_ids]:
                if floor_id not in floors:
                    raise ValueError(f"未知影响楼层 floor_id: {floor_id}")
        for obs in self.observations:
            if obs.floor_id is not None and obs.floor_id not in floors:
                raise ValueError(f"未知观察楼层 floor_id: {obs.floor_id}")
            if (
                obs.floor_id is not None
                and obs.object_id not in floors[obs.floor_id].object_ids
            ):
                raise ValueError("观察对象须列入对应楼层 object_ids")
        interior_levels = [f.level for f in self.floors if f.space_kind == "interior"]
        if len(interior_levels) != len(set(interior_levels)):
            raise ValueError("同一层 interior 只能提供一次；院落独立记录为第一层")
        object_floor_ids = [obj for floor in self.floors for obj in floor.object_ids]
        if len(object_floor_ids) != len(set(object_floor_ids)):
            raise ValueError("同一对象不能同时位于不同楼层")
        return self

    def validate_references(
        self,
        known_object_ids: Iterable[str],
        known_subject_ids: Iterable[str],
        known_object_purposes: Optional[Mapping[str, str]] = None,
        known_object_roles: Optional[Mapping[str, Set[str]]] = None,
        known_object_floors: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Validate enclosing-request references without requiring birth charts.

        Context members supply their own identities. Other occupants can be
        passed in by the aggregate request, so floor use does not force roles.
        """
        objects: Set[str] = set(known_object_ids) | {o.object_id for o in self.objects}
        subjects = set(known_subject_ids) | {
            m.subject_id for m in self.household_members
        }
        for obj in self.objects:
            existing_purpose = (known_object_purposes or {}).get(obj.object_id)
            if existing_purpose is not None:
                expected_kind = "opening" if existing_purpose == "door" else "furniture"
                if obj.kind != expected_kind:
                    raise ValueError(f"环境对象与已有类型不一致: {obj.object_id}")
            if (
                existing_purpose is not None
                and obj.purpose is not None
                and existing_purpose != obj.purpose
            ):
                raise ValueError(f"环境对象与已有用途不一致: {obj.object_id}")
            if (
                existing_purpose is not None
                and obj.role in {"bed", "desk", "stove"}
                and obj.role != existing_purpose
            ):
                raise ValueError(f"环境角色与已有用途不一致: {obj.object_id}")
        for floor in self.floors:
            for subject_id in floor.subject_ids:
                if subject_id not in subjects:
                    raise ValueError(f"未知楼层使用人 subject_id: {subject_id}")
            for object_id in floor.object_ids:
                if object_id not in objects:
                    raise ValueError(f"未知楼层对象 object_id: {object_id}")
        for observation in self.observations:
            if observation.object_id not in objects:
                raise ValueError(f"未知环境观察对象 object_id: {observation.object_id}")
        roles = {key: set(values) for key, values in (known_object_roles or {}).items()}
        for object_id, purpose in (known_object_purposes or {}).items():
            roles.setdefault(object_id, set()).add(purpose)
        for obj in self.objects:
            roles.setdefault(obj.object_id, set()).update(
                value for value in (obj.role, obj.purpose) if value is not None
            )
            if obj.role == "pillar_corner":
                roles[obj.object_id].add("sharp_corner")
        validate_relation_references(
            self.interior_relations,
            roles,
            {
                **(known_object_floors or {}),
                **{
                    object_id: floor
                    for floor in self.floors
                    for object_id in floor.object_ids
                },
            },
        )
        for fact in self.material_facts:
            if fact.object_id not in objects:
                raise ValueError(f"未知材质器形对象 object_id: {fact.object_id}")
