"""Share fixed Ren protocol inputs and output-contract probes."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, JsonValue

import fatebridge.application.execution as execution
from fatebridge.application.tool_spec import ToolSpec
from tests.fixtures.ren_anchors import ANCHOR_PAYLOADS
from tests.support.transports import AS_OF, call_cli, native

REN_PROTOCOL_PAYLOAD: dict[str, JsonValue] = {
    "analysis_year": 2026,
    "analysis_month": 4,
    "analysis_day": 4,
    "analysis_hour": 21,
    "analysis_minute": 18,
    "analysis_second": 37,
    "analysis_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "is_diurnal": False,
    "guiren_profile": "tanyuan_xieji_v1",
}


def term_boundary_payload(tool_key: str) -> dict[str, JsonValue]:
    """Use the same civil second for each term consumer."""
    if tool_key == "sanshiunited":
        return {
            "date": "2026-04-04",
            "time": "21:18:37",
            "zone": "+08:00",
            "qimen_options": {"layout": "direct"},
            "taiyi_options": {},
            "use_true_solar_time": False,
            "liureng_is_diurnal": False,
        }
    else:
        payload = dict(REN_PROTOCOL_PAYLOAD)
    if tool_key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    else:
        pass
    return payload


def assert_output_fault_on_all_transports(
    tool_spec: ToolSpec,
    corrupted_output: dict[str, JsonValue],
    is_projected: bool,
    rest_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    request_payload: dict[str, JsonValue] | None = None,
) -> None:
    """Send a corrupted service result through the real output gate."""
    execute_spec = execution.execute_spec

    def execute_with_corrupted_output(
        spec: ToolSpec,
        request: BaseModel,
        *,
        render_snapshot: bool = True,
        strict_validation: bool | None = None,
    ) -> dict[str, JsonValue]:
        if spec.key == tool_spec.key:
            spec = replace(
                spec, bind=lambda _: (lambda: deepcopy(corrupted_output), (), {})
            )
        else:
            pass
        return execute_spec(
            spec,
            request,
            render_snapshot=render_snapshot,
            strict_validation=strict_validation,
        )

    monkeypatch.setattr(execution, "execute_spec", execute_with_corrupted_output)
    mcp_options: dict[str, JsonValue] = {}
    http_parameters = {"as_of": AS_OF, "response_char_limit": "0"}
    cli_flags = ["--response-char-limit", "0"]
    if is_projected:
        http_parameters.update(fields="analysis_type", strict_fields="true")
        mcp_options.update(fields=["analysis_type"], strict_fields=True)
        cli_flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    else:
        pass
    request_payload = (
        ANCHOR_PAYLOADS[tool_spec.key] if request_payload is None else request_payload
    )
    assert tool_spec.rest_path is not None
    http_response = rest_client.post(
        tool_spec.rest_path, json=request_payload, params=http_parameters
    )
    mcp_response = asyncio.run(native(tool_spec, request_payload, **mcp_options))
    exit_code, cli_output = call_cli(
        tool_spec, request_payload, tmp_path, capsys, flags=cli_flags
    )
    assert http_response.status_code == 500 and mcp_response.is_error and exit_code == 1
    assert cli_output["error_code"] == "internal_error"
