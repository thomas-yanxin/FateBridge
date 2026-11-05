"""Source-specific Sukuyo scenarios through REST, MCP and CLI."""

import pytest

from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_conditional_mansion_days_across_all_surfaces(monkeypatch, capsys, part):
    payload = {
        "date": "2024-08-04",
        "time": "09:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
        "natal_mansion": "室",
        "activity": "travel",
        "activity_details": ["personal_departure"],
    }
    if part is not None:
        payload["calendar_day_part"] = part
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.personal_day",
            "sukuyo.activity_assessment",
            "sukuyo.candidate_mansion_days",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["2024-06-15", "1957-09-24"])
def test_whole_day_lists_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.japanese_selected_reference.primary_general_day_reference",
            "sukuyo.calendar_day.japanese_selected_reference.full_favorable_membership_comparison",
            "sukuyo.calendar_day.classifications",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
@pytest.mark.parametrize(
    "date,reference",
    [
        ("1957-09-24", "image_witness_context_followup"),
        ("1957-09-24", "calendar_clause_meanings"),
        ("1957-09-24", "natal_half_application"),
        ("1903-06-25", "image_witness_native_completion"),
        ("1957-09-24", "later_seibunkan_comparison"),
    ],
)
def test_critical_source_context_across_rest_mcp_cli(
    monkeypatch, capsys, part, date, reference
):
    payload = {
        "date": date,
        "time": "12:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
    if part is not None:
        payload["calendar_day_part"] = part
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            f"sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.{reference}",
            "sukuyo.calendar.status",
            "sukuyo.calendar.natal_su27",
            "sukuyo.calendar.candidate_su27s",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize(
    "first_part, second_part, first_date, first_zone",
    [
        ("first_half", "first_half", "1341-05-24", "+09:00"),
        (None, None, "1341-05-24", "+09:00"),
        ("first_half", "first_half", "1341-05-23", "+08:00"),
        ("second_half", "second_half", "1341-05-24", "+09:00"),
    ],
)
def test_sukuyo_joint_support_across_rest_native_mcp_and_cli(
    monkeypatch, capsys, first_part, second_part, first_date, first_zone
):
    payload = {
        "person1_date": first_date,
        "person1_zone": first_zone,
        "person2_date": "1341-05-24",
        "person2_zone": "+09:00",
        "calendar_profile": "hinoo_t1299_host27",
        "calendar_basis": "japanese_naoj_historical_utc09",
    }
    for key, value in (
        ("person1_calendar_day_part", first_part),
        ("person2_calendar_day_part", second_part),
    ):
        if value is not None:
            payload[key] = value
    _check_surfaces(
        monkeypatch,
        capsys,
        "sukuyo_compatibility",
        payload,
        ["person1", "person2", "candidate_relation_analysis", "summary"],
    )


@pytest.mark.parametrize(
    "date,basis,zone",
    [
        ("2024-02-11", "chinese_hko_utc08", "+08:00"),
        ("1903-06-25", "chinese_hko_utc08", "+08:00"),
        ("0821-01-11", "japanese_naoj_historical_utc09", "+09:00"),
    ],
)
def test_sukuyo_lingbi_reference_across_actual_transports(
    monkeypatch, capsys, date, basis, zone
):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": zone,
            "calendar_basis": basis,
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.kenyu_lingbi_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["2017-10-17", "2017-10-19", "1957-09-24"])
def test_sukuyo_pair_comparison_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        ["sukuyo.kenyu_lingbi_reference", "sukuyo.calendar", "sukuyo.reading_text"],
    )


@pytest.mark.parametrize(
    "date,basis,zone",
    [
        ("2025-02-02", "chinese_hko_utc08", "+08:00"),
        ("1957-09-24", "chinese_hko_utc08", "+08:00"),
        ("0820-03-22", "japanese_naoj_historical_utc09", "+09:00"),
    ],
)
def test_sukuyo_printed_clock_across_actual_transports(
    monkeypatch, capsys, date, basis, zone
):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": zone,
            "calendar_basis": basis,
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.kenyu_printed_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["2025-01-06", "2025-01-11", "1957-09-24"])
def test_sukuyo_enpo_reference_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.special_day_evidence",
            "sukuyo.calendar_day.clock_doctrine",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_local_surfaces_keep_old_capture_new_followup_and_half_condition(
    monkeypatch, capsys, part
):
    payload = {
        "date": "1903-06-25",
        "time": "12:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
    if part is not None:
        payload["calendar_day_part"] = part
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
            "sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_native_followup",
            "sukuyo.calendar.status",
            "sukuyo.calendar.natal_su27",
            "sukuyo.calendar.candidate_su27s",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_quotation_comparison_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation",
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation.subsequent_quotation_comparison.kanbun_printed_witness",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_research_direction_reference_across_actual_transports(
    monkeypatch, capsys, date
):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.dayan_reconstruction_scope_reference",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )


@pytest.mark.parametrize("date", ["2025-01-29", "1903-06-25"])
def test_printed_collation_across_actual_transports(monkeypatch, capsys, date):
    suffix = "calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation"
    payload = {
        "date": date,
        "time": "12:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
    fields = ["sukuyo." + suffix, "sukuyo.calendar", "sukuyo.reading_text"]
    _check_surfaces(monkeypatch, capsys, "suzhan", payload, fields)


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_zhidu_context_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation.subsequent_quotation_comparison.upstream_calendar_context",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
