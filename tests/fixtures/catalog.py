"""Catalogue lookup shared by skill contract tests."""

from fatebridge.application.description import spec_is_cli_safe
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG


def cli_specs_by_name() -> dict[str, ToolSpec]:
    return {spec.tool_name: spec for spec in CATALOG if spec_is_cli_safe(spec)}
