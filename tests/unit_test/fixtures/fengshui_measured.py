"""Shared measured workstation inputs and transport expectations."""

import json
from pathlib import Path

from pydantic import JsonValue

from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.services.fengshui import assess as _assess


def measured_request(
    *, search: bool = False, charts: bool = False
) -> dict[str, JsonValue]:
    request = json.loads(
        Path("docs/examples/fengshui-workstation-measured.json").read_text()
    )
    scene = request["workstation_layout"]["scene"]
    scene["desktops"][0]["items"][0]["healthy"] = dict(
        value=True, observation_basis="user_confirmed", evidence="独立确认状态良好"
    )
    if not search:
        request["workstation_layout"].pop("search")
    else:
        pass
    if charts:
        template = json.loads(
            Path("docs/examples/fengshui-workstation-activity.json").read_text()
        )
        request["methods"] = ["xuankong_natal", "annual_stars", "monthly_stars"]
        request["xuankong"] = template["xuankong"]
        request["effective_year"] = 2026
        request["monthly"] = dict(effective_solar_year=2026, solar_month_number=3)
        request["workstation_layout"].update(
            evaluation_period=9,
            evaluation_period_evidence="独立评价运，不改变2004年竣工宅盘",
            timeliness_ruleset_id="wang_zhongzhou_timeliness_v1",
        )
    else:
        pass
    return request


def measured_result(request: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return _assess(AssessRequest.model_validate(request))["layout_analysis"]["workstation_layout_analysis"]


def body(
    object_id: str,
    kind: str,
    x: float,
    y: float,
    width: float,
    depth: float,
    bottom: float,
    top: float,
    blocks: bool = False,
) -> dict[str, JsonValue]:
    return dict(
        object_id=object_id,
        kind=kind,
        footprint=dict(
            center=dict(x=x, y=y), width_m=width, depth_m=depth, rotation_degrees=0
        ),
        bottom_m=bottom,
        top_m=top,
        blocks_view=blocks,
    )


def rotation_payload(
    angle: float, center_x: float = 1, width: float = 2
) -> dict[str, JsonValue]:
    return {
        "methods": [],
        "workstation_layout": {
            "scene": {
                "frame_id": "analytic-closed-room",
                "units": "m",
                "boundary": {
                    "vertices": [
                        {"x": 0, "y": 0},
                        {"x": 2, "y": 0},
                        {"x": 2, "y": 4},
                        {"x": 0, "y": 4},
                    ]
                },
                "observation_basis": "measured",
                "evidence": "Exact synthetic rectangle; no physical site is asserted.",
                "inventory_confirmed": True,
                "bodies": [
                    {
                        "object_id": "desk",
                        "kind": "desk",
                        "footprint": {
                            "center": {"x": center_x, "y": 2},
                            "width_m": width,
                            "depth_m": 1,
                            "rotation_degrees": angle,
                        },
                        "bottom_m": 0,
                        "top_m": 0.75,
                        "blocks_view": False,
                    }
                ],
                "seats": [
                    {
                        "desk_id": "desk",
                        "offset": {"x": 0, "y": -1.2},
                        "facing_offset_degrees": 0,
                        "body_width_m": 0.5,
                        "body_depth_m": 0.5,
                        "eye_height_m": 1.2,
                        "head_height_m": 1.4,
                        "view_half_angle_degrees": 80,
                        "operating_zone": {
                            "center": {"x": 0, "y": -1.2},
                            "width_m": 0.4,
                            "depth_m": 0.4,
                        },
                        "activity": "work",
                        "sector_anchor": "seat",
                    }
                ],
            }
        },
    }
