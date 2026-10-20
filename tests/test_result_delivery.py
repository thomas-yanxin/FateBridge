"""Large responses stay bounded while the original run remains fully readable."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.private_files import ensure_private_directory, open_private_file


@pytest.fixture
def store(tmp_path, monkeypatch):
    result = delivery.ResultStore(tmp_path / "private")
    monkeypatch.setattr(delivery, "RESULT_STORE", result)
    monkeypatch.setattr(api, "RESULT_STORE", result)
    return result


def large_payload():
    return {
        "summary": "年度主题不是精确行运判断",
        "analysis_context": {"analysis_datetime": "2026-10-14T12:07:00+08:00"},
        "time_lords": {
            "timeline": [{"id": n, "text": '中文"换行\n' * 30} for n in range(100)]
        },
        "run_metadata": {"run_id": "original", "tool_name": "western_timing_analysis"},
    }


def reconstruct(store, result_id, path=None):
    parts = []
    offset = 0
    while True:
        page = store.page(result_id, offset, path)
        assert len(page["text"]) <= delivery.PAGE_CHARS
        # Each envelope is valid JSON even when its text is a document fragment.
        assert json.loads(json.dumps(page, ensure_ascii=False)) == page
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    text = "".join(parts)
    assert hashlib.sha256(text.encode()).hexdigest() == page["sha256"]
    return json.loads(text)


@pytest.mark.parametrize("compact", [False, True])
def test_bounded_delivery_preserves_all_values_and_original_receipt(store, compact):
    original = large_payload()
    shaped = delivery.bound_response(original, 8192, compact=compact)
    assert len(delivery._json(shaped, compact)) <= 8192
    assert shaped["summary"] == original["summary"]
    assert shaped["analysis_context"] == original["analysis_context"]
    assert shaped["run_metadata"] == original["run_metadata"]
    ref = shaped["result_delivery"]
    assert ref["file_payload_path"] == "payload"
    assert ref["deferred_fields"] == ["time_lords"]
    assert reconstruct(store, ref["result_id"]) == original
    assert (
        reconstruct(store, ref["result_id"], "time_lords.timeline.7")
        == original["time_lords"]["timeline"][7]
    )
    # These helpers verify POSIX ownership/mode or the Windows owner-only ACL.
    ensure_private_directory(store.directory)
    os.close(open_private_file(Path(ref["file_path"]), os.O_RDONLY))
    assert delivery.bound_response(original, 0) is original


def test_small_payload_is_not_rewritten_or_stored(store):
    original = {"summary": "small"}
    assert delivery.bound_response(original, 8192) is original
    assert not store.directory.exists()


@pytest.mark.parametrize("result_id", ["../private", "a" * 47, "z" * 48])
def test_result_references_cannot_escape_the_private_directory(store, result_id):
    with pytest.raises(ParameterError):
        store.get(result_id)


def test_expired_result_is_reported_and_never_recalculated(store, monkeypatch):
    ref = store.put(large_payload())
    monkeypatch.setattr(delivery.time, "time", lambda: ref["expires_at"] + 1)
    with pytest.raises(ParameterError, match="过期"):
        store.page(ref["result_id"])
    assert not Path(ref["file_path"]).exists()


def test_pages_reject_missing_paths_and_invalid_offsets(store):
    ref = store.put(large_payload())
    for kwargs in [{"offset": -1}, {"offset": 10**9}, {"path": "time_lords.missing"}]:
        with pytest.raises(ParameterError):
            store.page(ref["result_id"], **kwargs)


def _cli_args(payload):
    args = ["western_timing_analysis"]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    return args + [
        "--no-include-snapshot-text",
        "--compact",
        "--response-char-limit",
        "8192",
    ]


def test_real_western_exact_time_and_delivery_match_all_transports(
    store, capsys, monkeypatch
):
    spec = next(s for s in CATALOG if s.key == "western_timing_analysis")
    payload = example_input(spec)
    payload.update(analysis_hour=12, analysis_minute=7)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app)
    response = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "response_char_limit": 8192,
            "include_snapshot_text": "false",
            "as_of": "2026-10-14T12:07:00+08:00",
        },
    )
    assert response.status_code == 200

    async def native():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "include_snapshot_text": False,
                    "as_of": "2026-10-14T12:07:00+08:00",
                },
            )
            assert not result.is_error
            assert json.loads(result.content[0].text) == result.structured_content
            ref = result.structured_content["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert (
                manifest["run_metadata"]["run_id"]
                == result.structured_content["run_metadata"]["run_id"]
            )
            uri = f"fatebridge://results/{ref['result_id']}/fields/analysis_context.analysis_datetime/0"
            page = json.loads((await client.read_resource(uri))[0].text)
            assert json.loads(page["text"]) == "2026-10-14T12:07:00+08:00"
            return result.structured_content

    protocol = asyncio.run(native())
    capsys.readouterr()
    assert run(_cli_args(payload) + ["--as-of", "2026-10-14T12:07:00+08:00"]) == 0
    cli = json.loads(capsys.readouterr().out)
    full = []
    for shaped in [response.json(), protocol, cli]:
        ref = shaped["result_delivery"]
        original = reconstruct(store, ref["result_id"])
        assert (
            original["analysis_context"]["analysis_datetime"]
            == "2026-10-14T12:07:00+08:00"
        )
        assert (
            original["transits"]["current_transit"]["analysis_datetime"]
            == "2026-10-14T12:07:00+08:00"
        )
        assert (
            original["analysis_context"]["birth_datetime"]
            == "1990-05-15T10:30:00+09:00"
        )
        assert original["run_metadata"] == shaped["run_metadata"]
        full.append({k: v for k, v in original.items() if k != "run_metadata"})
        page = rest.get(
            f"/api/results/{ref['result_id']}/pages",
            params={"path": "analysis_context.analysis_datetime"},
        ).json()
        assert json.loads(page["text"]) == "2026-10-14T12:07:00+08:00"
    assert full[0] == full[1] == full[2]


def test_recommended_western_first_view_fits_default_budget(store):
    spec = next(s for s in CATALOG if s.key == "western_timing_analysis")

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **example_input(spec),
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )

    result = asyncio.run(invoke())
    assert not result.is_error
    assert "result_delivery" not in result.structured_content
    assert (
        result.structured_content["transits"]["current_transit"]["analysis_datetime"]
        == "2026-10-14T12:00:00+08:00"
    )
    assert len(result.content[0].text) <= delivery.DEFAULT_MCP_RESPONSE_CHARS


def test_result_reader_respects_mcp_tool_profiles(store):
    ref = store.put(large_payload())

    async def read_hidden():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            with pytest.raises(Exception, match="未在当前 MCP 配置中公开"):
                await client.read_resource(ref["manifest_uri"])

    asyncio.run(read_hidden())


def test_rest_result_readers_require_api_key_and_report_bad_references(
    store, monkeypatch
):
    ref = store.put(large_payload())
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(
            header_name="X-API-Key", api_keys={"test": "test-secret"}
        ),
    )
    client = TestClient(api.app)
    base = f"/api/results/{ref['result_id']}"
    for path in [base, base + "/pages"]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-API-Key": "test-secret"}).status_code == 200
    assert (
        client.get(
            "/api/results/invalid", headers={"X-API-Key": "test-secret"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            base + "/pages",
            params={"path": "missing"},
            headers={"X-API-Key": "test-secret"},
        ).status_code
        == 404
    )
