"""Large responses stay bounded while the original run remains fully readable."""

import asyncio
import copy
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from httpx2 import Response

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli import run
from fatebridge.services import western_events
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.private_files import ensure_private_directory, open_private_file
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt
from tests.support.result_delivery import reconstruct, store
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    cached_mcp_app,
    call_calculation,
    rest,
    surface_calls,
)

__all__ = ["rest", "store", "surface_calls"]


class SurfaceResponse(NamedTuple):
    rest: Response
    mcp: CallToolResult
    cli_exit_code: int
    cli: ServiceResult


class SurfaceCalls(Protocol):
    def __call__(
        self, spec: ToolSpec, payload: ServiceResult, *, projection: ServiceResult
    ) -> SurfaceResponse: ...


def large_payload() -> ServiceResult:
    return {
        "summary": "年度主题不是精确行运判断",
        "analysis_context": {"analysis_datetime": "2026-10-14T12:07:00+08:00"},
        "time_lords": {
            "timeline": [{"id": n, "text": '中文"换行\n' * 30} for n in range(100)]
        },
        "run_metadata": {"run_id": "original", "tool_name": "western_timing_analysis"},
    }


@pytest.mark.parametrize("compact", [False, True])
def test_bounded_delivery_preserves_all_values_and_original_receipt(
    store: delivery.ResultStore, compact: bool
) -> None:
    original = large_payload()
    shaped = delivery.bound_response(original, 8192, compact=compact)
    assert len(format_json_response(shaped, compact=compact)) <= 8192
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
    assert delivery.bound_response(original, 0) == original


def test_cli_overflow_preserves_audit_result_without_metadata(
    store: delivery.ResultStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = SPECS["bazi_birth"]
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(example_input(spec)), encoding="utf-8")
    argv = [
        "--no-metadata",
        spec.tool_name,
        "--subject-file",
        str(subject),
        "--detail",
        "audit",
        "--as-of",
        AS_OF,
    ]
    assert run(argv) == 0
    complete = json.loads(capsys.readouterr().out)
    assert run([*argv, "--response-char-limit", "4096"]) == 0
    inline = json.loads(capsys.readouterr().out)
    assert "run_metadata" not in inline and "run_metadata" not in complete
    reference = inline["result_delivery"]
    result_id = reference["result_id"]
    assert reconstruct(store, result_id) == complete
    read_args = ["result-read", result_id, "--directory", str(store.directory)]
    assert run([*read_args, "--path", "bazi_birth.four_pillars"]) == 0
    page = json.loads(capsys.readouterr().out)
    assert json.loads(page["text"]) == complete["bazi_birth"]["four_pillars"]
    assert "verification" not in page

    file_path = Path(reference["file_path"])
    record = json.loads(file_path.read_text(encoding="utf-8"))
    record["payload"]["bazi_birth"]["four_pillars"] = {}
    file_path.write_text(json.dumps(record), encoding="utf-8")
    assert run(read_args) == 1
    assert json.loads(capsys.readouterr().out)["issues"] == [
        {"path": "result_id", "code": "result_digest_mismatch"}
    ]


def test_small_payload_is_not_rewritten_or_stored(store: delivery.ResultStore) -> None:
    original = {"summary": "small"}
    assert delivery.bound_response(original, 8192) == original
    assert not store.directory.exists()


