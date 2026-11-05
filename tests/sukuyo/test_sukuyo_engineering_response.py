"""Whole-answer delivery binds evidence without assigning semantic credit."""

from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_engineering import (
    AnswerCoverage,
    AnswerSpan,
    Artifact,
    Requirement,
    Selection,
    build_engineering_annex,
    build_engineering_response,
    build_engineering_response_request,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/sukuyo/build_sukuyo_engineering_response.py"


def artifact(tmp_path, name, value):
    path = tmp_path / name
    raw = (json.dumps(value, ensure_ascii=False) + "\n").encode()
    path.write_bytes(raw)
    return Artifact(path, hashlib.sha256(raw).hexdigest(), "declared-test-version")


def inputs(tmp_path):
    question = "  整题：逐人结果及工程记录？\n保留未定。 "
    calc = artifact(tmp_path, "calc.json", {"candidate": None, "adverse": [1, 2]})
    evidence = artifact(tmp_path, "evidence.json", {"rows": [None, {"failed": True}]})
    answer = artifact(
        tmp_path,
        "answer.json",
        {"question": question, "answer": "🌙计算仍有未定。\n原件缺失，暂不能认证。"},
    )
    requirements = [
        Requirement("calc", "解释全部计算", (Selection(calc), Selection(evidence))),
        Requirement("source", "解释原件", unavailable_reason="原件尚未取得"),
    ]
    coverage = [
        AnswerCoverage("calc", (AnswerSpan(0, 8, "🌙计算仍有未定。"),)),
        AnswerCoverage("source", (AnswerSpan(9, 20, "原件缺失，暂不能认证。"),)),
    ]
    # Character offsets below are independent literals for the complete text.
    assert len("🌙计算仍有未定。") == 8
    return question, calc, requirements, answer, coverage


def descriptor(source):
    return {
        "path": source.path.name,
        "sha256": source.sha256,
        "source_version": source.source_version,
    }


def request_file(tmp_path):
    question, calc, requirements, answer, coverage = inputs(tmp_path)
    data = {
        "request_kind": "engineering",
        "question": question,
        "calculation": descriptor(calc),
        "requirements": [
            {
                "id": row.id,
                "text": row.text,
                "selections": [
                    {"artifact": descriptor(s.artifact), "pointer": s.pointer}
                    for s in row.selections
                ],
                "unavailable_reason": row.unavailable_reason,
            }
            for row in requirements
        ],
        "answer": descriptor(answer),
        "coverage": [
            {
                "requirement_id": row.requirement_id,
                "spans": [
                    {"start": s.start, "end": s.end, "quote": s.quote}
                    for s in row.spans
                ],
            }
            for row in coverage
        ],
    }
    return artifact(tmp_path, "request.json", data)


def test_whole_answer_scientific_evidence_and_unavailable_are_retained(tmp_path):
    args = inputs(tmp_path)
    result = build_engineering_response(*args)
    question, calc, requirements, answer, _ = args
    assert result["question"] == question
    assert result["answer"] == json.loads(answer.path.read_bytes())["answer"]
    assert result["annex"] == build_engineering_annex(question, calc, requirements)
    assert result["annex"]["calculation"]["value"] == {
        "candidate": None,
        "adverse": [1, 2],
    }
    assert result["annex"]["requirements"][0]["evidence"][1]["value"] == {
        "rows": [None, {"failed": True}]
    }
    assert not result["annex"]["evidence_complete"]
    assert result["annex"]["requirements"][1]["status"] == "unavailable"
    assert result["declared_requirement_mapping_complete"]
    assert result["span_unit"] == "unicode_codepoints_zero_based_half_open"
    for key in [
        "semantic_verdict",
        "real_world_efficacy",
        "source_support_of_answer",
        "question_requirement_completeness",
    ]:
        assert result[key] == "not_assessed"


@pytest.mark.parametrize("change", ["missing", "unknown", "duplicate", "empty"])
def test_mapping_gaps_cannot_silently_drop_an_obligation(tmp_path, change):
    args = list(inputs(tmp_path))
    rows = args[-1]
    if change == "missing":
        rows.pop()
    elif change == "unknown":
        rows[0] = replace(rows[0], requirement_id="not-declared")
    elif change == "duplicate":
        rows.append(rows[0])
    else:
        rows[0] = replace(rows[0], spans=())
    with pytest.raises(ValueError):
        build_engineering_response(*args)


@pytest.mark.parametrize(
    "span",
    [
        AnswerSpan(True, 8, "🌙计算仍有未定。"),
        AnswerSpan(0, False, "🌙计算仍有未定。"),
        AnswerSpan(0.0, 8, "🌙计算仍有未定。"),
        AnswerSpan(-1, 8, "🌙计算仍有未定。"),
        AnswerSpan(0, 99, "🌙计算仍有未定。"),
        AnswerSpan(8, 8, ""),
        AnswerSpan(0, 8, "别的原文"),
        AnswerSpan(8, 9, "\n"),
    ],
)
def test_invalid_or_stale_literal_ranges_fail(tmp_path, span):
    args = list(inputs(tmp_path))
    args[-1][0] = AnswerCoverage("calc", (span,))
    with pytest.raises(ValueError, match="span"):
        build_engineering_response(*args)


def test_duplicate_range_within_requirement_is_rejected(tmp_path):
    args = list(inputs(tmp_path))
    row = args[-1][0]
    args[-1][0] = replace(row, spans=row.spans * 2)
    with pytest.raises(ValueError, match="span"):
        build_engineering_response(*args)


def test_shared_passage_between_requirements_does_not_prove_semantics(tmp_path):
    question, calc, requirements, _, coverage = inputs(tmp_path)
    text = "所有原典和现实预测均满分。"
    answer = artifact(tmp_path, "wrong.json", {"question": question, "answer": text})
    coverage = [
        AnswerCoverage(row.id, (AnswerSpan(0, len(text), text),))
        for row in requirements
    ]
    result = build_engineering_response(question, calc, requirements, answer, coverage)
    assert result["literal_span_alignment_verified"]
    assert result["declared_requirement_mapping_complete"]
    assert result["semantic_verdict"] == "not_assessed"
    assert result["source_support_of_answer"] == "not_assessed"
    assert not result["annex"]["evidence_complete"]


@pytest.mark.parametrize("question", ["整题：逐人结果及工程记录？\n保留未定。", "换题"])
def test_even_whitespace_question_rewriting_is_rejected(tmp_path, question):
    args = list(inputs(tmp_path))
    original = json.loads(args[3].path.read_bytes())
    original["question"] = question
    args[3] = artifact(tmp_path, "rewritten.json", original)
    with pytest.raises(ValueError, match="question"):
        build_engineering_response(*args)


def test_answer_drift_and_answer_used_as_own_evidence_fail(tmp_path):
    args = list(inputs(tmp_path))
    answer = args[3]
    args[1] = answer
    with pytest.raises(ValueError, match="own"):
        build_engineering_response(*args)
    args = list(inputs(tmp_path))
    args[2] = [Requirement("self", "自引", (Selection(answer),))]
    with pytest.raises(ValueError, match="own"):
        build_engineering_response(*args)
    args = list(inputs(tmp_path))
    alias = tmp_path / "answer-copy.json"
    alias.write_bytes(args[3].path.read_bytes())
    source = Artifact(alias, args[3].sha256, args[3].source_version)
    args[2] = [Requirement("self", "相同字节自引", (Selection(source),))]
    with pytest.raises(ValueError, match="own"):
        build_engineering_response(*args)
    args = list(inputs(tmp_path))
    args[3].path.write_text("{}")
    with pytest.raises(ValueError, match="SHA"):
        build_engineering_response(*args)


def test_request_and_all_shared_artifacts_are_read_once(tmp_path, monkeypatch):
    request = request_file(tmp_path)
    original = Path.read_bytes
    reads = []

    def read(path):
        reads.append(path)
        assert reads.count(path) == 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    result = build_engineering_response_request(request)
    assert len(reads) == len(result["artifacts"]) == 4
    monkeypatch.setattr(Path, "read_bytes", original)
    (tmp_path / "calc.json").write_text("{}")
    assert result["annex"]["calculation"]["value"]["adverse"] == [1, 2]


@pytest.mark.parametrize("literal", ["1e999", "-1e999"])
@pytest.mark.parametrize("target", ["request", "calculation", "evidence", "answer"])
def test_exponent_overflow_in_any_full_artifact_is_rejected(tmp_path, target, literal):
    request = request_file(tmp_path)
    data = json.loads(request.path.read_bytes())
    if target == "request":
        path = request.path
    elif target == "evidence":
        path = tmp_path / "evidence.json"
        # Even a field outside the selected subtree is parsed and checked.
        data["requirements"][0]["selections"][1]["pointer"] = "/rows"
    else:
        path = tmp_path / ("calc.json" if target == "calculation" else "answer.json")
    value = path.read_bytes().rstrip()
    path.write_bytes(value[:-1] + b', "unselected": ' + literal.encode() + b"}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if target == "request":
        request = replace(request, sha256=digest)
    else:
        if target == "calculation":
            data["calculation"]["sha256"] = digest
            data["requirements"][0]["selections"][0]["artifact"]["sha256"] = digest
        elif target == "evidence":
            data["requirements"][0]["selections"][1]["artifact"]["sha256"] = digest
        else:
            data["answer"]["sha256"] = digest
        request = artifact(tmp_path, "request.json", data)
    with pytest.raises(ValueError, match="Non-finite"):
        build_engineering_response_request(request)


@pytest.mark.parametrize("wrapped", [False, True])
def test_reformatted_and_selected_answer_objects_cannot_self_support(tmp_path, wrapped):
    question, calc, requirements, answer, coverage = inputs(tmp_path)
    value = json.loads(answer.path.read_bytes())
    other = artifact(
        tmp_path, "reformatted.json", {"nested": value} if wrapped else value
    )
    # Re-encode to make the direct-object case differ in actual bytes.
    other.path.write_text(json.dumps(json.loads(other.path.read_bytes()), indent=3))
    other = replace(other, sha256=hashlib.sha256(other.path.read_bytes()).hexdigest())
    assert other.sha256 != answer.sha256
    if wrapped:
        requirements[0] = replace(
            requirements[0], selections=(Selection(other, "/nested"),)
        )
    else:
        calc = other
    with pytest.raises(ValueError, match="own"):
        build_engineering_response(question, calc, requirements, answer, coverage)


def test_historical_answer_comparison_is_not_forbidden_by_shared_words(tmp_path):
    args = list(inputs(tmp_path))
    old = json.loads(args[3].path.read_bytes())
    old["question"] = "另一个历史问题"
    source = artifact(tmp_path, "historical-answer.json", old)
    args[2][0] = replace(args[2][0], selections=(Selection(source),))
    result = build_engineering_response(*args)
    assert result["source_support_of_answer"] == "not_assessed"


@pytest.mark.parametrize("pointer", ["/answer", "/question"])
def test_complete_source_identity_is_checked_when_only_a_field_is_selected(
    tmp_path, pointer
):
    question, calc, requirements, answer, coverage = inputs(tmp_path)
    path = tmp_path / "reformatted-partial.json"
    path.write_text(json.dumps(json.loads(answer.path.read_bytes()), indent=4))
    source = Artifact(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), "test-source"
    )
    assert source.sha256 != answer.sha256
    requirements[0] = replace(requirements[0], selections=(Selection(source, pointer),))
    with pytest.raises(ValueError, match="own"):
        build_engineering_response(question, calc, requirements, answer, coverage)


def test_combining_CRLF_repeated_text_and_multiple_spans_are_literal(tmp_path):
    question, calc, requirements, _, _ = inputs(tmp_path)
    text = "e\u0301\r\n🌙原文。\n后段；后段"
    answer = artifact(tmp_path, "unicode.json", {"question": question, "answer": text})
    coverage = [
        AnswerCoverage(
            "calc", (AnswerSpan(0, 2, "e\u0301"), AnswerSpan(4, 8, "🌙原文。"))
        ),
        AnswerCoverage("source", (AnswerSpan(12, 14, "后段"),)),
    ]
    result = build_engineering_response(question, calc, requirements, answer, coverage)
    assert result["answer"] == text
    assert result["coverage"][1]["spans"][0]["start"] == 12


@pytest.mark.parametrize("change", ["unknown_field", "not_engineering", "not_array"])
def test_request_schema_or_route_cannot_be_guessed(tmp_path, change):
    request = request_file(tmp_path)
    data = json.loads(request.path.read_bytes())
    if change == "unknown_field":
        data["scores"] = "pass"
    elif change == "not_engineering":
        data["request_kind"] = "consultation"
    else:
        data["coverage"] = {}
    request = artifact(tmp_path, "request.json", data)
    with pytest.raises(ValueError):
        build_engineering_response_request(request)


def test_cli_executes_assembly_from_relative_bound_files_without_overwrite(tmp_path):
    request = request_file(tmp_path)
    output = tmp_path / "result.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--request",
        str(request.path),
        "--request-sha256",
        request.sha256,
        "--request-version",
        request.source_version,
        "--output",
        str(output),
    ]
    run = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    raw = output.read_bytes()
    result = json.loads(raw)
    assert result["request_artifact"]["sha256"] == request.sha256
    assert result["semantic_verdict"] == "not_assessed"
    assert result["answer"] == "🌙计算仍有未定。\n原件缺失，暂不能认证。"
    rerun = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert rerun.returncode != 0
    assert output.read_bytes() == raw
    bad = tmp_path / "bad.json"
    command[command.index("--request-sha256") + 1] = "0" * 64
    command[-1] = str(bad)
    failed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert failed.returncode != 0 and "SHA" in failed.stderr
    assert not bad.exists()


def test_failed_staging_write_cannot_publish_partial_result(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("engineering_delivery_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fail_fsync(_):
        raise OSError(errno.ENOSPC, "simulated staging failure")

    monkeypatch.setattr(module.os, "fsync", fail_fsync)
    output = tmp_path / "result.json"
    with pytest.raises(OSError, match="staging failure"):
        module.publish_output(output, b'{"complete":true}')
    assert not output.exists()
    assert not list(tmp_path.iterdir())
