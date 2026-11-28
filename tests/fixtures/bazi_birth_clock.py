"""Shared fictional birth-clock inputs and the corresponding receipt paths."""

from pydantic import JsonValue

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.birth import BaziClockRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import inputs

TIMING_NAMES = {
    "bazi_timing",
    "bazi_luck_cycles",
    "bazi_yearly_timing",
    "bazi_monthly_timing",
    "bazi_daily_timing",
    "bazi_hourly_timing",
    "solar_term_timeline",
}
SPECS = [
    s
    for s in CATALOG
    if (s.family == "bazi" and issubclass(s.request_model, BaziClockRequest))
    or s.name in TIMING_NAMES
]
BASE: dict[str, JsonValue] = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_timezone="UTC",
    use_true_solar_time=False,
)


def receipt_path(spec: ToolSpec) -> str:
    if spec.name == "bazi_birth_chart":
        return "bazi_birth.calendar_context.birth_time_input"
    if spec.family == "bazi" and spec.name != "bazi_overview":
        return f"{spec.name.removeprefix('bazi_')}_analysis.calendar_context.birth_time_input"
    return "calendar_context.birth_time_input"


def leaf(payload: JsonValue, path: str) -> dict[str, JsonValue]:
    for field_name in path.split("."):
        assert isinstance(payload, dict), path
        payload = payload[field_name]
    assert isinstance(payload, dict), path
    return payload


def omitted_payload(spec: ToolSpec) -> dict[str, JsonValue]:
    result = {**inputs(spec), **BASE}
    result.pop("birth_minute", None)
    result.pop("birth_second", None)
    return result
