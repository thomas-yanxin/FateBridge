"""Source-frozen exact ratios, not elapsed time or predictive observations."""

import hashlib
import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.meihua_timing import (
    build_postheaven_count_reference,
    postheaven_timing_ruleset,
)
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_timing_v1"
CASES = json.loads((FIXTURE / "arithmetic3072.json").read_text())
PROFILE = json.loads((FIXTURE / "profile.json").read_text())
CATEGORIES = json.loads(
    (
        Path(__file__).parent / "fixtures/meihua_observed_categories_v1/cases.json"
    ).read_text()
)["cases"]


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def reference(result):
    return result["interpretation"]["motion_context"].get("postheaven_count_reference")


def test_source_frozen_before_production_and_variants_do_not_create_two_days():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert not freeze["new_production_module_present"]
    assert not freeze["new_profile_present"]
    assert freeze["cases"] == 3072
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert postheaven_timing_ruleset() == PROFILE
    altered = postheaven_timing_ruleset()
    altered["scales"][0]["numerator"] = 9
    assert postheaven_timing_ruleset() == PROFILE
    assert "二花皆朝夕" in PROFILE["exception"]["quote"]
    assert "二日花皆朝夕" in PROFILE["exception"]["comparison_quote"]
    assert PROFILE["exception"]["variants"][0]["not_a_two_day_duration"]


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=lambda c: ":".join(
        [
            c["casting"]["upper_trigram"],
            c["casting"]["lower_trigram"],
            c["casting"]["hour_branch"],
            str(c["activity"]),
        ]
    ),
)
def test_all_3072_before_frozen_operands_and_ratios_bind_actual_source_cast(case):
    result = calculate_meihua_cast(
        casting=case["casting"], observer_activity=case["activity"]
    )
    assert "error" not in result
    assert result["meihua"]["seed"]["line_sum"] == case["unreduced_total"]
    assert result["meihua"]["seed"]["moving_line"] == case["moving_line"]
    item = reference(result)
    if case["activity"] is None:
        assert item is None
        return
    assert item["nominal_scaled_count"] == case["expected_scaled_count"]
    assert item["unreduced_total"] == case["unreduced_total"]
    assert [r["number"] for r in item["operands"]] == [
        case["upper_number"],
        case["lower_number"],
        case["hour_number"],
    ]
    assert resolve(result, item["observer_activity_fact_path"]) == case["activity"]
    assert resolve(result, item["total_fact_path"]) == case["unreduced_total"]
    assert resolve(result, item["moving_line_fact_path"]) == case["moving_line"]
    for row in item["operands"][:2]:
        assert resolve(result, row["fact_path"]) == row["number"]
    assert (
        resolve(result, item["operands"][2]["fact_path"])
        == case["casting"]["hour_branch"]
    )
    assert item["hour_added_times"] == 1
    assert item["moving_line_remainder_used_as_timing_total"] is False
    assert item["rounding_applied"] is False
    assert item["contextual_exception_applied_automatically"] is False
    assert item["full_timing_synthesis"] == "not_computed"
    assert all(
        item[key] is None
        for key in (
            "time_unit",
            "duration",
            "start_instant",
            "event_time",
            "real_world_observation_window",
            "real_outcome",
        )
    )
    assert item["independent_verified_observations"] == 0
    assert item["summary"] in result["summary"]
    assert result["interpretation"]["motion_context"]["summary"].endswith(
        item["summary"]
    )


@pytest.mark.parametrize("case", CATEGORIES, ids=lambda c: c["id"])
@pytest.mark.parametrize("activity", ["walking", "seated", "standing"])
def test_reused_category_mapping_uses_original_hour_and_source_trigram_numbers(
    case, activity
):
    result = calculate_meihua_cast(casting=case["input"], observer_activity=activity)
    item = reference(result)
    expected = case["expected"]
    hour = "子丑寅卯辰巳午未申酉戌亥".index(case["input"]["hour_branch"]) + 1
    total = expected["upper_number"] + expected["lower_number"] + hour
    factor = {
        "walking": Fraction(1, 2),
        "seated": Fraction(2),
        "standing": Fraction(1),
    }[activity]
    value = total * factor
    assert item["unreduced_total"] == total
    assert item["nominal_scaled_count"] == {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "exact_rational": str(value),
    }
    assert item["casting_method"] == "observed_categories"
    assert result["meihua"]["base_hexagram"]["binary_code"] == expected["base_code"]


