"""Grade observable tool behavior against preregistered case rules."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict

from pydantic import JsonValue
from typing_extensions import NotRequired, Required


class CaseContract(TypedDict, total=False):
    manual_review: Required[list[str]]
    expected_tool_errors: dict[str, JsonValue]
    required_any: list[list[str]]
    no_calculation: bool
    forbidden_tools: list[str]
    allowed_tools: list[str] | None
    arguments: dict[str, dict[str, JsonValue]]
    argument_paths: dict[str, dict[str, JsonValue]]
    instant_arguments: dict[str, dict[str, str]]
    max_successful_calls: dict[str, int]
    max_total_calls: dict[str, int]
    full_export: str


class CapturedErrorBinding(TypedDict):
    journal_record_sha256: JsonValue
    is_error: Literal[True]
    scope: str


class ObservedCall(TypedDict):
    server: str | None
    tool: str | None
    arguments: dict[str, JsonValue]
    status: JsonValue
    error: JsonValue
    protocol_error: bool
    error_response: dict[str, JsonValue] | None
    mcp_tool: NotRequired[str]
    mcp_arguments: NotRequired[dict[str, JsonValue]]
    captured_returned_error: NotRequired[CapturedErrorBinding]


class Grade(TypedDict):
    mechanical_checks_passed: bool
    failures: list[str]
    tool_calls: list[ObservedCall]
    commands: list[str]
    manual_review: list[str]


def walk(value: JsonValue) -> Iterator[dict[str, JsonValue]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)
    else:
        pass


@dataclass(kw_only=True)
class EventObservations:
    calls: list[ObservedCall]
    commands: list[str]
    has_malformed_completed_event: bool


def parse_observations(events: list[JsonValue]) -> EventObservations:
    calls: list[ObservedCall] = []
    commands: list[str] = []
    has_malformed_completed_event = False
    for event in events:
        # note (evaluation): Started and completed events refer to the same call.
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        else:
            pass
        item = event.get("item")
        if not isinstance(item, dict):
            has_malformed_completed_event = True
            continue
        else:
            pass
        if item.get("type") == "mcp_tool_call":
            server, tool = item.get("server"), item.get("tool")
            arguments, result = item.get("arguments", {}), item.get("result")
            is_valid_call = (
                isinstance(server, str)
                and isinstance(tool, str)
                and isinstance(arguments, dict)
                and (result is None or isinstance(result, dict))
            )
            response = result if isinstance(result, dict) else {}
            calls.append(
                {
                    "server": server if isinstance(server, str) else None,
                    "tool": tool if isinstance(tool, str) else None,
                    "arguments": arguments if isinstance(arguments, dict) else {},
                    "status": item.get("status") if is_valid_call else "failed",
                    "error": (
                        item.get("error") if is_valid_call else "malformed_tool_call"
                    ),
                    "protocol_error": bool(
                        response.get("isError") or response.get("is_error")
                    ),
                    "error_response": error_response(response),
                }
            )
        else:
            pass
        for node in walk(item):
            command = node.get("command")
            if isinstance(command, str):
                commands.append(command)
            else:
                pass
    return EventObservations(
        calls=calls,
        commands=commands,
        has_malformed_completed_event=has_malformed_completed_event,
    )


def observations(events: list[JsonValue]) -> tuple[list[ObservedCall], list[str]]:
    parsed = parse_observations(events)
    return parsed.calls, parsed.commands


def error_response(result: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    """Extract an actual structured error; never infer a code from prose."""
    for key in ("structuredContent", "structured_content"):
        value = result.get(key)
        if isinstance(value, dict) and isinstance(value.get("error_code"), str):
            return value
        else:
            pass
    content = result.get("content")
    if not isinstance(content, list):
        return None
    else:
        pass
    for block in content:
        if not isinstance(block, dict):
            continue
        else:
            pass
        text = block.get("text")
        if not isinstance(text, str):
            continue
        else:
            pass
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("error_code"), str):
            return value
        else:
            pass
    return None


def matches_expected_error(actual: JsonValue, expected: JsonValue) -> bool:
    """Only predeclared exact typed error fields can authorize a refusal case."""
    required = {"error_code", "status_code", "retryable"}
    return (
        isinstance(actual, dict)
        and isinstance(expected, dict)
        and required <= expected.keys()
        and type(expected["error_code"]) is str
        and bool(expected["error_code"])
        and type(expected["status_code"]) is int
        and type(expected["retryable"]) is bool
        and all(
            key in actual
            and type(value) in {str, int, bool, type(None)}
            and type(actual.get(key)) is type(value)
            and actual.get(key) == value
            for key, value in expected.items()
        )
    )


def expected_error_call(call: ObservedCall, expected: JsonValue) -> bool:
    return (
        (
            (call["status"] == "completed" and call["protocol_error"])
            or (
                call["status"] == "failed"
                and call.get("captured_returned_error") is not None
            )
        )
        and not call["error"]
        and matches_expected_error(call["error_response"], expected)
    )


def grade_case(
    case: CaseContract,
    events: list[JsonValue],
    final: str,
    returncode: int,
    captured_tool_records: list[dict[str, JsonValue]] | None = None,
) -> Grade:
    parsed = parse_observations(events)
    own = [c for c in parsed.calls if c["server"] == "fatebridge"]
    if (
        captured_tool_records is not None
        and len(own) == len(captured_tool_records)
        and all(
            c["tool"] == r.get("tool") and c["arguments"] == r.get("arguments")
            for c, r in zip(own, captured_tool_records)
        )
    ):
        matched_replies = captured_tool_records
    else:
        matched_replies = [{} for _ in own]
    for call, record in zip(own, matched_replies):
        if call["tool"] == "run_calculation":
            envelope = call["arguments"]
            name = envelope.get("tool")
            inputs = envelope.get("arguments")
            if isinstance(name, str) and (inputs is None or isinstance(inputs, dict)):
                call["mcp_tool"] = "run_calculation"
                call["mcp_arguments"] = envelope
                call["tool"] = name
                call["arguments"] = {
                    **(inputs or {}),
                    **{
                        k: v
                        for k, v in envelope.items()
                        if k not in {"tool", "arguments"}
                    },
                }
            else:
                pass
        else:
            pass
        response = record.get("result")
        response_error = (
            error_response(response) if isinstance(response, dict) else None
        )
        tool = call["tool"]
        if (
            tool is not None
            and isinstance(response, dict)
            and record.get("event") == "tool_call"
            and record.get("outcome") == "returned"
            and response.get("is_error") is True
            and call["error_response"] is not None
            and response_error == call["error_response"]
            and matches_expected_error(
                response_error,
                case.get("expected_tool_errors", {}).get(tool),
            )
        ):
            call["captured_returned_error"] = {
                "journal_record_sha256": record.get("sha256"),
                "is_error": True,
                "scope": "Matched actual server reply; raw CLI status retained",
            }
        else:
            pass
    names = {c["tool"] for c in own}
    failures = []
    if parsed.has_malformed_completed_event:
        failures.append("malformed_completed_event")
    else:
        pass
    if returncode or not final.strip():
        failures.append("execution_failed_or_empty_answer")
    else:
        pass
    if any(c["server"] != "fatebridge" for c in parsed.calls):
        failures.append("unexpected_external_service")
    else:
        pass
    last = {c["tool"]: c for c in own}
    expected_errors = case.get("expected_tool_errors", {})
    if any(
        (c["status"] == "failed" or c["error"] or c["protocol_error"])
        and not expected_error_call(
            c, expected_errors.get(c["tool"]) if c["tool"] is not None else None
        )
        for c in last.values()
    ):
        failures.append("unrecovered_tool_failure")
    else:
        pass
    for name, expected in expected_errors.items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or not all(expected_error_call(c, expected) for c in selected):
            failures.append("expected_tool_error_not_matched:" + name)
        else:
            pass
    for choices in case.get("required_any", []):
        if not names.intersection(choices):
            failures.append("missing_tool:" + "|".join(choices))
        else:
            pass
    if case.get("no_calculation") and any(
        name
        not in {
            "knowledge_read",
            "knowledge_catalog",
            "knowledge_registry",
            "discover_capabilities",
            "describe_capability",
            "read_result",
            "read_mcp_resource",
            "list_mcp_resources",
            "list_mcp_resource_templates",
        }
        for name in names
    ):
        failures.append("unexpected_calculation")
    else:
        pass
    if names.intersection(case.get("forbidden_tools", [])):
        failures.append("out_of_scope_tool")
    else:
        pass
    allowed = case.get("allowed_tools")
    if allowed is not None:
        allowed_names = set(allowed)
        if allowed_names:
            allowed_names.update(
                ("discover_capabilities", "describe_capability", "read_result")
            )
        else:
            pass
        if names - allowed_names:
            failures.append("out_of_scope_tool")
        else:
            pass
    else:
        pass
    for name, expected in case.get("arguments", {}).items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or any(
            c["arguments"].get(key) != value
            for c in selected
            for key, value in expected.items()
        ):
            failures.append("input_mismatch:" + name)
        else:
            pass
    for name, expected in case.get("argument_paths", {}).items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or any(
            not _same_argument_path(c["arguments"], path, value)
            for c in selected
            for path, value in expected.items()
        ):
            failures.append("input_mismatch:" + name)
        else:
            pass
    for name, expected_instants in case.get("instant_arguments", {}).items():
        selected = [c for c in own if c["tool"] == name]

        def same_instant(actual: JsonValue, expected: str) -> bool:
            if not isinstance(actual, str) or not isinstance(expected, str):
                return False
            else:
                pass
            try:
                actual_time = datetime.fromisoformat(actual)
                expected_time = datetime.fromisoformat(expected)
                return (
                    actual_time.utcoffset() is not None
                    and expected_time.utcoffset() is not None
                    and actual_time == expected_time
                )
            except ValueError:
                return False

        if not selected or any(
            not same_instant(c["arguments"].get(key), value)
            for c in selected
            for key, value in expected_instants.items()
        ):
            failures.append("instant_mismatch:" + name)
        else:
            pass
    for name, maximum in case.get("max_successful_calls", {}).items():
        successful = [
            c
            for c in own
            if c["tool"] == name
            and c["status"] == "completed"
            and not c["error"]
            and not c["protocol_error"]
        ]
        if len(successful) > maximum:
            failures.append("repeated_calculation:" + name)
        else:
            pass
    for name, maximum in case.get("max_total_calls", {}).items():
        if sum(c["tool"] == name for c in own) > maximum:
            failures.append("repeated_tool_attempt:" + name)
        else:
            pass
    if case.get("full_export"):
        selected = [c for c in own if c["tool"] == case["full_export"]]
        if (
            not selected
            or selected[0]["arguments"].get("fields") is not None
            or (
                selected[0].get("mcp_tool") == "run_calculation"
                and selected[0]["mcp_arguments"].get("detail") != "audit"
            )
        ):
            failures.append("projected_full_export")
        else:
            pass
    else:
        pass
    return {
        "mechanical_checks_passed": not failures,
        "failures": failures,
        "tool_calls": own,
        "commands": parsed.commands,
        "manual_review": case["manual_review"],
    }


GRADING_POLICY: Literal["observed_tool_contracts_v3"] = "observed_tool_contracts_v3"


def _same_argument_path(
    arguments: dict[str, JsonValue], path: str, expected: JsonValue
) -> bool:
    value: JsonValue = arguments
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        else:
            pass
        value = value[part]
    return value == expected and isinstance(value, bool) == isinstance(expected, bool)
