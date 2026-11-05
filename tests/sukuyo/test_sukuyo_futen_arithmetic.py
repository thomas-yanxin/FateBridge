"""Check against the complete reference sealed before production code existed."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_futen_arithmetic as arithmetic
from fatebridge.core.sukuyo_futen_clock import futen_clock_reference

REFERENCE = Path(__file__).parents[1] / "data/sukuyo-futen-arithmetic-source-v1.json"


def ratio(value):
    return Fraction(value["numerator"], value["denominator"])


def test_all_fifteen_source_rows_match_preimplementation_independent_arithmetic():
    reference = json.loads(REFERENCE.read_bytes())
    result = arithmetic.futen_arithmetic_reference()
    rows = result["all_fifteen_row_checks"]
    assert len(rows) == len(reference["all15_checks"]) == 15
    for actual, expected in zip(rows, reference["all15_checks"], strict=True):
        assert [actual["year"], actual["month"], actual["is_leap_month"]] == expected[
            "key"
        ]
        assert actual["lunation_offset"] == expected["offset"]
        assert actual["calculated_mean"]["cycle_units"] == expected["mean_cycle_units"]
        assert (
            actual["sum_using_printed_corrections"]["cycle_units"]
            == expected["true_from_printed_corrections_units"]
        )
        assert actual["mean_minus_printed_units"] == 0
        assert actual["sum_minus_printed_units"] == 0
        assert actual["correction_functions_reconstructed"] is False
    assert [r["lunation_offset"] for r in rows] == list(range(-2, 13))
    assert reference["no_repository_calculation_imported"]


def test_cycle_origin_units_labels_and_rounding_conflicts_are_not_erased():
    expected = json.loads(REFERENCE.read_bytes())
    result = arithmetic.futen_arithmetic_reference()
    chain = result["calculated_chain"]
    for field in [
        "accumulated_units",
        "unadjusted_run_remainder",
        "adjusted_run_remainder",
        "anomaly_units",
    ]:
        assert chain[field] == expected[field]
    assert chain["mean_cycle_with_qi_ying"]["cycle_units"] == 232576
    assert chain["mean_literal_without_qi_ying"]["cycle_units"] == 434041
    assert chain["literal_without_qi_ying_minus_printed_units"] == 201465
    assert chain["mean_cycle_with_qi_ying"]["ganzhi"] == "丁亥"
    assert result["printed_example"]["mean_cycle_name_literal"] == "壬午"
    assert chain["printed_mean_name_index"] == 18
    assert chain["printed_mean_name_matches_index"] is False
    assert chain["anomaly_dependency"]["remainder_basis"] == "unadjusted_run_remainder"
    assert chain["anomaly_dependency"]["remainder_units"] == 192502
    assert chain["anomaly_dependency"]["modulus_units"] == 275544
    assert ratio(chain["winter_to_mean_units_exact"]) == Fraction(1223948, 3)
    assert ratio(chain["winter_exact_minus_printed_units"]) == Fraction(2, 3)
    assert ratio(chain["rain_cycle_days_exact"]) == Fraction(433335, 10000)
    assert ratio(chain["rain_cycle_days_using_printed_denominator"]) == Fraction(
        433335, 1000
    )


def test_ordinary_and_leap_eleventh_month_are_distinct_and_not_relabelled():
    result = arithmetic.futen_arithmetic_reference()
    rows = result["all_fifteen_row_checks"]
    regular, leap = rows[12:14]
    assert (regular["month"], regular["is_leap_month"]) == (11, False)
    assert (leap["month"], leap["is_leap_month"]) == (11, True)
    assert regular["calculated_mean"]["cycle_units"] == 185636
    assert leap["calculated_mean"]["cycle_units"] == 480942
    comparison = result["plus_eleven_label_comparison"]
    assert comparison["source_step_label"] == "11月1日"
    assert comparison["table_month_key"] == [1164, 11, True]
    assert not comparison["source_months_relabelled"]


def test_threshold_disagreement_is_exposed_instead_of_choosing_a_new_day_boundary():
    result = arithmetic.futen_arithmetic_reference()
    senmyo, futen = result["threshold_unit_checks"]
    assert ratio(senmyo["nominal_hours_from_printed_units"]) == Fraction(128, 7)
    assert ratio(senmyo["units_at_printed_nominal_hour"]) == 6300
    assert senmyo["printed_threshold_units"] == 6400
    assert ratio(senmyo["printed_units_minus_units_at_hour"]) == 100
    assert ratio(senmyo["nominal_hours_minus_printed_hour"]) == Fraction(2, 7)
    assert ratio(futen["nominal_hours_from_printed_units"]) == 18
    assert ratio(futen["printed_units_minus_units_at_hour"]) == 0
    assert all(not r["threshold_selected_for_calendar"] for r in [senmyo, futen])
    units = result["conditional_unit_model_reference"]
    assert units["source_pdf_sha256"] == (
        "4ebd396bd1e32d16b68a6acff56c0b18039430c4889feda38ad3f57b7beaac2c"
    )
    assert units["unit_denominators_are_selected_2015_models"] is True
    assert units["unit_denominators_printed_in_selected_2024_captions"] is False
    for key in [
        "historical_absolute_dates_assigned",
        "historical_calendar_adjudicated",
        "T1299_pingming_or_hinoo_half_established",
        "leap_short_month_priority_established",
        "applied_to_current_date_or_mansion",
    ]:
        assert result["scope"][key] is False


@pytest.mark.parametrize(
    "mutation",
    ["drop_row", "merge_leap", "change_qi_ying", "erase_name", "change_threshold"],
)
def test_source_changes_require_recollation_not_silent_score_improvement(
    monkeypatch, tmp_path, mutation
):
    bundle = json.loads(arithmetic.SOURCE.read_bytes())
    if mutation == "drop_row":
        bundle["rows"].pop()
    elif mutation == "merge_leap":
        bundle["rows"][13]["is_leap_month"] = False
    elif mutation == "change_qi_ying":
        bundle["constants"]["qi_ying_units"] = 0
    elif mutation == "erase_name":
        bundle["printed_example"]["mean_cycle_name_literal"] = "丁亥"
    elif mutation == "change_threshold":
        bundle["threshold_labels"][0]["printed_threshold_units"] = 6300
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False))
    monkeypatch.setattr(arithmetic, "SOURCE", path)
    with pytest.raises(ValueError, match="重新校核"):
        arithmetic.futen_arithmetic_reference()


def test_reference_is_integrated_and_returns_isolated_data():
    expected = arithmetic.futen_arithmetic_reference()
    actual = futen_clock_reference()["selected_reconstruction_arithmetic"]
    assert actual == expected
    actual["rows"][0]["year"] = 9999
    assert arithmetic.futen_arithmetic_reference() == expected
    text = "\n".join(arithmetic.futen_arithmetic_lines(deepcopy(expected)))
    for value in [
        "15行",
        "閏餘o",
        "192502",
        "200759",
        "232576",
        "434041",
        "壬午",
        "丁亥",
        "480942",
        "185636",
        "1223948/3",
        "2/3",
        "6400",
        "6300",
        "128/7",
        "原文书",
        "订正函数",
        "平明",
        "半日",
        "现实预测",
        "采用未加閏應",
        "2015研究",
    ]:
        assert value in text


@pytest.mark.parametrize("change", ["drop_model", "change_units"])
def test_conditional_units_are_bound_to_the_actual_two_source_models(
    monkeypatch, tmp_path, change
):
    bundle = json.loads(arithmetic.UNIT_SOURCE.read_bytes())
    if change == "drop_model":
        bundle["models"].pop()
    else:
        bundle["models"][1]["day_units"] = 10000
    path = tmp_path / "unit-models.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False))
    monkeypatch.setattr(arithmetic, "UNIT_SOURCE", path)
    with pytest.raises(ValueError, match="研究模型"):
        arithmetic.futen_arithmetic_reference()


def test_modern_host_source_and_missing_validation_receipt_are_explained():
    from fatebridge.core.sukuyo import calendar_mansion, day_evidence

    calendar = calendar_mansion("2026-02-17", "10:00:00", "+08:00")
    text = day_evidence(calendar)["reading_text"]
    assert calendar["calendar_system"] == "modern_chinese_lunisolar"
    assert calendar["calendar_backend"] in text
    assert calendar["calendar_source"] in text
    assert "HKO（香港天文台）年度历表参考" in text
    assert "本次返回未附现代中国历日的全域独立验收范围" in text
