"""Retain the complete development grid, including unknown table conditions."""

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_kenyu_lingbi import lookup_lingbi_interval
from fatebridge.core.sukuyo_kenyu_pairs import conditional_pair_comparison
from fatebridge.core.sukuyo_profiles import fullmoon_calculation
from scripts.check_sukuyo_kenyu_pairs import verify_pairs


def test_sukuyo_pair_source_matches_both_literal_membership_reads():
    report = verify_pairs()
    assert report["errors"] == []
    assert report["readable_memberships_checked"] == 27
    assert report["no_fourth_monday_member_inserted"]
    assert not report["independent_human_image_acceptance"]


def test_sukuyo_complete_preimplementation_grid_keeps_all_unlisted_conditions():
    fixture = json.loads(
        (Path(__file__).parent / "data/sukuyo-kenyu-component-grid.json").read_bytes()
    )
    expected = {
        (r[0], r[1], r[2]): dict(zip(fixture["full_grid_columns"], r))
        for r in fixture["full_grid"]
    }
    counts = Counter()
    for month in range(1, 13):
        for day in range(1, 31):
            calendar = {
                "lunar_month": month,
                "lunar_day": day,
                "profile_calculation": {
                    "host_calculation": fullmoon_calculation(month, day, SU27_ORDER)
                },
            }
            lookups = [
                lookup_lingbi_interval(month, first, day) for first in "日月火水木金土"
            ]
            comparison = conditional_pair_comparison(calendar, lookups, None)
            assert comparison["status"] == "conditional_component_model"
            for row in comparison["conditional_month_start_comparisons"]:
                key = (month, row["condition_month_start_luminary"], day)
                baseline = expected[key]
                assert (
                    row["baseline_fullmoon27_mansion"]
                    == baseline["t1299_fullmoon27_mansion"]
                )
                assert (
                    row["hypothetical_day_luminary"]
                    == baseline["hypothetical_day_luminary"]
                )
                assert (
                    row["conditional_pair_match"]
                    is baseline["ndl_pair_model_membership"]
                )
                assert (
                    row["membership_in_printed_interval"]
                    is baseline["nagoya_printed_interval_membership"]
                )
                assert row["comparison"] == baseline["comparison"]
                counts[row["comparison"]] += 1
    assert len(expected) == sum(counts.values()) == 2520
    assert (
        dict(counts)
        == fixture["counts"]
        == {
            "listed_agree_true": 357,
            "listed_agree_false": 333,
            "unlisted_pair_model_false": 1827,
            "unlisted_pair_model_true": 3,
        }
    )


@pytest.mark.parametrize(
    "date,day,mansion,ruler",
    [
        ("2017-10-17", 28, "角", "火"),
        ("2017-10-18", 29, "亢", "水"),
        ("2017-10-19", 30, "氐", "木"),
    ],
)
def test_sukuyo_unlisted_positive_is_explained_without_filling_the_month_table(
    date, day, mansion, ruler
):
    result = day_evidence(calendar_mansion(date, "06:30:00"))
    reference = result["kenyu_lingbi_reference"]
    selected = reference["weekday_mansion_comparison"][
        "selected_civil_condition_comparison"
    ]
    assert selected["condition_lunar_day"] == day
    assert selected["condition_month_start_luminary"] == "水"
    assert selected["baseline_fullmoon27_mansion"] == mansion
    assert selected["hypothetical_day_luminary"] == ruler
    assert selected["conditional_pair_match"] is True
    assert selected["membership_in_printed_interval"] is None
    assert selected["comparison"] == "unlisted_pair_model_true"
    assert (
        reference["selected_civil_month_start_lookup"]["membership_in_printed_interval"]
        is None
    )
    assert len(reference["printed_rows"]) == 23
    assert (
        f"{ruler}曜、基准{mansion}宿，组合命中，月表未列、判断未定"
        in result["reading_text"]
    )
    assert reference["applied_to_primary_or_activities"] is False


def test_sukuyo_leap_keeps_seven_conditions_and_uses_unadjusted_baseline_only():
    calendar = calendar_mansion(
        "1957-09-24",
        "06:30:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    before = deepcopy(calendar)
    result = day_evidence(calendar)
    comparison = result["kenyu_lingbi_reference"]["weekday_mansion_comparison"]
    assert calendar == before
    assert result["day_mansion"] is None
    assert set(calendar["candidate_su27s"]) == {"角", "轸"}
    assert comparison["baseline_fullmoon27_calculation"]["direct_mansion"] == "角"
    assert not comparison["selected_profile_mansion_or_hinoo_half_used"]
    assert comparison["selected_civil_condition_comparison"] is None
    assert len(comparison["conditional_month_start_comparisons"]) == 7
    for first in "日月火水木金土":
        assert f"若朔为{first}曜" in result["reading_text"]
    comparison["source_reference"]["memberships"]["月"].append("牛")
    comparison["baseline_fullmoon27_calculation"]["direct_mansion"] = "牛"
    fresh = day_evidence(calendar)["kenyu_lingbi_reference"][
        "weekday_mansion_comparison"
    ]
    assert len(fresh["source_reference"]["memberships"]["月"]) == 3
    assert fresh["baseline_fullmoon27_calculation"]["direct_mansion"] == "角"


@pytest.mark.parametrize(
    "damage", ["missing", "different_day", "different_digest", "disagree"]
)
def test_sukuyo_pair_model_never_substitutes_the_selected_mansion_for_missing_basis(
    damage,
):
    calendar = calendar_mansion("2017-10-17", "06:30:00")
    host = calendar["profile_calculation"]["host_calculation"]
    if damage == "missing":
        del calendar["profile_calculation"]["host_calculation"]
    elif damage == "different_day":
        host["lunar_day"] = 27
    elif damage == "different_digest":
        host["source_bundle_sha256"] = "0" * 64
    else:
        host["methods_agree"] = False
    lookups = [lookup_lingbi_interval(8, first, 28) for first in "日月火水木金土"]
    comparison = conditional_pair_comparison(calendar, lookups, lookups[3])
    assert comparison["status"].startswith("not_evaluated")
    assert comparison["conditional_month_start_comparisons"] == []
    assert comparison["selected_civil_condition_comparison"] is None


def test_sukuyo_pair_model_refuses_inconsistent_period_context():
    calendar = calendar_mansion("2017-10-17", "06:30:00")
    with pytest.raises(ValueError, match="条件不一致"):
        conditional_pair_comparison(
            calendar, [lookup_lingbi_interval(8, "水", 27)], None
        )
