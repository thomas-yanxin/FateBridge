"""Evidence substitution controls; synthetic cases never grade model fidelity."""

import ast
import asyncio
import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.agent_capture import CaptureJournal
from fatebridge.validation.meihua_semantic_binding import (
    PROMPT_BUILDER_AST_SHA256,
    audit_observed_inputs,
    audit_preparation,
    bind_answer_fields,
    file_sha,
    lookup,
    observed_sources,
    portable_ast_sha,
    preparation_commitment,
)
from scripts.evaluate_agent import grade, model_prompt, source_manifest
from tests.test_agent_evaluation import event

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def journal(path, rows):
    stream = CaptureJournal(path)

    async def append():
        for row in rows:
            await stream.append(row)

    try:
        asyncio.run(append())
    finally:
        stream.close()


def packet(run="actual-run", **business):
    return {
        **business,
        "run_metadata": {"run_id": run, "business_output_sha256": digest(business)},
    }


def call(value, arguments=None):
    return {
        "event": "tool_call",
        "outcome": "returned",
        "tool": "meihua_cast",
        "arguments": arguments or {},
        "result": {"structured_content": value, "is_error": False},
    }


@pytest.fixture
def prepared(tmp_path):
    """Two identical inputs with distinct runs must bind separately, plus no-call."""
    source = tmp_path / "source/scripts/evaluate_agent.py"
    source.parent.mkdir(parents=True)
    source.write_text(inspect.getsource(model_prompt))
    write(
        tmp_path / "source-manifest.json",
        {"scripts/evaluate_agent.py": file_sha(source)},
    )
    cases, references, worksheet, rows = [], [], [], []
    arguments = {
        "casting": {"method": "object_count", "count": 1, "hour_branch": "酉"},
        "fields": None,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    for i in range(3):
        case = {
            "id": f"case_{i}",
            "prompt": "虚构测试",
            "allowed_tools": [],
            "manual_review": ["必须人工核对原句"],
        }
        ref = {"case": case["id"]}
        if i < 2:
            case["allowed_tools"] = ["meihua_cast"]
            case["reference_request"] = {
                "tool": "meihua_cast",
                "arguments": {"casting": arguments["casting"]},
            }
            case["reference_assertions"] = [{"path": "value", "value": False}]
            value = packet(f"reference-{i}", value=False)
            rows.append(call(value, arguments))
            name = f"reference-payloads/{i}.json"
            write(
                tmp_path / name,
                {
                    "tool": "meihua_cast",
                    "arguments": arguments,
                    "structured_content": value,
                    "is_error": False,
                },
            )
            ref.update(
                reference_status="captured_real_mcp",
                run_id=f"reference-{i}",
                payload_file=name,
                payload_sha256=file_sha(tmp_path / name),
            )
        else:
            case["no_calculation"] = True
            ref["reference_status"] = "no_calculation_required"
        cases.append(case)
        references.append(ref)
        worksheet.append(
            {
                "case": case["id"],
                "model_status": "not_run",
                "semantic_status": "pending",
                "checks": [
                    {
                        "criterion": case["manual_review"][0],
                        "status": "pending",
                        "answer_quote": None,
                        "actual_model_run_id": None,
                        "evidence_paths": [],
                        "reviewer": None,
                    }
                ],
            }
        )
        p = tmp_path / f"model-prompts/{case['id']}.txt"
        p.parent.mkdir(exist_ok=True)
        p.write_text(model_prompt(case))
    write(tmp_path / "case-dataset.json", {"cases": cases})
    write(
        tmp_path / "review-worksheet.json", {"model_invocations": 0, "cases": worksheet}
    )
    write(
        tmp_path / "preparation.json",
        {
            "model_invocations": 0,
            "semantic_acceptance": "not_run",
            "selected_case_count": 3,
            "dataset_sha256": file_sha(tmp_path / "case-dataset.json"),
            "source_manifest_sha256": file_sha(tmp_path / "source-manifest.json"),
            "references": references,
        },
    )
    write(
        tmp_path / "proposed-execution.json",
        {"requires_session_authorization_for_independent_model": True},
    )
    journal(tmp_path / "reference-mcp.jsonl", rows)
    return tmp_path


def audit(path):
    commitment = preparation_commitment(path)
    return audit_preparation(
        path, commitment, expected_commitment_sha256=digest(commitment)
    )


def test_preparation_keeps_pending_criteria_and_disambiguates_identical_inputs(
    prepared,
):
    result = audit(prepared)
    assert result["actual_reference_calls"] == 2
    assert result["criteria_pending"] == 3
    assert result["reference_assertions_verified"] == 2
    assert result["semantic_acceptance"] == "not_run"
    assert result["model_invocations"] == 0
    assert not result["independent_review_performed"]


@pytest.mark.parametrize(
    "name",
    [
        "case-dataset.json",
        "preparation.json",
        "source-manifest.json",
        "review-worksheet.json",
        "reference-mcp.jsonl",
        "model-prompts/case_0.txt",
        "reference-payloads/0.json",
        "proposed-execution.json",
    ],
)
def test_external_commitment_rejects_modified_reference_files(prepared, name):
    commitment = preparation_commitment(prepared)
    p = prepared / name
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Committed preparation file changed"):
        audit_preparation(
            prepared, commitment, expected_commitment_sha256=digest(commitment)
        )


def test_rewriting_local_hashes_does_not_change_the_separately_pinned_receipt(prepared):
    original = preparation_commitment(prepared)
    p = prepared / "proposed-execution.json"
    write(p, {"command": ["different command"]})
    with pytest.raises(ValueError, match="separately pinned"):
        audit_preparation(
            prepared,
            preparation_commitment(prepared),
            expected_commitment_sha256=digest(original),
        )


def test_commitment_cannot_omit_a_required_reference_file(prepared):
    commitment = preparation_commitment(prepared)
    del commitment["files"]["reference-mcp.jsonl"]
    with pytest.raises(ValueError, match="full reference set"):
        audit_preparation(
            prepared, commitment, expected_commitment_sha256=digest(commitment)
        )


def test_cli_preserves_binding_only_scope_and_uses_nonzero_failure_exit(prepared):
    receipt = prepared / "receipt.json"
    commitment = preparation_commitment(prepared)
    write(receipt, {"commitment": commitment})
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_meihua_semantic_binding.py"),
        "preparation",
        str(prepared),
        "--commitment",
        str(receipt),
        "--expected-commitment-sha256",
        digest(commitment),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["semantic_acceptance"] == "not_run"
    result = subprocess.run(command[:-1] + ["0" * 64], capture_output=True, text=True)
    assert result.returncode == 2
    assert not json.loads(result.stdout)["binding_passed"]


@pytest.mark.parametrize(
    "target", ["run", "type", "review", "prompt", "source", "business"]
)
def test_self_report_resealing_cannot_hide_cross_bindings(prepared, target):
    if target == "run":
        p = prepared / "preparation.json"
        v = json.loads(p.read_text())
        v["references"][1]["run_id"] = "reference-0"
        write(p, v)
    elif target == "type":
        p = prepared / "case-dataset.json"
        v = json.loads(p.read_text())
        v["cases"][0]["reference_assertions"][0]["value"] = 0
        write(p, v)
        p = prepared / "preparation.json"
        v = json.loads(p.read_text())
        v["dataset_sha256"] = file_sha(prepared / "case-dataset.json")
        write(p, v)
    elif target == "review":
        p = prepared / "review-worksheet.json"
        v = json.loads(p.read_text())
        v["cases"][0]["checks"][0]["status"] = "pass"
        write(p, v)
    elif target == "prompt":
        (prepared / "model-prompts/case_0.txt").write_text("偷换题目")
    elif target == "source":
        (prepared / "source/scripts/evaluate_agent.py").write_text("changed")
    else:
        p = prepared / "reference-payloads/0.json"
        v = json.loads(p.read_text())
        v["structured_content"]["value"] = True
        write(p, v)
        p = prepared / "preparation.json"
        v = json.loads(p.read_text())
        v["references"][0]["payload_sha256"] = file_sha(
            prepared / "reference-payloads/0.json"
        )
        write(p, v)
    with pytest.raises((ValueError, KeyError)):
        audit(prepared)


@pytest.fixture
def answer_capture(tmp_path):
    answer = tmp_path / "answer.txt"
    answer.write_text("本次尚未知。")
    capture = tmp_path / "capture.jsonl"
    journal(capture, [call(packet(value=None, flag=False, items=[{"n": 2}]))])
    return answer, capture


def bind(paths, **changes):
    answer, capture = paths
    claim = {
        "start": 0,
        "end": 6,
        "quote": "本次尚未知。",
        "journal_index": 0,
        "run_id": "actual-run",
        "path": "value",
        "value": None,
        **changes,
    }
    return bind_answer_fields(
        answer,
        capture,
        [claim],
        expected_answer_sha256=file_sha(answer),
        expected_capture_sha256=file_sha(capture),
        reference_run_ids=["reference-0"],
    )


def test_literal_binding_never_awards_semantic_or_execution_authenticity(
    answer_capture,
):
    result = bind(answer_capture)
    assert result["literal_claims_bound"] == 1
    assert result["semantic_acceptance"] == "not_assessed"
    assert not result["model_execution_authenticity_independently_verified"]


@pytest.mark.parametrize(
    "changes",
    [
        {"quote": "肯定未知。"},
        {"end": 999},
        {"start": True},
        {"journal_index": True},
        {"run_id": "reference-0"},
        {"run_id": "other-run"},
        {"path": "missing"},
        {"path": "flag", "value": 0},
        {"path": "items.-1.n", "value": 2},
        {"path": "items.00.n", "value": 2},
    ],
)
def test_answer_substitution_null_and_boolean_confusion_are_rejected(
    answer_capture, changes
):
    with pytest.raises(ValueError):
        bind(answer_capture, **changes)


def test_answer_bytes_and_capture_chain_are_pinned(answer_capture):
    answer, capture = answer_capture
    sha = file_sha(answer)
    answer.write_text("改写答案")
    with pytest.raises(ValueError, match="pinned receipt"):
        bind_answer_fields(
            answer,
            capture,
            [],
            expected_answer_sha256=sha,
            expected_capture_sha256=file_sha(capture),
            reference_run_ids=[],
        )
    answer.write_text("本次尚未知。")
    row = json.loads(capture.read_text())
    row["result"]["structured_content"]["value"] = "forged"
    capture.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="bytes changed"):
        bind(answer_capture)


