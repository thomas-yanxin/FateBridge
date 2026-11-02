"""Held source readings and strict separation of incomplete witness grids."""

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.core.guolao_grid_witnesses as module
from fatebridge.core.guolao_grid import load_grid

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-grid-witnesses-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_actual_original_sources_and_each_read_view_match_the_recorded_bytes():
    for entry in REFERENCE["source_files"] + REFERENCE["reading_aids"]:
        assert (
            hashlib.sha256((FIXTURE / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
        )
    assert (
        hashlib.sha256(module.DATA.read_bytes()).hexdigest() == REFERENCE["data_sha256"]
    )
    assert not REFERENCE["second_independent_collator"]
    assert not REFERENCE["common_textual_ancestor_ruled_out"]


@pytest.mark.parametrize("case", REFERENCE["held_cases"])
def test_four_loci_preserve_each_named_source_and_the_old_grid(case):
    before = load_grid().cell(case["palace"], case["column"])
    result = module.compare_witnesses(palace=case["palace"], column=case["column"])
    base = result["base"]["reading"]
    assert base["mansion_marker"] == case["base_marker"]
    assert base["numeral_value"] == case["base_numeral"]
    assert base["attached_text"] == case["base_attached"]
    assert len(result["witnesses"]) == 2
    for witness in result["witnesses"]:
        reading = witness["reading"]
        assert reading["mansion_marker"] == case["witness_marker"]
        assert reading["attached_text"] == case["witness_attached"]
        assert reading["attached_integer"] == case["witness_integer"]
        assert reading["numeral_value"] is None
        assert witness["differs_from_base"]
        assert witness["source"]["source_sha256"]
        assert witness["source"]["credit"]
    assert result["witness_readings_agree"]
    assert result["column_shift_applied"] == 0
    for key in [
        "full_grid_collated",
        "base_reading_replaced",
        "second_independent_collator",
        "textual_genealogy_established",
        "life_degree_accepted",
        "used_in_native_birth_chart",
    ]:
        assert result[key] is False
    assert load_grid().cell(case["palace"], case["column"]) == before


@pytest.mark.parametrize(
    "palace,column,error",
    [
        ("子", 2, ValueError),
        ("丑", 10, ValueError),
        ("午", 29, ValueError),
        ("午", 0, ValueError),
        ("午", 31, ValueError),
        ("子午", 1, ValueError),
        ("子", True, TypeError),
        ("子", 1.0, TypeError),
    ],
)
def test_uncollated_or_invalid_positions_do_not_inherit_a_better_witness(
    palace, column, error
):
    with pytest.raises(error):
        module.compare_witnesses(palace=palace, column=column)


@pytest.mark.parametrize(
    "field", ["source_id", "source_image_sha256", "data_sha256", "marker_data_sha256"]
)
def test_changed_base_requires_new_collation(tmp_path, monkeypatch, field):
    data = json.loads(module.DATA.read_bytes())
    data["base_binding"][field] = "another-version"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", path)
    with pytest.raises(ValueError, match="重新校勘"):
        module.compare_witnesses(palace="子", column=1)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_reading",
        "duplicate_reading",
        "wrong_source",
        "duplicate_source",
        "empty_sources",
        "duplicate_locus",
    ],
)
def test_incomplete_or_mixed_witness_records_are_rejected(
    tmp_path, monkeypatch, mutation
):
    data = json.loads(module.DATA.read_bytes())
    readings = data["loci"][0]["readings"]
    if mutation == "missing_reading":
        readings.pop()
    elif mutation == "duplicate_reading":
        readings[1] = readings[0]
    elif mutation == "wrong_source":
        readings[1]["witness_id"] = "a-different-scan"
    elif mutation == "duplicate_source":
        data["witnesses"].append(data["witnesses"][0])
    elif mutation == "empty_sources":
        data["witnesses"] = []
    else:
        data["loci"].append(data["loci"][0])
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", path)
    with pytest.raises(ValueError):
        module.compare_witnesses(palace="子", column=1)


def test_attached_reading_cannot_be_reused_for_a_different_marker_or_column():
    from fatebridge.core.guolao_grid import GridCell, MarkerReading

    reading = module.WitnessCell(
        "explicit-scan",
        "子",
        1,
        GridCell("危", None, False),
        MarkerReading("子", 1, "危", "integer", "十一", 11),
    )
    with pytest.raises(ValueError):
        replace(reading, column=2)
    with pytest.raises(ValueError):
        replace(reading, cell=GridCell("虚", None, False))
    with pytest.raises(ValueError):
        replace(reading, witness_id="")


def test_actual_research_command_and_uncollated_error():
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_guolao_grid_witnesses.py"),
        "--palace",
        "午",
        "--column",
    ]
    result = subprocess.run(
        [*command, "15"], env=env, text=True, capture_output=True, check=True
    )
    actual = json.loads(result.stdout)
    assert actual == module.compare_witnesses(palace="午", column=15)
    error = subprocess.run([*command, "29"], env=env, text=True, capture_output=True)
    assert error.returncode != 0 and "未校勘" in error.stderr
    assert not error.stdout
