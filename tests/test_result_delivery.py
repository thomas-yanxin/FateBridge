"""Large responses stay bounded while the original run remains fully readable."""

import asyncio
import copy
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
from tests.fixtures.mcp_receipt import assert_same_run_receipt


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


@pytest.mark.parametrize("compact", [False, True])
def test_current_cards_keep_facts_and_restore_every_deferred_child(store, compact):
    original = {
        key: {
            "first_view": {
                "status": "partial" if key == "left" else "current",
                "current": {"stem": "甲", "start_at": "2026-01-01T00:00:00+08:00"},
                "source_details": key * 12000,
                "end_at": "2036-01-01T00:00:00+08:00",
            }
        }
        for key in ("left", "right")
    }
    original["run_metadata"] = {"run_id": "same-run", "tool_name": "timing_analysis"}
    before = copy.deepcopy(original)
    result = delivery.bound_response(original, 4096, compact=compact)
    assert len(delivery._json(result, compact)) <= 4096
    ref = result["result_delivery"]
    assert set(ref["deferred_fields"]) == {
        "left.first_view.source_details",
        "right.first_view.source_details",
    }
    assert len(ref["deferred_fields"]) == 2
    restored = copy.deepcopy(result)
    restored.pop("result_delivery")
    for key in ("left", "right"):
        for name in ("status", "current", "end_at"):
            assert result[key]["first_view"][name] == before[key]["first_view"][name]
    for path in ref["deferred_fields"]:
        root, view, child = path.split(".")
        restored[root][view][child] = reconstruct(store, ref["result_id"], path)
    assert restored == reconstruct(store, ref["result_id"]) == before == original


def test_supplementary_receipt_details_do_not_displace_complete_business(store):
    original = {
        "analysis": {"facts": "甲" * 5800},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "taiyi",
            "business_output_sha256": "b" * 64,
            "input_sha256": "c" * 64,
            "contract_sha256": "d" * 64,
            "runtime": {
                "environment_sha256": "e" * 64,
                "ephemeris": {"files": {"data.se1": "a" * 64}, "sha256": "f" * 64},
                "details": "runtime" * 100,
            },
            "provenance": {"source": ["source" * 150]},
            "determinism": {"scope": "same implementation" * 100},
        },
    }
    before = copy.deepcopy(original)
    result = delivery.bound_response(original, 8192)
    assert len(delivery._json(result)) <= 8192
    assert result["analysis"] == original["analysis"]
    ref = result["result_delivery"]
    assert ref["deferred_fields"] == [
        "run_metadata.runtime",
        "run_metadata.provenance",
        "run_metadata.determinism",
    ]
    assert result["run_metadata"]["business_output_sha256"] == "b" * 64
    assert result["run_metadata"]["runtime"]["ephemeris_files_count"] == 1
    restored = copy.deepcopy(result["run_metadata"])
    for path in ref["deferred_fields"]:
        key = path.removeprefix("run_metadata.")
        restored[key] = reconstruct(store, ref["result_id"], path)
    assert restored == before["run_metadata"]
    assert reconstruct(store, ref["result_id"]) == before == original


def test_receipt_fields_stay_inline_when_the_full_reference_fits(store):
    files = {f"reference-{i}.se1": "a" * 64 for i in range(120)}
    inventory_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    original = {
        "analysis": {"facts": ["actual calculation"]},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "ziwei_birth",
            "provenance": {"source": "keep this exact source"},
            "determinism": {"scope": "keep this exact scope"},
            "runtime": {
                "environment_sha256": "b" * 64,
                "ephemeris": {"files": files, "sha256": inventory_hash},
            },
        },
    }
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, 8192)
    assert shaped["result_delivery"]["deferred_fields"] == ["run_metadata.runtime"]
    assert not shaped["result_delivery"].get("compact_reference")
    assert shaped["analysis"] == original["analysis"]
    assert shaped["run_metadata"]["provenance"] == before["run_metadata"]["provenance"]
    assert (
        shaped["run_metadata"]["determinism"] == before["run_metadata"]["determinism"]
    )
    assert reconstruct(store, shaped["result_delivery"]["result_id"]) == before
    assert original == before