def resource_rows(*, field=False):
    complete = packet(value={"known": None})
    text = json.dumps(complete["value"] if field else complete, ensure_ascii=False)
    sha = hashlib.sha256(text.encode()).hexdigest()
    projected = {
        "run_metadata": complete["run_metadata"],
        "result_delivery": {
            "result_id": "same-result",
            "sha256": sha,
            "total_chars": len(text),
            "total_bytes": len(text.encode()),
            "result_file": "/never/open/this/file",
        },
    }
    rows = [call(projected)]
    for start, end in [(0, 5), (5, len(text))]:
        page = {
            "offset": start,
            "text": text[start:end],
            "next_offset": end if end < len(text) else None,
            "sha256": sha,
        }
        tail = f"fields/value/{start}" if field else f"pages/{start}"
        if field:
            page.update(path="value", result_id="same-result")
        rows.append(
            {
                "event": "resource_read",
                "outcome": "returned",
                "uri": "fatebridge://results/same-result/" + tail,
                "result": {"contents": [{"text": json.dumps(page)}]},
            }
        )
    return rows


@pytest.mark.parametrize("field", [False, True])
def test_completed_actual_pages_only_supply_observed_child_values(tmp_path, field):
    rows = resource_rows(field=field)
    assert "value" not in observed_sources(rows)[0]["packet"]
    assert not observed_sources(rows[:2])[0]["fields"]
    a = tmp_path / "answer.txt"
    a.write_text("本次尚未知。")
    c = tmp_path / "capture.jsonl"
    journal(c, rows)
    assert bind((a, c), path="value.known")["literal_claims_bound"] == 1
    c2 = tmp_path / "incomplete.jsonl"
    journal(c2, rows[:2])
    with pytest.raises(ValueError, match="absent"):
        bind((a, c2), path="value.known")


