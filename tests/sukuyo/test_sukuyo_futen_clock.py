"""Keep historical unit models, printed differences and current dates distinct."""

from copy import deepcopy
from fractions import Fraction

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_futen_clock import (
    FUTEN,
    SENMYO,
    decode_clock,
    futen_clock_lines,
    futen_clock_reference,
)
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def ratio(value):
    return Fraction(value["numerator"], value["denominator"])


def test_all_three_published_points_and_both_models_keep_exact_residuals():
    reference = futen_clock_reference()
    points = reference["selected_point_comparisons"]
    assert [r["literal"] for r in points] == ["未6刻31分", "酉初刻6分", "戌2刻26分"]
    assert [
        ratio(r["decoded"][FUTEN]["units_from_selected_day_origin"]) for r in points
    ] == [Fraction(18143, 3), Fraction(21268, 3), Fraction(24428, 3)]
    assert [r["printed_futen_units"] for r in points] == [6047, 7089, 8142]
    assert [ratio(r["exact_futen_minus_printed_units"]) for r in points] == [
        Fraction(2, 3),
        Fraction(1, 3),
        Fraction(2, 3),
    ]
    assert [
        ratio(r["decoded"][SENMYO]["units_from_selected_day_origin"]) for r in points
    ] == [5085, 5956, 6844]
    assert [ratio(r["exact_senmyo_in_10000_units"]) for r in points] == [
        Fraction(84750, 14),
        Fraction(148900, 21),
        Fraction(171100, 21),
    ]
    assert [ratio(r["exact_senmyo_in_10000_minus_printed"]) for r in points] == [
        Fraction(-3, 7),
        Fraction(10, 21),
        Fraction(-8, 21),
    ]
    assert all(ratio(r["exact_senmyo_minus_printed_units"]) == 0 for r in points)
    interval = reference["exact_intervals"][FUTEN]
    assert [
        ratio(interval[k])
        for k in [
            "start_to_middle_units",
            "middle_to_end_units",
            "total_units",
            "second_minus_first_interval_units",
        ]
    ] == [Fraction(3125, 3), Fraction(3160, 3), 2095, Fraction(35, 3)]
    assert reference["printed_futen_intervals"] == {
        "start_to_middle": 1042,
        "middle_to_end": 1053,
        "total": 2095,
    }
    assert not interval["source_asymmetry_removed"]


def test_explicit_clock_origin_preserves_previous_nominal_day_and_exact_boundary():
    first = decode_clock("子初刻0分", model=FUTEN)
    assert first["nominal_day_shift"] == -1
    assert ratio(first["nominal_day_fraction_from_selected_origin"]) == Fraction(-1, 24)
    assert ratio(first["fraction_within_shifted_nominal_day"]) == Fraction(23, 24)
    assert (
        ratio(
            decode_clock("子時正", model=FUTEN)[
                "nominal_day_fraction_from_selected_origin"
            ]
        )
        == 0
    )
    boundary = decode_clock("亥8刻28分", model=SENMYO)
    assert boundary["at_next_branch_boundary"]
    assert ratio(boundary["nominal_day_fraction_from_selected_origin"]) == Fraction(
        23, 24
    )
    assert not first["civil_date_or_clock_assigned"]
    assert ratio(
        decode_clock("丑初刻", model=FUTEN)["nominal_day_fraction_from_selected_origin"]
    ) == Fraction(1, 24)


@pytest.mark.parametrize(
    "model,literal",
    [
        (FUTEN, "未6刻100分"),
        (SENMYO, "未6刻84分"),
        (FUTEN, "未8刻34分"),
        (SENMYO, "未8刻29分"),
        (FUTEN, "未6刻半"),
        (FUTEN, "未6:31"),
        (FUTEN, "未時"),
        (FUTEN, None),
        ("guessed_1240", "未6刻31分"),
    ],
)
def test_unknown_model_or_ambiguous_and_overflow_clock_is_rejected(model, literal):
    with pytest.raises(ValueError):
        decode_clock(literal, model=model)


