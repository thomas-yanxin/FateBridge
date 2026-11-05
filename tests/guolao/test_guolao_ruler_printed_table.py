"""Full literal-table integrity and source gaps that rate-only queries cannot show."""

import copy
import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_ruler_printed_table as core
from fatebridge.core.guolao_ruler_calendar import NominalSourceDate as Date
from fatebridge.core.guolao_ruler_calendar import ruler_calendar_scale
from fatebridge.validation.guolao_ruler_printed_table import audit_printed_limit_table

FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-ruler-printed-table-v1"


def test_complete_literal_reading_and_original_scan_freeze_precede_numeric_comparison():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    frozen = json.loads(
        (FIXTURE / "literal-freeze-before-numeric-comparison.json").read_text()
    )
    assert (
        hashlib.sha256(core.DATA.read_bytes()).hexdigest()
        == ref["data_sha256"]
        == core.REFERENCE_SHA256
    )
    literal = (FIXTURE / "literal-rows.json").read_bytes()
    assert (
        hashlib.sha256(literal).hexdigest()
        == frozen["literal_rows_sha256"]
        == ref["literal_sha256"]
    )
    assert frozen["comparison_executed"] is False
    assert frozen["all210_slots_recorded"] is True
    assert ref["independent_new_scan_obtained"] is False
    assert ref["independent_second_collator"] is False
    for name, item in ref["artifacts"].items():
        assert (
            hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == item["sha256"]
        )
    pdf = FIXTURE / ref["existing_source_pdf"]
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == ref["source"]["pdf_sha256"]
    data = json.loads(core.DATA.read_bytes())
    assert len(data["read_views"]) == 14
    assert sum(len(r["cells"]) for r in data["rows"]) == 210


@pytest.mark.parametrize("group", core.GROUPS)
def test_all_literal_interval_starts_and_last_day_fractions_resolve_without_rate_fallback(
    group,
):
    table = core.load_printed_limit_table(core.PROFILE)
    for cell in table.rows[group]:
        for date in [
            cell.start,
            Date(cell.last.year, cell.last.month, cell.last.day, 1 - F(1, 10**100)),
        ]:
            result = table.lookup(group, date)
            assert result["status"] == "unique_literal_cell"
            assert result["selected_cell"] == cell.column
            assert result["formula_fallback_used"] is False
            assert (
                result["calendar_date"]
                is result["birth_age"]
                is result["life_degree"]
                is None
            )
    end = Date.from_elapsed_days(max(c.end_exclusive_days for c in table.rows[group]))
    result = table.lookup(group, end)
    assert result["status"] == "at_printed_limit_end"
    assert result["selected_cell"] is None and not result["matching_cells"]


@pytest.mark.parametrize(
    "date,expected",
    [
        (Date(1, 2, 24, 1 - F(1, 10**100)), 1),
        (Date(1, 2, 25), None),
        (Date(1, 3, 1), None),
        (Date(1, 3, 24, 1 - F(1, 10**100)), None),
        (Date(1, 3, 25), 2),
    ],
)
def test_disease_row30_nominal_day_gap_is_retained_at_every_boundary(date, expected):
    result = core.load_printed_limit_table(core.PROFILE).lookup("jie", date)
    assert result["selected_cell"] == expected
    if expected is None:
        assert result["status"] == "unassigned_printed_gap"
        assert result["matching_cells"] == []
    assert result["formula_fallback_used"] is False


@pytest.mark.parametrize(
    "group,palace,date,literal_cell,formula_cell",
    [
        ("qianyi", "迁移", Date(8, 3, 13), 27, 28),
        ("jie", "疾厄", Date(5, 3, 12), 19, 18),
        ("nupu", "奴仆", Date(3, 1, 1), 13, 14),
    ],
)
def test_printed_internal_boundaries_remain_distinct_from_constant_month_day_rate(
    group, palace, date, literal_cell, formula_cell
):
    table = core.load_printed_limit_table(core.PROFILE)
    assert table.lookup(group, date)["selected_cell"] == literal_cell
    assert ruler_calendar_scale(palace).position(date)["cell"] == formula_cell


def test_all210_endpoint_comparisons_keep_seven_source_discrepancies_and_all_rows():
    result = audit_printed_limit_table()
    assert result["complete_comparisons"] == 210
    assert result["equal_endpoint_cells"] == 203
    assert result["different_endpoint_cells"] == 7
    different = {
        (c["group"], c["column"]): (
            F(c["literal_minus_formula_start_nominal_days_exact"]),
            F(c["literal_minus_formula_end_exclusive_nominal_days_exact"]),
        )
        for c in result["comparisons"]
        if not c["endpoints_agree"]
    }
    assert different == {
        ("qianyi", 27): (F(0), F(1)),
        ("qianyi", 28): (F(1), F(0)),
        ("jie", 1): (F(0), F(-30)),
        ("jie", 18): (F(0), F(-1)),
        ("jie", 19): (F(-1), F(0)),
        ("nupu", 13): (F(0), F(30)),
        ("nupu", 14): (F(30), F(0)),
    }
    gaps = [(r["group"], v) for r in result["literal_table"]["rows"] for v in r["gaps"]]
    assert len(gaps) == 1
    assert gaps[0][0] == "jie" and gaps[0][1]["signed_gap_nominal_days_exact"] == "30"
    assert result["rate_formula_replaced_by_table"] is False
    assert result["full_birth_limit_schedule_accepted"] is False
    assert result["real_world_predictive_efficacy_established"] is False


