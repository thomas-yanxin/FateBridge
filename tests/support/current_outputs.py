"""Exercise every current tool for schema and field-projection checks."""

from collections.abc import Callable
from functools import cache
from typing import Any

import pytest


@pytest.fixture(scope="session")
def current_raw_business() -> Callable[[str], dict[str, Any]]:
    from fatebridge.application.execution import (
        invoke_validated_service,
        result_is_error,
    )
    from fatebridge.core.execution_context import call_clock
    from fatebridge.services.tool_catalog import CATALOG
    from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES
    from tests.support.ephemeris_context import empty_ephemeris_path

    specs = {spec.name: spec for spec in CATALOG}

    @cache
    def calculate(key: str) -> dict[str, Any]:
        spec = specs[key]
        with empty_ephemeris_path(), call_clock("2026-10-12T02:00:00Z"):
            factory = (
                REST_POST_CASES[spec.rest_path]
                if spec.rest_path
                else MCP_CASES[spec.name][1]
            )
            request = spec.request_model.model_validate(factory())
            result = invoke_validated_service(spec, request)
            assert not result_is_error(result), (spec.name, result)
        return result

    return calculate


@pytest.fixture(scope="session")
def current_business(current_raw_business) -> Callable[[str], dict[str, Any]]:
    from fatebridge.core.public_output import public_payload

    @cache
    def calculate(key: str) -> dict[str, Any]:
        return public_payload(current_raw_business(key))

    return calculate
