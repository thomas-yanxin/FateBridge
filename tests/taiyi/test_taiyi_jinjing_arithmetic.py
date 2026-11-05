"""Independent arithmetic catches fitting to tables and numerically silent bad traces."""

import ast
import copy
import json
import shutil
import subprocess
import sys

import pytest

from scripts.taiyi.audit_taiyi_jinjing_arithmetic import CORPUS, ROOT, compare, verify
from scripts.taiyi.capture_taiyi_jinjing_arithmetic import capture


@pytest.fixture(scope="module")
def actuals():
    return capture()


@pytest.fixture(scope="module")
def report(actuals):
    return compare(actuals)


@pytest.mark.parametrize(
    "reference",
    verify()["grid"]["controls"],
    ids=lambda r: f"{r['marker']}-{r['taiyi_number']}",
)
def test_every_declared_input_and_trace_against_frozen_source_algebra(
    report, reference
):
    row = next(
        r
        for r in report["reference_controls"]
        if (r["marker"], r["taiyi_number"])
        == (reference["marker"], reference["taiyi_number"])
    )
    assert row["count_matches"] is True
    assert row["trace_matches"] is True


def test_full_original_source_values_and_old_failures_are_not_regraded(report):
    data = verify()
    expected = {
        (r["id"], camp): r["table_counts"][camp + "_count"]
        for r in data["source"]["rows"]
        for camp in ("main", "guest")
    }
    assert len(report["independent_source_counts"]) == len(expected) == 288
    assert {
        (r["id"], r["camp"]): r["source_table_count"]
        for r in report["independent_source_counts"]
    } == expected
    old = json.loads(
        (ROOT / "tests/data/taiyi/known_source_disagreements.json").read_text()
    )
    assert (
        report["old_11_count_disagreements_retained"]
        == old["groups"]["counts"]["differences"]
    )
    assert len(report["old_11_count_disagreements_retained"]) == 11
    assert (
        report["old_3_position_disagreements_retained"]
        == old["groups"]["positions"]["differences"]
    )
    assert len(report["old_3_position_disagreements_retained"]) == 3
    assert len(report["source_position_comparisons"]) == 576
    assert (
        len(report["actual_core_counts"])
        == len(report["production_source_recounts"])
        == 288
    )
    assert not report["engine_arithmetic_failures"]
    assert not report["engine_source_recount_failures"]
    assert report["selected_rule_is_complete_classical_adjudication"] is False
    assert report["whole_classic_acceptance_passed"] is False


def test_all_coincident_source_slots_include_the_disagreeing_yin46(report):
    slots = report["same_point_all20_source_slots"]["source_slots"]
    assert len(slots) == 20
    row = next(r for r in slots if r["id"] == "yin-46" and r["camp"] == "guest")
    assert row["table_count"] == 2
    compared = next(
        r
        for r in report["independent_source_counts"]
        if r["id"] == "yin-46" and r["camp"] == "guest"
    )
    assert compared["independent_count"] == 1
    assert compared["matches_table"] is False


def test_fitting_an_actual_board_to_a_printed_count_fails_independent_arithmetic(
    actuals,
):
    altered = copy.deepcopy(actuals)
    core = next(r["core"] for r in altered["boards"] if r["id"] == "yang-39")
    core["main_count"] = 25
    report = compare(altered)
    row = next(
        r
        for r in report["engine_arithmetic_failures"]
        if r["id"] == "yang-39" and r["camp"] == "main"
    )
    assert row["actual_matches_table"] is True
    assert row["independent_count_for_actual_inputs"] == 35
    assert row["engine_arithmetic_matches"] is False
    source = next(
        r
        for r in report["independent_source_counts"]
        if r["id"] == "yang-39" and r["camp"] == "main"
    )
    assert source["source_table_count"] == 25
    assert source["independent_count"] == 35


