"""Astro bindings tool declarations and domain binding helpers."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.bindings import lazy_service, resolve_service
from fatebridge.application.tool_spec import BoundServiceCall, ServiceInput
from fatebridge.core.requests.astrology import AstroChartPolyRequest

calculate_core_chart_analysis = lazy_service(
    "fatebridge.services.astrology", "calculate_core_chart_analysis"
)


calculate_germany_chart_analysis = lazy_service(
    "fatebridge.services.astrology", "calculate_germany_chart_analysis"
)


calculate_relative_chart_analysis = lazy_service(
    "fatebridge.services.astrology", "calculate_relative_chart_analysis"
)


def _astro_chart_bind(
    req: BaseModel,
) -> BoundServiceCall:
    assert isinstance(req, AstroChartPolyRequest)
    data = req.service_inputs()
    variant = data.pop("chart_variant", "chart")
    apparent_model = data.pop("apparent_model", "native")
    if variant == "chart":
        data["apparent_model"] = apparent_model
    if variant == "germany":
        for key in (
            "guolao_month_basis",
            "guolao_seasonal_anchor_policy",
            "node_mode",
            "divisions",
            "saptavargaja_profile",
            "drekkana_profile",
            "cheshta_model",
            "birth_microsecond",
        ):
            data.pop(key, None)
        return BoundServiceCall(
            resolve_service(calculate_germany_chart_analysis), (), data
        )
    else:
        return BoundServiceCall(
            resolve_service(calculate_core_chart_analysis),
            (),
            {**data, "chart_variant": variant},
        )


def _astro_relative_flat_bind(
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
            "hsys": arguments["hsys"],
            "zodiacal": arguments["zodiacal"],
            "relationship_focus": arguments["relationship_focus"],
            "davison_variant": arguments["davison_variant"],
        },
    )
