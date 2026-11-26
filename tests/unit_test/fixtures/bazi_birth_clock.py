"""Shared fictional birth-clock inputs and the corresponding receipt paths."""

from pydantic import JsonValue

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.birth import BaziClockRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import inputs

TIMING_KEYS = {
    "timing_analysis",
    "dayun_analysis",
    "liunian_analysis",
    "liuyue_analysis",
    "liuri_analysis",
    "liushi_analysis",
    "jieqi_timeline_analysis",
}
SPECS = [
    s
    for s in CATALOG
    if (s.family == "bazi" and issubclass(s.request_model, BaziClockRequest))
    or s.key in TIMING_KEYS
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
    if spec.key == "bazi_birth":
        return "bazi_birth.calendar_context.birth_time_input"
    else:
        pass
    if spec.family == "bazi" and spec.key != "analyze_destiny":
        return f"{spec.key.removeprefix('bazi_')}_analysis.calendar_context.birth_time_input"
    else:
        pass
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
