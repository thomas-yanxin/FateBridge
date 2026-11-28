"""Read fictional starter inputs and evidence views for public discovery."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import cast

from pydantic import JsonValue
from typing_extensions import NotRequired, TypedDict

from fatebridge.application.tool_spec import EvidenceViews, ToolSpec


class AgentExamples(TypedDict):
    note: str
    subjects: dict[str, dict[str, JsonValue]]
    tools: dict[str, str | dict[str, JsonValue]]
    suggested_fields: NotRequired[dict[str, list[str]]]
    evidence_views: NotRequired[dict[str, EvidenceViews]]
    call_guidance: NotRequired[dict[str, dict[str, JsonValue]]]


def validate_agent_examples() -> AgentExamples:
    """Validate packaged examples against the AgentExamples TypedDict schema."""
    from pydantic import TypeAdapter

    path = Path(__file__).resolve().parents[1] / "data/agent_examples.json"
    return TypeAdapter(AgentExamples).validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _examples() -> AgentExamples:
    path = Path(__file__).resolve().parents[1] / "data/agent_examples.json"
    return cast(AgentExamples, json.loads(path.read_bytes()))


def example_input(spec: ToolSpec) -> dict[str, JsonValue] | None:
    bundle = _examples()
    source = bundle["tools"].get(spec.name)
    if source is None:
        return None
    elif isinstance(source, str):
        source = bundle["subjects"][source]
    inputs = {
        field: deepcopy(value)
        for field, value in source.items()
        if field in spec.request_model.model_fields
    }
    spec.request_model.model_validate(inputs)
    return inputs


def example_context() -> dict[str, str | bool]:
    """Describe the purpose of the fictional discovery inputs."""
    return {
        "fictional": True,
        "purpose": "schema_and_transport_demo",
        "use_as_user_default": False,
    }


def suggested_fields(spec: ToolSpec, *, view: str | None = None) -> list[str] | None:
    """Return the fields for a declared view or the default first response."""
    if view is not None:
        views = evidence_views(spec) or {}
        if view not in views:
            raise ValueError(f"Unknown evidence view for {spec.name}: {view}")
        else:
            return list(views[view]["fields"])
    else:
        fields = _examples().get("suggested_fields", {}).get(spec.name)
        return list(fields) if fields is not None else None


def evidence_views(spec: ToolSpec) -> EvidenceViews | None:
    """Return independent copies of published field selections."""
    views = deepcopy(_examples().get("evidence_views", {}).get(spec.name))
    if spec.evidence_views_builder is not None:
        return spec.evidence_views_builder(views)
    else:
        return views


def call_guidance(spec: ToolSpec) -> dict[str, JsonValue] | None:
    """Return an independent copy of the tool's published call guidance."""
    return deepcopy(_examples().get("call_guidance", {}).get(spec.name))
