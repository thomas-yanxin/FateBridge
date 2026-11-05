"""Literal numeric witness, declared algebra readings and retained uncertainty."""

import copy
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.jyotish.audit_jyotish_santhanam_drishti import (
    build_report,
    commentary_values,
    given_benefic_drik_readings,
    ordinary,
    speculum_rows,
    verse_values,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/jyotish-santhanam-drishti-primary.json"
PRIMARY = json.loads(FIXTURE.read_text())
HAND = json.loads(
    (ROOT / "tests/fixtures/jyotish-santhanam-drishti-hand-probes.json").read_text()
)


def test_source_seal_and_complete_literal_table():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == (
        "ab77bddd393fe930824c1080f39d0f1b6507b9424952c88b3106e90bbf1e2eba"
    )
    rows = speculum_rows(PRIMARY)
    assert len(rows) == 540
    assert sum(r["equal"] for r in rows) == 538
    assert [rows[0]["angle_degrees"], rows[-1]["angle_degrees"]] == ["30", "599/2"]
    conflicts = [r for r in rows if not r["equal"]]
    assert [(r["angle_degrees"], r["printed"]) for r in conflicts] == [
        ("555/2", "11.75"),
        ("276", "11.50"),
    ]
    assert PRIMARY["commentary_additions"]["Mars"]["strict_interiors"][1][1] == "249"


@pytest.mark.parametrize(
    "row", HAND["hand_probes"], ids=lambda r: r["body"] + r["angle"]
)
def test_algebra_probes_frozen_before_auditor_implementation(row):
    x = Fraction(row["angle"])
    assert commentary_values(PRIMARY, row["body"], x) == [Fraction(row["commentary"])]
    assert verse_values(row["body"], x, False) == [Fraction(row["verse_exact6"])]
    assert verse_values(row["body"], x, True) == [Fraction(row["verse_sector6"])]


def test_all_grid_positions_and_unresolved_cases_remain_present():
    report = build_report(PRIMARY)
    dense = report["dense_comparison"]
    assert len(dense["rows"]) == dense["positions"] == 2160
    assert dense["candidate_sets_differ"] == 677
    assert dense["positions_with_endpoint_ambiguity"] == 12
    for body in ["Mars", "Jupiter", "Saturn"]:
        assert {
            Fraction(r["angle_degrees"]) for r in dense["rows"] if r["body"] == body
        } == {Fraction(i, 2) for i in range(720)}
    assert report["production_activation_eligible"] is False
    assert report["complete_single_original_accepted"] is False
    assert report["ordinary_speculum"]["unique_literal_coordinates"] == 538
    assert report["ordinary_speculum"]["terminal300_not_printed"] is True
    assert report["independent_real_event_cases"] == 0


@pytest.mark.parametrize(
    "body,x,expected",
    [
        ("Mars", 249, ["51/2", "81/2"]),
        ("Saturn", 270, ["15", "60"]),
        ("Jupiter", 150, ["0", "30"]),
    ],
)
def test_commentary_endpoints_do_not_select_the_larger_value(body, x, expected):
    assert commentary_values(PRIMARY, body, Fraction(x)) == list(
        map(Fraction, expected)
    )


def test_special_verse_reading_endpoints_keep_both_algebraic_neighbors():
    assert verse_values("Saturn", Fraction(270), False) == [0, 60]
    assert verse_values("Jupiter", Fraction(270), False) == [15, 30]
    assert verse_values("Mars", Fraction(210), False) == [45, 60]
    assert verse_values("Mars", Fraction(210), True) == [60]


def test_table_never_adjudicates_direction_or_extra_clause():
    report = build_report(PRIMARY)
    assert len(report["ordinary_speculum"]["conflicts"]) == 2
    assert not report["direction_probe"]["direction_uniquely_selected"]
    assert list(map(Fraction, report["direction_probe"]["ordinary_values"])) == [
        30,
        Fraction("7.5"),
    ]
    assert given_benefic_drik_readings(Fraction(0), Fraction(60), Fraction(30)) == {
        "quarter_only_raman120": Fraction("22.5"),
        "whole_replaces_quarter": Fraction(90),
        "whole_superadded_after_quarter": Fraction("112.5"),
    }
    assert set(
        given_benefic_drik_readings(Fraction(-120), Fraction(0), Fraction(0)).values()
    ) == {-30}


def test_altered_printed_value_is_detected_without_dropping_the_cell():
    changed = copy.deepcopy(PRIMARY)
    changed["ordinary_speculum"]["columns"][0]["values"][0] = "0.01"
    report = build_report(changed)
    assert report["ordinary_speculum"]["printed_cells"] == 540
    assert len(report["ordinary_speculum"]["conflicts"]) == 3


@pytest.mark.parametrize("fault", ["missing_cell", "wrong_end", "duplicate_column"])
def test_incomplete_or_duplicate_source_domain_is_rejected(fault):
    changed = copy.deepcopy(PRIMARY)
    columns = changed["ordinary_speculum"]["columns"]
    if fault == "missing_cell":
        columns[0]["values"].pop()
    elif fault == "wrong_end":
        columns[0]["end"] = [40, 30]
    else:
        columns.append(copy.deepcopy(columns[0]))
    with pytest.raises(ValueError):
        speculum_rows(changed)


def test_standalone_pure_gate_preserves_failures_and_never_overwrites(tmp_path):
    # An isolated standard-library invocation needs no installed FateBridge.
    script = ROOT / "scripts/jyotish/audit_jyotish_santhanam_drishti.py"
    result = tmp_path / "result.json"
    cmd = [sys.executable, "-I", str(script), "--report"]
    before = FIXTURE.read_bytes()
    completed = subprocess.run([*cmd, str(result)], capture_output=True)
    assert completed.returncode == 1, completed.stderr
    assert (
        json.loads(result.read_text())["status"]
        == "selected_witness_readings_not_uniquely_adjudicated"
    )
    for target in [result, FIXTURE]:
        raw = target.read_bytes()
        rejected = subprocess.run([*cmd, str(target)], capture_output=True)
        assert rejected.returncode == 2
        assert target.read_bytes() == raw
    assert FIXTURE.read_bytes() == before
