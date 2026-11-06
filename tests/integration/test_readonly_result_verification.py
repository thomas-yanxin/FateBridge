"""Verified original-result reads must not require filesystem writes."""

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.diagnostics import resolve_codex_cli
from fatebridge.utils.errors import ParameterError

ROOT = Path(__file__).resolve().parents[2]
from tests.support.result_delivery import (
    RESULT_CASES,
    RESULT_PAYLOADS,
    block_writes,
    forbidden,
)


@pytest.fixture
def stored(tmp_path):
    store = delivery.ResultStore(tmp_path / "private")
    payload = copy.deepcopy(RESULT_PAYLOADS[RESULT_CASES[0]["id"]])
    return store, payload, store.put(payload)


@pytest.mark.parametrize("case", RESULT_CASES, ids=lambda c: c["id"])
def test_original_pages_and_field_documents_are_unchanged_without_writes(
    case, tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path / "private")
    payload = RESULT_PAYLOADS[case["id"]]
    ref = store.put(payload)
    before = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    values = {
        None: payload,
        "input_normalized": payload["input_normalized"],
        "numerology_evidence.birth_clock": payload["numerology_evidence"][
            "birth_clock"
        ],
        "canping_timing.first_period": payload["canping_timing"]["first_period"],
        "canping_timing.first_period.2": 0,
    }
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        for path, value in values.items():
            expected = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            for offset in (0, 1, min(2048, len(expected)), len(expected)):
                actual = store.verified_page(
                    ref["result_id"], case["run_id"], offset, path
                )
                assert actual["text"] == expected[offset : offset + delivery.PAGE_CHARS]
                assert actual["total_chars"] == len(expected)
                assert actual["verification"]["run_id"] == case["run_id"]
                assert actual["verification"]["calculation_repeated"] is False
        with pytest.raises(ParameterError):
            store.verified_page(ref["result_id"], case["run_id"], path="missing")
    assert {p.name: p.read_bytes() for p in store.directory.iterdir()} == before


def test_default_store_construction_does_not_probe_for_a_writable_directory(
    monkeypatch,
):
    monkeypatch.setattr(delivery, "default_result_directory", forbidden)
    delivery.ResultStore()


def test_missing_explicit_store_read_never_creates_a_cache_directory(
    tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path / "missing")
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        with pytest.raises(ParameterError):
            store.verified_page("a" * 48, "original-run")
    assert not store.directory.exists()


@pytest.mark.parametrize(
    "fault", ["digest", "run", "scope", "payload", "metadata", "expired"]
)
def test_readonly_verification_keeps_all_original_rejections(
    fault, stored, monkeypatch
):
    store, payload, ref = stored
    run = payload["run_metadata"]["run_id"]
    args = {}
    if fault == "digest":
        path = Path(ref["file_path"]).with_suffix(".meta")
        metadata = json.loads(path.read_text())
        metadata["sha256"] = "0" * 64
        path.write_text(json.dumps(metadata))
    elif fault == "run":
        run = "another-run"
    elif fault == "scope":
        args["allowed_tools"] = {"not_this_tool"}
    elif fault == "payload":
        path = Path(ref["file_path"])
        record = json.loads(path.read_text())
        record["payload"]["input_normalized"]["gender"] = "tampered"
        path.write_text(json.dumps(record, ensure_ascii=False))
    elif fault == "metadata":
        path = Path(ref["file_path"]).with_suffix(".meta")
        metadata = json.loads(path.read_text())
        metadata["total_chars"] += 1
        path.write_text(json.dumps(metadata, ensure_ascii=False))
    elif fault == "expired":
        monkeypatch.setattr(delivery.time, "time", lambda: ref["expires_at"] + 1)
    before = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        with pytest.raises(ValueError if fault == "scope" else ParameterError):
            store.verified_page(ref["result_id"], run, **args)
    assert {p.name: p.read_bytes() for p in store.directory.iterdir()} == before


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual local Codex macOS sandbox")
def test_existing_cli_contract_works_in_actual_readonly_sandbox(tmp_path):
    task_temp = tmp_path / "task-tmp"
    task_temp.mkdir()
    old_temp = tempfile.tempdir
    old_env = os.environ.get("TMPDIR")
    try:
        os.environ["TMPDIR"] = str(task_temp)
        tempfile.tempdir = None
        store = delivery.ResultStore()
        payload = RESULT_PAYLOADS[RESULT_CASES[0]["id"]]
        ref = store.put(payload)
    finally:
        tempfile.tempdir = old_temp
        if old_env is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = old_env
    probe = str(task_temp / "must-not-be-created")
    program = (
        "import os,sys;\n"
        "try: fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)\n"
        "except PermissionError: pass\n"
        "else: os.close(fd); raise AssertionError('sandbox permits writes')\n"
        "from fatebridge.cli import run\n"
        "raise SystemExit(run(sys.argv[2:]))\n"
    )
    command = [
        resolve_codex_cli()["path"],
        "sandbox",
        "-c",
        'sandbox_mode="read-only"',
        "--",
        sys.executable,
        "-B",
        "-c",
        program,
        probe,
        "result-read",
        ref["result_id"],
        "--run-id",
        payload["run_metadata"]["run_id"],
        "--path",
        "numerology_evidence.birth_clock",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "TMPDIR": str(task_temp)},
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    page = json.loads(result.stdout)
    assert page["verification"]["scope"] == "entire_retained_payload"
    assert page["verification"]["run_id"] == payload["run_metadata"]["run_id"]
    assert not Path(probe).exists()