@pytest.mark.parametrize(
    "casting,activity,expected",
    [
        (
            {
                "method": "observed_trigrams",
                "upper_trigram": "乾",
                "lower_trigram": "巽",
                "hour_branch": "卯",
            },
            "walking",
            "5",
        ),
        (
            {
                "method": "observed_trigrams",
                "upper_trigram": "乾",
                "lower_trigram": "乾",
                "hour_branch": "子",
            },
            "walking",
            "3/2",
        ),
        (
            {
                "method": "observed_trigrams",
                "upper_trigram": "艮",
                "lower_trigram": "离",
                "hour_branch": "午",
            },
            "walking",
            "17/2",
        ),
        (
            {
                "method": "observed_trigrams",
                "upper_trigram": "坤",
                "lower_trigram": "坤",
                "hour_branch": "亥",
            },
            "seated",
            "56",
        ),
    ],
)
def test_literal_arithmetic_anchors_never_round_or_reuse_the_line(
    casting, activity, expected
):
    result = calculate_meihua_cast(casting=casting, observer_activity=activity)
    assert reference(result)["nominal_scaled_count"]["exact_rational"] == expected


@pytest.mark.parametrize(
    "casting",
    [
        {"method": "existing", "hexagram_code": "011111", "moving_line": 4},
        {
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        {"method": "object_count", "count": 10, "hour_branch": "卯"},
        {"method": "length_zhang_chi", "zhang": 1, "chi": 2},
        {"method": "length_chi_cun", "chi": 1, "cun": 2, "hour_branch": "卯"},
        {"method": "text_count", "character_count": 17},
        {"method": "text_strokes", "strokes": [1, 5]},
        {"method": "text_tones", "tones": [1, 2, 3, 4]},
        {
            "method": "single_character_strokes",
            "script_style": "regular",
            "left_strokes": 1,
            "right_strokes": 2,
            "total_strokes": 3,
        },
        {
            "method": "lunar_time_added_count",
            "year_branch": "寅",
            "lunar_month": 12,
            "lunar_day": 1,
            "hour_branch": "午",
            "added_count": 4,
        },
    ],
)
def test_other_casting_origins_do_not_borrow_postheaven_timing(casting):
    result = calculate_meihua_cast(casting=casting, observer_activity="standing")
    assert "error" not in result
    assert reference(result) is None
    for candidate in result["interpretation"].get("casting_readings") or []:
        assert "postheaven_count_reference" not in candidate["motion_context"]


def test_time_cast_and_unknown_observer_do_not_invent_postheaven_origin_or_activity():
    result = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=27,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        observer_activity="walking",
    )
    assert reference(result) is None
    result = calculate_meihua_cast(
        casting={
            "method": "observed_trigrams",
            "upper_trigram": "乾",
            "lower_trigram": "巽",
            "hour_branch": "卯",
        },
        question="测试问句含行坐立，不可推定占者活动",
    )
    assert reference(result) is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("raw_upper_number", 5),
        ("line_sum", 4),
        ("line_sum", True),
        ("moving_line", 1),
        ("hour_branch", "亥"),
    ],
)
def test_mismatched_raw_count_hour_or_remainder_is_rejected(key, value):
    result = calculate_meihua_cast(
        casting={
            "method": "observed_trigrams",
            "upper_trigram": "乾",
            "lower_trigram": "巽",
            "hour_branch": "卯",
        }
    )
    cast = deepcopy(result["meihua"])
    cast["seed"][key] = value
    with pytest.raises(ValueError, match="Timing|timing"):
        build_postheaven_count_reference(
            cast,
            observer_activity="walking",
            activity_fact_path="input_normalized.observer_activity",
        )


def test_no_numeric_multiplier_is_invented_for_unimplemented_activity():
    result = calculate_meihua_cast(
        casting={
            "method": "observed_trigrams",
            "upper_trigram": "乾",
            "lower_trigram": "巽",
            "hour_branch": "卯",
        }
    )
    with pytest.raises(ValueError, match="No selected numeric scale"):
        build_postheaven_count_reference(
            result["meihua"],
            observer_activity="lying",
            activity_fact_path="input_normalized.observer_activity",
        )