@pytest.mark.parametrize(
    "mutation", ["offset", "chain", "hash", "run", "length", "uri"]
)
def test_page_substitutions_fail_closed(mutation):
    rows = resource_rows()
    page = json.loads(rows[2]["result"]["contents"][0]["text"])
    if mutation == "offset":
        page["offset"] = 6
    elif mutation == "chain":
        page["next_offset"] = 5
    elif mutation == "hash":
        page["sha256"] = "0" * 64
    elif mutation == "run":
        page["text"] = page["text"].replace("actual-run", "forged-run")
    elif mutation == "length":
        rows[0]["result"]["structured_content"]["result_delivery"]["total_bytes"] += 1
    else:
        rows[2]["uri"] += "x"
    rows[2]["result"]["contents"][0]["text"] = json.dumps(page)
    with pytest.raises(ValueError):
        observed_sources(rows)


def test_cross_result_field_and_conflicting_pages_are_rejected():
    rows = resource_rows(field=True)
    page = json.loads(rows[1]["result"]["contents"][0]["text"])
    page["result_id"] = "other-result"
    rows[1]["result"]["contents"][0]["text"] = json.dumps(page)
    with pytest.raises(ValueError, match="another result"):
        observed_sources(rows)
    rows = resource_rows()
    conflict = copy.deepcopy(rows[-1])
    page = json.loads(conflict["result"]["contents"][0]["text"])
    page["text"] += "x"
    conflict["result"]["contents"][0]["text"] = json.dumps(page)
    with pytest.raises(ValueError, match="Conflicting"):
        observed_sources(rows + [conflict])


