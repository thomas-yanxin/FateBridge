"""Transport repair supplements first failures; native results stay scoped."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.audit_astrodice_venus_epoch import recovery_comparison

ROOT = Path(__file__).resolve().parents[1]
FIRST = ROOT / "tests/fixtures/astrodice-venus-epoch-v1"
FIXTURE = FIRST.with_name("astrodice-venus-epoch-recovery-v1")
PASS = "declared_lines_satisfied_under_reference_model"
UNKNOWN = "reference_quality_unresolved"


def read(path):
    return json.loads(path.read_text())


def test_both_phases_are_frozen_without_replacing_the_first_outages():
    assert hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest() == (
        "8a15e42442811afbc9197fea4233281719c6df5658d62ceffe3c1ff3ade4f7d9"
    )
    manifest = read(FIXTURE / "manifest.json")
    assert (
        hashlib.sha256((FIRST / "manifest.json").read_bytes()).hexdigest()
        == manifest["first_fixture_manifest_sha256"]
    )
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    original = read(FIXTURE / "candidate-seal-before-A.json")["candidate_files"]
    updated = read(FIXTURE / "recovery-source-seal.json")["files"]
    assert {n: v for n, v in original.items() if n.startswith("src/fatebridge/")} == {
        n: v for n, v in updated.items() if n.startswith("src/fatebridge/")
    }


def test_recovery_reuses_successes_and_preserves_all_three_complete_paths():
    result = recovery_comparison(FIRST, FIXTURE / "recovery-first")
    assert result == read(FIXTURE / "serial-recovery-comparison.json")
    assert (
        not result["first_failures_replaced"] and result["new_holdout_conditions"] == 0
    )
    encodings = result["encodings"]
    assert sum(v["original_success_batches_reused"] for v in encodings.values()) == 166
    assert (
        sum(v["failed_original_batches_resubmitted"] for v in encodings.values()) == 29
    )
    assert all(v["first_reference_exit_code"] == 2 for v in encodings.values())
    assert {k: v["followup_reference_exit_code"] for k, v in encodings.items()} == {
        "JD": 0,
        "MJD": 2,
        "CAL": 2,
    }
    assert encodings["JD"]["coverage"]["accepted_primary_points"] == 1154
    assert all(
        encodings[k]["coverage"]["rejected_epoch_rows"] == 26 for k in ["MJD", "CAL"]
    )


def test_actual_native_outputs_keep_position_rate_and_source_evidence_distinct():
    physical = read(FIXTURE / "before-first-candidate.json")["physical_files"]
    for name, digest in physical.items():
        relative = name.replace("astrodice-de441-records-v1/", "source-records/", 1)
        assert hashlib.sha256((FIXTURE / relative).read_bytes()).hexdigest() == digest
    for model in ["swieph", "jpl"]:
        for encoding in ["JD", "MJD", "CAL"]:
            value = read(
                FIXTURE
                / "recovery-first"
                / f"B-{encoding}-{model}-candidate-first.json"
            )
            assert value["exit_code"] == (0 if encoding == "JD" else 2)
            assert value["all_planned_case_count"] == 2
            assert not value["candidate_numerical_formula_changed"]
            assert value["fixed_position_arcsec"] == 0.02
            assert value["fixed_rate_arcsec_per_day"] == 0.002
            assert not value["physical_sources"]["has_unidentified_sources"]
            for file in value["physical_sources"]["files"]:
                assert file["sha256"] in physical.values()
            for row in value["rows"]:
                position, rate = row["layers"]["position"], row["layers"]["rate"]
                assert position["status"] == PASS
                assert position["conditional_error_upper_arcsec"] <= 0.02
                assert rate["status"] == (PASS if encoding == "JD" else UNKNOWN)
                if encoding == "JD":
                    assert set(rate["frames"]) == {"tropical", "lahiri"}
                    for frame in rate["frames"].values():
                        assert (
                            frame["policy"]["method_id"]
                            == "fatebridge_complete_position_derivative_v8"
                        )
                        error = abs(
                            frame["candidate_rate_degrees_per_day"] * 3600
                            - frame["reference"]["midpoint_arcsec_per_day"]
                        )
                        assert error == frame["midpoint_error_arcsec_per_day"]
                        assert (
                            frame["conditional_error_upper_arcsec_per_day"]
                            == error
                            + frame["reference"][
                                "rounding_and_frame_check_radius_arcsec_per_day"
                            ]
                        )
                        assert frame["conditional_error_upper_arcsec_per_day"] <= 0.002


def test_recovery_cannot_omit_an_original_failed_request(tmp_path):
    recovery = tmp_path / "recovery"
    shutil.copytree(FIXTURE / "recovery-first", recovery)
    path = recovery / "B-JD-raw/requests.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    first_new = next(
        i for i, value in enumerate(entries) if value["network_request_performed"]
    )
    entries.pop(first_new)
    path.write_text("".join(json.dumps(value) + "\n" for value in entries))
    with pytest.raises(ValueError, match="Recovery request set changed"):
        recovery_comparison(FIRST, recovery)