@pytest.mark.parametrize("compact", [False, True])
def test_response_delivery_stores_only_the_exact_requested_facts(
    store: delivery.ResultStore, compact: bool
) -> None:
    original = {
        "selected": {"kept": '中文"换行\n' * 3000, "omitted": "not selected"},
        "unselected": "not selected",
        "snapshot_text": "not requested",
        "run_metadata": {"run_id": "selected-run", "tool_name": "gua_lookup"},
    }
    before = copy.deepcopy(original)
    result = deliver_response(
        original,
        fields=["selected.kept", "snapshot_text"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=4096,
        compact=compact,
    )
    text = json.dumps(
        result,
        ensure_ascii=False,
        **({"separators": (",", ":")} if compact else {"indent": 2}),
    )
    assert len(text) <= 4096
    assert result["run_metadata"] == before["run_metadata"]
    reference = result["result_delivery"]
    assert reference["deferred_fields"] == ["selected"]
    assert reconstruct(store, reference["result_id"]) == {
        "selected": {"kept": before["selected"]["kept"]},
        "run_metadata": before["run_metadata"],
    }
    assert original == before


def test_response_delivery_keeps_errors_out_of_projection_and_storage(
    store: delivery.ResultStore,
) -> None:
    original = {
        "error": "unavailable" * 1000,
        "error_code": "source_unavailable",
        "retryable": False,
        "issues": [{"path": "source", "code": "missing"}],
        "trace_id": "request-trace",
    }
    result = deliver_response(
        original,
        fields=["missing"],
        strict_fields=True,
        response_char_limit=4096,
        failed=True,
    )
    assert result == original
    assert not store.directory.exists()


def test_invalid_strict_projection_does_not_publish_a_result(
    store: delivery.ResultStore,
) -> None:
    original = large_payload()
    before = copy.deepcopy(original)
    with pytest.raises(ParameterError) as caught:
        deliver_response(
            original,
            fields=["time_lords.missing"],
            strict_fields=True,
            response_char_limit=4096,
        )
    assert caught.value.issues == [
        {"path": "time_lords.missing", "code": "unknown_projection_path"}
    ]
    assert not store.directory.exists()
    assert original == before


@pytest.mark.parametrize("compact", [False, True])
def test_current_cards_keep_facts_and_restore_every_deferred_child(
    store: delivery.ResultStore, compact: bool
) -> None:
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
    assert len(format_json_response(result, compact=compact)) <= 4096
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


def test_supplementary_receipt_details_do_not_displace_complete_business(
    store: delivery.ResultStore,
) -> None:
    original = {
        "analysis": {"facts": "甲" * 5800},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "taiyi",
            "runtime": {
                "ephemeris": {"files": ["data.se1"]},
                "details": "runtime" * 100,
            },
            "provenance": {"source": ["source" * 150]},
            "determinism": {"scope": "same implementation" * 100},
        },
    }
    before = copy.deepcopy(original)
    result = delivery.bound_response(original, 8192)
    assert len(format_json_response(result)) <= 8192
    assert result["analysis"] == original["analysis"]
    ref = result["result_delivery"]
    assert ref["deferred_fields"] == [
        "run_metadata.runtime",
        "run_metadata.provenance",
        "run_metadata.determinism",
    ]
    assert result["run_metadata"]["runtime"]["ephemeris_files_count"] == 1
    restored = copy.deepcopy(result["run_metadata"])
    for path in ref["deferred_fields"]:
        key = path.removeprefix("run_metadata.")
        restored[key] = reconstruct(store, ref["result_id"], path)
    assert restored == before["run_metadata"]
    assert reconstruct(store, ref["result_id"]) == before == original


def test_receipt_fields_stay_inline_when_the_full_reference_fits(
    store: delivery.ResultStore,
) -> None:
    files = [f"reference-{i}-{'source_' * 12}.se1" for i in range(120)]

    original = {
        "analysis": {"facts": ["actual calculation"]},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "ziwei_birth",
            "provenance": {"source": "keep this exact source"},
            "determinism": {"scope": "keep this exact scope"},
            "runtime": {
                "ephemeris": {"files": files},
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


def test_duplicate_locators_do_not_displace_complete_business_facts(
    store: delivery.ResultStore,
) -> None:
    files = [f"reference-{i}-{'source_' * 12}.se1" for i in range(120)]

    original = {
        "analysis_context": {"clock": "one run"},
        "ziwei_birth": {"all_facts": ""},
        "run_metadata": {
            "run_id": "same-run",
            "tool_name": "ziwei_birth",
            "provenance": {"record": "p" * 500},
            "runtime": {
                "ephemeris": {"files": files},
            },
        },
    }
    # Construct a portable boundary fixture from actual locator overhead.
    # This sizes synthetic text only; real chart fields are never reduced.
    prototype = delivery.bound_response(original, 8192)
    assert prototype["result_delivery"]["deferred_fields"] == ["run_metadata.runtime"]
    original["ziwei_birth"]["all_facts"] = "中" * (
        8192 + 50 - len(format_json_response(prototype))
    )
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, 8192)
    ref = shaped["result_delivery"]
    assert ref["compact_reference"] is True
    assert ref["deferred_fields"] == ["run_metadata.runtime"]
    assert len(format_json_response(shaped)) <= 8192
    assert shaped["ziwei_birth"] == original["ziwei_birth"]
    assert shaped["analysis_context"] == original["analysis_context"]
    manifest = store.manifest(ref["result_id"])
    assert manifest["total_chars"] == ref["total_chars"]
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
        len(
            format_json_response({**shaped, "result_delivery": restored_full_reference})
        )
        > 8192
    )
    full = reconstruct(store, ref["result_id"])
    assert full == before == original
    assert_same_run_receipt(shaped["run_metadata"], full["run_metadata"])
    record = json.loads(Path(manifest["file_path"]).read_text())
    assert record[manifest["file_payload_path"]] == original


