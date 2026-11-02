"""Source arithmetic is independent of the unactivated native mean model."""

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.jyotish_motion import cheshta_arc
from scripts.audit_jyotish_motion import (
    audit_tables,
    build_report,
    compare_oracle_tables,
    primary_angular_reference,
)

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = json.loads((ROOT / "tests/fixtures/jyotish-motion-primary.json").read_text())


def calculate(mean, true, apogee, **updates):
    return cheshta_arc(
        mean,
        true,
        apogee,
        **{
            "mean_frame": "declared_test_frame",
            "true_frame": "declared_test_frame",
            "seeghrochcha_frame": "declared_test_frame",
            **updates,
        },
    )


@pytest.mark.parametrize(
    "case", PRIMARY["worked_angular_cases"], ids=lambda v: v["planet"]
)
def test_primary_printed_angular_cases_without_fitting_mean_model(case):
    result = calculate(*(float(case[k]) for k in ("mean", "true", "seeghrochcha")))
    assert result["status"] == "calculated_arc"
    assert result["value"] == pytest.approx(
        float(case["printed_virupa"]), abs=0.0051, rel=0
    )
    assert result["value"] == pytest.approx(
        primary_angular_reference(case), abs=1e-12, rel=0
    )


@pytest.mark.parametrize(
    "mean,true,apogee,expected",
    [
        (350, 10, 180, 60),
        (10, 350, 180, 60),
        (-10, 10, 90, 30),
        (0, 20, 10, 0),
        (100, 140, 300, 60),
        (100, 140, 30, 30),
        (100, 140, 330, 50),
        (0, 0, 300, 20),
    ],
)
def test_hand_arcs_fold_and_unwrap_the_midpoint(mean, true, apogee, expected):
    result = calculate(mean, true, apogee)
    assert result["value"] == expected
    assert 0 <= result["branches"][0]["reduced_kendra"] <= 180
    for rotate in range(0, 360, 15):
        rotated = calculate(
            (mean + rotate) % 360, (true + rotate) % 360, (apogee + rotate) % 360
        )
        assert rotated["value"] == result["value"]


def test_large_integral_longitudes_normalize_without_float_overflow():
    assert calculate(360 * 10**1000 + 350, 10, 180)["value"] == 60


def test_opposed_midpoint_never_selects_the_more_favourable_branch():
    result = calculate(0, 180, 100)
    assert result["value"] is None
    assert result["status"] == "opposed_midpoint_not_adjudicated"
    assert {row["midpoint"] for row in result["branches"]} == {90, 270}
    assert sorted(row["virupa"] for row in result["branches"]) == pytest.approx(
        [10 / 3, 170 / 3]
    )
    before = calculate(0, math.nextafter(180, 0), 100)
    after = calculate(0, math.nextafter(180, 360), 100)
    assert before["status"] == after["status"] == "calculated_arc"
    assert abs(before["value"] - after["value"]) > 50


@pytest.mark.parametrize("key", ["mean_frame", "true_frame", "seeghrochcha_frame"])
def test_historical_and_native_frames_cannot_be_silently_combined(key):
    with pytest.raises(ValueError, match="frames must match"):
        calculate(1, 2, 3, **{key: "native_Lahiri"})
    with pytest.raises(ValueError, match="nonempty"):
        calculate(1, 2, 3, **{key: " "})


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1"])
@pytest.mark.parametrize("index", range(3))
def test_invalid_angular_values_are_rejected(bad, index):
    values = [1, 2, 3]
    values[index] = bad
    with pytest.raises(ValueError, match="finite real"):
        calculate(*values)


def test_complete_literal_table_audit_keeps_unknown_glyphs_and_all_conflicts():
    count = sum(
        len(row) for table in PRIMARY["tables"].values() for row in table["rows"]
    )
    assert count == 252
    result = audit_tables(PRIMARY)
    assert result["evaluated_relations"] == 383
    assert len(result["skipped_unclear_relations"]) == 9
    assert result["conflicts"]
    jupiter = next(
        row
        for row in result["conflicts"]
        if row["body"] == "Jupiter"
        and row["column_days"] == 1000
        and row["rows"] == [3, 9]
    )
    assert jupiter["literal_cells"] == ["249.29", "78.87"]
    assert jupiter["residual_degrees"] == 51
    assert jupiter["material_over_0_1_degree"]


def test_primary_interval_and_missing_term_failures_remain_explicit():
    report = build_report(PRIMARY)
    assert report["interval_arithmetic"]["float_days"] == pytest.approx(
        6862 + (14 * 3600 - 4) / 86400
    )
    assert report["interval_arithmetic"]["14h_minus_printed_seconds"] == pytest.approx(
        201.6
    )
    assert report["venus_example48"]["unexplained_gap"] == 3.20
    assert not report["native_activation_eligible"]
    assert report["independent_real_event_cases"] == 0


def test_source_audit_cli_exits_nonzero_without_mutating_the_reference(tmp_path):
    fixture = ROOT / "tests/fixtures/jyotish-motion-primary.json"
    before = hashlib.sha256(fixture.read_bytes()).hexdigest()
    path = tmp_path / "audit.json"
    process = subprocess.run(
        [sys.executable, "-m", "scripts.audit_jyotish_motion", "--report", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1, process.stderr
    assert json.loads(path.read_text())["status"] == "source_table_not_consistent"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("which", ["primary", "oracle"])
def test_audit_report_cannot_overwrite_its_reference_inputs(tmp_path, which):
    # Use a disposable project copy: a broken guard must not corrupt repo data.
    script = tmp_path / "scripts/audit_jyotish_motion.py"
    script.parent.mkdir()
    script.write_bytes((ROOT / "scripts/audit_jyotish_motion.py").read_bytes())
    primary = tmp_path / "tests/fixtures/jyotish-motion-primary.json"
    primary.parent.mkdir(parents=True)
    primary.write_bytes(
        (ROOT / "tests/fixtures/jyotish-motion-primary.json").read_bytes()
    )
    oracle = tmp_path / "oracle.json"
    oracle.write_bytes(
        (ROOT / "tests/fixtures/jyotish-motion-reference.json").read_bytes()
    )
    report = primary if which == "primary" else oracle
    before = report.read_bytes()
    result = subprocess.run(
        [sys.executable, str(script), "--report", str(report), "--oracle", str(oracle)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "must not overwrite" in result.stderr
    assert report.read_bytes() == before


def test_reference_table_differences_remain_counterevidence():
    oracle = json.loads(
        (ROOT / "tests/fixtures/jyotish-motion-reference.json").read_text()
    )
    assert oracle["provenance"]["version"] == "4.8.7"
    result = compare_oracle_tables(PRIMARY, oracle)
    assert result["compared_clear_cells"] == 250
    difference = next(
        row
        for row in result["differences"]
        if row["body"] == "Sun" and row["row"] == 2 and row["column_days"] == 1000
    )
    assert difference["printed"] == "71.2053"
    assert difference["software"] == 171.2053
    case = next(
        row for row in oracle["examples"] if row["interval_reported_by_oracle"] == 8.25
    )
    mean = case["mean_outputs_by_internal_index"]
    assert mean["linear_mean"]["Sun"] - mean["table_mean"]["Sun"] == pytest.approx(
        7.8848, abs=1e-10, rel=0
    )
    # Table lookup discarded the8 unit days; do not copy that implementation.
    assert any(
        value > 60
        for row in oracle["examples"]
        for values in row["raw_cheshta_lists"].values()
        if isinstance(values, list)
        for value in values
    )
