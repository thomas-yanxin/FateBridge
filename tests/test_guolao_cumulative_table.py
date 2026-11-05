"""Full literal columns, contradictory printed increments and empty endpoints."""

import csv
import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_cumulative_table as table
from fatebridge.core import guolao_day_rate as previous
from fatebridge.core.guolao_calendar_year import gujin_fixed_qice_year
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.validation.guolao_calendars import (
    audit_named_year_grid,
    compare_literal_calendar_methods,
    compare_official_calendar,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-cumulative-table-v1"


def test_complete_original_images_transcription_and_reading_corrections_are_pinned():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    for artifact in reference["artifacts"]:
        raw = (FIXTURE / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    assert reference["single_collator"] and not reference["independent_second_collator"]
    rows = list(
        csv.DictReader((FIXTURE / "cumulative-and-increments-transcribed.csv").open())
    )
    data, digest = table._table()
    assert len(rows) == 169
    for row, actual in zip(rows, data["rows"], strict=True):
        assert int(row["limit_index"]) == actual["limit_index"]
        for key in ["cumulative_ancient_du", "signed_increment_ancient_du"]:
            assert (row[key] or None) == actual[key]
        assert row["increment_label"] == actual["increment_label"]
    assert digest == hashlib.sha256(table.DATA.read_bytes()).hexdigest()
    journal = json.loads((FIXTURE / "reading-corrections.json").read_text())
    assert (
        journal["initial_sha256"]
        == hashlib.sha256(
            (FIXTURE / "initial-transcription-before-diagnostic.txt").read_bytes()
        ).hexdigest()
    )
    assert len(journal["corrections"]) == 13
    assert journal["genuine_source_increment_conflicts_retained"] == [12, 155, 163]


def test_separately_printed_columns_keep_three_real_inconsistencies():
    result = table.audit_gujin45_cumulative_table()
    assert (
        result["numeric_cumulative_cells"],
        result["numeric_signed_increment_cells"],
    ) == (167, 168)
    assert result["empty_cumulative_indices"] == [0, 168]
    assert result["empty_increment_indices"] == [168]
    assert result["cumulative_vs_previous_integer_model_disagreements"] == []
    differences = result["printed_increment_vs_adjacent_cumulative_disagreements"]
    assert [r["limit_index"] for r in differences] == [12, 155, 163]
    assert [F(r["printed_minus_adjacent_exact"]) for r in differences] == [
        F(-3, 10000),
        F(3, 10000),
        F(1, 5000),
    ]
    assert all(not r["printed_increment_replaced"] for r in differences)
    assert len(result["boundary_jumps"]) == 167
    assert result["nonzero_boundary_jumps"] == 21
    assert not result["independent_second_collator"]
    assert not result["complete_source_calendar_accepted"]


@pytest.mark.parametrize(
    "within,index,cumulative,increment",
    [
        ("1.0250", 12, "1.28712000", ".10225075"),
        ("12.7522", 155, "1.38967075", "-.10225075"),
        ("13.4083", 163, ".54806875", "-.10817275"),
    ],
)
@pytest.mark.parametrize("slow", [False, True])
def test_literal_increment_not_its_adjacent_difference_drives_interpolation(
    within, index, cumulative, increment, slow
):
    anomaly = F(within) + (F("13.7773") if slow else F())
    result = table.gujin_literal_lunar(anomaly)
    expected = F(cumulative) + F(increment) / 2
    assert result["whole_limit_index"] == index
    assert F(result["signed_correction_ancient_du_exact"]) == (
        expected if slow else -expected
    )
    assert F(result["interpolation_fraction_exact"]) == F(1, 2)
    assert not result["adjacent_cumulative_difference_used_to_supply_increment"]
    assert result["source_selected_signed_increment_ancient_du"] == (
        "0" + increment
        if increment.startswith(".")
        else "-0" + increment[1:] if increment.startswith("-.") else increment
    )
    old = previous.gujin_day_rate_lunar(anomaly)
    assert (
        old["signed_correction_ancient_du_exact"]
        != result["signed_correction_ancient_du_exact"]
    )


def test_origin_empty_is_retained_with_only_its_explicit_zero_origin_policy():
    result = table.gujin_literal_lunar(F(".041"))
    assert result["source_selected_cumulative_ancient_du"] is None
    assert result["empty_cumulative_origin_interpreted_as_zero"]
    assert F(result["signed_correction_ancient_du_exact"]) == F("-.055407875")
    endpoint = table.gujin_literal_lunar(F("13.7773"))
    assert endpoint["whole_limit_index"] == 168
    assert endpoint["source_selected_cumulative_ancient_du"] is None
    assert endpoint["source_selected_signed_increment_ancient_du"] is None
    assert endpoint["signed_correction_ancient_du_exact"] is None
    assert not endpoint["empty_cumulative_endpoint_filled"]


def test_last_interval_uses_its_own_printed_slope_without_filling_endpoint():
    result = table.gujin_literal_lunar(F("13.7363"))
    assert result["whole_limit_index"] == 167
    assert result["source_selected_signed_increment_ancient_du"] == "-0.11081575"
    assert F(result["signed_correction_ancient_du_exact"]) == F("-.055407875")
    assert table._table()[0]["rows"][168]["cumulative_ancient_du"] is None


@pytest.mark.parametrize("anomaly", ["7.2807", "7.285", "7.2987", "21.0623"])
def test_literal_table_does_not_bypass_existing_day_rate_ambiguity(anomaly):
    result = table.gujin_literal_lunar(F(anomaly))
    assert result["status"] == "ambiguous_literal_rate_not_repaired"
    assert result["whole_limit_index"] is None
    assert result["signed_correction_ancient_du_exact"] is None


def test_literal_runtime_is_independent_of_previous_integer_formula(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("integer formula must not supply literal-table cells")

    monkeypatch.setattr(previous, "_integer_angle", forbidden)
    lunar = table.gujin_literal_lunar(F(1))
    assert lunar["signed_correction_ancient_du_exact"] is not None
    conjunction = table.gujin_literal_conjunction(F(), 0)
    assert conjunction["time_correction_days_exact"] is not None
    assert conjunction["profile_id"] == table.PROFILE


def test_original49_local_angle_retains_published_rounding_residual():
    result = table.gujin_literal_lunar(F("23.310758"))
    assert result["whole_limit_index"] == 116
    assert result["source_selected_cumulative_ancient_du"] == "4.56040000"
    assert result["source_selected_signed_increment_ancient_du"] == "-0.05629675"
    value = F(result["signed_correction_ancient_du_exact"])
    assert value == F(745590902827, 164000000000)
    assert 0 < value - F("4.546285") < F(".000001")


@pytest.mark.parametrize("elapsed", [31, 296])
def test_prior_endpoint_gap_still_uses167_and_never_supplies168(elapsed):
    middle = shoushi_winter_cycle(elapsed).zhongji_days
    result = table.gujin_literal_conjunction(middle, 10)
    assert result["lunar_velocity"]["whole_limit_index"] == 167
    assert result["lunar_velocity"]["printed_velocity_ancient_du_per_limit"] == "1.2071"
    assert result["time_correction_days_exact"] is not None
    year = gujin_fixed_qice_year(middle, conjunction_method="literal_table")
    assert year["complete_named_year_assigned"]
    assert year["profile_id"] == table.CALENDAR_PROFILE
    assert not year["complete_historical_calendar_accepted"]


@pytest.mark.parametrize(
    "reference,expected,unknown",
    [("jiajing3_1524_wdl108", 26, 0), ("wanli27_1599_nlc_preview", 6, 4)],
)
def test_unchanged_official_facts_remain_distinct_from_missing_reference(
    reference, expected, unknown
):
    result = compare_official_calendar(reference, conjunction_method="literal_table")
    assert result["counts"] == dict(
        matches=expected,
        mismatches=0,
        computed_unavailable=0,
        reference_unreadable_or_unprovided=unknown,
    )
    assert not result["parameters_selected_by_reference_fit"]
    assert not result["pre_registered_holdout"]


def test_full_grid_keeps_all_eight_unresolved_years():
    result = audit_named_year_grid(0, 400, conjunction_method="literal_table")
    assert result["input_years"] == 400 and result["input_years_dropped"] == 0
    assert result["counts"] == dict(
        complete_under_named_fixed_qice_policy=392, partial_calendar_year=8
    )
    assert [r["elapsed_years"] for r in result["unresolved"]] == [
        45,
        46,
        66,
        168,
        188,
        310,
        311,
        331,
    ]


@pytest.mark.parametrize("elapsed", [31, 45, 46, 243])
def test_method_comparison_keeps_all_declared_positions_and_missingness(elapsed):
    result = compare_literal_calendar_methods(elapsed, elapsed + 1)
    assert result["input_years"] == 1
    assert result["conjunction_comparison_positions"] == 18
    positions = result["rows"][0]["conjunction_correction_comparisons"]
    assert [p["lunation_index"] for p in positions] == list(range(18))
    assert sum(result["conjunction_comparison_status_counts"].values()) == 18
    for p in positions:
        if p["comparison_status"] != "compared":
            assert p["literal_minus_integer_correction_days_exact"] is None
    if elapsed == 46:
        assert (
            result["conjunction_comparison_status_counts"][
                "not_requested_by_year_builder"
            ]
            == 3
        )
        assert (
            result["conjunction_comparison_status_counts"]["source_value_unavailable"]
            == 1
        )
    assert not result["methods_selected_by_year_or_reference_fit"]
    assert not result["missing_or_unrequested_corrections_counted_as_agreement"]


@pytest.mark.parametrize(
    "mutation",
    [
        "row_count",
        "ordering",
        "origin",
        "endpoint",
        "precision",
        "label",
        "sign",
        "divisor",
        "origin_policy",
        "collation_level",
        "second_collator",
        "rate_witness",
    ],
)
def test_malformed_or_overclaimed_source_tables_fail_closed(
    tmp_path, monkeypatch, mutation
):
    data = json.loads(table.DATA.read_text())
    if mutation == "row_count":
        data["rows"].pop()
    elif mutation == "ordering":
        data["rows"].reverse()
    elif mutation == "origin":
        data["rows"][0]["cumulative_ancient_du"] = "0.00000000"
    elif mutation == "endpoint":
        data["rows"][168]["signed_increment_ancient_du"] = "0.00000000"
    elif mutation == "precision":
        data["rows"][1]["cumulative_ancient_du"] = "0.110815750"
    elif mutation == "label":
        data["rows"][12]["increment_label"] = "損"
    elif mutation == "sign":
        data["rows"][12]["signed_increment_ancient_du"] = "-0.10225075"
    elif mutation == "divisor":
        data["interpolation_divisor_days"] = "0.082008"
    elif mutation == "origin_policy":
        data["origin_policy"] = "fill_all_empty_cells"
    elif mutation == "collation_level":
        data["full_single_collator_field_transcription"] = False
    elif mutation == "second_collator":
        data["independent_second_collator"] = True
    else:
        data["day_rate_data_sha256"] = "0" * 64
    path = tmp_path / "table.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(table, "DATA", path)
    with pytest.raises(ValueError):
        table.gujin_literal_lunar(F(1))


@pytest.mark.parametrize("value", [1, 1.2, "1", True])
def test_exact_original_day_input_required(value):
    with pytest.raises(TypeError):
        table.gujin_literal_lunar(value)


@pytest.mark.parametrize(
    "arguments", [["--table-audit"], ["--anomaly-days", "13.7773"]]
)
def test_cli_research_output_is_json_and_retains_missing_endpoint(
    monkeypatch, capsys, arguments
):
    monkeypatch.setattr(sys, "argv", ["audit_guolao_cumulative.py", *arguments])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_cumulative.py"), run_name="__main__"
        )
    assert exited.value.code == 0
    result = json.loads(capsys.readouterr().out)
    if "--anomaly-days" in arguments:
        assert result["signed_correction_ancient_du_exact"] is None


@pytest.mark.parametrize(
    "arguments",
    [["--conjunction-method", "literal_table"], ["--conjunction-method=literal_table"]],
)
def test_literal_pair_comparison_rejects_single_method_override(monkeypatch, arguments):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_guolao_calendar_year.py",
            "--compare-literal-grid",
            "0",
            "1",
            *arguments,
        ],
    )
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_calendar_year.py"), run_name="__main__"
        )
    assert exited.value.code == 2
