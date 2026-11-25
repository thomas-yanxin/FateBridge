"""
Standalone western predictive timing tool surfaces for FateBridge.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.export_parser import parse_export_content
from fatebridge.services.snapshot_builders import (
    format_snapshot_json,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.services.western_timing import (
    calculate_western_timing_module_analysis,
)
from fatebridge.utils.errors import handle_calculation_error

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "solarreturn": {
        "analysis_type": "西占太阳返照",
        "technique": "solarreturn",
        "path": ("returns", "solar_return"),
        "section_kind": "chart",
        "label": "太阳返照",
    },
    "lunarreturn": {
        "analysis_type": "西占月亮返照",
        "technique": "lunarreturn",
        "path": ("returns", "lunar_return"),
        "section_kind": "chart",
        "label": "月亮返照",
    },
    "transit": {
        "analysis_type": "西占行运盘",
        "technique": "transit",
        "path": ("transits", "current_transit"),
        "section_kind": "transit",
        "label": "行运盘",
    },
    "solararc": {
        "analysis_type": "西占太阳弧",
        "technique": "solararc",
        "path": ("directions", "solar_arc"),
        "section_kind": "chart",
        "label": "太阳弧",
    },
    "givenyear": {
        "analysis_type": "西占指定年盘",
        "technique": "givenyear",
        "path": ("directions", "given_year"),
        "section_kind": "chart",
        "label": "指定年盘",
    },
    "profection": {
        "analysis_type": "西占年小限",
        "technique": "profection",
        "path": ("time_lords", "annual_profection"),
        "section_kind": "chart",
        "label": "年小限",
    },
    "pd": {
        "analysis_type": "西占主限",
        "technique": "primarydirect",
        "path": ("directions", "primary_directions"),
        "section_kind": "pd",
        "label": "主/界限法",
    },
    "pdchart": {
        "analysis_type": "西占主限法盘",
        "technique": "primarydirchart",
        "path": ("directions", "primary_direction_chart"),
        "section_kind": "pdchart",
        "label": "主限法盘",
    },
    "zr": {
        "analysis_type": "西占黄道释放",
        "technique": "zodialrelease",
        "path": ("time_lords", "zodiacal_releasing"),
        "section_kind": "zr",
        "label": "黄道释放",
    },
    "firdaria": {
        "analysis_type": "西占法达星限",
        "technique": "firdaria",
        "path": ("time_lords", "firdaria"),
        "section_kind": "firdaria",
        "label": "法达星限",
    },
    "decennials": {
        "analysis_type": "西占十年星限",
        "technique": "decennials",
        "path": ("time_lords", "decennials"),
        "section_kind": "decennials",
        "label": "十年星限",
    },
}


def _extract_path(payload: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    current: Any = payload
    for key in path:
        current = current[key]
    if not isinstance(current, dict):
        raise TypeError(f"Expected dict payload at {'.'.join(path)}")
    else:
        pass
    return current


def _build_context(result: dict[str, Any], label: str) -> dict[str, Any]:
    analysis_context = result.get("analysis_context", {})
    return {
        "tool": label,
        "summary": result.get("summary"),
        "birth_datetime": analysis_context.get("birth_datetime"),
        "analysis_datetime": analysis_context.get("analysis_datetime"),
        "age_years": analysis_context.get("age_years"),
        "house_system": analysis_context.get("house_system"),
        "house_system_code": analysis_context.get("house_system_code"),
        "house_system_label_zh": analysis_context.get("house_system_label_zh"),
        "zodiac_type": analysis_context.get("zodiac_type"),
        "return_location": analysis_context.get("return_location"),
        "engine": result.get("natal_reference", {})
        .get("calculation_basis", {})
        .get("engine_backend", "fatebridge-offline"),
    }


def _build_aspect_summary(
    label: str, result: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "label": label,
        "summary": result.get("summary"),
    }
    if "sign_changes" in payload:
        summary["sign_changes"] = payload["sign_changes"]
    else:
        pass
    if "exact_hits" in payload:
        summary["exact_hits"] = payload["exact_hits"]
    else:
        pass
    if "current_window" in payload:
        summary["current_window"] = payload["current_window"]
    else:
        pass
    if len(summary) == 2:
        summary["note"] = "离线独立工具未额外生成单独相位表，请结合星盘信息阅读。"
    else:
        pass
    return summary


def _build_sections(
    *,
    section_kind: str,
    label: str,
    result: dict[str, Any],
    payload: dict[str, Any],
) -> list[tuple[str, str]]:
    natal_reference = result.get("natal_reference", {})
    context = _build_context(result, label)

    if section_kind == "chart":
        return [
            ("起盘信息", format_snapshot_json(context)),
            (
                "星盘信息",
                format_snapshot_json(
                    {"natal_reference": natal_reference, "module": payload},
                ),
            ),
            (
                "相位",
                format_snapshot_json(_build_aspect_summary(label, result, payload)),
            ),
        ]
    else:
        pass

    if section_kind == "transit":
        return [
            ("起盘信息", format_snapshot_json(context)),
            (
                "星盘信息",
                format_snapshot_json(
                    {
                        "natal_reference": natal_reference,
                        "transit_reference": payload.get("transit_reference"),
                        "house_emphasis": payload.get("house_emphasis"),
                        "location": payload.get("location"),
                    },
                ),
            ),
            (
                "相位",
                format_snapshot_json(
                    {
                        "summary": result.get("summary"),
                        "orb_limit": payload.get("orb_limit"),
                        "top_hits": payload.get("hits"),
                        "exact_hits": payload.get("exact_hits"),
                    },
                ),
            ),
        ]
    else:
        pass

    if section_kind == "pd":
        return [
            ("出生时间", format_snapshot_json(context)),
            ("星盘信息", format_snapshot_json(natal_reference)),
            (
                "主/界限法设置",
                format_snapshot_json(
                    {
                        "method": payload.get("method"),
                        "method_label": payload.get("method_label"),
                        "time_key": payload.get("time_key"),
                        "time_key_label": payload.get("time_key_label"),
                        "pd_type": payload.get("pd_type"),
                        "direction_mode": payload.get("direction_mode"),
                        "direction_mode_label": payload.get("direction_mode_label"),
                        "coordinate_system": payload.get("coordinate_system"),
                        "coordinate_label": payload.get("coordinate_label"),
                        "approximation": payload.get("approximation"),
                        "approximation_label": payload.get("approximation_label"),
                        "coordinate_precision": payload.get("coordinate_precision"),
                        "coordinate_backend": payload.get("coordinate_backend"),
                        "aspects": payload.get("aspects"),
                    },
                ),
            ),
            (
                "主/界限法表格",
                format_snapshot_json(
                    {
                        "current_arc_degrees": payload.get("current_arc_degrees"),
                        "current_window": payload.get("current_window"),
                        "past_window": payload.get("past_window"),
                        "future_window": payload.get("future_window"),
                        "exact_window": payload.get("exact_window"),
                        "timeline": payload.get("timeline"),
                    },
                ),
            ),
        ]
    else:
        pass

    if section_kind == "pdchart":
        return [
            ("出生时间", format_snapshot_json(context)),
            ("星盘信息", format_snapshot_json(natal_reference)),
            (
                "主限法盘设置",
                format_snapshot_json(
                    {
                        "method": payload.get("method"),
                        "method_label": payload.get("method_label"),
                        "time_key": payload.get("time_key"),
                        "time_key_label": payload.get("time_key_label"),
                        "pd_type": payload.get("pd_type"),
                        "direction_mode": payload.get("direction_mode"),
                        "direction_mode_label": payload.get("direction_mode_label"),
                        "coordinate_system": payload.get("coordinate_system"),
                        "coordinate_label": payload.get("coordinate_label"),
                        "approximation": payload.get("approximation"),
                        "approximation_label": payload.get("approximation_label"),
                        "coordinate_precision": payload.get("coordinate_precision"),
                        "coordinate_backend": payload.get("coordinate_backend"),
                        "show_pd_bounds": payload.get("show_pd_bounds"),
                    },
                ),
            ),
            (
                "主限法盘说明",
                format_snapshot_json(
                    {
                        "current_arc_degrees": payload.get("current_arc_degrees"),
                        "bounds_overlay": payload.get("bounds_overlay"),
                        "directed_points": payload.get("directed_points"),
                        "directed_lots": payload.get("directed_lots"),
                        "sign_changes": payload.get("sign_changes"),
                        "exact_hits": payload.get("exact_hits"),
                    },
                ),
            ),
        ]
    else:
        pass

    if section_kind == "zr":
        return [
            ("起盘信息", format_snapshot_json(context)),
            (
                "星盘信息",
                format_snapshot_json(
                    {
                        "sect": natal_reference.get("sect"),
                        "lots": natal_reference.get("lots"),
                    },
                ),
            ),
            ("基于X点推运", format_snapshot_json(payload)),
        ]
    else:
        pass

    if section_kind == "firdaria":
        return [
            ("出生时间", format_snapshot_json(context)),
            ("星盘信息", format_snapshot_json(natal_reference)),
            ("法达星限表格", format_snapshot_json(payload)),
        ]
    else:
        pass

    if section_kind == "decennials":
        display_reference = dict(natal_reference)
        display_reference["calculation_basis"] = {
            key: value
            for key, value in natal_reference.get("calculation_basis", {}).items()
            if key
            in {
                "engine_backend",
                "engine_precision",
                "ephemeris_model",
                "calendar",
                "time_scale",
                "julian_day_tt",
                "julian_day_ut1",
                "future_leap_seconds_assumed_unchanged",
                "horizon_method",
                "ayanamsha_model",
                "ayanamsha_degrees",
            }
        }
        return [
            ("起盘信息", format_snapshot_json(context)),
            ("星盘信息", format_snapshot_json(display_reference, compact=True)),
            (
                "十年大运设置",
                format_snapshot_json(
                    {
                        "resolved_start_planet": payload.get("resolved_start_planet"),
                        "resolved_start_planet_label": payload.get(
                            "resolved_start_planet_label"
                        ),
                        "base_order": payload.get("base_order"),
                    },
                ),
            ),
            ("基于X起运", format_snapshot_json(payload, compact=True)),
        ]
    else:
        pass

    raise ValueError(f"Unsupported section kind: {section_kind}")


def calculate_timing_tool(
    tool_name: str,
    *,
    selected_sections: list[str] | None = None,
    render_snapshot: bool = True,
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
        else:
            pass

        payload = _extract_path(result, spec["path"])
        response = {
            "analysis_type": spec["analysis_type"],
            "engine": result.get("natal_reference", {})
            .get("calculation_basis", {})
            .get("engine_backend", "fatebridge-offline"),
            "analysis_context": result.get("analysis_context"),
            "natal_reference": result.get("natal_reference"),
            tool_name: payload,
            "summary": result.get("summary"),
        }
        if not render_snapshot:
            return response
        else:
            pass
        sections = _build_sections(
            section_kind=spec["section_kind"],
            label=spec["label"],
            result=result,
            payload=payload,
        )
        snapshot_text = _render_snapshot_text(sections)
        snapshot_export = parse_export_content(
            technique=spec["technique"],
            content=snapshot_text,
            selected_sections=selected_sections,
        )

        return {
            **response,
            "snapshot_text": snapshot_text,
            "snapshot_export": snapshot_export,
        }
    except Exception as exc:
        return handle_calculation_error(exc, spec["analysis_type"])
