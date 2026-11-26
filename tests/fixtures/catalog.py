"""Catalogue lookup shared by public contract tests."""

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG


def cli_specs_by_name() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in CATALOG}
