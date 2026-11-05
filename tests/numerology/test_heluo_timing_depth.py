"""Scanned original witnesses, finite original examples and full-domain invariants."""

import json
from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import (
    calculate,
    gua_lines,
    judge,
)
from fatebridge.core.heluo_timing import (
    SOURCE_SHA256,
    annual_sequence,
    annual_timeline,
    build_heluo_timing,
    daily_template,
    monthly_sequence,
)
from fatebridge.core.output_numerology import HeluoTiming
from fatebridge.services.divination import calculate_heluo_analysis

ROOT = Path(__file__).parents[1] / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "timing-reference.json").read_text())


def example_chart():
    return calculate(
        four_pillars={"year": "甲子", "month": "丁卯", "day": "庚申", "hour": "庚辰"},
        gender="男",
        birth_year=1924,
        month_zhi="卯",
        hour_zhi="辰",
    )


def test_original_page_witnesses_are_pinned_and_not_generated_from_the_calculation():
    source = json.loads((ROOT / "manifest.json").read_text())
    assert source["pdf_sha256"] == SOURCE_SHA256
    assert [i["pdf_page_1based"] for i in source["images"]] == [37, 38, 39, 40]
    for image in source["images"]:
        data = (ROOT / image["file"]).read_bytes()
        assert data.startswith(b"\x89PNG")
        assert sha256(data).hexdigest() == image["sha256"]


@pytest.mark.parametrize("case", REFERENCE["annual"], ids=lambda c: c["id"])
def test_annual_examples_visually_transcribed_from_original_pages(case):
    rows = annual_sequence(case["base_lines"], case["period_pos"], case["start_yang"])
    assert [r["gua"] for r in rows] == case["names"]
    assert [r["pos"] for r in rows] == case["positions"]
    assert [r["changed_pos"] for r in rows] == case["changed_positions"]


def test_all_twelve_months_of_guan_upper_line_match_the_original_example():
    case = REFERENCE["monthly"]
    rows = monthly_sequence(case["annual_lines"], case["annual_pos"])
    assert [r["gua"] for r in rows] == case["names"]
    assert [r["pos"] for r in rows] == case["positions"]
    assert [r["month_index"] for r in rows] == list(range(1, 13))
    # March comes from January; feeding February's 无妄 into March is wrong.
    assert rows[2]["input_lines"] == rows[0]["lines"]
    assert rows[2]["input_lines"] != rows[1]["lines"]


def test_daily_blocks_reset_to_the_original_month_and_each_use_six_positions():
    case = REFERENCE["daily"]
    rows = daily_template(case["month_lines"], case["month_pos"])
    for block in case["explicit_blocks"] + case["rule_derived_blocks"]:
        selected = rows[block["slots"][0] - 1 : block["slots"][1]]
        assert len(selected) == 6
        assert {r["gua"] for r in selected} == {block["name"]}
        assert {r["changed_pos"] for r in selected} == {block["changed_pos"]}
        assert [r["pos"] for r in selected] == case["daily_positions_per_block"]
        assert all(r["input_lines"] == case["month_lines"] for r in selected)
    assert [r["day_index"] for r in rows] == list(range(1, 31))


def test_all_64_hexagrams_six_period_positions_and_both_year_parities_have_traceable_changes():
    # Domain invariants supplement, rather than replace, the original examples.
    for bits in product((0, 1), repeat=6):
        for pos, start_yang in product(range(1, 7), (False, True)):
            lines = list(bits)
            before = lines[:]
            rows = annual_sequence(lines, pos, start_yang)
            assert len(rows) == (9 if bits[pos - 1] else 6)
            for index, row in enumerate(rows):
                differences = [
                    i for i, (a, b) in enumerate(zip(before, row["lines"]), 1) if a != b
                ]
                assert differences == (
                    [] if row["changed_pos"] is None else [row["changed_pos"]]
                )
                assert row["input_lines"] == before
                assert row["gua"] and 1 <= row["pos"] <= 6
                before = row["lines"][:]
                assert row["ordinal_in_period"] == index + 1
            assert lines == list(bits)


