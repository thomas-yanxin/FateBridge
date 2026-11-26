"""Schema and compact capability descriptions derived from ToolSpec."""

from types import UnionType
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

UNION_ORIGINS = (UnionType, get_origin(Annotated[int, "u"] | None))

from fatebridge.application.examples import (
    call_guidance,
    compact_fields,
    evidence_views,
    example_context,
    example_input,
    suggested_fields,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.schema_cache import model_schema


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
        inner = getattr(args[0], "__name__", str(args[0])) if args else "str"
        return f"list[{inner}]"
    if isinstance(base, type):
        return base.__name__
    return str(base)


def describe_spec(spec: ToolSpec) -> dict[str, Any]:
    """Describe one tool's full schemas, capabilities and available transports."""
    return _describe_contract(spec, include_output_schema=True)


def _describe_contract(
    spec: ToolSpec, *, include_output_schema: bool
) -> dict[str, Any]:
    """Build requested contracts without generating schemas that are discarded."""
    parameters = [
        {
            "name": name,
            "flag": "--" + name.replace("_", "-"),
            "type": field_type_name(field.annotation),
            "required": field.is_required(),
            "default": (
                None
                if field.is_required()
                else field.get_default(call_default_factory=True)
            ),
            "description": field.description or "",
            "nested_model": is_model_field(field.annotation),
        }
        for name, field in spec.request_model.model_fields.items()
    ]
    example = example_input(spec)
    views = evidence_views(spec)
    guidance = call_guidance(spec)
    fields = suggested_fields(spec)
    default_fields = compact_fields(spec)
    record: dict[str, Any] = {
        **(
            {"example_input": example, "example_context": example_context()}
            if example is not None
            else {}
        ),
        **({"evidence_views": views} if views is not None else {}),
        **({"call_guidance": guidance} if guidance is not None else {}),
        "tool": spec.name,
        "summary": spec.summary,
        "operation_label_zh": spec.operation_label_zh,
        "family": spec.family,
        "annotations": spec.execution_hints.as_annotations(),
        "reproducibility": spec.reproducibility.as_manifest(),
        "method_contract_coverage": (
            "declared_subset" if spec.methods else "not_registered"
        ),
        "method_contracts": [method.as_manifest() for method in spec.methods],
        "method_registration": {
            "scope": "domain_methods_and_runtime_policy_witnesses",
            "status": "registered" if spec.methods else "not_registered",
            "applicability_contract": "input_schema_and_runtime_domain_preconditions",
            "version_semantics": "contract_v1 is a registration contract; actual algorithm versions are recorded separately",
        },
        "full_result_required_fields": list(spec.required_output_fields),
        "full_result_empty_object_policy": "reject_required_roots",
        "execution": {
            "cpu_bound": spec.cpu_bound,
            "budget_scope": "process_shared_across_transports",
        },
        "surfaces": {
            "cli": True,
            "cli_name": spec.name,
            "rest_path": spec.rest_path,
            "mcp_name": spec.name if spec.expose_mcp else None,
        },
        "parameters": parameters,
        "input_schema": model_schema(spec.request_model),
        "output_fields": (
            list(spec.output_model.model_fields) if spec.output_model else []
        ),
        "cli_request_file": spec.cli_request_file,
        "projection_note": (
            "默认 detail=compact 返回核心业务字段；需要指定字段时传 fields"
            "（严格校验路径，支持点号子路径）；需要完整结果时传 detail=audit。"
            "run_metadata 自动保留；不要猜测字段名。"
        ),
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


def summarize_spec(spec: ToolSpec) -> dict[str, Any]:
    return {
        "tool": spec.name,
        "family": spec.family,
        "label": spec.operation_label_zh,
        "summary": spec.summary,
        "surfaces": {
            "cli": True,
            "cli_name": spec.name,
            "rest_path": spec.rest_path,
            "mcp_name": spec.name if spec.expose_mcp else None,
        },
        "method_ids": [method.method_id for method in spec.methods],
    }


def describe_input_spec(spec: ToolSpec) -> dict[str, Any]:
    """Call contract with input schema and output root names; output_schema is on detail=full."""
    return _describe_contract(spec, include_output_schema=False)
