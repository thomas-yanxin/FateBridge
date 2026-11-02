"""Source-scoped interior relationships, independent of compass or birth data.

``pillar_corner`` explicitly identifies a solid projecting pillar corner, not
every furniture corner. ``toilet_wall`` identifies the shared wall at the toilet
fixture's side, not any partition adjoining a bathroom.
"""

from typing import Any, Iterable, Literal, Mapping, Optional, Set, Tuple, get_args

from pydantic import Field, StrictBool, field_validator, model_validator

from .numeric_inputs import FengshuiInput as _DeferredModel

InteriorRole = Literal[
    "main_entry_door",
    "bathroom_door",
    "stove",
    "sharp_corner",
    "pillar_corner",
    "bed",
    "desk",
    "exposed_beam",
    "pipe",
    "toilet_wall",
    "mirror",
]
InteriorRelationKind = Literal[
    "main_entry_door_faces_bathroom_door",
    "bathroom_door_faces_stove",
    "sharp_corner_points_at_stove",
    "pillar_corner_points_at_bed",
    "sharp_corner_points_at_desk",
    "exposed_beam_above_stove",
    "exposed_beam_above_bed",
    "pipe_above_stove",
    "bed_headboard_against_toilet_wall",
    "mirror_faces_bed",
    "bed_above_stove",
    "stove_back_against_toilet_wall",
]
SUPPORTED_INTERIOR_ROLES = frozenset(get_args(InteriorRole))
RELATION_ROLES: Mapping[str, Tuple[str, str]] = {
    "main_entry_door_faces_bathroom_door": ("main_entry_door", "bathroom_door"),
    "bathroom_door_faces_stove": ("bathroom_door", "stove"),
    "sharp_corner_points_at_stove": ("sharp_corner", "stove"),
    "pillar_corner_points_at_bed": ("pillar_corner", "bed"),
    "sharp_corner_points_at_desk": ("sharp_corner", "desk"),
    "exposed_beam_above_stove": ("exposed_beam", "stove"),
    "exposed_beam_above_bed": ("exposed_beam", "bed"),
    "pipe_above_stove": ("pipe", "stove"),
    "bed_headboard_against_toilet_wall": ("bed", "toilet_wall"),
    "mirror_faces_bed": ("mirror", "bed"),
    "bed_above_stove": ("bed", "stove"),
    "stove_back_against_toilet_wall": ("stove", "toilet_wall"),
}


class InteriorRelation(_DeferredModel):
    """An explicit predicate; merely sharing a room never establishes it."""

    relation_id: str = Field(min_length=1, max_length=100)
    source_object_id: str = Field(min_length=1, max_length=100)
    target_object_id: str = Field(min_length=1, max_length=100)
    kind: InteriorRelationKind
    present: Optional[StrictBool] = Field(
        description="必须显式提供；null为未知，照片true/false均仅为候选观察"
    )
    observation_basis: Literal["measured", "user_confirmed", "image_observed"]
    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("relation_id", "source_object_id", "target_object_id", "evidence")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("室内关系的对象、ID与依据不能为空白")
        return value

    @model_validator(mode="after")
    def different_objects(self) -> "InteriorRelation":
        if self.source_object_id == self.target_object_id:
            raise ValueError("室内关系的来源物件与目标物件不能相同")
        return self


def _level(floor: Any) -> Any:
    return floor.get("level") if isinstance(floor, Mapping) else floor.level


def validate_relation_references(
    relations: Iterable[InteriorRelation],
    roles: Mapping[str, Set[str]],
    floor_maps: Mapping[str, Any],
) -> None:
    """Validate explicit identities and known levels, never infer from labels.

    An object can have both a use (desk) and a source attribute (sharp corner).
    Photo observations are candidates, including their spatial interpretation.
    """
    relation_ids: Set[str] = set()
    predicates: Set[Tuple[str, str, str]] = set()
    for relation in relations:
        if relation.relation_id in relation_ids:
            raise ValueError("interior_relations.relation_id 不可重复")
        relation_ids.add(relation.relation_id)
        predicate = (
            relation.kind,
            relation.source_object_id,
            relation.target_object_id,
        )
        if predicate in predicates:
            raise ValueError("相同种类及端点的室内关系不可重复")
        predicates.add(predicate)
        for object_id, required_role in zip(
            (relation.source_object_id, relation.target_object_id),
            RELATION_ROLES[relation.kind],
        ):
            if object_id not in roles:
                raise ValueError(f"室内关系引用未知对象 {object_id}")
            if required_role not in roles[object_id]:
                raise ValueError(f"{object_id} 必须明确具有角色 {required_role}")
        if (
            relation.present is not True
            or relation.observation_basis == "image_observed"
        ):
            continue
        source_floor = floor_maps.get(relation.source_object_id)
        target_floor = floor_maps.get(relation.target_object_id)
        if source_floor is None or target_floor is None:
            continue
        source_level, target_level = _level(source_floor), _level(target_floor)
        if source_level is None or target_level is None:
            continue
        if relation.kind == "bed_above_stove":
            if source_level <= target_level:
                raise ValueError("已确认床在灶上方时，床的楼层必须高于灶的楼层")
        elif source_level != target_level:
            raise ValueError("已确认的室内水平/顶上关系不能跨已知不同楼层")
