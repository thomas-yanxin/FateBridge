"""Selected clock arithmetic must retain conflicting readings and date gaps."""

from fractions import Fraction

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_guchureki_clock import (
    MODEL,
    clock_arithmetic_reference,
    decode_clock,
    quantity_fun,
    seasonal_ordinal,
)
from scripts.sukuyo.check_sukuyo_guchureki_clock import verify_guchureki_clock


def fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def test_sukuyo_guchureki_all_printed_pairs_and_adverse_residuals_are_retained():
    result = verify_guchureki_clock()
    assert result["errors"] == []
    assert result["record_groups_checked"] == 40
    assert result["paired_readings_checked"] == 42
    assert result["residual_counts_by_exact_fun"] == {
        "0": 34,
        "1": 4,
        "-1/2": 2,
        "-1": 2,
    }
    assert result["nonzero_residual_groups_retained"] == 6
    assert result["nonzero_residual_readings_retained"] == 8
    rows = clock_arithmetic_reference(include_all_rows=True)["table_check"][
        "all_readings"
    ]
    assert len(rows) == 42
    assert len([r for r in rows if r["printed_sum"] is None]) == 2
    for name in ["芒種13日", "大雪13日"]:
        variants = [r for r in rows if r["season_label"] == name]
        assert len(variants) == 2
        assert {fraction(r["symmetry_residual_fun"]) for r in variants} == {
            Fraction(-1, 2),
            Fraction(-1),
        }


@pytest.mark.parametrize(
    "literal,expected,boundary",
    [
        ("卯初0分", Fraction(0), False),
        ("卯時正", Fraction(25, 2), False),
        ("卯4刻1分", Fraction(25), True),
        ("亥4刻1分", Fraction(25), True),
        ("寅3刻4分半", Fraction(45, 2), False),
        ("申3刻4分", Fraction(22), False),
    ],
)
def test_sukuyo_guchureki_zero_midpoint_boundary_and_half_fun(
    literal, expected, boundary
):
    result = decode_clock(literal, model=MODEL)
    assert fraction(result["within_branch_fun"]) == expected
    assert result["literal"] == literal
    assert result["at_next_branch_boundary"] is boundary
    assert not result["civil_date_or_clock_assigned"]
    if literal == "亥4刻1分":
        assert result["next_branch_if_boundary"] == "子"


@pytest.mark.parametrize(
    "literal",
    [
        "卯初半",
        "卯3刻半",
        "半刻",
        "卯4刻2分",
        "卯3刻7分",
        "卯5刻",
        "卯時正1分",
        "午-1刻",
        "",
        None,
        "卯0.5分",
    ],
)
def test_sukuyo_guchureki_rejects_ambiguous_units_or_invalid_clock_points(literal):
    with pytest.raises(ValueError):
        decode_clock(literal, model=MODEL)


def test_sukuyo_guchureki_sums_are_quantities_not_clock_points():
    assert fraction(quantity_fun("3刻7分", model=MODEL)) == 25
    assert fraction(quantity_fun("4刻1分", model=MODEL)) == 25
    assert fraction(quantity_fun("4刻2分", model=MODEL)) == 26
    with pytest.raises(ValueError):
        decode_clock("卯4刻2分", model=MODEL)
    with pytest.raises(ValueError):
        quantity_fun("半刻", model=MODEL)
    with pytest.raises(ValueError):
        decode_clock("卯時正", model="senmyoreki")


