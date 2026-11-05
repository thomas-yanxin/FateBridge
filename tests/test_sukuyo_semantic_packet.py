"""Whole-file binding prevents missing count/byte evidence and dropped cases."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_engineering import Artifact
from fatebridge.validation.sukuyo_semantic_packet import (
    build_whole_answer_review_packet,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (ROOT / "tests/data/sukuyo-semantic-packet-before-code-v96.json").read_bytes()
)


def artifact(path, raw, version="test literal"):
    path.write_bytes(raw)
    return Artifact(path, hashlib.sha256(raw).hexdigest(), version)


def inputs(tmp_path):
    return (
        artifact(tmp_path / "request.json", REFERENCE["request_utf8"].encode()),
        artifact(tmp_path / "answers.json", REFERENCE["answers_utf8"].encode()),
    )


def test_complete_files_case_order_and_unknown_metadata_match_precode_literal(tmp_path):
    request, answers = inputs(tmp_path)
    result = build_whole_answer_review_packet(request, answers)
    assert result["items"] == REFERENCE["expected_cases"]
    assert result["case_count"] == REFERENCE["derived_case_count"] == 2
    assert result["request_case_order"] == ["a", "b"]
    for label, value, prefix in [
        ("request", request, "request"),
        ("answers", answers, "answers"),
    ]:
        record = result[label]
        assert record["sha256"] == value.sha256 == REFERENCE[prefix + "_sha256"]
        assert record["bytes"] == REFERENCE[prefix + "_bytes"]
        assert record["raw_utf8_file_text"] == REFERENCE[prefix + "_utf8"]
        assert record["value"] == json.loads(REFERENCE[prefix + "_utf8"])
    assert result["request"]["value"]["claimed_count"] == 999
    assert result["request"]["value"]["future"]["summary"] == {"unresolved": True}
    assert result["request"]["value"]["unknown"] is None
    assert (
        result["answers"]["value"]["reader_claim"]
        == "self reported, not independently proven"
    )
    assert not result["earlier_reader_behaviour_independently_verified"]
    for key in [
        "semantic_verdict",
        "source_support_of_answer",
        "source_independence",
        "original_gate_verdict",
        "real_world_efficacy",
    ]:
        assert result[key] == "not_assessed"


def test_raw_text_and_parsed_value_use_the_same_single_file_read(tmp_path, monkeypatch):
    request, answers = inputs(tmp_path)
    read = Path.read_bytes
    counts = {}

    def counted(path):
        counts[path] = counts.get(path, 0) + 1
        return read(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    packet = build_whole_answer_review_packet(request, answers)
    assert counts == {request.path.resolve(): 1, answers.path.resolve(): 1}
    assert (
        len(packet["request"]["raw_utf8_file_text"].encode())
        == packet["request"]["bytes"]
    )


def test_answer_symlink_switch_after_bind_keeps_its_already_bound_bytes(
    tmp_path, monkeypatch
):
    from fatebridge.validation.sukuyo_engineering import _ArtifactReader

    request, answer_file = inputs(tmp_path)
    link = tmp_path / "answers-link.json"
    link.symlink_to(answer_file.path)
    answers = Artifact(link, answer_file.sha256, answer_file.source_version)
    original_bind = _ArtifactReader.bind
    switches = []

    def bind_then_switch(self, value, pointer=""):
        bound = original_bind(self, value, pointer)
        if value.path == link:
            switches.append(bound["path"])
            link.unlink()
            link.symlink_to(request.path)
        return bound

    monkeypatch.setattr(_ArtifactReader, "bind", bind_then_switch)
    packet = build_whole_answer_review_packet(request, answers)
    assert switches == [str(answer_file.path.resolve())]
    assert link.resolve() == request.path.resolve()
    for label in ("request", "answers"):
        record = packet[label]
        raw = record["raw_utf8_file_text"].encode()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
        assert len(raw) == record["bytes"]
        assert json.loads(raw) == record["value"]
    assert packet["answers"]["raw_utf8_file_text"] == REFERENCE["answers_utf8"]
    assert packet["items"] == REFERENCE["expected_cases"]


@pytest.mark.parametrize(
    "change",
    ["missing", "extra", "duplicate", "empty", "wrong_question", "empty_answer"],
)
def test_case_loss_duplication_or_question_drift_fails(tmp_path, change):
    request, _ = inputs(tmp_path)
    value = json.loads(REFERENCE["answers_utf8"])
    if change == "missing":
        value["answers"].pop()
    elif change == "extra":
        value["answers"].append({"id": "c", "answer": "extra"})
    elif change == "duplicate":
        value["answers"].append(copy.deepcopy(value["answers"][0]))
    elif change == "empty":
        value["answers"] = []
    elif change == "wrong_question":
        value["answers"][1]["question"] += " shortened"
    else:
        value["answers"][0]["answer"] = " \n"
    answers = artifact(
        tmp_path / "changed.json", json.dumps(value, ensure_ascii=False).encode()
    )
    with pytest.raises(ValueError):
        build_whole_answer_review_packet(request, answers)


@pytest.mark.parametrize(
    "change", ["duplicate", "bad_id", "empty_question", "empty_cases", "wrong_root"]
)
def test_request_cannot_hide_or_replace_whole_questions(tmp_path, change):
    _, answers = inputs(tmp_path)
    value = json.loads(REFERENCE["request_utf8"])
    if change == "duplicate":
        value["cases"].append(copy.deepcopy(value["cases"][0]))
    elif change == "bad_id":
        value["cases"][0]["id"] = 1
    elif change == "empty_question":
        value["cases"][0]["question"] = " "
    elif change == "empty_cases":
        value["cases"] = []
    else:
        value = []
    request = artifact(tmp_path / "changed-request.json", json.dumps(value).encode())
    with pytest.raises(ValueError):
        build_whole_answer_review_packet(request, answers)


@pytest.mark.parametrize(
    "raw", [b'{"cases":[],"cases":[]}', b'{"value":NaN}', b'{"value":1e999}']
)
def test_strict_json_failures_remain_failures(tmp_path, raw):
    _, answers = inputs(tmp_path)
    request = artifact(tmp_path / "invalid.json", raw)
    with pytest.raises(ValueError):
        build_whole_answer_review_packet(request, answers)


def test_byte_drift_and_same_file_identity_are_rejected(tmp_path):
    request, answers = inputs(tmp_path)
    request.path.write_bytes(request.path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA mismatch"):
        build_whole_answer_review_packet(request, answers)
    with pytest.raises(ValueError, match="separate byte identities"):
        build_whole_answer_review_packet(answers, answers)


def test_full_utf8_is_required_without_replacing_bad_bytes(tmp_path):
    _, answers = inputs(tmp_path)
    request = artifact(
        tmp_path / "utf16.json", REFERENCE["request_utf8"].encode("utf-16")
    )
    with pytest.raises(UnicodeDecodeError):
        build_whole_answer_review_packet(request, answers)


def test_case_id_format_and_case_vs_unique_question_units(tmp_path):
    request_value = json.loads(REFERENCE["request_utf8"])
    answer_value = json.loads(REFERENCE["answers_utf8"])
    for row in request_value["cases"] + answer_value["answers"]:
        row["case_id"] = row.pop("id")
    request_value["cases"][1]["question"] = request_value["cases"][0]["question"]
    request = artifact(
        tmp_path / "request-case-id.json", json.dumps(request_value).encode()
    )
    answers = artifact(
        tmp_path / "answers-case-id.json", json.dumps(answer_value).encode()
    )
    result = build_whole_answer_review_packet(request, answers, id_field="case_id")
    assert result["case_count"] == 2 and result["unique_question_count"] == 1
    assert [row["case_id"] for row in result["items"]] == ["a", "b"]


def test_cli_uses_the_same_packet_and_never_replaces_existing_output(tmp_path):
    request, answers = inputs(tmp_path)
    output = tmp_path / "packet.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/build_sukuyo_semantic_review.py"),
        "--request",
        str(request.path),
        "--request-sha256",
        request.sha256,
        "--request-version",
        request.source_version,
        "--answers",
        str(answers.path),
        "--answers-sha256",
        answers.sha256,
        "--answers-version",
        answers.source_version,
        "--output",
        str(output),
    ]
    first = subprocess.run(
        command, cwd=ROOT, env=os.environ.copy(), capture_output=True
    )
    assert first.returncode == 0, first.stderr
    assert json.loads(output.read_bytes()) == build_whole_answer_review_packet(
        request, answers
    )
    raw = output.read_bytes()
    second = subprocess.run(
        command, cwd=ROOT, env=os.environ.copy(), capture_output=True
    )
    assert second.returncode != 0 and output.read_bytes() == raw
    output.unlink()
    answers.path.write_bytes(answers.path.read_bytes() + b" ")
    invalid = subprocess.run(
        command, cwd=ROOT, env=os.environ.copy(), capture_output=True
    )
    assert invalid.returncode != 0 and not output.exists()
