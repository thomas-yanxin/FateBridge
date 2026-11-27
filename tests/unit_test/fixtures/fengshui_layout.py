"""Reusable residential layout and observation examples."""

from copy import deepcopy

from pydantic import JsonValue

from tests.fixtures.fengshui import payload


def environment_feature(
    object_id: str = "furniture", direction: str = "N", classification: str = "sand"
) -> dict[str, JsonValue]:
    return {
        "object_id": object_id,
        "direction": direction,
        "classification": classification,
        "classification_basis": "user_confirmed",
        "evidence": "本次位置与砂水分类独立确认，不按物品名称推断",
    }


def candidate_features(
    *, fresh: bool = False, facing_only: bool = False
) -> dict[str, JsonValue]:
    values = proposal_request()
    values["methods"] = ["jinsuo", "annual_stars"]
    values["features"] = [
        environment_feature(),
        environment_feature("fixed_wall", "NW", "sand"),
    ]
    candidate = values["layout_alternatives"][0]
    if facing_only:
        candidate["changes"] = ["facing"]
        candidate["placement"]["location_direction"] = "N"
    else:
        pass
    if fresh:
        candidate["features"] = [
            environment_feature(direction=candidate["placement"]["location_direction"])
        ]
    else:
        pass
    return values


def orientation(**changes: JsonValue) -> dict[str, JsonValue]:
    return {
        "direction_confirmed": True,
        "north_reference": "magnetic",
        "floorplan_alignment_confirmed": True,
        "center_confirmed": True,
        "evidence": "现场核对参考北、户型旋转及全宅中心",
        **changes,
    }


def facing_only() -> dict[str, JsonValue]:
    return {
        "methods": ["bazhai"],
        "analyze_layout": True,
        "occupants": [
            {"subject_id": "a", "birth_date": "2000-12-10", "gender": "male"}
        ],
        "placements": [
            {
                "object_id": "table",
                "purpose": "desk",
                "facing_direction": "W",
                "facing_role": "desk_facing",
                "subject_id": "a",
            }
        ],
    }


def material_fact(**values: JsonValue) -> dict[str, JsonValue]:
    return {
        "fact_id": "f",
        "object_id": "item",
        "material": "processed_wood",
        "observation_basis": "user_confirmed",
        "evidence": "确认对象实际属性，不按物名猜测",
        **values,
    }


def material_request(**values: JsonValue) -> dict[str, JsonValue]:
    return dict(
        methods=[],
        scene="shared_rental",
        environmental_context=dict(
            orientation=dict(
                direction_confirmed=False, evidence="只审查材料属性，方位未知"
            ),
            objects=[
                dict(
                    object_id="item",
                    label="待审物件",
                    kind="material_object",
                    evidence="物件身份已确认",
                )
            ],
            material_facts=[material_fact(**values)],
        ),
    )


def form() -> dict[str, JsonValue]:
    return {
        "object_id": "desk",
        "purpose": "desk",
        "observation_basis": "user_confirmed",
        "evidence": "已独立确认实际使用位置形态",
        "entrance_visible": True,
        "entrance_direct_line": False,
        "solid_backing": True,
    }


def observation(
    object_id: str = "furniture", purpose: str = "desk", **changes: JsonValue
) -> dict[str, JsonValue]:
    return {
        "object_id": object_id,
        "purpose": purpose,
        "entrance_visible": True,
        "entrance_direct_line": False,
        "solid_backing": True,
        "observation_basis": "user_confirmed",
        "evidence": "合成资料：独立核对使用位置",
        **changes,
    }


def proposal_request(
    purpose: str = "desk", role: str = "desk_facing"
) -> dict[str, JsonValue]:
    current = {
        "object_id": "furniture",
        "purpose": purpose,
        "location_direction": "N",
        "facing_direction": "S",
        "facing_role": role,
    }
    return {
        "scene": "home",
        "methods": ["bazhai", "annual_stars"],
        "house": {"sitting_trigram": "坎"},
        "effective_year": 2026,
        "occupants": [
            {
                "subject_id": "user",
                "birth_year": 1990,
                "gender": "male",
            }
        ],
        "placements": [current],
        "layout_constraints": [
            {
                "object_id": "furniture",
                "can_relocate": True,
                "can_rotate": True,
                "evidence": "允许搬位和转向",
            }
        ],
        "layout_alternatives": [
            {
                "candidate_id": "proposal",
                "object_id": "furniture",
                "changes": ["location", "facing"],
                "placement": {
                    **current,
                    "location_direction": "E",
                    "facing_direction": "N",
                },
                "physically_feasible": True,
                "evidence": "新位置可容纳且不妨碍操作、通行",
            }
        ],
    }


