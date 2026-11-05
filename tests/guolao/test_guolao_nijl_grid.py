"""Complete named-witness collation, source guards and unrepaired original cases."""

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.core.guolao_nijl_grid as module
from fatebridge.core.guolao_classical import BRANCHES
from fatebridge.core.guolao_grid import load_grid

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-nijl-grid-v1"


def test_frozen_original_full_literal_rows_and_read_views_have_bound_fingerprints():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert (
        hashlib.sha256((FIXTURE / reference["source_file"]).read_bytes()).hexdigest()
        == reference["source_image_sha256"]
        == module.SOURCE_SHA256
    )
    assert (
        hashlib.sha256(module.DATA.read_bytes()).hexdigest()
        == reference["runtime_data_sha256"]
        == module.DATA_SHA256
    )
    assert (
        hashlib.sha256(
            (FIXTURE / "literal-rows-before-domain-comparison.json").read_bytes()
        ).hexdigest()
        == reference["literal_reference_sha256"]
    )
    views = json.loads((FIXTURE / "reading-views.json").read_text())
    assert len(views["views"]) == 8
    for view in views["views"]:
        assert (
            hashlib.sha256((FIXTURE / view["file"]).read_bytes()).hexdigest()
            == view["sha256"]
        )
        assert (
            hashlib.sha256((FIXTURE / view["source_image"]).read_bytes()).hexdigest()
            == view["source_image_sha256"]
        )
        if view["file"].startswith("base-"):
            assert view["source_pixels"] == [2342, 1660]
            assert "国文学研究資料館提供" not in view["credit"]
        else:
            assert view["source_pixels"] == [5856, 4032]
            assert "国文学研究資料館提供" in view["credit"]
    assert "東北大学附属図書館所蔵" in reference["source_credit"]
    assert not reference["independent_blind_reference"]
    assert not reference["second_independent_collator"]


def test_all360_runtime_cells_equal_the_prior_frozen_literal_collation():
    """A transcription-to-contract check, not independent source truth."""
    held = json.loads(
        (FIXTURE / "literal-rows-before-domain-comparison.json").read_text()
    )
    assert "".join(row["palace"] for row in held["rows"]) == BRANCHES
    grid = module.load_nijl_grid()
    for row in held["rows"]:
        assert len(row["tokens"]) == 30
        for column, token in enumerate(row["tokens"], 1):
            cell = grid.cell(row["palace"], column)
            if ":" in token:
                mansion, text = token.split(":")
                assert cell["mansion_marker"] == mansion
                assert cell["marker_reading"]["text"] == text
                assert cell["numeral_value"] is None
            elif token == "初":
                assert cell["initial_marker"] and cell["numeral_value"] is None
            else:
                assert cell["numeral_value"] == int(token)
            assert cell["inherited_mansion"] is None
            assert cell["continuous_historical_degree"] is None
            assert cell["modern_longitude"] is None


@pytest.mark.parametrize(
    "palace,column,marker,text,value,base_text",
    [
        ("子", 1, "危", "十一", 11, "一"),
        ("丑", 10, "斗", "二十三", 23, None),
        ("辰", 23, "轸", "十七", 17, "十四"),
        ("午", 15, "星", "六", 6, None),
        ("午", 21, "柳", "十三", 13, "十二"),
        ("亥", 1, "奎", "初", None, "四"),
    ],
)
def test_six_directly_collated_loci_preserve_both_named_scan_readings(
    palace, column, marker, text, value, base_text
):
    before = load_grid().cell(palace, column)
    cell = module.literal_cell(palace=palace, column=column)["cell"]
    assert cell["mansion_marker"] == marker
    assert cell["marker_reading"]["text"] == text
    assert cell["marker_reading"]["integer_value"] == value
    attached = before["marker_reading"]
    assert (attached["text"] if attached else None) == base_text
    assert load_grid().cell(palace, column) == before


def test_full_comparison_keeps_all354_matches_and_six_differences():
    result = module.compare_ma591()
    assert result["compared_cells"] == len(result["cells"]) == 360
    assert result["matching_cells"] == 354 and result["different_cells"] == 6
    assert {(r["palace"], r["column"]) for r in result["cells"]} == {
        (p, c) for p in BRANCHES for c in range(1, 31)
    }
    assert [(r["palace"], r["column"]) for r in result["differences"]] == [
        ("子", 1),
        ("丑", 10),
        ("辰", 23),
        ("午", 15),
        ("午", 21),
        ("亥", 1),
    ]
    assert not result["old_reading_replaced"] and result["column_shift_applied"] == 0
    assert not result["life_degree_accepted"]


