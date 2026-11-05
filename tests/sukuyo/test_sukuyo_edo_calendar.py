"""Named historical context must not replace printed month labels or clocks."""

import hashlib
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_historical_calendar as historical
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_edo_calendar import SOURCE, calendar_method_reference


def test_data_bytes_match_frozen_source_readings_before_production():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == (
        "9a77377093e450e6b91edcf8e3c2ea2cb0ceb5b1fb1ea30eaabd9c783671a5e7"
    )


@pytest.mark.parametrize(
    "year,method",
    [
        (1685, "jokyo"),
        (1754, "jokyo"),
        (1755, "horeki"),
        (1770, "horeki"),
        (1771, "corrected_horeki"),
        (1797, "corrected_horeki"),
        (1798, "kansei"),
        (1843, "kansei"),
        (1844, "tenpo"),
        (1872, "tenpo"),
    ],
)
def test_named_period_is_lunar_year_context_not_era_name(year, method):
    ref = calendar_method_reference(year, 1, False)
    assert ref["calendar_period"]["id"] == method
    assert (
        ref["period_assignment_basis"]
        == "printed_lunar_year_not_civil_year_or_era_name"
    )
    assert not ref["calendar_labels_changed"]
    assert not ref["sukuyo_daybreak_or_half_mapping_established"]
    assert not ref["leap_short_month_priority_established"]
    assert ref["independent_historical_observations_added"] == 0


def test_horeki_era_year_four_during_civil_1755_still_uses_jokyo_context():
    source = historical.date_reference(date(1755, 1, 13))
    assert source["printed_lunar_year"] == 1754
    assert source["edo_calendar_method_reference"]["calendar_period"]["id"] == "jokyo"
    assert source["edo_calendar_method_reference"]["intercalation_research"] is None


def test_complete_ten_rows_and_later_counterexamples_are_retained():
    ref = calendar_method_reference(1792, 2, True)
    research = ref["intercalation_research"]
    rows = research["all_ten_selected_rows"]
    assert [r["year"] for r in rows] == [
        1773,
        1775,
        1778,
        1781,
        1784,
        1786,
        1789,
        1792,
        1794,
        1797,
    ]
    assert [r["year"] for r in rows if r["source_describes_irregular_placement"]] == [
        1773,
        1775,
        1786,
    ]
    current = research["current_year_record"]
    assert current["computed_new_moon_literal"] == "35.686"
    assert current["computed_principal_term_literal"] == "35.610"
    assert not current["source_describes_irregular_placement"]
    assert not research["author_rule_applied_to_primary"]
    assert not research["decimal_strings_are_modern_clock_times"]
    rows.clear()
    assert (
        len(
            calendar_method_reference(1792, 2, True)["intercalation_research"][
                "all_ten_selected_rows"
            ]
        )
        == 10
    )


def test_rule_next_month_is_not_used_as_a_replacement_leap_month():
    current = calendar_method_reference(1773, 3, True)["intercalation_research"]
    row = current["current_year_record"]
    assert row["published_leap_month_literal"] == "3月"
    assert row["month_after_conventional_leap_literal"] == "3月"
    assert row["conventional_leap_month_in_table2"] == 2
    assert current["current_month_is_source_reported_leap"]
    assert not calendar_method_reference(1773, 2, True)["intercalation_research"][
        "current_month_is_source_reported_leap"
    ]


def test_printed_size_and_covered_reform_days_remain_different():
    source = historical.date_reference(date(1872, 12, 31))
    assert source["source_month_length_days"] == 2
    note = source["edo_calendar_method_reference"]["reform_month_length_reference"]
    assert note["NDL_nominal_days_from_大"] == 30
    assert note["covered_reference_days"] == 2
    assert note["raw_difference_retained"]
    assert note["nominal_size_does_not_extend_covered_calendar"]
    with pytest.raises(ValueError):
        historical.lunar_fields(date(1873, 1, 1))


def test_outside_named_source_period_does_not_load_or_invent_context(monkeypatch):
    import fatebridge.core.sukuyo_edo_calendar as edo

    monkeypatch.setattr(edo, "SOURCE", Path("/not-an-available-reference.json"))
    assert edo.calendar_method_reference(1684, 12, False) is None
    assert edo.calendar_method_reference(1873, 1, False) is None


def test_native_reading_explains_nominal_reform_length_and_clock_limit():
    calendar = calendar_mansion(
        "1872-12-31", zone="+09:00", calendar_basis="japanese_naoj_historical_utc09"
    )
    text = day_evidence(calendar)["reading_text"]
    assert "天保暦" in text
    assert "原定月大小与实际覆盖天数分开" in text
    assert "30／2" in text
    assert "不据此复原古代钟时或原典平明／半日界" in text


@pytest.mark.parametrize("value", ["1755-01-13", "1773-04-22"])
def test_context_matches_rest_native_mcp_and_cli(monkeypatch, capsys, value):
    from tests.sukuyo.test_sukuyo_transports import (
        test_calendar_and_relations_across_all_real_transports as check,
    )

    check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": value,
            "zone": "+09:00",
            "calendar_basis": "japanese_naoj_historical_utc09",
            "calendar_profile": "hinoo_t1299_host27",
        },
        [
            "input_normalized",
            "params",
            "chart",
            "astronomy",
            "sukuyo.calendar",
            "sukuyo.reading_text",
            "validation",
            "summary",
        ],
    )
