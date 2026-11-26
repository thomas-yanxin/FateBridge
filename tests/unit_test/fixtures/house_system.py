"""Supply representative requests for tools with a house-system field."""

from pydantic import JsonValue

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.base import (
    AstroHouseValidatorMixin,
    OfflineHouseValidatorMixin,
)
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES

HOUSE_SYSTEM_SPECS = tuple(
    spec for spec in CATALOG if issubclass(spec.request_model, AstroHouseValidatorMixin)
)
HOUSE_CODE_SPECS = tuple(
    spec
    for spec in CATALOG
    if issubclass(spec.request_model, OfflineHouseValidatorMixin)
)


def house_system_payload(spec: ToolSpec) -> dict[str, JsonValue]:
    rest_payload_factory = REST_POST_CASES.get(spec.rest_path)
    if rest_payload_factory is not None:
        return rest_payload_factory()
    else:
        return MCP_CASES[spec.name][1]()
