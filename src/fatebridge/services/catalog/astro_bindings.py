"""Astro bindings tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fatebridge.application.bindings import resolve_service, service_ref
from fatebridge.application.tool_spec import BoundServiceCall, ServiceInput

if TYPE_CHECKING:
    from pydantic import BaseModel

calculate_core_chart_analysis = service_ref(
    "fatebridge.services.astrology", "calculate_core_chart_analysis"
)


calculate_germany_chart_analysis = service_ref(
    "fatebridge.services.astrology", "calculate_germany_chart_analysis"
)


calculate_relative_chart_analysis = service_ref(
    "fatebridge.services.astrology", "calculate_relative_chart_analysis"
)


def bind_astro_natal_chart(
    request: BaseModel,
) -> BoundServiceCall:
    from fatebridge.core.requests.astrology import AstroNatalChartRequest

    assert isinstance(request, AstroNatalChartRequest)
    arguments = request.model_dump()
    return BoundServiceCall(
        resolve_service(calculate_core_chart_analysis),
        (),
        {**arguments, "chart_variant": "chart"},
    )


def bind_relationship_chart(
    request: BaseModel,
) -> BoundServiceCall:
    arguments: dict[str, ServiceInput] = request.model_dump()

    def party(prefix: str) -> dict[str, ServiceInput]:
        return {
            field: arguments[f"{prefix}_{field}"]
            for field in (
                "name",
                "birth_year",
                "birth_month",
                "birth_day",
                "birth_hour",
                "birth_minute",
                "birth_timezone",
                "birth_longitude",
                "birth_latitude",
                "birth_place",
                "use_true_solar_time",
            )
        }

    return BoundServiceCall(
        resolve_service(calculate_relative_chart_analysis),
        (),
        {
            "inner_payload": party("inner"),
            "outer_payload": party("outer"),
            "relative_mode": arguments["relative_mode"],
            "house_system": arguments["house_system"],
            "zodiac_type": arguments["zodiac_type"],
            "relationship_focus": arguments["relationship_focus"],
            "davison_variant": arguments["davison_variant"],
        },
    )
