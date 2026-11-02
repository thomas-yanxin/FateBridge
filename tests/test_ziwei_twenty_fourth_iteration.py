"""Evaluation capture must preserve the ordinary server's published contracts."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.validation.agent_capture import read_capture


@pytest.mark.parametrize(
    "scenario,scope",
    [("onda-xingpan", "complete"), ("onda-xingpan", "topic"), ("", "complete")],
)
def test_capture_and_ordinary_stdio_publish_identical_contracts(
    tmp_path, scenario, scope
):
    root = Path(__file__).resolve().parents[1]

    async def published(module, log):
        transport = StdioTransport(
            command=sys.executable,
            args=["-X", "utf8", "-m", module],
            cwd=str(root),
            env={
                "PYTHONPATH": str(root / "src"),
                "FATEBRIDGE_MCP_FAMILIES": "",
                "FATEBRIDGE_MCP_SCENARIOS": scenario,
                "FATEBRIDGE_MCP_TOOL_SCOPE": scope,
                "FATEBRIDGE_EVALUATION_LOG": str(log),
            },
            log_file=tmp_path / (module + ".stderr.log"),
        )
        async with Client(transport, init_timeout=30) as client:
            return {
                "tools": {
                    t.name: t.model_dump(mode="json", by_alias=True)
                    for t in await client.list_tools()
                },
                "resources": [
                    r.model_dump(mode="json", by_alias=True)
                    for r in await client.list_resources()
                ],
                "resource_templates": [
                    t.model_dump(mode="json", by_alias=True)
                    for t in await client.list_resource_templates()
                ],
            }

    ordinary_log = tmp_path / "ordinary-should-not-capture.jsonl"
    normal = asyncio.run(published("fatebridge.mcp_server", ordinary_log))
    capture_log = tmp_path / "actual-capture.jsonl"
    captured = asyncio.run(
        published("fatebridge.validation.agent_capture", capture_log)
    )
    assert captured == normal
    assert {"ziwei_birth", "ziwei_horoscope", "ziwei_rules"} <= normal["tools"].keys()
    assert not ordinary_log.exists()
    journal = read_capture(capture_log)
    assert len(journal) == 1
    assert journal[0]["event"] == "tool_list"
    assert set(journal[0]["tool_names"]) == normal["tools"].keys()
    assert not any(r["event"] == "tool_call" for r in journal)


def test_capture_without_opt_in_fails_before_business_configuration(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "PYTHONPATH": str(root / "src"),
        "FATEBRIDGE_EVALUATION_LOG": "",
        "FATEBRIDGE_MCP_TOOL_SCOPE": "invalid-capture-must-not-build-this-app",
    }
    result = subprocess.run(
        [sys.executable, "-m", "fatebridge.validation.agent_capture"],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Evaluation capture requires an explicit new log path" in result.stderr
    assert "invalid_tool_scope" not in result.stderr
    assert not result.stdout


def test_targeted_rereading_does_not_resolve_a_conflict_by_matching_the_chart():
    from fatebridge.core.ziwei_sources import ziwei_day_source_evidence

    for branch in "寅未子":
        evidence = ziwei_day_source_evidence(
            bureau=6, lunar_day=8, actual_branch=branch
        )
        assert evidence["independent_review"]["method_id"].endswith("r22_corrected_v1")
        assert evidence["independent_review"]["direct_label_branches"] == ["未"]
        later = evidence["targeted_rereading"]
        assert later["direct_label_branches"] == ["寅", "未"]
        assert later["status"] == "conflicting_direct_labels"
        assert later["matches_unique_direct_branch"] is None
        assert later["unique_source_confirmation_supported"] is False
        assert later["reviewed_input_count"] == 5
        assert later["new_witness_count"] == 0
        assert later["whole_day_table_certified"] is False


def test_five_targeted_readings_keep_all_unknowns_and_original_transcription():
    import hashlib

    from fatebridge.core.ziwei_sources import ziwei_day_source_evidence
    from scripts.build_ziwei_targeted_rereading import ROOT, TARGET, build

    package = build()
    assert json.loads(TARGET.read_text()) == package
    assert {(r["bureau"], r["day"]) for r in package["records"]} == {
        (2, 21),
        (3, 11),
        (3, 12),
        (6, 6),
        (6, 8),
    }
    for row in package["records"]:
        variants = [
            ziwei_day_source_evidence(
                bureau=row["bureau"], lunar_day=row["day"], actual_branch=b
            )["targeted_rereading"]
            for b in "子丑寅卯辰巳午未申酉戌亥"
        ]
        assert all(v == variants[0] for v in variants)
        assert all(v["unique_source_confirmation_supported"] is False for v in variants)
        assert all(v["matches_unique_direct_branch"] is None for v in variants)
    assert (
        hashlib.sha256(
            (
                ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-days.json"
            ).read_bytes()
        ).hexdigest()
        == "4f19e3426fd3fcb03e2be94fdf8ad8121de0449f27d4d93cd9f38d308bc0634a"
    )


def test_targeted_generator_refuses_an_edited_frozen_first_reading(
    tmp_path, monkeypatch
):
    import shutil

    import scripts.build_ziwei_targeted_rereading as builder

    shutil.copytree(builder.FROZEN, tmp_path / "frozen")
    changed = tmp_path / "frozen/original-first-reading-frozen.json"
    changed.write_text(changed.read_text().replace("初八", "初六"))
    monkeypatch.setattr(builder, "FROZEN", changed.parent)
    with pytest.raises(ValueError, match="checksum mismatch"):
        builder.build()


@pytest.mark.parametrize("day", [7, 9])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_actual_birth_three_transports_keep_the_new_textual_conflict(
    day, profile, capsys, monkeypatch
):
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from fatebridge.application.result_delivery import RESULT_STORE
    from fatebridge.cli import run
    from fatebridge.mcp_server import create_mcp_app

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=1984,
        birth_month=2,
        birth_day=day,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        rule_profile=profile,
    )
    flags = dict(
        fields=["ziwei_birth.rule_trace"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
        as_of="2026-10-22T12:00:00+08:00",
    )
    response = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("fields", "ziwei_birth.rule_trace"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "8192"),
            ("as_of", flags["as_of"]),
        ],
    )
    assert response.status_code == 200

    async def native():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool("ziwei_birth", {**inputs, **flags})
            assert not result.is_error
            return result.structured_content

    args = ["ziwei_birth"]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--fields",
        "ziwei_birth.rule_trace",
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "8192",
        "--as-of",
        flags["as_of"],
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli_reply = json.loads(capsys.readouterr().out)
    readings = []
    for reply in [response.json(), asyncio.run(native()), cli_reply]:
        assert len(json.dumps(reply, ensure_ascii=False, separators=(",", ":"))) <= 8192
        if "result_delivery" in reply:
            ref = reply["result_delivery"]
            traces = RESULT_STORE.get(ref["result_id"])["ziwei_birth"]["rule_trace"]
            index = next(
                i
                for i, t in enumerate(traces)
                if t["rule_id"] == "ziwei_tianfu_placement"
            )
            page = RESULT_STORE.verified_page(
                ref["result_id"],
                ref["sha256"],
                reply["run_metadata"]["run_id"],
                path=f"ziwei_birth.rule_trace.{index}.outputs.source_comparison.targeted_rereading",
            )
            assert page["next_offset"] is None
            reading = json.loads(page["text"])
        else:
            reading = next(
                t
                for t in reply["ziwei_birth"]["rule_trace"]
                if t["rule_id"] == "ziwei_tianfu_placement"
            )["outputs"]["source_comparison"]["targeted_rereading"]
        assert reading["matches_unique_direct_branch"] is None
        assert reading["unique_source_confirmation_supported"] is False
        assert reading["direct_label_branches"] == ([] if day == 7 else ["寅", "未"])
        readings.append(reading)
    assert readings[0] == readings[1] == readings[2]


def test_capture_shutdown_restores_an_ordinary_app_and_allows_a_fresh_journal(
    tmp_path, monkeypatch
):
    import fatebridge.mcp_server as server
    import fatebridge.validation.agent_capture as capture

    baseline = list(server.app.middleware)

    async def read_tools():
        async with Client(server.app) as client:
            assert await client.list_tools()

    monkeypatch.setattr(server.app, "run", lambda **kwargs: asyncio.run(read_tools()))
    for index in range(2):
        path = tmp_path / f"run-{index}.jsonl"
        monkeypatch.setenv("FATEBRIDGE_EVALUATION_LOG", str(path))
        capture.main()
        assert server.app.middleware == baseline
        assert len(read_capture(path)) == 1
        # Ordinary access after capture must not write to a closed journal.
        asyncio.run(read_tools())
        assert len(read_capture(path)) == 1


def test_targeted_audit_rejects_false_confirmation_even_when_the_position_matches(
    monkeypatch,
):
    import scripts.audit_ziwei_targeted_rereading as audit

    original = audit.ziwei_day_source_evidence

    def false_confirmation(**kwargs):
        result = original(**kwargs)
        result["targeted_rereading"]["unique_source_confirmation_supported"] = True
        return result

    monkeypatch.setattr(audit, "ziwei_day_source_evidence", false_confirmation)
    report = audit.audit_targeted_rereading()
    assert report["targeted_inputs"] == 5
    assert report["conditional_receipts_checked"] == 60
    assert len(report["mismatches"]) == 60
