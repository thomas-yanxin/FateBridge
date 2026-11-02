"""Source contradictions survive both name hypotheses and isolated execution."""

import ast
import json
import shutil
import subprocess
import sys

import pytest

from scripts.audit_taiyi_wujing_internal import (
    CORPUS,
    HYPOTHESES,
    ROOT,
    audit,
    count_trace,
    name_position,
    observation,
    verify,
)


@pytest.fixture(scope="module")
def report():
    return audit()


@pytest.mark.parametrize("route", verify()["reference"]["manual_routes"])
def test_frozen_hand_routes_before_implementation(route):
    trace = count_trace(route["start"], route["stop"], verify()["reference"])
    assert [s for s in trace["steps"] if s["value"]] == route["terms"]
    assert trace["value"] == route["sum"]
    assert all(s["position"] != route["stop"] for s in trace["steps"])


def test_every_original_count_slot_is_reported_under_both_hypotheses(report):
    assert [h["hypothesis"] for h in report["hypotheses"]] == list(HYPOTHESES)
    assert report["selected_hypothesis"] is None
    for hypothesis in report["hypotheses"]:
        rows = hypothesis["source_rows"]
        assert len(rows) == len({(r["id"], r["camp"]) for r in rows}) == 288
        assert sum(hypothesis["totals"].values()) == 288
        assert hypothesis["complete_count_method_adjudicated"] is False
    assert report["original_1440_comparison_requirement_retained"] is True
    assert report["production_algorithm_executed"] is False
    assert report["production_results_used_as_expected"] is False
    assert report["source_erratum_adjudicated"] is False
    assert report["whole_classic_acceptance_passed"] is False


@pytest.mark.parametrize("edition", ["siku", "ming"])
@pytest.mark.parametrize("hypothesis", HYPOTHESES)
@pytest.mark.parametrize("camp", ["main", "guest"])
def test_two_edition_worked_case_retains_both_literal_counts(
    report, edition, hypothesis, camp
):
    source = verify()
    item = next(
        r
        for r in report["worked_edition_comparisons"]
        if (r["edition"], r["hypothesis"], r["camp"]) == (edition, hypothesis, camp)
    )
    expected = source["reference"]["manual_yang4_diagnostics"][edition][hypothesis][
        camp
    ]
    assert item["conditional_count"]["value"] == expected
    assert (
        item["literal_source_count"]
        == source["readings"]["yang4"][edition][camp + "_count"]
    )
    if edition == "ming" and camp == "main":
        assert item["literal_source_count"] == 55
        assert item["comparison_status"] == "different"


def test_changing_a_source_count_cannot_change_the_reconstructed_route():
    reference = verify()["reference"]
    trace = count_trace("乾", "午", reference)
    assert observation("test", "main", 25, trace)["comparison_status"] == "matching"
    changed = observation("test", "main", 55, trace)
    assert changed["conditional_count"]["value"] == 25
    assert changed["literal_source_count"] == 55
    assert changed["comparison_status"] == "different"


@pytest.mark.parametrize("position", [None, "中", "午"])
def test_missing_and_same_start_stop_positions_remain_unknown(position):
    assert count_trace(position, "午", verify()["reference"])["value"] is None


def test_other_aliases_are_not_added_by_the_two_name_swap():
    for hypothesis in HYPOTHESES:
        assert name_position("太炅", verify()["profile"], hypothesis) is None
        assert name_position("大族", verify()["profile"], hypothesis) == "酉"


@pytest.mark.parametrize("name", ["source-cohort.json", "nlc25-022-002.png"])
def test_source_tampering_is_rejected(tmp_path, name):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    (corpus / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        verify(corpus)


def test_source_auditor_has_only_standard_library_imports_and_runs_isolated(tmp_path):
    path = ROOT / "scripts/audit_taiyi_wujing_internal.py"
    tree = ast.parse(path.read_text())
    imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports <= {"__future__", "argparse", "hashlib", "json", "pathlib", "typing"}
    output = tmp_path / "source-report.json"
    process = subprocess.run(
        [sys.executable, "-I", str(path), "--output", str(output)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert process.returncode == 1
    assert "Traceback" not in process.stderr
    result = json.loads(output.read_text())
    assert result["production_algorithm_executed"] is False
    assert result["source_erratum_adjudicated"] is False
    assert result["required_count_slots"] == 288