def test_protocol_and_fastmcp_resource_serializations_are_both_observed_not_invented():
    protocol = resource_rows(field=True)
    native = copy.deepcopy(protocol)
    for row in native[1:]:
        block = row["result"]["contents"][0]
        block["content"] = block.pop("text")
    assert (
        observed_sources(native)[0]["fields"] == observed_sources(protocol)[0]["fields"]
    )
    native[1]["result"]["contents"][0]["text"] = "substituted"
    with pytest.raises(ValueError, match="contradictory"):
        observed_sources(native)


@pytest.mark.parametrize("field", [False, True])
@pytest.mark.parametrize(
    "mutation", [None, "uri_run", "uri_sha", "run", "sha", "repeated"]
)
def test_verified_resources_bind_original_receipt_and_actual_verification(
    field, mutation
):
    rows = resource_rows(field=field)
    sha = rows[0]["result"]["structured_content"]["result_delivery"]["sha256"]
    for row in rows[1:]:
        tail = row["uri"].split("same-result/", 1)[1]
        tail = tail.removeprefix("pages/")
        row["uri"] = (
            f"fatebridge://results/same-result/verified/actual-run/{sha}/{tail}"
        )
        page = json.loads(row["result"]["contents"][0]["text"])
        page.update(result_id="same-result", path="value" if field else None)
        page["verification"] = {
            "method": "retained_payload_sha256_v1",
            "scope": "entire_retained_payload",
            "payload_sha256": sha,
            "run_id": "actual-run",
            "calculation_repeated": False,
        }
        if mutation == "uri_run":
            row["uri"] = row["uri"].replace("actual-run", "another-run")
        elif mutation == "uri_sha":
            row["uri"] = row["uri"].replace(sha, "0" * 64)
        elif mutation == "run":
            page["verification"]["run_id"] = "another-run"
        elif mutation == "sha":
            page["verification"]["payload_sha256"] = "0" * 64
        elif mutation == "repeated":
            page["verification"]["calculation_repeated"] = 0
        row["result"]["contents"][0]["text"] = json.dumps(page)
    if mutation:
        with pytest.raises(ValueError):
            observed_sources(rows)
    else:
        source = observed_sources(rows)[0]
        assert (
            source["fields"]["value"] == {"known": None}
            if field
            else source["complete"]["value"] == {"known": None}
        )


@pytest.mark.asyncio
async def test_actual_local_stdio_projection_and_field_resources_bind_without_model(
    tmp_path,
):
    capture = tmp_path / "actual.jsonl"
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.validation.agent_capture"],
        cwd=str(ROOT),
        env={
            "PYTHONPATH": str(ROOT / "src"),
            "FATEBRIDGE_EVALUATION_LOG": str(capture),
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "complete",
        },
        log_file=tmp_path / "stderr.log",
    )
    arguments = {
        "casting": {"method": "object_count", "count": 1, "hour_branch": "酉"},
        "fields": ["meihua"],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 4096,
    }
    async with Client(transport) as client:
        reply = await client.call_tool("meihua_cast", arguments, raise_on_error=False)
        assert not reply.is_error
        value = reply.structured_content
        delivery = value["result_delivery"]
        run = value["run_metadata"]["run_id"]
        for route in [
            "fields/meihua.body_trigram/0",
            f"verified/{run}/{delivery['sha256']}/fields/meihua.use_trigram/0",
        ]:
            uri = f"fatebridge://results/{delivery['result_id']}/{route}"
            while uri:
                resource = await client.read_resource(uri)
                page = json.loads(resource[0].text)
                assert page["path"].startswith("meihua.")
                uri = (
                    (uri.rsplit("/", 1)[0] + "/" + str(page["next_offset"]))
                    if page["next_offset"] is not None
                    else None
                )
    from fatebridge.validation.agent_capture import read_capture

    sources = observed_sources(read_capture(capture))
    index, source = next(iter(sources.items()))
    answer = tmp_path / "answer.txt"
    answer.write_text("实际体用。")
    claims = [
        {
            "start": 0,
            "end": 5,
            "quote": "实际体用。",
            "journal_index": index,
            "run_id": run,
            "path": path,
            "value": data,
        }
        for path, data in source["fields"].items()
    ]
    assert len(claims) == 2
    result = bind_answer_fields(
        answer,
        capture,
        claims,
        expected_answer_sha256=file_sha(answer),
        expected_capture_sha256=file_sha(capture),
        reference_run_ids=[],
    )
    assert (
        result["literal_claims_bound"] == 2
        and result["semantic_acceptance"] == "not_assessed"
    )


