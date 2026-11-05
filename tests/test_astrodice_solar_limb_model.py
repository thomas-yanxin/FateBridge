"""Preserve model disagreement; a fitting diagnostic is not production success."""

import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_solar_limb_reference import replay
from scripts.audit_astrodice_solar_limb import (
    audit,
    direction,
    independent_aberration,
    separation,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/astrodice/solar_limb"


def read(name, root=FIXTURE):
    return json.loads((root / name).read_text())


@pytest.fixture(scope="module")
def current_rows():
    rows = {}
    original = read("geometric-reference.json", FIXTURE / "source-records")["rows"]
    selected = read("selection-first.json")["cohorts"]
    for cohort in ["A", "B"]:
        rows[cohort] = []
        for index, case in enumerate(selected[cohort]):
            kernel = (
                FIXTURE
                / "source-records"
                / original[case["window_index"]]["kernel_path"]
            )
            with pytest.MonkeyPatch.context() as env:
                env.setenv("SE_EPHE_PATH", str(kernel.parent))
                env.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
                rows[cohort].append(audit(FIXTURE, cohort, index))
    return rows


def test_independent_geometry_selects_the_same_32_conditions_without_candidate(
    tmp_path,
):
    output = tmp_path / "selection.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.select_astrodice_solar_limb",
            "--run",
            str(FIXTURE),
            "--fixture",
            str(FIXTURE / "source-records"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    selected = json.loads(output.read_text())
    assert selected == read("selection-first.json")
    assert [len(selected["cohorts"][cohort]) for cohort in ["A", "B"]] == [16, 16]
    assert not selected["candidate_or_apparent_residual_used"]
    assert not selected["physical_TT_TDB_conversion_certified"]


@pytest.mark.parametrize(
    "cohort,encoding", [(c, e) for c in ["A", "B"] for e in ["JD", "MJD"]]
)
def test_both_source_encodings_replay_every_planned_centre(cohort, encoding):
    prefix = cohort + "-" + encoding
    result = replay(
        FIXTURE / (prefix + "-protocol.json"),
        FIXTURE / (prefix + "-reference-first.json"),
        FIXTURE / (prefix + "-raw"),
    )
    assert len(result["rows"]) == 16
    assert all(row["status"] == "position_reference_replayed" for row in result["rows"])
    assert not result["rejected_epoch_rows"]
    assert (
        not result["rate_accuracy_assessed"]
        and not result["candidate_accuracy_assessed"]
    )
    for row in result["rows"]:
        point = row["observation"]
        if point["primary_visibility_code"] == "o":
            assert not point["primary_visibility_code_documented_exactly"]


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_default_and_global_no_gr_failures_cannot_be_replaced_by_piecewise_success(
    cohort,
    current_rows,
):
    rows = current_rows[cohort]
    assert (
        sum(Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1 for row in rows)
        == 8
    )
    for row in rows:
        inside = Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1
        assert (
            not row["production_formula_changed"] and not row["rate_accuracy_assessed"]
        )
        assert row["hypotheses_are_diagnostics_not_production_acceptance"]
        assert not row["full_goal_complete"]
        for value in row["comparisons"].values():
            tests = value["native_comparisons"]
            assert tests["default"]["status"] == (
                "numeric_failure" if inside else "declared_position_line_satisfied"
            )
            assert tests["no_GR"]["status"] == (
                "declared_position_line_satisfied" if inside else "numeric_failure"
            )
            assert (
                tests["piecewise_background_inside_no_GR"]["status"]
                == "declared_position_line_satisfied"
            )
            assert tests["piecewise_background_inside_no_GR"][
                "selected_native_mode"
            ] == ("no_GR" if inside else "default")
            assert tests["astrometric"]["status"] == "declared_position_line_satisfied"
            assert tests["no_aberration"]["status"] == "numeric_failure"
            assert all(test["fixed_line_arcsec"] == 0.02 for test in tests.values())
        assert (
            row["states"]["default"]["state_xyz_AU_and_AU_per_day"]
            == row["states"]["default_after_controls"]["state_xyz_AU_and_AU_per_day"]
        )
        assert row["native_default_repeat_drift_arcsec"] == 0


def test_independent_published_astrometric_aberration_keeps_the_source_signal(
    current_rows,
):
    for rows in current_rows.values():
        for row in rows:
            inside = Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1
            for value in row["comparisons"].values():
                result = independent_aberration(
                    FIXTURE,
                    row["case"],
                    value["observation"]["astrometric_printed_angles"],
                )
                error = separation(
                    result["direction"],
                    direction(value["observation"]["apparent_printed_angles"]),
                )
                assert (error < 0.02) == inside
                assert not result["candidate_accuracy_certified"]


def test_a_hidden_rate_claim_or_relaxed_epoch_budget_is_rejected_even_after_hash_rebinding(
    tmp_path,
):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "B-JD-protocol.json"
    plan = json.loads(path.read_text())
    plan["timestamp_printing_tolerance_days"] = "2e-9"
    path.write_text(json.dumps(plan))
    refpath = data / "B-JD-reference-first.json"
    raw = json.loads(refpath.read_text())
    raw["protocol_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    refpath.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Position-only protocol"):
        replay(path, refpath, data / "B-JD-raw")


def test_an_available_raw_centre_cannot_be_omitted(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "B-MJD-reference-first.json"
    raw = json.loads(path.read_text())
    raw["rows"][0]["samples"]["0"] = None
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Stored position differs"):
        replay(data / "B-MJD-protocol.json", path, data / "B-MJD-raw")
