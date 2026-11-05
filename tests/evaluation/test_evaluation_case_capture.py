"""Persist evidence before another case, and reject incomplete acceptance."""

import asyncio
import json
import os
import subprocess
import sys

import pytest

from fatebridge.validation.agent_capture import CaptureJournal, read_capture
from fatebridge.validation.case_capture import collect_cases, inspect_cases


def test_serialization_rejection_does_not_consume_a_sequence(tmp_path):
    path = tmp_path / "first.jsonl"
    journal = CaptureJournal(path, sync_to_disk=True)
    with pytest.raises(ValueError):
        asyncio.run(journal.append({"value": float("nan")}))
    asyncio.run(journal.append({"value": 1}))
    journal.close()
    records = read_capture(path)
    assert len(records) == 1 and records[0]["sequence"] == 1


def test_calculation_error_keeps_prior_results_and_failed_input(tmp_path):
    path = tmp_path / "failed.jsonl"
    calls = []

    def calculate(case):
        calls.append(case["id"])
        if case["id"] == 2:
            raise ValueError("controlled calculation failure")
        return {"actual": case["id"]}

    with pytest.raises(ValueError, match="controlled calculation"):
        asyncio.run(
            collect_cases(
                path,
                [{"id": i} for i in range(4)],
                calculate,
                context={"kind": "synthetic"},
            )
        )
    assert calls == [0, 1, 2]
    result = inspect_cases(path, require_complete=False)
    assert result["status"] == "failed" and result["completed_case_count"] == 2
    assert result["failed_case_index"] == 2 and result["pending_case_index"] is None
    assert result["results"] == [{"actual": 0}, {"actual": 1}]
    assert read_capture(path)[0]["cases"] == [{"id": i} for i in range(4)]
    with pytest.raises(ValueError, match="Incomplete evaluation"):
        inspect_cases(path)


def test_process_exit_retains_durable_prefix_without_claiming_completion(tmp_path):
    path = tmp_path / "abrupt.jsonl"
    code = """
import asyncio,os,sys
from pathlib import Path
from fatebridge.validation.case_capture import collect_cases
def calculate(case):
    if case['id']==2:os._exit(73)
    return {'actual':case['id']}
asyncio.run(collect_cases(Path(sys.argv[1]),[{'id':i} for i in range(4)],calculate,context={'kind':'synthetic abrupt exit'}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 73
    evidence = inspect_cases(path, require_complete=False)
    assert evidence["completed_case_count"] == 2 and evidence["pending_case_index"] == 2
    assert evidence["status"] == "incomplete"
    with pytest.raises(ValueError, match="Incomplete evaluation"):
        inspect_cases(path)


def test_result_is_saved_before_mutable_value_is_reused(tmp_path):
    path = tmp_path / "complete.jsonl"
    shared = {"actual": None}
    cases = [{"id": 0, "nested": []}, {"id": 1, "nested": []}]

    def calculate(case):
        case["nested"].append("private mutation")
        shared["actual"] = case["id"]
        return shared

    assert (
        asyncio.run(
            collect_cases(path, cases, calculate, context={"kind": "synthetic"})
        )
        == 2
    )
    assert cases == [{"id": 0, "nested": []}, {"id": 1, "nested": []}]
    evidence = inspect_cases(path)
    assert evidence["results"] == [{"actual": 0}, {"actual": 1}]
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        asyncio.run(collect_cases(path, cases, calculate, context={}))
    assert path.read_bytes() == original


def test_fsync_failure_preserves_bytes_and_poisons_further_appends(
    tmp_path, monkeypatch
):
    path = tmp_path / "io-failed.jsonl"
    journal = CaptureJournal(path, sync_to_disk=True)

    def fail(*args):
        raise OSError("controlled fsync failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="controlled fsync"):
        asyncio.run(journal.append({"event": "first"}))
    preserved = path.read_bytes()
    assert preserved
    with pytest.raises(RuntimeError, match="persistence"):
        asyncio.run(journal.append({"event": "second"}))
    assert path.read_bytes() == preserved
    journal.close()


def test_short_write_preserves_uncertain_prefix_and_refuses_continuation(tmp_path):
    path = tmp_path / "short.jsonl"
    journal = CaptureJournal(path)
    stream = journal._stream

    class ShortWriter:
        def write(self, line):
            stream.write(line[:-1])
            stream.flush()
            return len(line) - 1

        def close(self):
            stream.close()

    journal._stream = ShortWriter()
    with pytest.raises(OSError, match="Incomplete capture"):
        asyncio.run(journal.append({"value": 1}))
    original = path.read_bytes()
    assert original and journal.persistence_failed
    with pytest.raises(RuntimeError, match="persistence"):
        asyncio.run(journal.append({"value": 2}))
    assert path.read_bytes() == original
    journal.close()


def test_unserializable_result_is_a_failed_case_without_favorable_retry(tmp_path):
    path = tmp_path / "bad-result.jsonl"
    calls = []

    def calculate(case):
        calls.append(case["id"])
        return 1 if case["id"] == 0 else float("nan")

    with pytest.raises(ValueError):
        asyncio.run(
            collect_cases(path, [{"id": i} for i in range(3)], calculate, context={})
        )
    result = inspect_cases(path, require_complete=False)
    assert calls == [0, 1] and result["results"] == [1]
    assert result["status"] == "failed" and result["failed_case_index"] == 1
    with pytest.raises(ValueError, match="Incomplete"):
        inspect_cases(path)


@pytest.mark.parametrize("fault", ["changed_payload", "truncated", "no_completion"])
def test_tampered_or_incomplete_batch_is_not_accepted(tmp_path, fault):
    path = tmp_path / "tampered.jsonl"
    asyncio.run(
        collect_cases(path, [{"id": 0}], lambda case: {"actual": 0}, context={})
    )
    lines = path.read_text().splitlines()
    if fault == "changed_payload":
        value = json.loads(lines[2])
        value["result"]["actual"] = 1
        lines[2] = json.dumps(value)
    elif fault == "truncated":
        lines[-1] = lines[-1][:20]
    else:
        lines.pop()
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        inspect_cases(path)