def test_explicit_year_context_and_14_16_leaf_split_are_preserved():
    table = core.load_printed_limit_table(core.PROFILE)
    a = table.cell("fude", 14)["cell"]
    b = table.cell("fude", 15)["cell"]
    assert a["leaf"] == "right" and b["leaf"] == "left"
    assert a["explicit_last_day_year_marker"] == 6
    assert b["explicit_start_year_marker"] is None
    assert b["start_nominal_source_date"]["ordinal_year"] == 6
    assert table.cell("fude", 1)["printed_heading"] == "福德十一年／夫妻十一年"
    assert table.cell("fude", 1)["normalized_palaces"] == ["福德", "妻妾"]


@pytest.mark.parametrize("profile", [None, "", "nlc3150", True, core.PROFILE + " "])
def test_no_implicit_or_approximate_profile_selection(profile):
    with pytest.raises(ValueError):
        core.load_printed_limit_table(profile)


@pytest.mark.parametrize(
    "group,column",
    [("jie", 0), ("jie", 31), ("jie", True), ("jie", 1.0), ("疾厄", 1), ("unknown", 1)],
)
def test_cell_query_has_explicit_group_and_integer_column(group, column):
    with pytest.raises(ValueError):
        core.load_printed_limit_table(core.PROFILE).cell(group, column)


def test_changed_immutable_reference_is_not_silently_accepted(tmp_path, monkeypatch):
    path = tmp_path / "changed.json"
    path.write_bytes(core.DATA.read_bytes() + b"\n")
    monkeypatch.setattr(core, "DATA", path)
    with pytest.raises(ValueError, match="哈希"):
        core.load_printed_limit_table(core.PROFILE)


@pytest.mark.parametrize(
    "mutation",
    [
        "omit",
        "no_initial_year",
        "missing_rollover_marker",
        "wrong_year_policy",
        "formula_corrected",
    ],
)
def test_source_constructor_does_not_fill_cells_or_infer_year_rollover(mutation):
    source = json.loads(core.DATA.read_bytes())
    if mutation == "omit":
        source["rows"][0]["cells"].pop()
    elif mutation == "no_initial_year":
        source["rows"][0]["cells"][0] = "正月初一|五月十二"
    elif mutation == "missing_rollover_marker":
        source["rows"][0]["cells"][2] = "九月二十五|二月初六"
    elif mutation == "wrong_year_policy":
        source["year_context_policy"] = "auto_increment_year_when_month_wraps"
    else:
        source["source_intervals_corrected_by_formula"] = True
    with pytest.raises(ValueError):
        core.PrintedLimitTable(source, "synthetic_rejected_source")


def test_overlap_keeps_both_cells_without_selecting_one_or_using_formula():
    source = copy.deepcopy(json.loads(core.DATA.read_bytes()))
    source["rows"][0]["cells"][1] = "五月十二|九月二十四"
    table = core.PrintedLimitTable(source, "synthetic_overlap_not_a_new_source_version")
    result = table.lookup("fude", Date(1, 5, 12))
    assert result["status"] == "ambiguous_printed_overlap"
    assert result["selected_cell"] is None
    assert [c["column"] for c in result["matching_cells"]] == [1, 2]
    assert result["formula_fallback_used"] is False


@pytest.mark.parametrize("date", [Date(2027, 1, 1), "1-1-1", None])
def test_civil_year_or_untyped_date_not_coerced_into_the_table(date):
    with pytest.raises((TypeError, ValueError)):
        core.load_printed_limit_table(core.PROFILE).lookup("jie", date)


@pytest.mark.parametrize(
    "extra",
    [
        ["cell", "--group", "jie", "--column", "31"],
        ["lookup", "--group", "jie", "--nominal-source-date", "2027-1-1"],
        [
            "lookup",
            "--group",
            "jie",
            "--nominal-source-date",
            "1-3-1",
            "--fraction-of-nominal-day",
            "1/0",
        ],
    ],
)
def test_cli_parameter_errors_emit_no_success_payload(monkeypatch, capsys, extra):
    script = Path(__file__).parents[2] / "scripts/guolao/audit_guolao_printed_limits.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--profile", core.PROFILE, *extra])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script))["main"]()
    assert error.value.code == 2
    assert not capsys.readouterr().out