def test_same_named_units_and_returned_source_are_not_collapsed_or_mutable():
    expected = futen_clock_reference()
    actual = futen_clock_reference()
    actual["models"][0]["day_units"] = 8400
    actual["selected_point_comparisons"][0]["literal"] = "changed"
    assert futen_clock_reference() == expected
    assert ratio(expected["exact_units_per_double_hour"][FUTEN]) == Fraction(2500, 3)
    assert ratio(expected["exact_units_per_double_hour"][SENMYO]) == 700
    assert expected["unit_distinctions"]["1164_calculation"] == {
        "parts_per_day": 100,
        "subparts_per_part": 100,
    }
    assert not expected["unit_distinctions"]["995_expression_certified_exact_ratio"]
    text = "\n".join(futen_clock_lines(expected))
    for number in [
        "18143/3",
        "21268/3",
        "24428/3",
        "1042",
        "1053",
        "35/3",
        "子半",
        "平明",
        "1240",
        "1164",
        "995",
    ]:
        assert number in text


@pytest.mark.parametrize(
    "date,basis,mansion",
    [
        ("1010-04-12", "japanese_naoj_historical_utc09", "心"),
        ("2026-10-24", "chinese_hko_utc08", "昴"),
    ],
)
def test_unprovided_half_and_resolved_nonallocation_day_are_both_explained(
    date, basis, mansion
):
    calendar = calendar_mansion(
        date,
        "00:30:00",
        calendar_basis=basis,
        calendar_profile="hinoo_t1299_host27",
    )
    assert calendar["calendar_day_part"] is None
    assert calendar["profile_calculation"]["short_month_assignment"] is None
    assert calendar["natal_su27"] == mansion
    text = day_evidence(calendar)["reading_text"]
    assert "本次原典半日条件未声明" in text
    assert "本日未触发小月缺日补配的半日分配" in text
    assert f"未声明半日没有阻止本档案算得{mansion}宿" in text


@pytest.mark.parametrize("date", ["1010-04-12", "0820-03-22"])
def test_source_overlap_claim_carries_two_named_provider_bibliographies(date):
    calendar = calendar_mansion(
        date,
        "00:30:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    reference = calendar["calendar_reference"]["source_independence_reference"]
    assert reference["shared_bibliographic_titles"] == ["日本暦日原典"]
    assert {r["provider"] for r in reference["provider_statements"]} == {
        "NAOJ",
        "HuTime",
    }
    assert all(
        r["source_url"].startswith("https://") and len(r["source_html_sha256"]) == 64
        for r in reference["provider_statements"]
    )
    assert not reference["source_books_independently_collated"]
    assert not reference["per_record_dependency_established"]
    assert "方法说明均列《日本暦日原典》" in day_evidence(calendar)["reading_text"]


@pytest.mark.parametrize(
    "date,basis,half",
    [
        ("2036-07-23", "chinese_hko_utc08", "first_half"),
        ("2055-07-24", "chinese_hko_utc08", "second_half"),
        ("1010-04-12", "japanese_naoj_historical_utc09", None),
    ],
)
def test_static_historical_points_do_not_change_current_calendar_or_choose_half(
    date, basis, half
):
    calendar = calendar_mansion(
        date,
        "05:45:00",
        calendar_basis=basis,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=half,
    )
    before = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == before
    reference = evidence["calendar_day"]["clock_doctrine"][
        "futen_research_clock_arithmetic"
    ]
    for field in [
        "source_literal_points_are_for_current_input",
        "applied_to_runtime_day_boundary",
        "applied_to_hinoo_half",
        "T1299_pingming_equals_ziban_established",
        "leap_short_month_priority_established",
        "full_futen_calendar_reconstructed",
    ]:
        assert reference[field] is False
    if date == "2036-07-23":
        assert calendar["natal_su27"] is None
        assert calendar["candidate_su27s"] == ["星", "鬼"]
    elif date == "2055-07-24":
        assert calendar["natal_su27"] == "鬼"
    assert "三个时点均保留" in evidence["reading_text"]


@pytest.mark.parametrize("date", ["2026-10-24", "2036-07-23"])
def test_full_reference_and_native_explanation_across_rest_native_mcp_cli(
    monkeypatch, capsys, date
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "05:45:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.futen_research_clock_arithmetic",
            "sukuyo.reading_text",
            "sukuyo.calendar.natal_su27",
            "sukuyo.calendar.candidate_su27s",
        ],
    )
