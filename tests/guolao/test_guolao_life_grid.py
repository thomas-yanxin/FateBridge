"""Frozen facsimile, held readings and no inherited or shifted life degree."""

import hashlib
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import BRANCHES
from fatebridge.core.guolao_grid import DATA, GridCell, load_grid

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-life-grid-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_primary_scan_runtime_matrix_and_attribution_are_fingerprinted():
    assert (
        hashlib.sha256((FIXTURE / REFERENCE["source_image"]).read_bytes()).hexdigest()
        == REFERENCE["source_image_sha256"]
    )
    assert (
        hashlib.sha256(DATA.read_bytes()).hexdigest()
        == REFERENCE["runtime_data_sha256"]
    )
    g = load_grid()
    assert g.data_sha256 == REFERENCE["runtime_data_sha256"]
    assert "東北大学附属図書館所蔵" in g.credit
    assert g.source_image_sha256 == REFERENCE["source_image_sha256"]


@pytest.mark.parametrize("case", REFERENCE["hand_cases"])
def test_held_primary_readings_cover_both_leaves_and_all_twelve_palaces(case):
    cell = load_grid().cell(case["palace"], case["column"])
    for field in ["numeral_value", "initial_marker", "mansion_marker"]:
        if field in case:
            assert cell[field] == case[field]
    assert cell["leaf"] == ("right" if case["column"] <= 14 else "left")
    assert cell["inherited_mansion"] is None
    assert cell["continuous_historical_degree"] is None


def test_counts_distinguish_numeral_initial_and_untranscribed_marker_numbers():
    g = load_grid()
    r = g.audit()
    assert len(g.rows) == 12 and all(len(row) == 30 for row in g.rows)
    for field in [
        "positioned_cells",
        "regular_numeral_cells",
        "initial_marker_cells",
        "mansion_marker_cells",
    ]:
        assert r[field] == REFERENCE[field]
    for palace in BRANCHES:
        for column in range(1, 31):
            c = g.cell(palace, column)
            if c["mansion_marker"] or c["initial_marker"]:
                assert c["numeral_value"] is None
            assert c["modern_longitude"] is None
    assert not r["full_360_cell_numerical_mapping_accepted"]
    assert r["marker_attached_numerals_collated"]
    assert not r["marker_numeric_values_complete"]
    assert not r["fractional_tail_cells_collated"]


def test_unmarked_restart_is_reported_without_a_guessed_star_or_repair():
    r = load_grid().audit()
    assert len(r["unmarked_numeric_restarts"]) == 1
    jump = r["unmarked_numeric_restarts"][0]
    for key, value in REFERENCE["unmarked_restart"].items():
        assert jump[key] == value
    assert jump["new_mansion_inferred"] is None
    assert not jump["label_or_column_corrected"]


@pytest.mark.parametrize("case", REFERENCE["introductory_comparisons"])
def test_image9_discrepancies_remain_and_no_column_is_chosen_to_match_them(case):
    r = load_grid().compare(
        source_palace=case["source_palace"],
        target_palace=case["target_palace"],
        column=case["column"],
    )
    assert r["source_cell"]["numeral_value"] == case["source_numeral"]
    assert r["target_cell"]["numeral_value"] == case["same_column_numeral"]
    assert r["target_cell"]["numeral_value"] != case["image9_target_numeral"]
    assert r["column_shift_applied"] == 0
    assert r["life_degree"] is None and not r["life_degree_accepted"]
    assert not r["cell_mansion_context_inferred"]
    assert not r["used_in_native_birth_chart"]


def test_selected_eight_older_grid_readings_still_match_the_frozen_observations():
    older = json.loads(
        (FIXTURE.parent / "guolao-life-degree-facsimile-v1/reference.json").read_text()
    )
    values = {"六": 6, "五": 5, "三": 3, "四": 4, "二": 2}
    for case in older["selected_grid_readings"]["cells"]:
        assert (
            load_grid().cell(case["palace"], case["column"])["numeral_value"]
            == values[case["numeric_text"]]
        )


@pytest.mark.parametrize("column", [True, 15.0, Fraction(15), "15", None])
def test_columns_require_explicit_integer_indices_not_equivalent_angles(column):
    with pytest.raises(TypeError):
        load_grid().cell("子", column)


@pytest.mark.parametrize("column", [-1, 0, 31, 360])
def test_out_of_range_columns_are_not_wrapped_or_shifted(column):
    with pytest.raises(ValueError):
        load_grid().cell("子", column)


@pytest.mark.parametrize("palace", ["", "子丑", "Aries", "命"])
def test_undeclared_palace_rows_are_not_inferred(palace):
    with pytest.raises(ValueError):
        load_grid().cell(palace, 15)


def test_initial_is_not_numeric_zero_and_mansion_marker_is_not_a_hidden_degree():
    with pytest.raises(ValueError):
        GridCell(None, 0, False)
    with pytest.raises(ValueError):
        GridCell("虚", 9, False)
    with pytest.raises(ValueError):
        GridCell(None, None, False)
    with pytest.raises(TypeError):
        GridCell(None, True, False)
    g = load_grid()
    assert g.cell("丑", 2)["initial_marker"]
    assert g.cell("子", 12)["mansion_marker"] == "虚"
    assert g.cell("子", 12)["numeral_value"] is None


def test_matrix_is_frozen_and_missing_cells_are_not_reconstructed():
    g = load_grid()
    rows = [list(row) for row in g.rows]
    frozen = replace(g, rows=rows)
    rows[0].pop()
    assert len(frozen.rows[0]) == 30
    with pytest.raises(ValueError):
        replace(g, rows=rows)
    with pytest.raises(ValueError):
        replace(g, rows=g.rows[:-1])