def test_parity_belongs_to_each_new_period_and_base_hexagram_resets():
    chart = example_chart()
    rows = annual_timeline(chart, "甲子")
    assert rows[0]["period_start_yang"] is True
    assert rows[9]["age"] == 10 and rows[9]["period_pos"] == 1
    # A yin period at age 10 lasts six years. Age16 starts the next yang period
    # in 己卯, a yin year, even though the birth year itself was yang.
    assert rows[15]["ganzhi"] == "己卯"
    assert rows[15]["period_start_yang"] is False
    assert rows[15]["changed_pos"] == 2
    assert rows[15]["input_lines"] == chart["xian"]["lines"]
    assert rows[15]["gua"] == "天山遯"
    assert [r["age"] for r in rows] == list(range(1, len(rows) + 1))
    assert {r["period_index"] for r in rows} == set(range(1, 13))


def test_pre_lichun_birth_does_not_label_the_first_ganzhi_year_as_the_next_civil_year():
    r = calculate_heluo_analysis(
        date="2044-01-15",
        time="12:00:00",
        gender="男",
        use_true_solar_time=False,
        analysis_year=2043,
        month_index=1,
        day_index=1,
    )
    first = r["heluo_timing"]["annual_rows"][0]
    assert first["year_label"] == 2043 and first["ganzhi"] == "癸亥"
    assert r["dayun"]["all"][0]["yearStart"] == 2043
    assert r["heluo_timing"]["selected_annual"] == first
    assert "unresolved" in r["heluo_timing"]["calendar_policy"]["year"]


def test_selection_and_texts_match_actual_annual_monthly_and_daily_positions_without_mutating_sources():
    chart = example_chart()
    before = deepcopy(chart)
    r = build_heluo_timing(
        chart, "甲子", analysis_year=1939, month_index=3, day_index=10
    )
    assert chart == before
    assert r["selected_annual"]["gua"] == "天山遯"
    for key, text in zip(
        ("selected_annual", "selected_month", "selected_day"), r["selected_texts"]
    ):
        assert text["gua"] == r[key]["gua"]
        assert text["pos"] == r[key]["pos"] == text["zhouyi_verse"]["position"]
        assert text["branch_selection"] == "no_automatic_xie_or_buxie_selection"
    assert len(r["monthly_rows"]) == 12 and len(r["daily_template"]) == 30
    assert r["prediction_validation"] == "not_validated"
    assert not any("start_at" in row or "end_at" in row for row in r["daily_template"])
    r["selected_texts"][0]["heluo_commentary"]["detail"] = "mutated"
    again = build_heluo_timing(chart, "甲子", analysis_year=1939)
    assert again["selected_texts"][0]["heluo_commentary"]["detail"] != "mutated"
    HeluoTiming.model_validate(r)


@pytest.mark.parametrize(
    "changes",
    [
        {"analysis_year": 1923},
        {"analysis_year": 2300},
        {"month_index": 2},
        {"analysis_year": 1924, "day_index": 1},
        {"analysis_year": 1924, "month_index": 0},
        {"analysis_year": 1924, "month_index": 1, "day_index": 31},
    ],
)
def test_missing_parents_and_out_of_range_labels_are_rejected(changes):
    with pytest.raises(ValueError):
        build_heluo_timing(example_chart(), "甲子", **changes)


@pytest.mark.parametrize(
    "lines,pos",
    [([0, 1], 1), ([0, 1, 2, 0, 1, 0], 2), ([0, 1, 0, 0, 1, True], 2), ([0] * 6, 0)],
)
def test_invalid_sequences_fail_before_constructing_a_plausible_hexagram(lines, pos):
    with pytest.raises(ValueError):
        annual_sequence(lines, pos, True)


def test_nested_contract_rejects_numeric_string_line_positions():
    with pytest.raises(ValidationError):
        HeluoTiming.model_validate({"selected_day": {"pos": "2"}})


def test_inconsistent_birth_year_and_pillars_cannot_generate_a_plausible_year_label():
    with pytest.raises(ValueError, match="出生年与年柱不一致"):
        calculate(
            four_pillars={
                "year": "甲子",
                "month": "丁卯",
                "day": "庚申",
                "hour": "庚辰",
            },
            gender="男",
            birth_year=2000,
            month_zhi="卯",
            hour_zhi="辰",
        )


def test_month_table_matches_wuwang_through_actual_judge():
    # Test the matching operation independently of the birth calculator.
    chart = example_chart()
    chart["xian"].update(
        {"name": "天雷無妄", "up": "乾", "low": "震", "lines": gua_lines("乾", "震")}
    )
    assert (
        judge(
            chart,
            {"year": "甲子", "month": "癸酉", "day": "庚申", "hour": "庚辰"},
            "酉",
        )["deTime"]
        is True
    )