def relation_request(
    present: bool = True, basis: str = "user_confirmed"
) -> dict[str, JsonValue]:
    return dict(
        scene="shared_rental",
        methods=[],
        environmental_context=dict(
            orientation=dict(
                direction_confirmed=False, evidence="未测方位，只核明确物理关系"
            ),
            objects=[
                dict(
                    object_id="mirror",
                    kind="material_object",
                    role="mirror",
                    label="镜",
                    evidence="明确确认镜面",
                ),
                dict(
                    object_id="bed",
                    kind="furniture",
                    purpose="bed",
                    label="床",
                    evidence="明确确认用途",
                ),
                dict(
                    object_id="corner",
                    kind="material_object",
                    role="pillar_corner",
                    label="柱角",
                    evidence="明确确认实体尖角源",
                ),
            ],
            interior_relations=[
                dict(
                    relation_id="reflection",
                    source_object_id="mirror",
                    target_object_id="bed",
                    kind="mirror_faces_bed",
                    present=present,
                    observation_basis=basis,
                    evidence="镜与床关系独立观察，不从镜子名称推断",
                )
            ],
        ),
    )


def relation_candidate(moving: str = "mirror") -> dict[str, JsonValue]:
    request = relation_request()
    fresh = deepcopy(request["environmental_context"]["interior_relations"][0])
    fresh.update(present=False, evidence="候选位置独立核对：不再正对床")
    operation = "facing" if moving == "mirror" else "location"
    request["layout_constraints"] = [
        dict(
            object_id=moving,
            can_relocate=True,
            can_rotate=True,
            evidence="用户明确许可本对象动作",
        )
    ]
    request["layout_alternatives"] = [
        dict(
            candidate_id="candidate",
            object_id=moving,
            changes=[operation],
            environmental_context=dict(interior_relations=[fresh]),
            physically_feasible=True,
            evidence="候选可容纳、保持操作与通行",
        )
    ]
    return request


def form_inputs(**changes: JsonValue) -> dict[str, JsonValue]:
    return {
        "methods": [],
        "form_observations": [
            {
                "object_id": "x",
                "purpose": "desk",
                "entrance_position": "front_left",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": True,
                "observation_basis": "user_confirmed",
                "evidence": "已确认使用者视野、入口直线与实体支撑",
                **changes,
            }
        ],
    }


def adjustment_inputs(goal: str = "drain") -> dict[str, JsonValue]:
    inputs = facing_only()
    inputs["element_adjustments"] = [
        {
            "request_id": "r",
            "object_id": "table",
            "target_method": "bazhai",
            "subject_id": "a",
            "aspect": "facing",
            "goal": goal,
            "evidence": "基于当前作用域判定，按所选版本比较元素调节候选",
        }
    ]
    return inputs


def annual_inputs(
    direction: str = "S", facing: str = "W", year: int = 2026
) -> dict[str, JsonValue]:
    return {
        "methods": ["annual_stars"],
        "effective_year": year,
        "annual_remedy_ruleset_id": "pang_2026_annual_v1",
        "placements": [
            {
                "object_id": "x",
                "purpose": "desk",
                "location_direction": direction,
                "facing_direction": facing,
                "facing_role": "desk_facing",
            }
        ],
    }


def surface_input(
    goal: str = "abundance",
    zone: str = "near_right",
    basis: str = "user_confirmed",
    healthy: bool | None = None,
) -> dict[str, JsonValue]:
    inputs = {
        "methods": [],
        "surface_layouts": [
            {
                "object_id": "work-surface",
                "ruleset_id": "desktop_bagua_btb_v1",
                "shape": "rectangular",
                "anchor": "seated_near_edge",
                "goal": goal,
                "observation_basis": basis,
                "evidence": "矩形桌面与坐者使用沿已确认，目标由使用者给出",
                "items": [
                    {
                        "object_id": "specimen",
                        "label": "室内盆栽",
                        "representation": "living_plant",
                        "zone": zone,
                        "zone_observation_basis": basis,
                        "observation_basis": basis,
                        "evidence": "实际活植物",
                    }
                ],
            }
        ],
        "surface_constraints": [
            {
                "object_id": "work-surface",
                "can_move_items": True,
                "can_add_items": False,
                "feasible_zones": ["far_left"],
                "evidence": "远左放得下且保留入口视野，允许移动已有物件",
            }
        ],
    }
    if healthy is not None:
        inputs["surface_layouts"][0]["items"][0]["healthy"] = {
            "value": healthy,
            "observation_basis": "user_confirmed",
            "evidence": "独立核对植物/鲜花状态，不从身份或位置推定",
        }
    else:
        pass
    return inputs
