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


def batch_example_input() -> dict[str, JsonValue]:
    """Build a valid BatchRequest example dynamically from packaged agent examples."""
    bundle = _examples()
    subjects = bundle["subjects"]
    tools = bundle["tools"]
    suggested_map = bundle.get("suggested_fields", {})

    subject_id, raw_subject = next(iter(subjects.items()))
    subject_profile: dict[str, JsonValue] = {
        ("timezone" if key == "birth_timezone" else key): deepcopy(value)
        for key, value in raw_subject.items()
    }

    subject_tools = [name for name, source in tools.items() if source == subject_id][:2]
    dict_tool_entry = next(
        (
            (name, source)
            for name, source in tools.items()
            if isinstance(source, dict)
            and source
            and not any(
                key in {"date", "occupants"}
                or key.startswith(
                    (
                        "birth_",
                        "analysis_",
                        "person1_",
                        "inner_",
                        "question_",
                        "candidate_",
                    )
                )
                for key in source
            )
        ),
        None,
    )

    calls: list[JsonValue] = []
    if subject_tools:
        first_tool = subject_tools[0]
        first_call: dict[str, JsonValue] = {
            "id": "call_1",
            "tool": first_tool,
            "subject": subject_id,
        }
        if first_fields := suggested_map.get(first_tool):
            first_call["fields"] = [first_fields[0]]
        calls.append(first_call)
    if dict_tool_entry is not None:
        dict_tool_name, dict_args = dict_tool_entry
        calls.append(
            {
                "id": f"call_{len(calls) + 1}",
                "tool": dict_tool_name,
                "arguments": deepcopy(dict_args),
            }
        )
    if len(subject_tools) > 1:
        calls.append(
            {
                "id": f"call_{len(calls) + 1}",
                "tool": subject_tools[1],
                "subject": subject_id,
            }
        )

    analysis_source = next(
        (
            source
            for source in [*subjects.values(), *tools.values()]
            if isinstance(source, dict) and isinstance(source.get("analysis_year"), int)
        ),
        None,
    )
    analysis_year = (
        analysis_source["analysis_year"]
        if analysis_source and isinstance(analysis_source.get("analysis_year"), int)
        else 2026
    )
    analysis_month = (
        analysis_source["analysis_month"]
        if analysis_source and isinstance(analysis_source.get("analysis_month"), int)
        else 4
    )
    analysis_day = (
        analysis_source["analysis_day"]
        if analysis_source and isinstance(analysis_source.get("analysis_day"), int)
        else 6
    )
    analysis_hour = (
        analysis_source["analysis_hour"]
        if analysis_source and isinstance(analysis_source.get("analysis_hour"), int)
        else 9
    )
    analysis_minute = (
        analysis_source["analysis_minute"]
        if analysis_source and isinstance(analysis_source.get("analysis_minute"), int)
        else 30
    )
    analysis_datetime = (
        f"{analysis_year:04d}-{analysis_month:02d}-{analysis_day:02d}"
        f"T{analysis_hour:02d}:{analysis_minute:02d}:00+08:00"
    )
    context_payload: dict[str, JsonValue] = {"analysis_datetime": analysis_datetime}
    if isinstance(raw_subject.get("birth_place"), str):
        context_payload["place"] = raw_subject["birth_place"]

    return {
        "subjects": {subject_id: subject_profile},
        "context": context_payload,
        "defaults": {"use_true_solar_time": True},
        "calls": calls,
        "as_of": analysis_datetime,
    }
