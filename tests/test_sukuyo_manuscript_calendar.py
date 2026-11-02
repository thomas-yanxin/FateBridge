"""Frozen pre-code source readings expose conflicts without repairing glyphs."""

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_manuscript_calendar import (
    audit_exit_code,
    audit_month_start_insertions,
)

FIXTURE = (
    Path(__file__).parent / "fixtures/sukuyo-manuscript-month-cells-first-v100.json"
)
DATA = json.loads(FIXTURE.read_bytes())
ROWS = DATA["literal_records"]["suspected_leap_insertions"]


def test_all_original_29_candidates_and_58_precode_reference_edges_retained():
    original = deepcopy(ROWS)
    report = audit_month_start_insertions(ROWS, evaluate_conditional_adjacency=True)
    assert report["source_records"] == ROWS == original
    assert report["candidate_count"] == 29 and report["edge_count"] == 58
    for actual, expected in zip(
        report["edges"], DATA["before_code_expected_edges"], strict=True
    ):
        for key in ("id", "edge", "first_literal", "last_literal", "checks", "status"):
            assert actual[key] == expected[key], (actual["id"], key)
    assert (
        report["totals"]
        == DATA["before_code_expected_totals"]
        == {
            "compatible_under_hypothesis": 54,
            "incompatible_under_hypothesis": 3,
            "not_fully_assessed": 1,
        }
    )
    assert audit_exit_code(report) == 1
    assert report["historical_calendar_truth"] == "not_assessed"
    assert report["source_adoption"] == "not_assessed"


def test_no_adjacency_inference_by_default_and_unread_candidate_never_selected():
    report = audit_month_start_insertions(ROWS)
    assert report["totals"] == {"not_assessed_adjacency_not_evaluated": 58}
    assert audit_exit_code(report) == 3
    evaluated = audit_month_start_insertions(ROWS, evaluate_conditional_adjacency=True)
    unknown = next(r for r in evaluated["edges"] if r["id"] == "12-L-4")
    assert unknown["first_literal"]["sexagenary"] is None
    assert unknown["first_literal"]["sexagenary_candidates"] == ["甲寅"]
    assert unknown["checks"]["sexagenary"]["status"].startswith("not_assessed")
    assert all(r["month_number"] is None for r in evaluated["source_records"])


def test_independent_month_length_period_examples_and_single_weekday_conflict():
    rows = [
        {
            "id": "literal-example",
            "before": {"size": "大", "sexagenary": "甲子", "weekday": "日"},
            "marked_cell": {"size": "小", "sexagenary": "甲午", "weekday": "火"},
            "after": {"size": "大", "sexagenary": "癸亥", "weekday": "水"},
        }
    ]
    report = audit_month_start_insertions(rows, evaluate_conditional_adjacency=True)
    assert report["totals"] == {"compatible_under_hypothesis": 2}
    assert audit_exit_code(report) == 0
    rows[0]["marked_cell"]["weekday"] = "水"
    report = audit_month_start_insertions(rows, evaluate_conditional_adjacency=True)
    assert report["totals"] == {"incompatible_under_hypothesis": 2}
    assert report["source_records"][0]["marked_cell"]["weekday"] == "水"


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_id",
        "missing_after",
        "numeric_weekday",
        "numeric_size",
        "missing_marked",
    ],
)
def test_structurally_bad_records_are_not_turned_into_uncertain_or_passing(change):
    rows = deepcopy(ROWS[:1])
    if change == "duplicate_id":
        rows.append(deepcopy(rows[0]))
    elif change == "missing_after":
        del rows[0]["after"]
    elif change == "numeric_weekday":
        rows[0]["marked_cell"]["weekday"] = 0
    elif change == "numeric_size":
        rows[0]["marked_cell"]["size"] = False
    else:
        rows[0]["marked_cell"] = None
    with pytest.raises(ValueError):
        audit_month_start_insertions(rows, evaluate_conditional_adjacency=True)


def call_cli(path, output, *, fingerprint=None, evaluate=True):
    root = Path(__file__).parents[1]
    args = [
        sys.executable,
        str(root / "scripts/check_sukuyo_manuscript_calendar.py"),
        "--input",
        str(path),
        "--input-sha256",
        fingerprint or hashlib.sha256(path.read_bytes()).hexdigest(),
        "--input-version",
        "literal-first-v100",
        "--output",
        str(output),
    ]
    if evaluate:
        args.append("--evaluate-conditional-adjacency")
    return subprocess.run(
        args, cwd=root, env=os.environ.copy(), capture_output=True, text=True
    )


def test_real_cli_binds_original_bytes_and_reports_conflicts_without_overwriting(
    tmp_path,
):
    output = tmp_path / "audit.json"
    run = call_cli(FIXTURE, output)
    assert run.returncode == 1, run.stderr
    body = json.loads(output.read_bytes())
    assert body["input_binding"]["raw_utf8_file_text"].encode() == FIXTURE.read_bytes()
    assert body["report"]["totals"] == DATA["before_code_expected_totals"]
    original = output.read_bytes()
    run = call_cli(FIXTURE, output)
    assert run.returncode == 2
    assert output.read_bytes() == original


def test_real_cli_hash_mismatch_and_default_unassessed_are_not_green(tmp_path):
    output = tmp_path / "audit.json"
    run = call_cli(FIXTURE, output, fingerprint="0" * 64)
    assert run.returncode == 2 and not output.exists()
    run = call_cli(FIXTURE, output, evaluate=False)
    assert run.returncode == 3, run.stderr
    body = json.loads(output.read_bytes())
    assert body["report"]["totals"] == {"not_assessed_adjacency_not_evaluated": 58}


def test_cli_partial_write_failure_publishes_nothing_and_allows_retry(
    tmp_path, monkeypatch
):
    import errno
    import importlib.util
    import tempfile

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "literal_audit_cli", root / "scripts/check_sukuyo_manuscript_calendar.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "audit.json"
    failing = True
    original_open = Path.open
    original_temporary = tempfile.NamedTemporaryFile

    class PartialWrite:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, raw):
            if failing:
                self.stream.write(raw[:120])
                raise OSError(errno.ENOSPC, "injected partial output")
            return self.stream.write(raw)

    def opened(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return PartialWrite(stream) if path == output and mode == "x" else stream

    def temporary(*args, **kwargs):
        return PartialWrite(original_temporary(*args, **kwargs))

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", temporary)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_sukuyo_manuscript_calendar.py",
            "--input",
            str(FIXTURE),
            "--input-sha256",
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "--input-version",
            "unadjudicated-first-v100",
            "--output",
            str(output),
            "--evaluate-conditional-adjacency",
        ],
    )
    assert module.main() == 2
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []
    failing = False
    assert module.main() == 1
    raw = output.read_bytes()
    assert json.loads(raw)["report"]["totals"] == DATA["before_code_expected_totals"]
    assert module.main() == 2
    assert output.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [output]
