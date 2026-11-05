"""Visible readings remain literal despite absent text and numeric conflicts."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

import fatebridge.core.guolao_grid as module

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-grid-markers-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_marker_dataset_primary_scan_and_resampled_reading_aid_have_fingerprints():
    assert (
        hashlib.sha256((FIXTURE / REFERENCE["source_image"]).read_bytes()).hexdigest()
        == REFERENCE["source_image_sha256"]
    )
    assert (
        hashlib.sha256(module.MARKER_DATA.read_bytes()).hexdigest()
        == REFERENCE["marker_data_sha256"]
    )
    aid = REFERENCE["reading_aid"]
    assert (
        hashlib.sha256((FIXTURE / aid["file"]).read_bytes()).hexdigest()
        == aid["sha256"]
    )
    assert not REFERENCE["independent_second_collator"]


@pytest.mark.parametrize("case", REFERENCE["held_cases"])
def test_held_visible_text_is_not_replaced_with_the_next_number_plus_one(case):
    r = module.load_grid().cell(case["palace"], case["column"])
    reading = r["marker_reading"]
    for k, v in case.items():
        assert reading[k] == v
    assert r["numeral_value"] is None  # Existing ordinary-cell field keeps its scope.
    assert not reading["coordinate_semantics_accepted"]
    assert r["continuous_historical_degree"] is None


def test_all_39_readings_are_recorded_without_a_fake_number_for_initial_or_blank():
    g = module.load_grid()
    a = g.audit()
    assert a["marker_readings_recorded"] == 39
    assert a["marker_reading_counts"] == REFERENCE["reading_counts"]
    assert a["all_marker_readings_recorded"]
    assert not a["marker_numeric_values_complete"]
    assert not a["marker_coordinate_semantics_accepted"]
    assert not a["full_360_cell_numerical_mapping_accepted"]
    assert not a["life_degree_accepted"]
    assert a["marker_data_sha256"] == REFERENCE["marker_data_sha256"]


def test_all_three_new_numeric_conflicts_and_the_earlier_unmarked_restart_remain():
    a = module.load_grid().audit()
    assert len(a["marker_to_regular_numeric_discontinuities"]) == 3
    for expected, actual in zip(
        REFERENCE["new_marker_discontinuities"],
        a["marker_to_regular_numeric_discontinuities"],
    ):
        for k, v in expected.items():
            assert actual[k] == v
        assert not actual["meaning_adjudicated"]
        assert not actual["label_or_column_corrected"]
    assert a["unmarked_numeric_restarts"][0]["from_column"] == 14
    assert a["unmarked_numeric_restarts"][0]["to_column"] == 15


@pytest.mark.parametrize(
    "palace,mansion,text,column",
    [("子", "虚", "九", 12), ("辰", "轸", "十四", 23), ("丑", "斗", None, 10)],
)
def test_literal_marker_lookup_returns_exact_declared_source_not_a_life_degree(
    palace, mansion, text, column
):
    r = module.load_grid().compare_marker(
        source_palace=palace, target_palace="午", mansion=mansion, attached_text=text
    )
    assert r["source_cell"]["column"] == r["target_cell"]["column"] == column
    assert r["matched_marker"]["text"] == text
    assert r["column_shift_applied"] == 0
    assert r["life_degree"] is None and not r["life_degree_accepted"]


@pytest.mark.parametrize(
    "palace,mansion,text",
    [
        ("子", "危", "十一"),
        ("辰", "轸", "十七"),
        ("午", "柳", "十三"),
        ("丑", "斗", "二十三"),
        ("丑", "斗", "零"),
        ("辰", "氐", None),
        ("子", "虚", "9"),
    ],
)
def test_mismatching_guesses_and_filled_blank_are_rejected(palace, mansion, text):
    with pytest.raises(ValueError, match="附字"):
        module.load_grid().compare_marker(
            source_palace=palace,
            target_palace="午",
            mansion=mansion,
            attached_text=text,
        )


@pytest.mark.parametrize("value", [9, 9.0, Fraction(9), True])
def test_literal_text_argument_is_not_a_continuous_numeric_coordinate(value):
    with pytest.raises(TypeError):
        module.load_grid().compare_marker(
            source_palace="子", target_palace="午", mansion="虚", attached_text=value
        )


def test_incomplete_or_duplicated_readings_are_not_silently_joined():
    g = module.load_grid()
    with pytest.raises(ValueError):
        replace(g, marker_readings=g.marker_readings[:-1])
    with pytest.raises(ValueError):
        replace(g, marker_readings=())
    with pytest.raises(ValueError):
        replace(g, marker_readings=(*g.marker_readings, g.marker_readings[0]))
    with pytest.raises(ValueError):
        replace(
            g,
            marker_readings=(
                replace(g.marker_readings[0], mansion="女"),
                *g.marker_readings[1:],
            ),
        )
    readings = list(g.marker_readings)
    frozen = replace(g, marker_readings=readings)
    readings.pop()
    assert len(frozen.marker_readings) == 39


def test_overlay_rejects_different_matrix_or_source_scan_fingerprints(
    tmp_path, monkeypatch
):
    raw = json.loads(module.MARKER_DATA.read_text())
    for field in ["matrix_data_sha256", "source_image_sha256", "matrix_source_id"]:
        altered = {**raw, field: "different_source"}
        path = tmp_path / f"{field}.json"
        path.write_text(json.dumps(altered))
        monkeypatch.setattr(module, "MARKER_DATA", path)
        with pytest.raises(ValueError, match="跨版本"):
            module.load_grid()


@pytest.mark.parametrize(
    "kind,text,value,error",
    [
        ("integer", "九", 9.0, TypeError),
        ("integer", "九", True, TypeError),
        ("integer", "九", 10, ValueError),
        ("initial", "初", 0, ValueError),
        ("not_visible", None, 0, ValueError),
        ("not_visible", "初", None, ValueError),
    ],
)
def test_reading_types_do_not_turn_missing_or_initial_into_zero(
    kind, text, value, error
):
    with pytest.raises(error):
        module.MarkerReading("子", 12, "虚", kind, text, value)


@pytest.mark.parametrize(
    "args,expected_column",
    [
        (["--source-marker", "虚", "--marker-text", "九", "--source-palace", "子"], 12),
        (
            ["--source-marker", "斗", "--marker-not-visible", "--source-palace", "丑"],
            10,
        ),
    ],
)
def test_cli_marker_mode_requires_and_preserves_the_literal_source_selection(
    args, expected_column
):
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/guolao/audit_guolao_life_grid.py"),
            *args,
            "--target-palace",
            "午",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    r = json.loads(proc.stdout)["comparison"]
    assert r["source_cell"]["column"] == expected_column
    assert r["column_selection"] == "exact_named_marker_and_attached_text"


@pytest.mark.parametrize(
    "args",
    [
        ["--marker-text", "九"],
        ["--source-marker", "虚", "--source-palace", "子", "--target-palace", "午"],
        [
            "--column",
            "12",
            "--source-palace",
            "子",
            "--target-palace",
            "午",
            "--marker-text",
            "九",
        ],
    ],
)
def test_cli_does_not_guess_missing_source_arguments(args):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/guolao/audit_guolao_life_grid.py"), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2 and not proc.stdout
