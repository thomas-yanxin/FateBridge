"""Assertions shared by nested output and transport contract tests."""

import asyncio
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import ValidationError as SchemaError
from pydantic import BaseModel, JsonValue, ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.tool_spec import ToolSpec
from tests.support.transports import (
    AS_OF,
    SPECS,
    cached_output_validator,
    call_cli,
    inputs,
    native,
)


def schema_leaf(
    root: dict[str, JsonValue], node: dict[str, JsonValue], path: str
) -> dict[str, JsonValue]:
    """Resolve optional models, map values and list items along a schema path."""

    def unwrap(value: JsonValue) -> dict[str, JsonValue]:
        while True:
            assert isinstance(value, dict)
            if "$ref" in value:
                reference = value["$ref"]
                assert isinstance(reference, str) and reference.startswith("#/")
                value = root
                for segment in reference[2:].split("/"):
                    assert isinstance(value, dict)
                    value = value[segment.replace("~1", "/").replace("~0", "~")]
            elif "anyOf" in value:
                alternatives = value["anyOf"]
                assert isinstance(alternatives, list)
                candidates = []
                for alternative in alternatives:
                    assert isinstance(alternative, dict)
                    if alternative.get("type") != "null":
                        candidates.append(alternative)
                    else:
                        pass
                assert len(candidates) == 1
                value = candidates[0]
            else:
                return value

    for segment in path.split("."):
        schema = unwrap(node)
        if segment == "[]":
            child = schema["items"]
        elif segment == "{}":
            child = schema["additionalProperties"]
        else:
            properties = schema["properties"]
            assert isinstance(properties, dict)
            child = properties[segment]
        assert isinstance(child, dict)
        node = child
    return unwrap(node)


def reject_nested_fact_fault(
    key: str,
    payload: dict[str, JsonValue],
    rest: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Require the contract fault before projection on REST, MCP and CLI."""
    spec = SPECS[key]
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(payload)
    with pytest.raises(SchemaError):
        cached_output_validator(spec.output_model).validate(payload)

    original = execution.execute_spec

    def broken_output(actual: ToolSpec, request: BaseModel) -> dict[str, JsonValue]:
        if actual.key == key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(payload), (), {})
            )
        else:
            pass
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken_output)
    request = inputs(spec)
    # Selecting an unrelated field cannot hide corrupt professional facts:
    # validation is performed before projection in the shared execution unit.
    http = rest.post(
        spec.rest_path,
        json=request,
        params={"as_of": AS_OF, "fields": "analysis_type", "trace_id": "nested-fault"},
    )
    protocol = asyncio.run(
        native(spec, request, fields=["analysis_type"], trace_id="nested-fault")
    )
    code, output = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        ["--fields", "analysis_type", "--trace-id", "nested-fault"],
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert {
        k: v for k, v in protocol.structured_content.items() if k != "operation"
    } == output
    assert http.json() == {
        k: v for k, v in output.items() if k not in {"operation", "status_code"}
    }
    assert output["status_code"] == 500
    assert output["error_code"] == "internal_error"
    assert output["trace_id"] == "nested-fault"
    assert "private-wrong-value" not in json.dumps(output)