@pytest.mark.parametrize("limit", [4096, 8192])
def test_manifest_locator_preserves_sources_before_deferring_receipt_facts(
    store: delivery.ResultStore, limit: int
) -> None:
    original = {
        "analysis": {"facts": ""},
        "run_metadata": {
            "run_id": "same-run",
            "provenance": {"source": "source" * 120},
            "determinism": {"scope": "same exact implementation"},
            "runtime": {
                "ephemeris": {
                    "files": [
                        f"reference-{i}-{'source_' * 12}.se1" for i in range(100)
                    ],
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
    original["analysis"]["facts"] = "中" * (
        limit - len(format_json_response(minimal)) - 12
    )
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, limit)
    ref = shaped["result_delivery"]
    assert len(format_json_response(shaped)) <= limit
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
    assert manifest["total_chars"] == ref["total_chars"]
    assert Path(manifest["file_path"]).exists()
    assert (
        json.loads(Path(manifest["file_path"]).read_text())[
            manifest["file_payload_path"]
        ]
        == before
    )
    assert reconstruct(store, ref["result_id"]) == before == original


@pytest.mark.parametrize("result_id", ["../private", "a" * 47, "z" * 48])
def test_result_references_cannot_escape_the_private_directory(
    store: delivery.ResultStore, result_id: str
) -> None:
    with pytest.raises(ParameterError):
        store.get(result_id)


def test_expired_result_is_reported_and_never_recalculated(
    store: delivery.ResultStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = store.put(large_payload())
    monkeypatch.setattr(delivery.time, "time", lambda: ref["expires_at"] + 1)
    with pytest.raises(ParameterError, match="过期"):
        store.page(ref["result_id"])
    assert Path(ref["file_path"]).exists()
    store.put({"summary": "new result"})
    assert not Path(ref["file_path"]).exists()


def test_pages_reject_missing_paths_and_invalid_offsets(
    store: delivery.ResultStore,
) -> None:
    ref = store.put(large_payload())
    for kwargs in [{"offset": -1}, {"offset": 10**9}, {"path": "time_lords.missing"}]:
        with pytest.raises(ParameterError):
            store.page(ref["result_id"], **kwargs)


def _cli_args(payload: ServiceResult) -> list[str]:
    args = ["western_timing"]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    return args + [
        "--no-include-snapshot-text",
        "--compact",
        "--response-char-limit",
        "8192",
    ]


def test_real_western_exact_time_and_delivery_match_all_transports(
    store: delivery.ResultStore,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    async def native() -> ServiceResult:
        async with Client(cached_mcp_app()) as client:
            result = await call_calculation(
                client,
                spec.tool_name,
                {
                    **payload,
                    "include_snapshot_text": False,
                    "as_of": "2026-10-14T12:07:00+08:00",
                },
            )
            assert not result.is_error
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
            inline_metadata["runtime"] = restored
        else:
            pass
        evidence = inline_metadata.get("calculation_evidence")
        if evidence and "delivery_path" in evidence:
            restored = reconstruct(store, ref["result_id"], evidence["delivery_path"])
            inline_metadata["calculation_evidence"] = restored
        else:
            pass
        assert original["run_metadata"] == inline_metadata
        full.append({k: v for k, v in original.items() if k != "run_metadata"})
        page = rest.get(
            f"/api/results/{ref['result_id']}/pages",
            params={"path": "analysis_context.analysis_datetime"},
        ).json()
        assert json.loads(page["text"]) == "2026-10-14T12:07:00+08:00"
    assert full[0] == full[1] == full[2]


def test_recommended_western_first_view_fits_default_budget(
    store: delivery.ResultStore,
) -> None:
    spec = next(s for s in CATALOG if s.key == "western_timing_analysis")

    async def invoke() -> CallToolResult:
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client,
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
        assert set(result.structured_content["result_delivery"]["deferred_fields"]) <= {
            "run_metadata.runtime"
        }
    else:
        pass
    assert (
        result.structured_content["transits"]["current_transit"]["analysis_datetime"]
        == "2026-10-14T12:00:00+08:00"
    )
    assert (
        len(format_json_response(result.structured_content))
        <= delivery.DEFAULT_MCP_RESPONSE_CHARS
    )


def test_compact_sukuyo_uses_the_same_inline_chart_across_transports(
    store: delivery.ResultStore, surface_calls: SurfaceCalls
) -> None:
    spec = next(spec for spec in CATALOG if spec.key == "suzhan")
    arguments = example_input(spec)
    budget = delivery.DEFAULT_MCP_RESPONSE_CHARS
    response, protocol, code, cli = surface_calls(
        spec, arguments, projection={"detail": "compact", "response_char_limit": budget}
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    http = response.json()
    mcp = protocol.structured_content
    assert len(format_json_response(protocol.structured_content)) <= budget
    assert business(http) == business(cli) == business(mcp)
    assert http["sukuyo"] and http["validation"]
    assert "result_delivery" not in http
    assert not store.directory.exists()


@pytest.mark.parametrize("key", ["astro_mundane", "astro_extrareturns"])
@pytest.mark.parametrize("include_snapshot", [False, True])
def test_western_event_compact_snapshots_render_only_on_request(
    key: str,
    include_snapshot: bool,
    surface_calls: SurfaceCalls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered = []
    render = western_events._render_snapshot_text

    def record_snapshot(sections: Sequence[tuple[str, str]]) -> str:
        snapshot = render(sections)
        rendered.append(snapshot)
        return snapshot

    monkeypatch.setattr(western_events, "_render_snapshot_text", record_snapshot)
    spec = next(spec for spec in CATALOG if spec.key == key)
    projection = {"detail": "compact", "response_char_limit": 0}
    if include_snapshot:
        projection["include_snapshot_text"] = True
    else:
        pass
    http, mcp, code, cli = surface_calls(
        spec, example_input(spec), projection=projection
    )
    assert http.status_code == 200 and not mcp.is_error and code == 0
    payloads = [http.json(), mcp.structured_content, cli]
    assert business(payloads[0]) == business(payloads[1]) == business(payloads[2])
    if include_snapshot:
        assert rendered == [payload["snapshot_text"] for payload in payloads]
    else:
        assert not rendered
        assert all("snapshot_text" not in payload for payload in payloads)


def test_export_unicode_is_readable_from_each_original_run(
    store: delivery.ResultStore,
    surface_calls: SurfaceCalls,
    rest: TestClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blocks = ["[公开]\n" + "中文 ☊ 😀 é\n" * 600, "【空段】", "[公开]\n第二段"]
    blocks = [block.strip() for block in blocks]
    content = "\n\n".join(blocks)
    response, protocol, code, cli = surface_calls(
        SPECS["export_parse"],
        {
            "technique": "generic",
            "content": content,
            "selected_sections": ["公开", "空段"],
        },
        projection={
            "detail": "audit",
            "fields": ["export_text", "sections"],
            "strict_fields": True,
            "response_char_limit": 4096,
        },
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    assert len(response.text) <= 4096
    assert len(format_json_response(protocol.structured_content)) <= 4096
    assert len(format_json_response(cli, compact=False)) <= 4096
    outputs = [response.json(), protocol.structured_content, cli]
    for output in outputs:
        result_id = output["result_delivery"]["result_id"]
        run_id = output["run_metadata"]["run_id"]
        assert reconstruct(store, result_id, "export_text") == content
        sections = reconstruct(store, result_id, "sections")
        assert [section["content"] for section in sections] == blocks
        verified = rest.get(
            f"/api/results/{result_id}/verified",
            params={"expected_run_id": run_id, "path": "export_text"},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["verification"]["run_id"] == run_id
        assert verified.json()["verification"]["calculation_repeated"] is False
        assert (
            run(
                [
                    "result-read",
                    result_id,
                    "--directory",
                    str(store.directory),
                    "--run-id",
                    run_id,
                    "--path",
                    "export_text",
                ]
            )
            == 0
        )
        assert json.loads(capsys.readouterr().out) == verified.json()

    async def read_mcp_pages() -> None:
        async with Client(cached_mcp_app(families="export")) as client:
            for output in outputs:
                result_id = output["result_delivery"]["result_id"]
                run_id = output["run_metadata"]["run_id"]
                resource = f"fatebridge://results/{result_id}/verified/{run_id}/fields/export_text"
                fragments = []
                offset = 0
                while offset is not None:
                    page = json.loads(
                        (await client.read_resource(f"{resource}/{offset}"))[0].text
                    )
                    assert page["verification"]["run_id"] == run_id
                    assert page["verification"]["calculation_repeated"] is False
                    assert page["offset"] == offset
                    fragments.append(page["text"])
                    offset = page["next_offset"]
                assert json.loads("".join(fragments)) == content

    asyncio.run(read_mcp_pages())


def test_result_reader_respects_mcp_tool_profiles(store: delivery.ResultStore) -> None:
    ref = store.put(large_payload())

    async def read_hidden() -> None:
        async with Client(cached_mcp_app(families="fengshui")) as client:
            with pytest.raises(Exception, match="未在当前 MCP 配置中公开"):
                await client.read_resource(ref["manifest_uri"])

    asyncio.run(read_hidden())


def test_rest_result_readers_require_api_key_and_report_bad_references(
    store: delivery.ResultStore, monkeypatch: pytest.MonkeyPatch
) -> None:
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
