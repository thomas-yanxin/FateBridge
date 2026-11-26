"""Serve the export registry and parsed snapshot sections."""

from __future__ import annotations

from pydantic import JsonValue

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.export_contracts import build_export_registry
from fatebridge.core.export_parser import parse_export_content
from fatebridge.utils.errors import calculation_guard


@calculation_guard("导出注册表")
def calculate_export_registry(
    *,
    technique: str | None = None,
) -> ServiceResult:
    return {**build_export_registry(technique=technique)}


@calculation_guard("导出解析")
def calculate_export_parse(
    *,
    technique: str,
    content: str,
    selected_sections: list[str] | None = None,
    planet_info: dict[str, JsonValue] | None = None,
    astro_meaning: dict[str, JsonValue] | None = None,
) -> ServiceResult:
    return {
        **parse_export_content(
            technique=technique,
            content=content,
            selected_sections=selected_sections,
            planet_info=planet_info,
            astro_meaning=astro_meaning,
        )
    }