def test_duplicate_locators_do_not_displace_complete_business_facts(store):
    files = {f"reference-{i}.se1": "a" * 64 for i in range(120)}
    digest = hashlib.sha256(
        json.dumps(
            files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    original = {
        "analysis_context": {"clock": "one run"},
        "ziwei_birth": {"all_facts": ""},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "ziwei_birth",
            "provenance": {"record": "p" * 500},
            "runtime": {
                "environment_sha256": "b" * 64,
                "ephemeris": {"files": files, "sha256": digest},
            },
        },
    }
    # Construct a portable boundary fixture from actual locator overhead.
    # This sizes synthetic text only; real chart fields are never reduced.
    prototype = delivery.bound_response(original, 8192)
    assert prototype["result_delivery"]["deferred_fields"] == ["run_metadata.runtime"]
    original["ziwei_birth"]["all_facts"] = "中" * (
        8192 + 50 - len(delivery._json(prototype))
    )
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, 8192)
    ref = shaped["result_delivery"]
    assert ref["compact_reference"] is True
    assert ref["deferred_fields"] == ["run_metadata.runtime"]
    assert len(delivery._json(shaped)) <= 8192
    assert shaped["ziwei_birth"] == original["ziwei_birth"]
    assert shaped["analysis_context"] == original["analysis_context"]
    manifest = store.manifest(ref["result_id"])
    assert manifest["sha256"] == ref["sha256"]
    omitted = ("available_fields", "total_bytes", "page_chars", "rest_manifest_path")
    assert all(k not in ref and k in manifest for k in omitted)
    assert ref["file_path"] == manifest["file_path"]
    assert ref["file_payload_path"] == manifest["file_payload_path"]
    restored_full_reference = {
        **ref,
        **{k: manifest[k] for k in omitted},
    }
    restored_full_reference.pop("compact_reference")
    assert (
        len(delivery._json({**shaped, "result_delivery": restored_full_reference}))
        > 8192
    )
    full = reconstruct(store, ref["result_id"])
    assert full == before == original
    assert_same_run_receipt(shaped["run_metadata"], full["run_metadata"])
    record = json.loads(Path(manifest["file_path"]).read_text())
    assert record[manifest["file_payload_path"]] == original


@pytest.mark.parametrize("limit", [4096, 8192])
def test_manifest_locator_preserves_sources_before_deferring_receipt_facts(
    store, limit
):
    original = {
        "analysis": {"facts": ""},
        "run_metadata": {
            "run_id": "same-run",
            "provenance": {"source": "source" * 120},
            "determinism": {"scope": "same exact implementation"},
            "runtime": {
                "environment_sha256": "e" * 64,
                "ephemeris": {
                    "files": {str(i): "a" * 64 for i in range(100)},
                    "sha256": "f" * 64,
                },
            },
        },
    }
    prototype = delivery.bound_response(original, limit)
    reference = {
        k: v
        for k, v in prototype["result_delivery"].items()
        if k
        not in {
            "available_fields",
            "total_bytes",
            "page_chars",
            "rest_manifest_path",
            "first_page_uri",
            "file_path",
            "file_payload_path",
        }
    }
    reference["compact_reference"] = True
    reference["deferred_fields"] = ["run_metadata.runtime"]
    minimal = {**prototype, "result_delivery": reference}
    # Size only synthetic text from real locator overhead, never alter a real
    # business result or the requested budget to manufacture a passing case.
    original["analysis"]["facts"] = "中" * (limit - len(delivery._json(minimal)) - 12)
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, limit)
    ref = shaped["result_delivery"]
    assert len(delivery._json(shaped)) <= limit
    assert ref["deferred_fields"] == ["run_metadata.runtime"]
    assert "file_path" not in ref and "file_payload_path" not in ref
    assert "first_page_uri" not in ref
    assert ref["manifest_uri"].endswith(ref["result_id"])
    assert shaped["analysis"] == before["analysis"]
    assert shaped["run_metadata"]["provenance"] == before["run_metadata"]["provenance"]
    assert (
        shaped["run_metadata"]["determinism"] == before["run_metadata"]["determinism"]
    )
    manifest = store.manifest(ref["result_id"])
    assert manifest["sha256"] == ref["sha256"]
    assert Path(manifest["file_path"]).exists()
    assert (
        json.loads(Path(manifest["file_path"]).read_text())[
            manifest["file_payload_path"]
        ]
        == before
    )
    assert reconstruct(store, ref["result_id"]) == before == original


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
        inline_metadata = copy.deepcopy(shaped["run_metadata"])
        runtime = inline_metadata["runtime"]
        if "delivery_path" in runtime:
            restored = reconstruct(store, ref["result_id"], runtime["delivery_path"])
            assert (
                len(restored["ephemeris"]["files"]) == runtime["ephemeris_files_count"]
            )
            assert (
                restored["ephemeris"]["sha256"] == runtime["ephemeris_inventory_sha256"]
            )
            inline_metadata["runtime"] = restored
        assert original["run_metadata"] == inline_metadata
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
    if "result_delivery" in result.structured_content:
        assert result.structured_content["result_delivery"]["deferred_fields"] == [
            "run_metadata.runtime"
        ]
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
