"""Schema and compact capability descriptions derived from ToolSpec."""

import json
from typing import Any, Dict, List, Union, get_args, get_origin

from pydantic import BaseModel

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.schema_cache import model_schema


def resolve_spec(specs: List[ToolSpec], name: str) -> ToolSpec | None:
    """Accept a catalog key or published name without inventing transport aliases."""
    return next((s for s in specs if name in {s.key, s.tool_name}), None)


def unwrap_optional(annotation: Any) -> Any:
    """Strip a single ``Optional[...]`` / ``Union[..., None]`` wrapper."""
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if non_none:
            return non_none[0]
    return annotation


def is_model_field(annotation: Any) -> bool:
    """True if the (unwrapped) annotation is a nested pydantic model."""
    base = unwrap_optional(annotation)
    return isinstance(base, type) and issubclass(base, BaseModel)


def field_type_name(annotation: Any) -> str:
    """Render a field annotation as a short, agent-readable type string."""
    # Multi-member Unions (e.g. ``house_system: Union[int, str]``) must surface
    # every accepted type, not just the first — otherwise an agent reading the
    # self-describe surface sees only ``int`` and never learns it may pass
    # ``"placidus"``/``"equal_mc"``. (MCP input validation is unaffected; it
    # binds the live annotation, but the human/agent-readable ``type`` string
    # comes from here.)
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) > 1:
            return " | ".join(field_type_name(a) for a in non_none)
    base = unwrap_optional(annotation)
    origin = get_origin(base)
    if origin in (list, List):
        args = get_args(base)
        inner = getattr(args[0], "__name__", str(args[0])) if args else "str"
        return f"list[{inner}]"
    if isinstance(base, type):
        return base.__name__
    return str(base)


def spec_is_cli_safe(spec: "ToolSpec") -> bool:
    """Nested models need an explicit JSON request-file/argument contract."""
    return spec.cli_request_file or not any(
        is_model_field(f.annotation) for f in spec.request_model.model_fields.values()
    )


def describe_spec(spec: "ToolSpec") -> Dict[str, Any]:
    """Self-describing, transport-agnostic record for one tool.

    The CLI ``describe`` command and the REST ``GET /api/tools`` endpoint both
    render this, so an agent sees the same parameter schema, surfaces, and family
    regardless of how it discovers the tool. ``surfaces.mcp_name`` is ``None`` for
    REST-only tools so an agent never assumes an MCP tool that does not exist.
    """
    return _describe_contract(spec, include_output_schema=True)


def _describe_contract(
    spec: ToolSpec, *, include_output_schema: bool
) -> Dict[str, Any]:
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
    from fatebridge.application.examples import evidence_views, example_input

    example = example_input(spec)
    views = evidence_views(spec)
    return {
        **({"example_input": example} if example is not None else {}),
        **({"evidence_views": views} if views is not None else {}),
        "tool": spec.tool_name,
        "key": spec.key,
        "summary": spec.summary,
        "operation_label_zh": spec.operation_label_zh,
        "family": spec.family,
        "annotations": spec.execution_hints.as_annotations(),
        "reproducibility": spec.reproducibility.as_manifest(),
        "full_result_required_fields": list(spec.required_output_fields),
        "surfaces": {
            "cli": spec_is_cli_safe(spec),
            "cli_name": spec.tool_name if spec_is_cli_safe(spec) else None,
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


def summarize_spec(spec: ToolSpec) -> Dict[str, Any]:
    return {
        "tool": spec.tool_name,
        "key": spec.key,
        "summary": spec.summary,
        "operation_label_zh": spec.operation_label_zh,
        "family": spec.family,
        "surfaces": {
            "cli": spec_is_cli_safe(spec),
            "cli_name": spec.tool_name if spec_is_cli_safe(spec) else None,
            "rest_path": spec.rest_path,
            "mcp_name": spec.mcp_name,
        },
        "cli_request_file": spec.cli_request_file,
        "annotations": spec.execution_hints.as_annotations(),
        "reproducibility": spec.reproducibility.as_manifest(),
    }


def mcp_description(spec: ToolSpec) -> str:
    """Make a published tool callable without another discovery round trip."""
    from fatebridge.application.examples import (
        call_guidance,
        evidence_views,
        suggested_fields,
    )

    fields = suggested_fields(spec)
    guidance = call_guidance(spec)
    views = evidence_views(spec)
    summary = spec.summary + (
        " 调用参考系：" + json.dumps(guidance, ensure_ascii=False) if guidance else ""
    )
    if not fields:
        return summary
    return (
        summary
        + " 首轮可直接调用；建议 fields="
        + json.dumps(fields, ensure_ascii=False)
        + "; strict_fields=true, include_snapshot_text=false。"
        + "这些是可扩展的首轮视图；仅需更细字段时读取完整输出契约。"
        + (
            " 按本轮任务优先复制 evidence_views 中对应 fields（它们不是请求参数）："
            + json.dumps(views, ensure_ascii=False)
            if views
            else ""
        )
    )


def describe_input_spec(spec: ToolSpec) -> Dict[str, Any]:
    """Compact call contract; full output validation stays available on demand."""
    record = _describe_contract(spec, include_output_schema=False)
    record["output_fields"] = (
        list(spec.output_model.model_fields) if spec.output_model else []
    )
    record["output_contract_uri"] = f"fatebridge://tools/{spec.tool_name}"
    from fatebridge.application.examples import call_guidance, suggested_fields

    fields = suggested_fields(spec)
    if fields is not None:
        record["suggested_fields"] = fields
    guidance = call_guidance(spec)
    if guidance is not None:
        record["call_guidance"] = guidance
    record["projection_note"] = (
        "suggested_fields 是首轮参考，可按问题增减；否则按 output_fields 选业务分支。"
        "run_metadata 自动保留。"
        "需要更细路径时再读完整 output_schema；不要猜测字段名。"
    )
    return record
