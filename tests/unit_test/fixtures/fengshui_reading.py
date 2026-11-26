"""Shared natal inputs and independent printed chart examples."""

from copy import deepcopy
from pathlib import Path

from pydantic import JsonValue

from fatebridge.application.execution import execute_tool
from fatebridge.core.fengshui.xuankong import natal_rules
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import payload

PRINTED_CHART_FOLDER = Path(__file__).parents[2] / "data/fengshui_structure_reading_v1"

MOUNTAINS = natal_rules()["mountains"]


def natal_request(period: int = 7, angle: float = 0) -> dict[str, JsonValue]:
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period,
            "evidence": "Source-based numeric example; no real house",
        },
    }


def reading_inputs(
    current: int | None = 8,
    angle: float = 0,
    forms: list[dict[str, JsonValue]] | None = None,
    half: str | None = None,
) -> dict[str, JsonValue]:
    interpretation = {
        "include_calculation_reading": True,
        "timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1",
        "fixed_lingzheng": {},
        "external_forms": forms or [],
    }
    if current is not None:
        interpretation.update(
            current_period_number=current, period_evidence="独立评价运"
        )
    else:
        pass
    if half:
        interpretation["fixed_lingzheng"].update(
            five_period_half=half, half_evidence="明确五运分段"
        )
    else:
        pass
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 2,
            "evidence": "独立历史宅运",
        },
        "city_gate": {
            "reference_period_number": 9,
            "period_evidence": "独立城门参考运",
        },
        "interpretation": interpretation,
    }


def executed(
    req: dict[str, JsonValue] | None = None, tool: str = "xuankong_natal"
) -> dict[str, JsonValue]:
    spec = next(s for s in CATALOG if s.key == "fengshui_" + tool)
    return execute_tool(
        spec, spec.request_model.model_validate(req or reading_inputs())
    )


def trusted(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {"trusted_payload": deepcopy(payload)}


def source_comparison_request(
    period: int = 7, facing: float = 60, **extra: JsonValue
) -> dict[str, JsonValue]:
    return {
        "house": {"facing_degrees": facing, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period,
            "evidence": "虚构固定宅盘，用于原书数表与引擎差异核对",
        },
        **extra,
    }


def printed_chart_request(
    example: dict[str, JsonValue], offset: float = 0
) -> dict[str, JsonValue]:
    angle = next(
        m["center_degrees"] for m in MOUNTAINS if m["name"] == example["facing"]
    )
    return {
        "house": {
            "facing_degrees": (angle + offset) % 360,
            "north_reference": "magnetic",
        },
        "period": {
            "basis": "expert_confirmed",
            "period_number": example["period"],
            "evidence": "原典数字例，非真实住宅",
        },
        "interpretation": {
            "current_period_number": 9,
            "period_evidence": "独立评价九运",
        },
    }


def interpretation_input() -> dict[str, JsonValue]:
    return {
        "current_period_number": 9,
        "period_evidence": "已确认按九运评价，非宅盘历史定运",
        "external_forms": [
            {
                "direction": "N",
                "mountain_present": True,
                "water_present": False,
                "observation_basis": "user_confirmed",
                "evidence": "明确确认北宫外部有山形、无水形",
            }
        ],
    }


def natal_input() -> dict[str, JsonValue]:
    return {**payload("xuankong_natal"), "interpretation": interpretation_input()}


def assess_input() -> dict[str, JsonValue]:
    return {
        "methods": ["xuankong_natal"],
        "analyze_layout": True,
        "xuankong": natal_input(),
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "N"}
        ],
    }
