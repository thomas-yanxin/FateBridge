"""Full literal-table integrity and source gaps that rate-only queries cannot show."""

import copy
import gzip
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao import guolao_ruler_printed_table as core
from fatebridge.core.guolao.guolao_ruler_calendar import NominalSourceDate as Date
from fatebridge.core.guolao.guolao_ruler_calendar import ruler_calendar_scale
from validation.guolao_ruler_printed_table import audit_printed_limit_table

FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-ruler-printed-table-v1"
REFERENCE_DATA = Path(__file__).parents[1] / "data/guolao/ruler_flint_v1"
MANIFEST = json.loads((REFERENCE_DATA / "manifest.json").read_text())
BLOB = (REFERENCE_DATA / "reference.json.gz").read_bytes()
assert hashlib.sha256(BLOB).hexdigest() == MANIFEST["files"]["reference.json.gz"]
RULER_REFERENCE = json.loads(gzip.decompress(BLOB))
RULER_INPUTS = json.loads((REFERENCE_DATA / "arithmetic-inputs.json").read_text())


def test_complete_literal_reading_and_original_scan_freeze_precede_numeric_comparison() -> (
    None
):
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
) -> None:
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
def test_disease_row30_nominal_day_gap_is_retained_at_every_boundary(
    date, expected: int | None
) -> None:
    result = core.load_printed_limit_table(core.PROFILE).lookup("jie", date)
    assert result["selected_cell"] == expected
    if expected is None:
        assert result["status"] == "unassigned_printed_gap"
        assert result["matching_cells"] == []
    else:
        pass
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
    group: str, palace: str, date, literal_cell: int, formula_cell: int
) -> None:
    table = core.load_printed_limit_table(core.PROFILE)
    assert table.lookup(group, date)["selected_cell"] == literal_cell
    assert ruler_calendar_scale(palace).position(date)["cell"] == formula_cell


def test_all210_endpoint_comparisons_keep_seven_source_discrepancies_and_all_rows() -> (
    None
):
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


def test_explicit_year_context_and_14_16_leaf_split_are_preserved() -> None:
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
def test_no_implicit_or_approximate_profile_selection(profile) -> None:
    with pytest.raises(ValueError):
        core.load_printed_limit_table(profile)


@pytest.mark.parametrize(
    "group,column",
    [("jie", 0), ("jie", 31), ("jie", True), ("jie", 1.0), ("疾厄", 1), ("unknown", 1)],
)
def test_cell_query_has_explicit_group_and_integer_column(
    group: str, column: bool | float | int
) -> None:
    with pytest.raises(ValueError):
        core.load_printed_limit_table(core.PROFILE).cell(group, column)


def test_changed_immutable_reference_is_not_silently_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
def test_source_constructor_does_not_fill_cells_or_infer_year_rollover(
    mutation: str,
) -> None:
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


def test_overlap_keeps_both_cells_without_selecting_one_or_using_formula() -> None:
    source = copy.deepcopy(json.loads(core.DATA.read_bytes()))
    source["rows"][0]["cells"][1] = "五月十二|九月二十四"
    table = core.PrintedLimitTable(source, "synthetic_overlap_not_a_new_source_version")
    result = table.lookup("fude", Date(1, 5, 12))
    assert result["status"] == "ambiguous_printed_overlap"
    assert result["selected_cell"] is None
    assert [c["column"] for c in result["matching_cells"]] == [1, 2]
    assert result["formula_fallback_used"] is False


@pytest.mark.parametrize("date", [Date(2027, 1, 1), "1-1-1", None])
def test_civil_year_or_untyped_date_not_coerced_into_the_table(date) -> None:
    with pytest.raises((TypeError, ValueError)):
        core.load_printed_limit_table(core.PROFILE).lookup("jie", date)


