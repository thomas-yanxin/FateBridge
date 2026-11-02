"""Full old targets, source errors and newly readable literals remain distinct."""

import copy
import json
import shutil
import subprocess
import sys

import pytest

from scripts.audit_taiyi_wujing_cycles import audit as literal_audit
from scripts.audit_taiyi_wujing_facsimile import (
    CORPUS,
    ROOT,
    audit,
    compare,
    verify,
)


@pytest.fixture(scope="module")
def report():
    return audit()


@pytest.mark.parametrize(
    "target", verify()["readings"], ids=lambda r: r["id"] + "_" + r["field"]
)
def test_every_original_unknown_has_its_native_reading_without_dropping_a_target(
    report, target
):
    row = next(
        r
        for r in report["target_comparisons"]
        if (r["id"], r["field"]) == (target["id"], target["field"])
    )
    assert row["native_reading"] == target
    assert row["original_comparison"]["comparison_status"] == "unknown"
    assert row["effective_source_value"] == target["value"]
    if target["value"] is None:
        assert row["comparison_status"] == "unknown"


def test_original_1440_layer_and_all_original_differences_are_unchanged(report):
    old = literal_audit()
    assert report["original_layer"] == old
    assert report["current_literal_layer"] == old
    assert old == json.loads(
        (ROOT / "docs/validation/taiyi-jinjing-v22/report.json").read_text()
    )
    assert report["old_differences_retained"] == old["differences"]
    assert len(old["differences"]) == len(old["unknowns"]) == 45
    assert report["required_rows"] == 144
    assert report["required_observations"] == 1440
    assert len(report["source_rows"]) == 144
    assert all(len(r["comparisons"]) == 10 for r in report["source_rows"])
    assert report["native_values_clarified"] == 13
    for counts in report["field_totals"].values():
        assert (
            counts["required"]
            == sum(counts[k] for k in ["matching", "different", "unknown"])
            == 144
        )
    assert report["whole_classic_acceptance_passed"] is False
    assert report["source_or_production_arithmetic_corrected"] is False
    assert report["new_dated_cases"] == report["new_model_calls"] == 0


def test_actual_mismatch_is_not_turned_into_an_unknown_or_fitted_source_value():
    readings = verify()
    old = literal_audit()
    changed = copy.deepcopy(old)
    row = next(r for r in changed["source_rows"] if r["id"] == "yang-53")
    value = next(r for r in row["comparisons"] if r["actual_field"] == "guest_general")
    value["actual_value"] = 6
    result = compare(changed, readings)
    current = next(
        r
        for r in result["target_comparisons"]
        if r["id"] == "yang-53" and r["field"] == "guest_general"
    )
    assert current["effective_source_value"] == 5
    assert current["actual_value"] == 6
    assert current["comparison_status"] == "different"
    assert result["original_layer"] == old
    assert result["current_literal_layer"] == changed
    assert current["original_comparison"]["actual_value"] == 5
    assert current["current_literal_comparison"]["actual_value"] == 6
    assert old != changed
    assert readings == verify()


@pytest.mark.parametrize("name", ["native-readings.json", "native/page55.png"])
def test_changed_literal_or_native_image_is_rejected(tmp_path, name):
    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS, copied)
    (copied / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        verify(copied)


def test_documented_module_command_preserves_nonzero_classical_acceptance(tmp_path):
    path = tmp_path / "report.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.audit_taiyi_wujing_facsimile",
            "--output",
            str(path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert process.returncode == 1
    assert "Traceback" not in process.stderr
    report = json.loads(path.read_text())
    assert report["required_observations"] == 1440
    assert report["whole_classic_acceptance_passed"] is False
