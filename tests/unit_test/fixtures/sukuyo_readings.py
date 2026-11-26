"""Build reproducible Sukuyo readings and quotation checks for tests."""

from pydantic import JsonValue

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.sukuyo.sukuyo_hinoo_critical import critical_calendar_reference
from fatebridge.core.sukuyo.sukuyo_profiles import fullmoon_calculation, source_bundle
from fatebridge.core.sukuyo.sukuyo_relations import SU27_ORDER
from fatebridge.services.tool_catalog import CATALOG
from validation.claims import CalculationClaim
from validation.sukuyo import Focus, required_quote_paths


def payload(tool: str = "suzhan", **changes: JsonValue) -> dict[str, JsonValue]:
    spec = next(s for s in CATALOG if s.key == tool)
    params = (
        {
            "lat": "31n13",
            "lon": "121e28",
            "date": "2025-03-04",
            "time": "12:00:00",
            "zone": "+08:00",
            "natal_mansion": "奎",
            "activity": "marriage",
        }
        if tool == "suzhan"
        else {"person1_date": "1990-06-15", "person2_date": "1992-03-20"}
    )
    return execute_tool(
        spec,
        spec.request_model.model_validate({**params, **changes}),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )


def quotes(result: dict[str, JsonValue], focus: Focus) -> list[CalculationClaim]:
    receipt = result["run_metadata"]
    out = []
    for path in required_quote_paths(focus):
        value = result
        for key in path.split("."):
            value = value[key]
        out.append(
            CalculationClaim(
                path=path,
                value=value,
                run_id=receipt["run_id"],
            )
        )
    return out


def critical() -> dict[str, JsonValue]:
    return critical_calendar_reference(
        source_bundle()["hinoo_addendum"],
        [fullmoon_calculation(12, day, SU27_ORDER) for day in (1, 15, 30)],
    )