def test_shared_engine_recount_cannot_be_its_own_independent_oracle(actuals):
    altered = copy.deepcopy(actuals)
    assessment = next(
        r["assessment"] for r in altered["assessments"] if r["id"] == "yang-39"
    )
    next(r for r in assessment["counts"] if r["camp"] == "main")[
        "source_position_recount"
    ]["count"] = 25
    report = compare(altered)
    row = next(
        r
        for r in report["engine_source_recount_failures"]
        if r["id"] == "yang-39" and r["camp"] == "main"
    )
    assert row["engine_source_recount"] == 25
    assert row["independent_source_recount"] == 35
    assert row["recount_matches"] is False


@pytest.mark.parametrize("mutation", ["palace", "terminal"])
def test_right_total_does_not_hide_wrong_trace_facts(actuals, mutation):
    altered = copy.deepcopy(actuals)
    row = next(
        r
        for r in altered["count_grid"]
        if r["marker"] == "亥" and r["taiyi_number"] == 9
    )
    if mutation == "palace":
        row["trace"]["path"][0]["palace"] = "乾"
    else:
        row["trace"]["terminal_excluded"] = False
    result = compare(altered)
    row = next(
        r
        for r in result["reference_controls"]
        if r["marker"] == "亥" and r["taiyi_number"] == 9
    )
    assert row["actual_trace"]["count"] == 16
    assert row["count_matches"] is True
    assert row["trace_matches"] is False
    assert len(result["reference_control_failures"]) == 1


@pytest.mark.parametrize("group", ["count_grid", "boards"])
def test_bool_cannot_impersonate_integer_palace_identity(actuals, group):
    altered = copy.deepcopy(actuals)
    if group == "count_grid":
        row = next(r for r in altered[group] if r["taiyi_number"] == 1)
        row["taiyi_number"] = True
    else:
        row = next(r["core"] for r in altered[group] if r["core"]["taiyi_number"] == 1)
        row["taiyi_number"] = True
    with pytest.raises(ValueError, match="类型"):
        compare(altered)


@pytest.mark.parametrize("key", ["count_grid", "boards", "assessments"])
def test_missing_or_duplicate_runtime_rows_cannot_reduce_the_denominator(actuals, key):
    for duplicate in (False, True):
        altered = copy.deepcopy(actuals)
        if duplicate:
            altered[key][0] = copy.deepcopy(altered[key][1])
        else:
            altered[key].pop()
        with pytest.raises(ValueError, match="128|144"):
            compare(altered)


@pytest.mark.parametrize("name", ["reference-grid.json", "source-inputs.json"])
def test_changed_expected_value_or_source_table_is_rejected(tmp_path, name):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    (corpus / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        verify(corpus)


def test_source_only_isolated_entry_does_not_import_production_or_claim_runtime_acceptance(
    tmp_path,
):
    script = ROOT / "scripts/taiyi/audit_taiyi_jinjing_arithmetic.py"
    modules = {
        n.module.split(".")[0]
        for n in ast.walk(ast.parse(script.read_text()))
        if isinstance(n, ast.ImportFrom) and n.module
    }
    modules |= {
        a.name.split(".")[0]
        for n in ast.walk(ast.parse(script.read_text()))
        if isinstance(n, ast.Import)
        for a in n.names
    }
    assert modules <= {
        "__future__",
        "argparse",
        "copy",
        "hashlib",
        "json",
        "pathlib",
        "typing",
    }
    output = tmp_path / "source.json"
    process = subprocess.run(
        [sys.executable, "-I", str(script), "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1
    assert "Traceback" not in process.stderr
    summary = json.loads(process.stdout)
    assert summary["runtime_assessed"] is False
    assert summary["engine_arithmetic_failures"] is None
    assert summary["reference_control_failures"] is None
    report = json.loads(output.read_text())
    assert report["runtime_assessed"] is False
    assert report["reference_controls"] == report["actual_core_counts"] == []
    assert report["whole_classic_acceptance_passed"] is False