def test_sukuyo_guchureki_same_named_units_and_abstract_difference_not_collapsed():
    reference = clock_arithmetic_reference()
    exact = reference["exact_unit_relations"]
    assert fraction(exact["nominal_seconds_per_half_fun"]) == 144
    assert fraction(exact["nominal_seconds_per_half_koku"]) == 864
    assert fraction(exact["half_koku_minus_half_fun_nominal_seconds"]) == 720
    assert fraction(exact["fifty_vs_hundred_koku_unit_ratio"]) == 2
    assert fraction(exact["guchureki_vs_senmyoreki_fun_unit_ratio"]) == 28
    difference = reference["english_abstract_body_unit_difference"]
    assert difference["terminological_difference_retained"]
    assert not difference["authorial_intent_or_erratum_established"]
    assert (
        reference["comparative_units"]["engishiki_comparison"][
            "first_clock_koku_number"
        ]
        == 1
    )
    assert not reference["comparative_units"]["engishiki_comparison"][
        "decoder_admitted"
    ]


def test_sukuyo_guchureki_seasonal_labels_use_nominal_360_axis():
    reference = clock_arithmetic_reference(include_all_rows=True)
    names = reference["seasonal_axis"]["term_order_from_winter_solstice"]
    assert [
        seasonal_ordinal(name + str(day) + "日")
        for name in names
        for day in range(1, 16)
    ] == list(range(1, 361))
    assert seasonal_ordinal("小寒1日") == 16
    assert seasonal_ordinal("大雪13日") == 358
    assert (16 - 358) % 360 == 18
    assert not reference["seasonal_axis"]["civil_date_conversion_established"]
    for invalid in ["冬至16日", "2025-01-01", None]:
        with pytest.raises(ValueError):
            seasonal_ordinal(invalid)


def test_sukuyo_guchureki_reference_is_detached_from_cached_source():
    first = clock_arithmetic_reference()
    expected = clock_arithmetic_reference()
    first["table_check"]["exception_readings"][0]["sunrise_literal"] = "changed"
    first["selected_model"]["koku_per_day"] = 100
    assert clock_arithmetic_reference() == expected


def test_sukuyo_native_clock_delivery_explains_cycle_and_other_clock_origin():
    text = day_evidence(calendar_mansion("2025-01-07", "12:00:00"))["reading_text"]
    for detail in [
        "末段18",
        "没日位置",
        "平气",
        "公历冬至",
        "定气",
        "第1刻",
        "分制",
        "解码",
    ]:
        assert detail in text


@pytest.mark.parametrize("half", ["first_half", "second_half", None])
def test_sukuyo_native_clock_delivery_preserves_explicit_half_without_clock_guess(
    half,
):
    calendar = calendar_mansion(
        "1010-04-12",
        "12:00:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=half,
    )
    text = day_evidence(calendar)["reading_text"]
    if half:
        assert "本次已声明原典半日条件" in text
        assert half in text
        assert ("前半" if half == "first_half" else "后半") in text
    else:
        assert "本次已声明原典半日条件" not in text


@pytest.mark.parametrize("kind", ["pdf", "table"])
def test_sukuyo_guchureki_changed_source_capture_is_rejected(tmp_path, kind):
    path = tmp_path / kind
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        verify_guchureki_clock(
            **({"pdf_path": path} if kind == "pdf" else {"table_capture": path})
        )


@pytest.mark.parametrize(
    "date,basis",
    [
        ("1957-09-24", "chinese_hko_utc08"),
        ("0820-03-22", "japanese_naoj_historical_utc09"),
    ],
)
def test_sukuyo_guchureki_clock_reference_does_not_assign_current_daybreak_or_half(
    date, basis
):
    calendar = calendar_mansion(
        date,
        "00:30:00",
        calendar_basis=basis,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    day = day_evidence(calendar)
    reference = day["calendar_day"]["clock_doctrine"]["historical_clock_arithmetic"]
    assert not reference["applied_to_runtime_day_boundary"]
    assert not reference["applied_to_hinoo_half"]
    assert not reference["paper_event_definition"][
        "proves_T1299_pingming_zero_altitude"
    ]
    assert day["calendar_day"]["clock_evaluation_status"] == "not_computed"
    assert "360日平气名义轴" in day["reading_text"]
    if date == "1957-09-24":
        assert day["day_mansion"] is None and calendar["candidate_su27s"] == [
            "角",
            "轸",
        ]
