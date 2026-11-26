"""Schema and compact capability descriptions derived from ToolSpec."""

from types import UnionType
from typing import Annotated, get_args, get_origin

from pydantic import BaseModel

from fatebridge.application.examples import (
    call_guidance,
    compact_fields,
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.schema_cache import model_schema

UNION_ORIGINS = (UnionType, get_origin(Annotated[int, "u"] | None))


def resolve_spec(specs: list[ToolSpec], name: str) -> ToolSpec | None:
    return next((spec for spec in specs if spec.name == name), None)


def unwrap_optional(annotation: object) -> object:
    """Return the first non-null union member for nested-model inspection."""
    if get_origin(annotation) in UNION_ORIGINS:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if non_none:
            return non_none[0]
    return annotation


def is_model_field(annotation: object) -> bool:
    """True if the (unwrapped) annotation is a nested pydantic model."""
    base = unwrap_optional(annotation)
    return isinstance(base, type) and issubclass(base, BaseModel)


def field_type_name(annotation: object) -> str:
    """Render a field annotation as a short, agent-readable type string."""
    if get_origin(annotation) in UNION_ORIGINS:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) > 1:
            return " | ".join(field_type_name(a) for a in non_none)
    base = unwrap_optional(annotation)
    origin = get_origin(base)
    if origin is list:
        args = get_args(base)
        inner = (
            args[0].__name__
            if args and isinstance(args[0], type)
            else (str(args[0]) if args else "str")
        )
        return f"list[{inner}]"
    if isinstance(base, type):
        return base.__name__
    return str(base)


def _surfaces(spec: ToolSpec) -> dict[str, bool | str | None]:
    return {
        "cli": True,
        "rest": spec.rest_path,
        "mcp": spec.expose_mcp,
    }


def describe_spec(
    spec: ToolSpec, *, include_output_schema: bool = False
) -> ServiceResult:
    """Describe one tool's schema, capabilities and available transports."""
    return _describe_contract(spec, include_output_schema=include_output_schema)


def _describe_contract(spec: ToolSpec, *, include_output_schema: bool) -> ServiceResult:
    """Build requested contracts without generating schemas that are discarded."""
    example = example_input(spec)
    views = evidence_views(spec)
    guidance = call_guidance(spec)
    fields = suggested_fields(spec)
    default_fields = compact_fields(spec)
    root_fields = list(spec.output_fields)
    if not root_fields and spec.output_model:
        root_fields = list(spec.output_model.model_fields)
    record: ServiceResult = {
        **({"example_input": example} if example is not None else {}),
        **({"evidence_views": views} if views is not None else {}),
        **({"call_guidance": guidance} if guidance is not None else {}),
        "tool": spec.name,
        "summary": spec.summary,
        "operation_label_zh": spec.operation_label_zh,
        "family": spec.family,
        "annotations": spec.execution_hints.as_annotations(),
        "full_result_required_fields": list(spec.required_output_fields),
        "execution": {
            "cpu_bound": spec.cpu_bound,
        },
        "surfaces": _surfaces(spec),
        "input_schema": model_schema(spec.request_model),
        "output_fields": root_fields,
        "cli_request_file": spec.cli_request_file,
    }
    if fields is not None:
        record["suggested_fields"] = fields
    if default_fields is not None:
        record["compact_fields"] = default_fields
    if include_output_schema:
        record["output_schema"] = (
            model_schema(spec.output_model) if spec.output_model else None
        )
    return record


def summarize_spec(spec: ToolSpec) -> ServiceResult:
    return {
        "tool": spec.name,
        "family": spec.family,
        "label": spec.operation_label_zh,
        "summary": spec.summary,
        "surfaces": _surfaces(spec),
    }


def describe_input_spec(spec: ToolSpec) -> ServiceResult:
    """Call contract with input schema and output root names."""
    return _describe_contract(spec, include_output_schema=False)
