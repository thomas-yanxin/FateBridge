"""
Standalone western predictive timing tool surfaces for FateBridge.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fatebridge.core.export_parser import parse_export_content
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


def _json_block(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _extract_path(payload: Dict[str, Any], path: tuple[str, ...]) -> Dict[str, Any]:
    current: Any = payload
    for key in path:
        current = current[key]
    if not isinstance(current, dict):
        raise TypeError(f"Expected dict payload at {'.'.join(path)}")
    return current


def _build_context(result: Dict[str, Any], label: str) -> Dict[str, Any]:
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
    label: str, result: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "label": label,
        "summary": result.get("summary"),
    }
    if "sign_changes" in payload:
        summary["sign_changes"] = payload["sign_changes"]
    if "exact_hits" in payload:
        summary["exact_hits"] = payload["exact_hits"]
    if "current_window" in payload:
        summary["current_window"] = payload["current_window"]
    if len(summary) == 2:
        summary["note"] = "离线独立工具未额外生成单独相位表，请结合星盘信息阅读。"
    return summary


def _build_sections(
    *,
    section_kind: str,
    label: str,
    result: Dict[str, Any],
    payload: Dict[str, Any],
) -> list[tuple[str, str]]:
    natal_reference = result.get("natal_reference", {})
    context = _build_context(result, label)

    if section_kind == "chart":
        return [
            ("起盘信息", _json_block(context)),
            (
                "星盘信息",
                _json_block(
                    {
                        "natal_reference": natal_reference,
                        "module": payload,
                    }
                ),
            ),
            ("相位", _json_block(_build_aspect_summary(label, result, payload))),
        ]

    if section_kind == "transit":
        return [
            ("起盘信息", _json_block(context)),
            (
                "星盘信息",
                _json_block(
                    {
                        "natal_reference": natal_reference,
                        "transit_reference": payload.get("transit_reference"),
                        "house_emphasis": payload.get("house_emphasis"),
                        "location": payload.get("location"),
                    }
                ),
            ),
            (
                "相位",
                _json_block(
                    {
                        "summary": result.get("summary"),
                        "orb_limit": payload.get("orb_limit"),
                        "top_hits": payload.get("hits"),
                        "exact_hits": payload.get("exact_hits"),
                    }
                ),
            ),
        ]

    if section_kind == "pd":
        return [
            ("出生时间", _json_block(context)),
            ("星盘信息", _json_block(natal_reference)),
            (
                "主/界限法设置",
                _json_block(
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
                    }
                ),
            ),
            (
                "主/界限法表格",
                _json_block(
                    {
                        "current_arc_degrees": payload.get("current_arc_degrees"),
                        "current_window": payload.get("current_window"),
                        "past_window": payload.get("past_window"),
                        "future_window": payload.get("future_window"),
                        "exact_window": payload.get("exact_window"),
                        "timeline": payload.get("timeline"),
                    }
                ),
            ),
        ]

    if section_kind == "pdchart":
        return [
            ("出生时间", _json_block(context)),
            ("星盘信息", _json_block(natal_reference)),
            (
                "主限法盘设置",
                _json_block(
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
                    }
                ),
            ),
            (
                "主限法盘说明",
                _json_block(
                    {
                        "current_arc_degrees": payload.get("current_arc_degrees"),
                        "bounds_overlay": payload.get("bounds_overlay"),
                        "directed_points": payload.get("directed_points"),
                        "directed_lots": payload.get("directed_lots"),
                        "sign_changes": payload.get("sign_changes"),
                        "exact_hits": payload.get("exact_hits"),
                    }
                ),
            ),
        ]

    if section_kind == "zr":
        return [
            ("起盘信息", _json_block(context)),
            (
                "星盘信息",
                _json_block(
                    {
                        "sect": natal_reference.get("sect"),
                        "lots": natal_reference.get("lots"),
                    }
                ),
            ),
            ("基于X点推运", _json_block(payload)),
        ]

    if section_kind == "firdaria":
        return [
            ("出生时间", _json_block(context)),
            ("星盘信息", _json_block(natal_reference)),
            ("法达星限表格", _json_block(payload)),
        ]

    if section_kind == "decennials":
        # The complete native witnesses remain in the structured reference.
        # Do not repeat them in snapshot_text and each export representation.
        display_reference = dict(natal_reference)
        display_reference["calculation_basis"] = {
            key: value
            for key, value in natal_reference.get("calculation_basis", {}).items()
            if key not in {"longitude_motion", "apparent_position_policy"}
        }
        return [
            ("起盘信息", _json_block(context)),
            ("星盘信息", _json_block(display_reference)),
            (
                "十年大运设置",
                _json_block(
                    {
                        "resolved_start_planet": payload.get("resolved_start_planet"),
                        "resolved_start_planet_label": payload.get(
                            "resolved_start_planet_label"
                        ),
                        "base_order": payload.get("base_order"),
                    }
                ),
            ),
            ("基于X起运", _json_block(payload)),
        ]

    raise ValueError(f"Unsupported section kind: {section_kind}")


def _calculate_tool(
    tool_name: str,
    *,
    selected_sections: Optional[list[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    spec = TOOL_SPECS[tool_name]
    try:
        result = calculate_western_timing_module_analysis(
            technique=spec["technique"],
            **kwargs,
        )
        if "error" in result:
            return result

        payload = _extract_path(result, spec["path"])
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
            "analysis_type": spec["analysis_type"],
            "engine": result.get("natal_reference", {})
            .get("calculation_basis", {})
            .get("engine_backend", "fatebridge-offline"),
            "analysis_context": result.get("analysis_context"),
            "natal_reference": result.get("natal_reference"),
            tool_name: payload,
            "summary": result.get("summary"),
            "snapshot_text": snapshot_text,
            "snapshot_export": snapshot_export,
        }
    except Exception as exc:
        return handle_calculation_error(exc, spec["analysis_type"])


def calculate_solarreturn(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("solarreturn", selected_sections=selected_sections, **kwargs)


def calculate_lunarreturn(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("lunarreturn", selected_sections=selected_sections, **kwargs)


def calculate_transit(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("transit", selected_sections=selected_sections, **kwargs)


def calculate_solararc(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("solararc", selected_sections=selected_sections, **kwargs)


def calculate_givenyear(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("givenyear", selected_sections=selected_sections, **kwargs)


def calculate_profection(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("profection", selected_sections=selected_sections, **kwargs)


def calculate_pd(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("pd", selected_sections=selected_sections, **kwargs)


def calculate_pdchart(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("pdchart", selected_sections=selected_sections, **kwargs)


def calculate_zr(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("zr", selected_sections=selected_sections, **kwargs)


def calculate_firdaria(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("firdaria", selected_sections=selected_sections, **kwargs)


def calculate_decennials(
    *, selected_sections: Optional[list[str]] = None, **kwargs: Any
) -> Dict[str, Any]:
    return _calculate_tool("decennials", selected_sections=selected_sections, **kwargs)
