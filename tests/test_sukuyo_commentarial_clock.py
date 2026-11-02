"""Commentarial disagreements must survive calculation and transport."""

import copy

import pytest

from fatebridge.core import sukuyo_commentarial_clock as clock
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_sources import LoadedSource
from scripts.check_sukuyo_commentarial_clock import check_literal_days, verify_primary
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def test_all_twelve_literal_dates_keep_the_august_disagreement():
    result = clock.commentarial_boundary_reference()
    monthly = result["monthly_pushya_reference"]
    assert len(monthly["comparisons"]) == 12
    assert monthly["matching_controls"] == 11
    assert monthly["differing_controls"] == 1
    row = next(r for r in monthly["comparisons"] if not r["matches"])
    assert (row["lunar_month"], row["lunar_day"]) == (8, 23)
    assert row["quoted_mansion_literal"] == "補灑"
    assert row["normalized_quoted_mansion"] == "鬼" and row["host_mansion"] == "柳"
    assert not monthly["source_dates_changed_to_match_host"]
    assert not monthly["hinoo_half_or_leap_assignment_applied"]
    assert not monthly["quoted_work_independent_original_acquired"]


@pytest.mark.parametrize("mutation", ["duplicate", "omit", "boolean", "wrong_day"])
def test_literal_months_cannot_be_overwritten_or_silently_incomplete(
    monkeypatch, mutation
):
    loaded = clock.load_source(clock.SOURCE)
    source = loaded.data
    rows = source["monthly_pushya_reference"]["literal_days"]
    if mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "omit":
        rows.pop()
    elif mutation == "boolean":
        rows[0]["month"] = True
    else:
        rows[0]["day"] = 31
    monkeypatch.setattr(
        clock, "load_source", lambda _: LoadedSource(source, loaded.sha256)
    )
    with pytest.raises(ValueError, match="完整唯一且为合法整数"):
        clock.commentarial_boundary_reference()


def test_nested_day_boundary_accounts_and_white_eighth_condition_remain_distinct():
    result = clock.commentarial_boundary_reference()
    accounts = result["two_day_boundary_accounts"]
    assert [row["assigned_lunar_day"] for row in accounts["accounts"]] == [8, 9]
    assert not accounts["universal_boundary_established"]
    assert not accounts["mapped_to_modern_clock"]
    pair = result["second_month_eighth_ninth_comparison"]
    assert [row["direct_mansion"] for row in pair] == ["井", "鬼"]
    condition = result["white_eighth_pushya_condition"]
    assert condition["conditions"] == ["白月八日", "布灑／鬼星合"]
    assert not condition["all_white_eighth_days_assigned_pushya"]
    assert not condition["actual_lunar_conjunction_computed"]
    assert not condition["tithi_to_civil_date_mapping_established"]


def test_output_mutation_does_not_change_the_next_source_or_calculation():
    first = clock.commentarial_boundary_reference()
    first["monthly_pushya_reference"]["literal_days"][7]["day"] = 22
    first["monthly_pushya_reference"]["comparisons"][7]["host_mansion"] = "鬼"
    next_result = clock.commentarial_boundary_reference()
    assert next_result["monthly_pushya_reference"]["literal_days"][7]["day"] == 23
    assert (
        next_result["monthly_pushya_reference"]["comparisons"][7]["host_mansion"]
        == "柳"
    )


def test_reference_does_not_move_dates_or_choose_a_hinoo_precedence():
    current = calendar_mansion(
        "1903-06-25",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    before = copy.deepcopy(current)
    result = day_evidence(current)
    assert current == before
    assert result["calendar"]["candidate_su27s"] == ["鬼", "参"]
    assert result["day_mansion"] is None
    text = result["reading_text"]
    assert "8月23日原引補灑（鬼）／望宿柳" in text
    assert "11条相合、1条不同" in text
    assert "八月二十三原引日号保留" in text
    assert "二月八日为井、九日为鬼" in text
    assert "卯时以前仍属八日分" in text
    assert "不能将每月白八自动标为鬼宿" in text


def test_primary_checker_distinguishes_selected_text_from_originals():
    result = verify_primary()
    assert result["literal_month_day_controls"] == 12
    assert result["actual_capture_bytes_rechecked"] == []
    assert not result["all_three_actual_captures_rechecked"]
    assert not result["independent_manuscript_collation"]
    assert not result["historical_clock_mapping_established"]


@pytest.mark.parametrize("changed", ["control", "quotation"])
def test_source_quotation_and_executable_date_controls_cannot_drift_apart(changed):
    source = clock.load_source(clock.SOURCE).data
    if changed == "control":
        source["monthly_pushya_reference"]["literal_days"][7]["day"] = 22
    else:
        source["sources"][0]["selected_quotations"][0]["literal"] = source["sources"][
            0
        ]["selected_quotations"][0]["literal"].replace("八月二十三日", "八月二十二日")
    with pytest.raises(ValueError, match="未绑定所选原引日号"):
        check_literal_days(source)


@pytest.mark.parametrize("name", ["T2216", "T1788", "T0665"])
def test_primary_checker_rejects_substituted_actual_source_bytes(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="字节指纹不一致"):
        verify_primary({name: path})


@pytest.mark.parametrize("date", ["2024-03-17", "2024-09-25"])
def test_new_reference_across_actual_rest_native_mcp_and_cli(monkeypatch, capsys, date):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": date, "time": "04:30:00", "zone": "+08:00"},
        [
            "sukuyo.calendar_day.clock_doctrine.commentarial_boundary_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )
