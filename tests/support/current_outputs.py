"""Exercise every current tool for schema and field-projection checks."""

from collections.abc import Callable
from functools import cache

import pytest

from fatebridge.application.execution import execute_tool, result_is_error
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES
from tests.support.ephemeris_context import empty_ephemeris_path


@pytest.fixture(scope="session")
def current_business() -> Callable[[str], ServiceResult]:
    specs = {spec.key: spec for spec in CATALOG}

    @cache
    def calculate(key: str) -> ServiceResult:
        spec = specs[key]
        with empty_ephemeris_path():
            factory = (
                REST_POST_CASES[spec.rest_path]
                if spec.rest_path
                else MCP_CASES[spec.tool_name][1]
            )
            request = spec.request_model.model_validate(factory())
            result = execute_tool(
                spec,
                request,
                options=ExecutionOptions(as_of="2026-10-12T02:00:00Z"),
                include_metadata=False,
            )
            assert not result_is_error(result), (spec.key, result)
        return result

    return calculate