@pytest.mark.parametrize("error", ["is_error", "isError", "business_error"])
def test_actual_server_errors_cannot_be_hidden_by_successful_cli_events(error):
    legacy = grade({"manual_review": []}, [event("meihua_cast")], "answer", 0)
    assert legacy[
        "mechanical_checks_passed"
    ]  # Preserve the old observable-only grader.
    row = call(packet(value=None))
    if error == "business_error":
        row["result"]["structured_content"]["error_code"] = "BAD_INPUT"
    else:
        row["result"][error] = True
    with pytest.raises(ValueError, match="actual server error"):
        observed_sources([row])


@pytest.mark.parametrize("value", ["favorable_matter", False, 0, "", []])
def test_unknown_scenario_cannot_be_silently_filled(value):
    case = {"argument_absent_or_null": {"meihua_cast": ["matter_scenario"]}}
    with pytest.raises(ValueError, match="Unconfirmed input"):
        audit_observed_inputs(case, [call(packet(), {"matter_scenario": value})])
    assert audit_observed_inputs(case, [call(packet(), {"matter_scenario": None})]) == 1
    assert audit_observed_inputs(case, [call(packet())]) == 1
    with pytest.raises(ValueError, match="no actual call"):
        audit_observed_inputs(case, [])


@pytest.mark.parametrize("profile", ["runtime", "full"])
def test_source_freeze_ignores_only_finder_metadata(tmp_path, profile):
    for name in [
        "AGENTS.md",
        "pyproject.toml",
        "uv.lock",
        "src/a.py",
        "src/data.json",
        "docs/guide.md",
        "skills/a/SKILL.md",
        "docs/.other-hidden",
        "src/.DS_Store",
    ]:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("original")
    before = source_manifest(tmp_path, profile)
    (tmp_path / "src/.DS_Store").write_text("finder changed")
    assert source_manifest(tmp_path, profile) == before
    for name in [
        "src/a.py",
        "src/data.json",
        "docs/guide.md",
        "skills/a/SKILL.md",
        "docs/.other-hidden",
    ]:
        p = tmp_path / name
        p.write_text("changed")
        assert source_manifest(tmp_path, profile) != before
        p.write_text("original")


def test_prompt_ast_commitment_is_portable_and_rejects_executable_changes():
    node = ast.parse(inspect.getsource(model_prompt)).body[0]
    assert portable_ast_sha(node) == PROMPT_BUILDER_AST_SHA256
    changed = ast.parse(
        inspect.getsource(model_prompt).replace("allowed_tools", "other_tools")
    ).body[0]
    assert portable_ast_sha(changed) != PROMPT_BUILDER_AST_SHA256


def test_v40_preserves_all_old_cases_and_separate_pending_denominators():
    path = ROOT / "tests/fixtures/agent_behavior"
    dataset = json.loads((path / "meihua_current_semantic_cases_v40.json").read_text())
    cases = dataset["cases"]
    old = []
    for name, sha in dataset["case_origins"]["old_dataset_sha256"].items():
        assert file_sha(path / name) == sha
        old.extend(json.loads((path / name).read_text())["cases"])
    assert cases[:16] == old
    assert len(cases) == 28 and len({c["id"] for c in cases}) == 28
    assert sum(len(c["manual_review"]) for c in cases) == 84
    assert sum(bool(c.get("reference_request")) for c in cases) == 27
    assert dataset["target_weather_profile"] == "meihua_weather_v1@1.7.0"
    assert lookup({"a": [False]}, "a.0") is False
