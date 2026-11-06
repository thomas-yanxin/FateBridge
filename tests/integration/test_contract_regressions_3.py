"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.astro import native_execution as execution
from fatebridge.mcp_server import create_mcp_app
from tests.support.result_delivery import (
    RESULT_CASES,
    RESULT_PAYLOADS,
    forbidden,
)
from tests.support.transports import SPECS, business, call_cli, inputs, native, rest


def test_compact_typed_json_preserves_unicode_envelopes_and_numeric_values():
    original = {
        "文本": "完整见证\n不删样本",
        "map": ["datetime", "not an envelope"],
        "numbers": [0, -1, 0.0000000000000001, -0.0, True, None],
        "moment": datetime(2000, 1, 1, tzinfo=timezone.utc),
        "tuple": ("中文", 2),
    }
    message = {"kind": "result", "value": execution.encode(original)}
    old = json.dumps(message, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    compact = execution.message_bytes(message)
    assert len(compact) < len(old)
    assert json.loads(compact) == json.loads(old)
    assert execution.decode(json.loads(compact)["value"]) == original
    assert compact.endswith(b"\n") and compact.count(b"\n") == 1


def test_actual_message_limit_still_accepts_exactly64mib_and_rejects_one_extra_byte():
    limit = 64 * 1024 * 1024
    assert execution._MAX_MESSAGE == limit
    assert len(execution.message_bytes({"x": "a" * (limit - 9)})) == limit
    with pytest.raises(execution.NativeExecutionError, match="exceeds limit"):
        execution.message_bytes({"x": "a" * (limit - 8)})


@pytest.mark.parametrize("invalid", [float("inf"), float("-inf"), float("nan")])
def test_size_optimization_does_not_allow_nonfinite_json(invalid):
    with pytest.raises(ValueError):
        execution.message_bytes({"x": invalid})


@pytest.mark.parametrize("tool", ["canping", "heluo"])
def test_all_verified_transports_preserve_frozen_payload_without_lock_writes(
    tool, tmp_path, monkeypatch, capsys
):
    case = next(c for c in RESULT_CASES if c["tool"] == tool)
    payload = RESULT_PAYLOADS[case["id"]]
    store = delivery.ResultStore(tmp_path / "private")
    ref = store.put(payload)
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    monkeypatch.setattr(store, "_locked", forbidden)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    path = "numerology_evidence.birth_clock"
    run_id = payload["run_metadata"]["run_id"]
    response = TestClient(api.app).get(
        f"/api/results/{ref['result_id']}/verified",
        params={
            "expected_run_id": run_id,
            "path": path,
        },
    )
    assert response.status_code == 200, response.text
    assert (
        run(
            [
                "result-read",
                ref["result_id"],
                "--run-id",
                run_id,
                "--path",
                path,
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)

    async def read():
        async with Client(create_mcp_app(families="divination")) as client:
            uri = f"fatebridge://results/{ref['result_id']}/verified/{run_id}/fields/{path}/0"
            return json.loads((await client.read_resource(uri))[0].text)

    native = asyncio.run(read())
    assert (
        native
        == cli
        == response.json()
        == store.verified_page(ref["result_id"], run_id, path=path)
    )


@pytest.mark.parametrize(
    "state", ["current", "before_dayun", "missing_gender", "explicit_age"]
)
def test_first_view_keeps_every_current_fact_and_partial_status_on_three_surfaces(
    state, rest, tmp_path, capsys
):
    spec = SPECS["timing_analysis"]
    payload = {**inputs(spec), "use_true_solar_time": False}
    if state != "explicit_age":
        payload.pop("analysis_age", None)
    if state == "before_dayun":
        payload.update(
            analysis_year=payload["birth_year"],
            analysis_month=payload["birth_month"],
            analysis_day=payload["birth_day"],
            analysis_hour=12,
            analysis_minute=0,
        )
    elif state == "missing_gender":
        payload["gender"] = None
    full_response = rest.post(spec.rest_path, json=payload)
    assert full_response.status_code == 200, full_response.text
    dayun = full_response.json()["dayun_analysis"]
    expected = deepcopy(dayun)
    expected.pop("first_view")
    context = expected.get("timing_context")
    timeline = context.get("timeline") if isinstance(context, dict) else None
    if isinstance(timeline, dict):
        # No arbitrary field dropping: all metadata, conditions, model labels,
        # source references and exact boundaries survive. The original table
        # remains available in the same full service result.
        assert len(dayun["timing_context"]["timeline"]["periods"]) == 12
        timeline.pop("periods")
    assert dayun["first_view"] == expected
    if state == "before_dayun":
        assert expected["status"] == "before_dayun"
    elif state == "missing_gender":
        assert expected["status"] == "unavailable_missing_gender"
    else:
        assert expected["current_dayun"]
        assert expected["start_at"] < expected["end_at"]
        assert expected["selection_basis"] == (
            "explicit_age_reference"
            if state == "explicit_age"
            else "civil_calendar_moment"
        )
    fields = suggested_fields(spec)
    assert "dayun_analysis.first_view" in fields and "dayun_analysis" not in fields
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", p) for p in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    results = [http.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        assert result["dayun_analysis"]["first_view"] == expected
        assert result["analysis_calendar"]["analysis_date_context"][
            "bazi_month_boundary"
        ]
        assert result["liunian_analysis"]