def test_complete_visible_readings_do_not_turn_three_initial_marks_into_zero():
    audit = module.audit_nijl_grid()
    assert audit["regular_numeral_cells"] == 310
    assert audit["initial_marker_cells"] == 10
    assert audit["mansion_marker_cells"] == 40
    assert audit["marker_reading_counts"] == dict(integer=37, initial=3, not_visible=0)
    assert audit["unmarked_numeric_restarts"] == []
    assert audit["marker_to_regular_numeric_discontinuities"] == []
    assert audit["full360_literal_cells_collated"]
    for key in [
        "marker_numeric_values_complete",
        "full_360_cell_numerical_mapping_accepted",
        "full_grid_collation_is_coordinate_acceptance",
        "modern_epoch_calibrated",
        "life_degree_accepted",
        "used_in_native_birth_chart",
    ]:
        assert audit[key] is False
    for palace, column in [("辰", 1), ("申", 19), ("亥", 1)]:
        attached = module.literal_cell(palace=palace, column=column)["cell"][
            "marker_reading"
        ]
        assert attached["kind"] == "initial" and attached["integer_value"] is None


def test_selected_nijl_table_does_not_load_a_different_witness_to_fill_values(
    monkeypatch,
):
    def unavailable():
        pytest.fail("NIJL literal query must not use another witness's values")

    monkeypatch.setattr(module, "load_grid", unavailable)
    assert (
        module.literal_cell(palace="丑", column=10)["cell"]["marker_reading"][
            "integer_value"
        ]
        == 23
    )


def test_modified_unpinned_runtime_transcription_is_rejected(monkeypatch, tmp_path):
    path = tmp_path / "changed.json"
    data = json.loads(module.DATA.read_text())
    data["rows"][0]["cells"][1]["numeral_value"] = 9
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", path)
    with pytest.raises(ValueError, match="指纹"):
        module.load_nijl_grid()


@pytest.mark.parametrize(
    "fault", ["source", "order", "short_row", "missing", "duplicate"]
)
def test_structural_source_guards_even_with_a_caller_replaced_digest(
    fault, monkeypatch, tmp_path
):
    data = json.loads(module.DATA.read_text())
    if fault == "source":
        data["source_image_sha256"] = "another-scan"
    elif fault == "order":
        data["rows"][0], data["rows"][1] = data["rows"][1], data["rows"][0]
    elif fault == "short_row":
        data["rows"][0]["cells"].pop()
    elif fault == "missing":
        data["readings"].pop()
    else:
        data["readings"].append(copy.deepcopy(data["readings"][0]))
    path = tmp_path / "synthetic-malformed.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", path)
    monkeypatch.setattr(
        module, "DATA_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError):
        module.load_nijl_grid()


def test_comparison_cannot_silently_rebind_to_a_changed_ma591_transcription(
    monkeypatch,
):
    monkeypatch.setattr(
        module, "load_grid", lambda: replace(load_grid(), data_sha256="x")
    )
    with pytest.raises(ValueError, match="基准"):
        module.compare_ma591()
    assert (
        module.literal_cell(palace="亥", column=1)["cell"]["marker_reading"][
            "integer_value"
        ]
        is None
    )


def test_complete_nijl_table_keeps_both_selected_intro_numeric_counterexamples():
    result = module.compare_intro_examples()
    assert [r["example"]["id"] for r in result["cases"]] == [
        "luwei_xu6_xing5",
        "luwei_nv3_liu4",
    ]
    assert [r["target_literal_integer"] for r in result["cases"]] == [6, 5]
    assert [r["target_numeric_label_match"] for r in result["cases"]] == [False, False]
    assert [r["source_numeric_label_match"] for r in result["cases"]] == [True, True]
    assert [r["target_explicit_mansion_match"] for r in result["cases"]] == [True, None]
    assert all(r["column_shift_applied"] == 0 for r in result["cases"])
    assert all(not r["example"]["birth_datetime_known"] for r in result["cases"])
    assert not result["all_same_column_numeric_examples_agree"]
    assert not result["selected_table_usage_adjudicated"]
    assert not result["life_degree_accepted"]
    assert result["real_world_prediction_cases"] == 0


def test_original_example_mutation_cannot_remove_the_failed_rows(monkeypatch, tmp_path):
    data = json.loads(module.EXAMPLES.read_text())
    data["cases"].pop(0)
    path = tmp_path / "incomplete-examples.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "EXAMPLES", path)
    with pytest.raises(ValueError, match="原例"):
        module.compare_intro_examples()


@pytest.mark.parametrize(
    "palace,column", [("子", 0), ("子", 31), ("unknown", 1), ("子", True), ("子", 1.0)]
)
def test_literal_inputs_do_not_round_wrap_or_guess_columns(palace, column):
    with pytest.raises((TypeError, ValueError)):
        module.literal_cell(palace=palace, column=column)