@pytest.mark.parametrize(
    "group", RULER_INPUTS["groups"], ids=lambda group: group["group"]
)
def test_every_frozen_nominal_day_and_subday_matches_independent_rational_targets(
    group,
) -> None:
    scale = ruler_calendar_scale(group["palaces"][0])
    table = core.load_printed_limit_table(core.PROFILE)
    for row in RULER_REFERENCE["rows"]:
        if row["group"] != group["group"]:
            continue
        else:
            pass
        label = row["nominal_source_date"]
        days = F(row["elapsed_nominal_days_exact"])
        degrees = F(row["formula_degrees_exact"])
        date = Date(
            label["ordinal_year"],
            label["month"],
            label["day"],
            F(label["fraction_of_nominal_day_exact"]),
        )
        assert Date.from_elapsed_days(days).as_dict() == label
        assert date.elapsed_days == days
        assert scale.days_from_degrees(degrees) == days
        assert scale.degrees_from_days(days) == degrees
        position = scale.position(date)
        assert position["nominal_source_date"] == label
        assert position["limit_scale_degrees_exact"] == row["formula_degrees_exact"]
        assert (
            position["printed_annual_rate_scale_degrees_exact"]
            == row["printed_annual_degrees_exact"]
        )
        assert (
            position["month_day_minus_printed_annual_degrees_exact"]
            == row["monthday_minus_printed_annual_exact"]
        )
        assert position["cell"] == row["formula_cell"]
        assert position["status"] == row["formula_status"]
        assert scale.at_degrees(degrees) == position
        literal = table.lookup(group["group"], date)
        assert [cell["column"] for cell in literal["matching_cells"]] == row[
            "literal_matching_cells"
        ]
        assert literal["selected_cell"] == row["literal_selected_cell"]
        assert literal["status"] == row["literal_status"]
        assert literal["formula_fallback_used"] is False


@pytest.mark.parametrize(
    "group", RULER_INPUTS["groups"], ids=lambda group: group["group"]
)
def test_all_literal_and_formula_endpoints_match_independently_parsed_source(
    group,
) -> None:
    scale = ruler_calendar_scale(group["palaces"][0])
    table = core.load_printed_limit_table(core.PROFILE)
    comparison = {
        (cell["group"], cell["column"]): cell
        for cell in audit_printed_limit_table()["comparisons"]
    }
    for row in RULER_REFERENCE["cell_rows"]:
        if row["group"] != group["group"]:
            continue
        else:
            pass
        literal = table.cell(row["group"], row["column"])["cell"]
        assert literal["normalized_literal_text"] == row["literal_text"]
        assert literal["start_nominal_days_exact"] == row["literal_start_exact"]
        assert (
            literal["end_exclusive_nominal_days_exact"]
            == row["literal_end_exclusive_exact"]
        )
        assert literal["explicit_start_year_marker"] == row["explicit_start_year"]
        assert literal["explicit_last_day_year_marker"] == row["explicit_last_year"]
        formula = scale.cell_interval(row["column"])
        assert (
            formula["interval_start_nominal_days_exact"] == row["formula_start_exact"]
        )
        assert (
            formula["interval_end_nominal_days_exact"]
            == row["formula_end_exclusive_exact"]
        )
        assert formula["start_nominal_source_date"] == row["formula_start_label"]
        assert formula["last_included_nominal_day"] == row["formula_last_label"]
        assert (
            formula["end_exclusive_nominal_source_date"]
            == row["formula_end_exclusive_label"]
        )
        delta = comparison[row["group"], row["column"]]
        assert (
            delta["literal_minus_formula_start_nominal_days_exact"]
            == row["literal_minus_formula_start_exact"]
        )
        assert (
            delta["literal_minus_formula_end_exclusive_nominal_days_exact"]
            == row["literal_minus_formula_end_exact"]
        )
    expected = next(
        row for row in RULER_REFERENCE["audits"] if row["group"] == group["group"]
    )
    audit = scale.audit()
    assert (
        audit["month_day_degrees_per_nominal_year_exact"]
        == expected["monthday_annual_rate_exact"]
    )
    assert audit["annual_and_month_day_rates_agree"] == expected["annual_rate_agrees"]
    assert (
        audit["printed_annual_full_limit_degrees_exact"]
        == expected["printed_full_limit_degrees_exact"]
    )
    assert (
        audit["printed_annual_full_limit_minus_30_exact"]
        == expected["printed_full_limit_minus30_exact"]
    )
    assert (
        audit["month_day_full_limit_minus_source_duration_days_exact"]
        == expected["monthday_limit_minus_source_duration_days_exact"]
    )


@pytest.mark.parametrize("row", RULER_REFERENCE["date_only_stress"])
def test_independent_extreme_date_labels_preserve_exact_subdays_and_large_integers(
    row,
) -> None:
    elapsed = F(row["elapsed_nominal_days_exact"])
    date = Date.from_elapsed_days(elapsed)
    assert date.as_dict() == row["nominal_source_date"]
    assert date.elapsed_days == elapsed
