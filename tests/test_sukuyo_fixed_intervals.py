"""Full fixed-offset preimages against the frozen independent intersection oracle."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_date_support import local_date_support
from fatebridge.services.divination import calculate_sukuyo_compatibility

REFERENCE = (
    Path(__file__).parent / "data/sukuyo-fixed-interval-before-production-v72.json"
)
RAW = REFERENCE.read_bytes()
ROWS = json.loads(RAW)["expected_cases"]
EXPECTED_REFERENCE_SHA256 = (
    "1098368b23fdeb8e8549ada27993d9a5163b20d121e37cf28f4bfe0327975793"
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def epoch_microseconds(text):
    # Year-zero endpoints are checked through exact integer fields, below.
    delta = datetime.fromisoformat(text) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def test_independent_reference_was_frozen_before_the_production_repair():
    assert hashlib.sha256(RAW).hexdigest() == EXPECTED_REFERENCE_SHA256
    assert len(ROWS) == 366
    assert json.loads(RAW)["no_domain_or_production_timezone_parser_imported"]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["id"])
def test_all_fixed_offset_preimages_equal_independent_interval_intersections(row):
    result = local_date_support(
        row["date"], row["zone"], calendar_offset_hours=row["reference_hours"]
    )
    assert result["possible_calendar_dates"] == row["expected_calendar_dates"]
    assert len(result["utc_support_intervals"]) == len(row["expected_intervals"])
    for actual, expected in zip(
        result["utc_support_intervals"], row["expected_intervals"], strict=True
    ):
        assert actual["calendar_date"] == expected["calendar_date"]
        for edge in ("start", "end"):
            exact = actual.get(edge + "_utc_epoch_microseconds")
            if exact is None:
                if edge + "_utc_epoch_seconds" in actual:
                    exact = actual[edge + "_utc_epoch_seconds"] * 1000000
                else:
                    exact = epoch_microseconds(
                        actual[
                            edge
                            + (
                                "_utc_inclusive"
                                if edge == "start"
                                else "_utc_exclusive"
                            )
                        ]
                    )
            assert int(exact) == expected[edge + "_utc_epoch_microseconds"]
    assert result["civil_support_seconds"] == 86400
    assert result["complete_under_loaded_timezone_rules"]
    assert not result["birth_time_imputed"]


def test_one_microsecond_before_new_year_cannot_be_dropped_as_a_determined_mansion():
    result = calendar_mansion("2025-01-29", zone="8.0000000002777778")
    assert result["status"] == "partial" and result["natal_su27"] is None
    assert [row["calendar_date"] for row in result["calendar_candidates"]] == [
        "2025-01-28",
        "2025-01-29",
    ]
    assert len(result["candidate_su27s"]) == 2
    assert result["input_datetime"] is None and not result["birth_time_known"]


def test_ancient_lower_boundary_keeps_the_one_microsecond_year_zero_branch():
    result = calendar_mansion(
        "0001-01-01",
        zone="9.0000000002777778",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert result["date_support"]["possible_calendar_dates"] == [
        "0000-12-31",
        "0001-01-01",
    ]
    assert result["out_of_range_calendar_dates"] == ["0000-12-31"]
    assert not result["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]


def test_leap_month_overlap_keeps_both_reference_dates_and_every_existing_rule_branch():
    result = calendar_mansion(
        "0806-07-23",
        zone="9.0000000002777778",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert [row["calendar_date"] for row in result["calendar_candidates"]] == [
        "0806-07-22",
        "0806-07-23",
    ]
    leap = result["calendar_candidates"][1]
    assert leap["calendar_day_part"] == "first_half"
    assert leap["candidate_su27s"] == ["星", "鬼"] and leap["natal_su27"] is None
    assert (
        len(
            leap["profile_calculation"]["short_month_assignment"][
                "leap_short_month_precedence"
            ]["reconstruction_calculations"]
        )
        == 2
    )


def test_decimal_rounding_policy_is_delivered_even_when_rounding_matches_the_host_zone():
    result = calendar_mansion("2025-01-29", zone="8.0000000000000000001")
    assert (
        result["input_timezone_rules"]["decimal_hour_rounding"]
        == "nearest_microsecond_ties_even"
    )
    assert result["input_timezone_rules"]["rounding_error_bound_seconds"] == "0.0000005"
    assert result["calendar_date"] == "2025-01-29"
    assert result["input_datetime"] is None


def test_pair_cannot_lose_a_date_branch_or_impute_both_unknown_clocks():
    result = calculate_sukuyo_compatibility(
        person1_date="2025-01-29",
        person1_zone="8.0000000002777778",
        person2_date="2025-01-28",
        person2_zone="7.9999999997222222",
    )
    assert result["status"] == "partial" and result["pair"] is None
    for key in ("person1", "person2"):
        calendar = result[key]["calendar"]
        assert calendar["input_datetime"] is None and not calendar["birth_time_known"]
        assert len(calendar["calendar_candidates"]) == 2
        assert (
            calendar["input_timezone_rules"]["decimal_hour_rounding"]
            == "nearest_microsecond_ties_even"
        )


def test_ancient_microsecond_wire_keeps_exact_decimal_integers():
    result = local_date_support(
        "0001-01-01", "9.0000000002777778", calendar_offset_hours=9
    )
    first = json.loads(json.dumps(result))["utc_support_intervals"][0]
    assert isinstance(first["start_utc_epoch_microseconds"], str)
    assert isinstance(first["end_utc_epoch_microseconds"], str)
    assert (
        int(first["end_utc_epoch_microseconds"])
        - int(first["start_utc_epoch_microseconds"])
        == 1
    )


def test_precision_and_interval_length_are_delivered_from_actual_fields():
    calendar = calendar_mansion("2025-01-29", zone="8.0000000002777778")
    assert (
        calendar["input_timezone_rules"]["effective_offset_microseconds"]
        == "28800000001"
    )
    text = day_evidence(calendar)["reading_text"]
    assert "区间长0.000001秒" in text and "UTC+08:00:00.000001" in text
    assert "十进制整数字符串" in text and "不是出生概率" in text
    pair = calculate_sukuyo_compatibility(
        person1_date="2025-01-29",
        person1_zone="8.0000000002777778",
        person2_date="2025-01-28",
        person2_zone="7.9999999997222222",
    )
    assert "区间长0.000001秒" in pair["summary"]
