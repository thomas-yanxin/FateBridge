"""Original worked steps, retained source disagreements and input integrity."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import calculate, da_yun, gua_lines, transform_houtian
from fatebridge.core.heluo_timing import SOURCE_SHA256

ROOT = Path(__file__).parent / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "worked-reference.json").read_text())


def calculate_case(case, **changes):
    pillars = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
    args = dict(
        four_pillars=pillars,
        gender=case["gender"],
        birth_year=case["computational_year"],
        month_zhi=pillars["month"][1],
        hour_zhi=pillars["hour"][1],
        month_yang_ling=case["yang_ling"],
    )
    return calculate(**{**args, **changes})


def lookup(result, field):
    for key in field.split("."):
        result = result[key]
    return result


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["id"])
def test_original_worked_steps_and_hand_added_totals(case):
    result = calculate_case(case)
    for field, expected in case["arithmetic_totals"].items():
        assert result[field] == expected
    for field, expected in case["direct_expected"].items():
        assert lookup(result, field) == expected
    # The API has no historical instant; source-provided half-years cannot
    # acquire astronomical provenance merely by being passed as a boolean.
    assert result["yangLingBasis"] == "explicit_half_year"
    assert result["tianNum"] != 5 and result["diNum"] != 5
    if "direct_houtian_start_age" in case:
        timing = da_yun(result["xian"], result["hou"])
        assert timing["hou"][0]["ageStart"] == case["direct_houtian_start_age"]


def test_new_source_witnesses_are_identified_without_certifying_dates_or_outcomes():
    manifest = json.loads((ROOT / "worked-manifest.json").read_text())
    assert (
        REFERENCE["source_pdf_sha256"] == manifest["source_pdf_sha256"] == SOURCE_SHA256
    )
    assert len(manifest["images"]) == 9
    for row in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    assert REFERENCE["validated_historical_birth_instants"] == 0
    assert REFERENCE["real_world_outcomes"] == 0
    assert not REFERENCE["independent_second_review_completed"]


def test_literal_disagreements_cannot_be_replaced_with_runtime_answers():
    differences = []
    for case in REFERENCE["cases"]:
        result = calculate_case(case)
        for field, printed in case["source_totals"].items():
            if result[field] != printed:
                differences.append(
                    dict(
                        case_id=case["id"],
                        field=field,
                        printed=printed,
                        arithmetic=result[field],
                        repeated_in_source=case["source_repeated_totals"][field],
                    )
                )
    assert differences == REFERENCE["expected_source_total_disagreements"]
    assert differences  # A nonempty disagreement must remain in the audit.
    dates = REFERENCE["cases"][1]["source_date_readings"]
    assert "初二" in dates["NLC"] and "初三" in dates["NAJDA"]


@pytest.mark.parametrize("value", ["false", "true", "", "0", 0, 1, [], {}, None])
def test_houtian_half_year_must_be_boolean(value):
    with pytest.raises(ValueError, match="阴阳令"):
        transform_houtian("水雷屯", gua_lines("坎", "震"), 5, value)
    if value is not None:
        with pytest.raises(ValueError, match="阴阳令"):
            calculate_case(REFERENCE["cases"][3], month_yang_ling=value)


def test_tun_five_half_year_difference_is_preserved_and_no_input_mutates():
    lines = [1, 0, 0, 0, 1, 0]  # 屯, initial to upper.
    yin = transform_houtian("水雷屯", lines, 5, False)
    yang = transform_houtian("水雷屯", lines, 5, True)
    assert (yin["name"], yin["yuan"], yin["lines"]) == ("地雷復", 5, [1, 0, 0, 0, 0, 0])
    assert (yang["name"], yang["yuan"], yang["lines"]) == (
        "雷地豫",
        2,
        [0, 0, 0, 1, 0, 0],
    )
    assert lines == [1, 0, 0, 0, 1, 0]
    assert (
        calculate_case(REFERENCE["cases"][0], month_yang_ling=None)["yangLingBasis"]
        == "month_branch_half_year"
    )


@pytest.mark.parametrize("position", [True, False, 0, 7, -1, 1.0, "5", None])
def test_houtian_cannot_use_negative_indices_or_coerced_positions(position):
    with pytest.raises(ValueError, match="元堂"):
        transform_houtian("水雷屯", gua_lines("坎", "震"), position, False)


@pytest.mark.parametrize(
    "lines",
    [
        None,
        [],
        [1] * 5,
        [1] * 7,
        [1, 0, 0, 0, 2, 0],
        [True, 0, 0, 0, 1, 0],
        [1.0, 0, 0, 0, 1, 0],
    ],
)
def test_houtian_rejects_malformed_line_data(lines):
    with pytest.raises(ValueError, match="六个0/1"):
        transform_houtian("水雷屯", lines, 5, False)


def test_wrong_name_cannot_switch_the_three_supreme_exception():
    # Same six bits would otherwise produce a different result depending only
    # on the inconsistent name used to choose the exception.
    with pytest.raises(ValueError, match="卦名"):
        transform_houtian("坤為地", gua_lines("坎", "震"), 5, False)


@pytest.mark.parametrize("case", REFERENCE["cases"][:3], ids=lambda c: c["id"])
def test_derived_houtian_positions_are_not_counted_as_direct_readings(case):
    result = calculate_case(case)
    for field, expected in case.get("rule_derived_expected", {}).items():
        assert lookup(result, field) == expected
