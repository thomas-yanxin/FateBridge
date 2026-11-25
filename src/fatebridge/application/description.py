"""Schema and compact capability descriptions derived from ToolSpec."""

from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

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
    return next((spec for spec in specs if spec.tool_name == name), None)


def unwrap_optional(annotation: object) -> object:
    """Strip a single ``Optional[...]`` / ``Union[..., None]`` wrapper."""
    if get_origin(annotation) in (Union, UnionType):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if non_none:
            return non_none[0]
        else:
            pass
    else:
        pass
    return annotation


def is_model_field(annotation: object) -> bool:
    """True if the (unwrapped) annotation is a nested pydantic model."""
    base = unwrap_optional(annotation)
    return isinstance(base, type) and issubclass(base, BaseModel)


def field_type_name(annotation: object) -> str:
    """Render a field annotation as a short, agent-readable type string."""
    # Multi-member Unions (e.g. ``house_system: Union[int, str]``) must surface
    # every accepted type, not just the first — otherwise an agent reading the
    # self-describe surface sees only ``int`` and never learns it may pass
    # ``"placidus"``/``"equal_mc"``. (MCP input validation is unaffected; it
    # binds the live annotation, but the human/agent-readable ``type`` string
    # comes from here.)
    if get_origin(annotation) in (Union, UnionType):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) > 1:
            return " | ".join(field_type_name(a) for a in non_none)
        else:
            pass
    else:
        pass
    base = unwrap_optional(annotation)
    origin = get_origin(base)
    if origin is list:
        args = get_args(base)
        inner = getattr(args[0], "__name__", str(args[0])) if args else "str"
        return f"list[{inner}]"
    else:
        pass
    if isinstance(base, type):
        return base.__name__
    else:
        pass
    return str(base)


def spec_is_cli_safe(spec: ToolSpec) -> bool:
    """Nested models need an explicit JSON request-file/argument contract."""
    return spec.cli_request_file or not any(
        is_model_field(f.annotation) for f in spec.request_model.model_fields.values()
    )


def describe_spec(spec: ToolSpec) -> dict[str, Any]:
    """Self-describing, transport-agnostic record for one tool.

    The CLI ``describe`` command and the REST ``GET /api/tools`` endpoint both
    render this, so an agent sees the same parameter schema, surfaces, and family
    regardless of how it discovers the tool. ``surfaces.mcp_name`` is ``None`` for
    REST-only tools so an agent never assumes an MCP tool that does not exist.
    """
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
    cli_safe = spec_is_cli_safe(spec)
    return {
        **(
            {"example_input": example, "example_context": example_context()}
            if example is not None
            else {}
        ),
        **({"evidence_views": views} if views is not None else {}),
        **({"call_guidance": guidance} if guidance is not None else {}),
        "tool": spec.tool_name,
        "key": spec.key,
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
        **(
            {
                "full_result_required_fields_by_variant": {
                    variant: list(fields)
                    for variant, fields in spec.required_output_fields_by_variant.items()
                }
            }
            if spec.required_output_fields_by_variant
            else {}
        ),
        "full_result_empty_object_policy": "reject_required_roots",
        "execution": {
            "cpu_bound": spec.cpu_bound,
            "budget_scope": "process_shared_across_transports",
        },
        "surfaces": {
            "cli": cli_safe,
            "cli_name": spec.tool_name if cli_safe else None,
            "rest_path": spec.rest_path,
            "mcp_name": spec.mcp_name,
        },
        "parameters": parameters,
        "input_schema": model_schema(spec.request_model),
        "cli_request_file": spec.cli_request_file,
        **(
            {
                "output_schema": (
                    model_schema(spec.output_model) if spec.output_model else None
                )
            }
            if include_output_schema
            else {}
        ),
    }


def summarize_spec(spec: ToolSpec) -> dict[str, Any]:
    cli_safe = spec_is_cli_safe(spec)
    return {
        "tool": spec.tool_name,
        "key": spec.key,
        "summary": spec.summary,
        "operation_label_zh": spec.operation_label_zh,
        "family": spec.family,
        "surfaces": {
            "cli": cli_safe,
            "cli_name": spec.tool_name if cli_safe else None,
            "rest_path": spec.rest_path,
            "mcp_name": spec.mcp_name,
        },
        "cli_request_file": spec.cli_request_file,
        "annotations": spec.execution_hints.as_annotations(),
        "reproducibility": spec.reproducibility.as_manifest(),
        "method_ids": [method.method_id for method in spec.methods],
        "execution": {
            "cpu_bound": spec.cpu_bound,
            "budget_scope": "process_shared_across_transports",
        },
    }


def describe_input_spec(spec: ToolSpec) -> dict[str, Any]:
    """Compact call contract; full output validation stays available on demand."""
    record = _describe_contract(spec, include_output_schema=False)
    record["output_fields"] = (
        list(spec.output_model.model_fields) if spec.output_model else []
    )
    record["output_contract_uri"] = f"fatebridge://tools/{spec.tool_name}"
    fields = suggested_fields(spec)
    if fields is not None:
        record["suggested_fields"] = fields
    else:
        pass
    default_fields = compact_fields(spec)
    if default_fields != fields:
        record["compact_fields"] = default_fields
    else:
        pass
    record["projection_note"] = (
        "首次摘要使用 detail=compact 并省略 fields。"
        "suggested_fields 是可显式请求的业务字段参考，按问题取用。"
        "run_metadata 自动保留。"
        "需要更细路径时再读完整 output_schema；不要猜测字段名。"
    )
    return record
