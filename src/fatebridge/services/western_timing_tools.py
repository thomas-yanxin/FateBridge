"""Standalone western predictive timing tool surfaces for FateBridge."""

from __future__ import annotations

from typing import Any

from fatebridge.services.western_timing import (
    calculate_western_timing_module_analysis,
)
from fatebridge.utils.errors import handle_calculation_error

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "solar_return": {
        "analysis_type": "西占太阳返照",
        "technique": "solarreturn",
        "path": ("returns", "solar_return"),
    },
    "lunar_return": {
        "analysis_type": "西占月亮返照",
        "technique": "lunarreturn",
        "path": ("returns", "lunar_return"),
    },
    "transit_chart": {
        "analysis_type": "西占行运盘",
        "technique": "transit",
        "path": ("transits", "current_transit"),
    },
    "solar_arc": {
        "analysis_type": "西占太阳弧",
        "technique": "solararc",
        "path": ("directions", "solar_arc"),
    },
    "chart_for_year": {
        "analysis_type": "西占指定年盘",
        "technique": "givenyear",
        "path": ("directions", "given_year"),
    },
    "profection": {
        "analysis_type": "西占年小限",
        "technique": "profection",
        "path": ("time_lords", "annual_profection"),
    },
    "primary_directions": {
        "analysis_type": "西占主限",
        "technique": "primarydirect",
        "path": ("directions", "primary_directions"),
    },
    "primary_directions_chart": {
        "analysis_type": "西占主限法盘",
        "technique": "primarydirchart",
        "path": ("directions", "primary_direction_chart"),
    },
    "zodiacal_releasing": {
        "analysis_type": "西占黄道释放",
        "technique": "zodialrelease",
        "path": ("time_lords", "zodiacal_releasing"),
    },
    "firdaria": {
        "analysis_type": "西占法达星限",
        "technique": "firdaria",
        "path": ("time_lords", "firdaria"),
    },
    "decennials": {
        "analysis_type": "西占十年星限",
        "technique": "decennials",
        "path": ("time_lords", "decennials"),
    },
}


def _extract_path(payload: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    current: Any = payload
    for key in path:
        current = current[key]
    if not isinstance(current, dict):
        raise TypeError(f"Expected dict payload at {'.'.join(path)}")
    return current


def calculate_timing_tool(
    tool_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    spec = TOOL_SPECS[tool_name]
    try:
        result = calculate_western_timing_module_analysis(
            technique=spec["technique"],
            **kwargs,
        )
        if "error" in result:
            return result

        payload = _extract_path(result, spec["path"])
        return {
            "analysis_type": spec["analysis_type"],
            "engine": result.get("natal_reference", {})
            .get("calculation_basis", {})
            .get("engine_backend", "fatebridge-offline"),
            "analysis_context": result.get("analysis_context"),
            "natal_reference": result.get("natal_reference"),
            tool_name: payload,
            "summary": result.get("summary"),
        }
    except Exception as exc:
        return handle_calculation_error(exc, spec["analysis_type"])
