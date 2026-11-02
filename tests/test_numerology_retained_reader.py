"""A client can prove original delivery identity using only the stdlib reader."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "skills/_shared/read-retained-result.py"
REFERENCE_FILE = ROOT / "tests/fixtures/numerology_delivery_reading_v1/reference.json"
REFERENCE = json.loads(REFERENCE_FILE.read_bytes())
PAYLOAD = json.loads(REFERENCE["payload_literal"])


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


@pytest.fixture
def record(tmp_path):
    file = tmp_path / "original.json"
    file.write_bytes(
        encode({"expires_at": REFERENCE["expires_at"], "payload": PAYLOAD})
    )
    return file


def run(record, digest=None, run_id=None, path=None, offset=0):
    command = [
        sys.executable,
        "-I",
        "-S",
        str(READER),
        str(record),
        "--sha256",
        digest or REFERENCE["payload_sha256"],
        "--run-id",
        run_id or REFERENCE["run_id"],
        "--offset",
        str(offset),
    ]
    if path is not None:
        command += ["--path", path]
    before = {
        p.name: (p.stat().st_mtime_ns, p.read_bytes())
        for p in record.parent.iterdir()
        if p.is_file() and not p.is_symlink()
    }
    output = subprocess.run(
        command,
        cwd=record.parent,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "/nonexistent-no-project-imports"},
        timeout=10,
    )
    after = {
        p.name: (p.stat().st_mtime_ns, p.read_bytes())
        for p in record.parent.iterdir()
        if p.is_file() and not p.is_symlink()
    }
    assert before == after
    assert not output.stderr
    return output.returncode, json.loads(output.stdout)


@pytest.mark.parametrize("case", REFERENCE["field_cases"], ids=lambda x: x["path"])
def test_literal_original_order_and_fields_with_no_site_packages(record, case):
    code, page = run(record, path=case["path"])
    assert code == 0 and json.loads(page["text"]) == case["value"]
    assert page["next_offset"] is None
    proof = page["verification"]
    assert proof["payload_sha256"] == REFERENCE["payload_sha256"]
    assert proof["run_id"] == REFERENCE["run_id"]
    assert proof["scope"] == "entire_retained_payload"
    assert proof["calculation_repeated"] is False
    assert proof["service_reference_status_checked"] is False


@pytest.mark.parametrize("digest_kind", ["wrong", "outer", "sorted"])
def test_no_outer_file_hash_or_sorted_payload_substitution(record, digest_kind):
    digest = {
        "wrong": "0" * 64,
        "outer": hashlib.sha256(record.read_bytes()).hexdigest(),
        "sorted": REFERENCE["sorted_payload_sha256"],
    }[digest_kind]
    code, result = run(record, digest=digest, path="run_metadata.run_id")
    assert code == 1 and result["error_code"] == "result_digest_mismatch"
    assert "verification" not in result and "text" not in result


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_run",
        "missing_run",
        "wrong_shape_run",
        "changed_payload",
        "expired",
        "malformed_record",
        "non_object_payload",
        "bad_json",
        "bad_utf8",
        "surrogate",
    ],
)
def test_corrupted_or_wrong_identity_records_never_get_verified(record, fault):
    value = json.loads(record.read_bytes())
    digest = REFERENCE["payload_sha256"]
    run_id = REFERENCE["run_id"]
    expected = "invalid_result_record"
    if fault == "wrong_run":
        run_id = "another_original_run"
        expected = "result_run_mismatch"
    elif fault in ["missing_run", "wrong_shape_run"]:
        value["payload"]["run_metadata"] = (
            None if fault == "missing_run" else "another_run"
        )
        digest = hashlib.sha256(encode(value["payload"])).hexdigest()
        expected = "result_run_mismatch"
    elif fault == "changed_payload":
        value["payload"]["z"] = 4
        expected = "result_digest_mismatch"
    elif fault == "expired":
        value["expires_at"] = 1
        expected = "result_expired"
    elif fault == "malformed_record":
        value = []
    elif fault == "non_object_payload":
        value["payload"] = []
    elif fault == "surrogate":
        record.write_bytes(b'{"expires_at":4102444800,"payload":{"a":"\\ud800"}}')
    if fault not in ["surrogate", "bad_json", "bad_utf8"]:
        record.write_bytes(encode(value))
    if fault in ["bad_json", "bad_utf8"]:
        record.write_bytes(b"{" if fault == "bad_json" else b"\xff")
        expected = "result_file_unavailable"
    code, result = run(record, digest=digest, run_id=run_id)
    assert code == 1 and result["error_code"] == expected
    assert result["retryable"] is False and "verification" not in result


@pytest.mark.parametrize(
    "expiry",
    [None, True, "4102444800", float("nan"), float("inf"), -(10**400), 10**400],
)
def test_invalid_expiry_is_a_controlled_error(record, expiry):
    value = json.loads(record.read_bytes())
    value["expires_at"] = expiry
    record.write_bytes(encode(value))
    code, result = run(record)
    assert code == 1 and result["error_code"] == "invalid_result_record"


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ({"path": "rows.99.value"}, "unknown_result_path"),
        ({"path": "missing"}, "unknown_result_path"),
        ({"path": "a", "offset": -1}, "invalid_offset"),
        ({"path": "a", "offset": 999}, "invalid_offset"),
        ({"path": "a" * 1001}, "invalid_result_path"),
        ({"digest": "not_a_digest"}, "invalid_digest"),
        ({"run_id": "bad/run"}, "invalid_run_id"),
    ],
)
def test_bad_requests_do_not_emit_reading_proof(record, arguments, expected):
    code, result = run(record, **arguments)
    assert code == 1 and result["error_code"] == expected
    assert "verification" not in result


@pytest.mark.parametrize("kind", ["symbolic_link", "directory", "missing"])
def test_unavailable_file_types_fail_without_writes(record, kind):
    path = record.parent / "other"
    if kind == "symbolic_link":
        path.symlink_to(record)
    elif kind == "directory":
        path.mkdir()
    code, result = run(path)
    assert code == 1 and result["error_code"] == "result_file_unavailable"


def test_multiple_unicode_pages_are_bounded_and_not_a_full_read_claim(record):
    value = json.loads(record.read_bytes())
    value["payload"]["a"] = "甲😀乙" * 2000
    record.write_bytes(encode(value))
    digest = hashlib.sha256(encode(value["payload"])).hexdigest()
    parts = []
    offset = 0
    while True:
        code, page = run(record, digest=digest, path="a", offset=offset)
        assert code == 0 and page["offset"] == offset
        assert len(page["text"]) <= REFERENCE["page_chars"]
        assert page["verification"]["payload_sha256"] == digest
        parts.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    joined = "".join(parts)
    assert len(parts) > 1 and json.loads(joined) == value["payload"]["a"]
    assert hashlib.sha256(joined.encode()).hexdigest() == page["sha256"]
