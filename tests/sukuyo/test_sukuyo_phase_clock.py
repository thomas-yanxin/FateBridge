"""Ritual phase conditions must not silently redefine a civil input day."""

from copy import deepcopy

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_phase_clock import (
    SOURCE,
    phase_clock_reference,
    validate_selected_claims,
)
from fatebridge.core.sukuyo_sources import load_source
from scripts.sukuyo.check_sukuyo_phase_clock import verify_primary
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def test_current_fifteenth_day_name_does_not_assert_the_ritual_phase_condition():
    calendar = calendar_mansion("2026-10-24", "05:30:00", "+08:00")
    before = deepcopy(calendar)
    day = day_evidence(calendar)
    reference = day["calendar_day"]["clock_doctrine"]["phase_and_time_reference"]
    current = reference["host_day_number_reference"]
    assert calendar == before
    assert calendar["lunar_day"] == 15 and calendar["natal_su27"] == "昴"
    assert (current["named_half"], current["named_half_day"]) == ("白", 15)
    assert current["ritual_phase_condition_status"] == "not_evaluated"
    assert not current["source_conditional_case_applied_to_this_date"]
    condition = reference["phase_day_distinction"]["conditional_source_case"]
    assert condition["ritual_half_under_stated_condition"] == "黑"
    assert not condition["condition_established_by_civil_month_length_alone"]
    text = day["reading_text"]
    assert "小月在白分内时，其月十五日即属黑分" in text
    assert "这不是实测月相或角距tithi" in text
    assert "不能只凭民用小月二十九天就判定条件成立" in text


def test_selected_text_keeps_morning_character_and_thirty_time_debate():
    reference = phase_clock_reference(16)
    assert reference["host_day_number_reference"]["named_half"] == "黑"
    assert len(reference["sources"]) == 2
    assert sum(len(s["selected_quotations"]) for s in reference["sources"]) == 5
    assert reference["morning_reference"]["selected_character_pair"] == ["晨", "辰"]
    debate = reference["time_wording_reference"]
    assert debate["T1796_literal"] == "西方曆法晝夜各有三十時"
    assert debate["T2216_unresolved_literals"] == ["上一件尚未詳", "後釋本據尚未分明"]
    assert not debate["selected_debate_resolved"]
    assert debate["accepted_modern_minutes_per_time_unit"] is None
    assert not debate["T1299_day_eight_night_eight_replaced"]


@pytest.mark.parametrize(
    "mutation",
    [
        "condition_day",
        "moon_examples",
        "quarter_name",
        "quarter_role",
        "full_role",
        "comment_moon",
        "comment_next",
        "comment_half",
        "morning",
        "time",
        "unresolved",
    ],
)
def test_interpretive_controls_cannot_drift_from_the_selected_text(mutation):
    data = load_source(SOURCE).data
    phase = data["phase_day_distinction"]
    if mutation == "condition_day":
        phase["conditional_source_case"]["assumed_civil_day_number"] = 14
    elif mutation == "moon_examples":
        phase["phase_reference"]["full_moon_civil_day_examples"] = [14, 15]
    elif mutation == "quarter_name":
        phase["phase_reference"]["quarter_source_name"] = "九日"
    elif mutation == "quarter_role":
        phase["phase_reference"]["quarter_source_name"] = "十四日"
    elif mutation == "full_role":
        phase["phase_reference"]["full_moon_source_name"] = "八日"
    elif mutation == "comment_moon":
        phase["commentarial_case"]["full_moon_at_civil_day"] = 15
    elif mutation == "comment_next":
        phase["commentarial_case"]["next_civil_day"] = 16
    elif mutation == "comment_half":
        phase["commentarial_case"]["next_day_half_under_stated_condition"] = "白"
    elif mutation == "morning":
        data["morning_reference"]["character_distinction_literal"] = "晨辰可以通用"
    elif mutation == "time":
        data["time_wording_reference"]["T2216_question_literal"] = "日夜通計合有六十時"
    else:
        data["time_wording_reference"]["T2216_unresolved_literals"] = ["已詳"]
    with pytest.raises(ValueError, match="未绑定所选原句"):
        validate_selected_claims(data)


@pytest.mark.parametrize("mutation", ["duplicate", "omit"])
def test_selected_source_context_cannot_be_duplicated_or_omitted(mutation):
    data = load_source(SOURCE).data
    if mutation == "duplicate":
        data["sources"].append(deepcopy(data["sources"][0]))
    else:
        data["sources"][1]["selected_quotations"].pop()
    with pytest.raises(ValueError, match="完整唯一|选段不完整"):
        validate_selected_claims(data)


def test_returned_data_cannot_change_later_readings_or_choose_a_leap_model():
    first = phase_clock_reference(1)
    first["phase_day_distinction"]["commentarial_case"]["next_civil_day"] = 16
    assert (
        phase_clock_reference(1)["phase_day_distinction"]["commentarial_case"][
            "next_civil_day"
        ]
        == 15
    )
    calendar = calendar_mansion(
        "2036-07-23",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    day = day_evidence(calendar)
    assert day["calendar"]["candidate_su27s"] == ["星", "鬼"]
    assert day["calendar"]["natal_su27"] is None
    assert (
        day["calendar_day"]["clock_doctrine"]["phase_and_time_reference"]["scope"][
            "leap_short_month_priority_established"
        ]
        is False
    )


@pytest.mark.parametrize("day", [True, 0, 31, 1.5])
def test_day_name_reference_rejects_non_dates(day):
    with pytest.raises(ValueError, match="1..30整数"):
        phase_clock_reference(day)


def test_offline_checker_does_not_claim_actual_capture_or_phase_measurement():
    result = verify_primary()
    assert result["numerical_controls_bound_to_selected_text"]
    assert not result["all_actual_captures_rechecked"]
    assert result["actual_capture_bytes_rechecked"] == []
    assert not result["actual_lunar_phase_or_tithi_computed"]


@pytest.mark.parametrize("source", ["T1796", "T2216"])
def test_checker_rejects_substituted_publisher_bytes(tmp_path, source):
    path = tmp_path / source
    path.write_bytes(b"substituted")
    with pytest.raises(ValueError, match="实际来源字节不同"):
        verify_primary({source: path})


@pytest.mark.parametrize("date", ["2026-10-24", "2036-07-23"])
def test_phase_and_time_reference_across_actual_rest_native_mcp_cli(
    monkeypatch, capsys, date
):
    kwargs = (
        {}
        if date == "2026-10-24"
        else {
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        }
    )
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": date, "time": "05:30:00", "zone": "+08:00", **kwargs},
        [
            "sukuyo.calendar_day.clock_doctrine.phase_and_time_reference",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
