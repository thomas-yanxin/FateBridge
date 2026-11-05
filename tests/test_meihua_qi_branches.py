"""Actual unit labels and frozen literal time classes, never future outcomes."""

import hashlib
import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_qi_branches import _reading, qi_branch_unit_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.meihua_qi_branches_reference import (
    FOLDER,
    GEOMETRY,
    PROFILE,
    TRUTH,
    validate_branch_node,
)

BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")


def test_all_literal_source_atoms_and_primary_calendar_labels_frozen_before_new_module():
    freeze = json.loads((FOLDER / "reference-freeze.json").read_bytes())
    assert (
        not freeze["new_production_module_present"]
        and not freeze["new_profile_present"]
    )
    assert not freeze["calendar_expected_values_from_production"]
    for name, h in freeze["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == h
    assert qi_branch_unit_ruleset() == PROFILE and len(TRUTH) == 384
    assert PROFILE["unit_branch_atoms"]["坤"]["unit_branches"]["month"] == list(
        "辰戌丑未申"
    )
    assert PROFILE["unit_branch_atoms"]["坤"]["unit_branches"]["day"] == list("未申")
    assert "五金年月日時" in PROFILE["unparsed_legacy_time_text"]["乾"]


@pytest.mark.parametrize("code,line", list(GEOMETRY))
@pytest.mark.parametrize("topic", ["wealth", "reputation"])
@pytest.mark.parametrize("branch", [None, *BRANCHES])
def test_all_9984_geometry_topic_day_month_contexts_keep_units_and_actual_roles(
    code, line, topic, branch
):
    args = {
        "casting": {"method": "existing", "hexagram_code": code, "moving_line": line},
        "interpretation_topic": topic,
    }
    if branch:
        args.update(
            season_month_branch=branch,
            day_qi_context={"label": "合成同支不同单位核对", "day_branch": branch},
        )
    result = calculate_meihua_cast(**args)
    assert "error" not in result
    layer = result["interpretation"]
    node = layer["topic_reading"]["qi_branch_timing_reference"]
    validate_branch_node(result, layer, node)
    assert (
        not node["input_unit_labels"]["year"] and not node["input_unit_labels"]["hour"]
    )
    assert (
        node["input_unit_labels"]["month"] == []
        if branch is None
        else len(node["input_unit_labels"]["month"]) == 1
    )


@pytest.mark.parametrize(
    "year,hour,month,day,added",
    list(itertools.product(BRANCHES, BRANCHES, [1, 6, 12], [1, 29], [1, 7])),
)
@pytest.mark.parametrize("topic", ["wealth", "reputation"])
def test_all_3456_lunar_added_year_hour_month_contexts_keep_reported_source(
    year, hour, month, day, added, topic
):
    casting = {
        "method": "lunar_time_added_count",
        "year_branch": year,
        "lunar_month": month,
        "lunar_day": day,
        "hour_branch": hour,
        "added_count": added,
    }
    result = calculate_meihua_cast(casting=casting, interpretation_topic=topic)
    assert "error" not in result
    layer = result["interpretation"]
    node = layer["topic_reading"]["qi_branch_timing_reference"]
    validate_branch_node(result, layer, node)
    assert node["input_unit_labels"]["year"][0]["branch"] == year
    assert node["input_unit_labels"]["hour"][0]["branch"] == hour
    assert (
        node["input_unit_labels"]["month"][0]["branch"]
        == PROFILE["nominal_month_labels"][str(month)]
    )
    assert node["input_unit_labels"]["month"][0]["is_leap_month"] is None
    assert not node["input_unit_labels"]["day"]


@pytest.mark.parametrize(
    "case", json.loads((FOLDER / "calendar4.json").read_bytes())["rows"]
)
@pytest.mark.parametrize("topic", ["wealth", "reputation"])
def test_primary_cny_boundaries_keep_lunar_year_nominal_month_jie_month_and_day_alternative(
    case, topic
):
    y, m, d = map(int, case["date"].split("-"))
    result = calculate_meihua_analysis(
        analysis_year=y,
        analysis_month=m,
        analysis_day=d,
        analysis_hour=case["hour"],
        analysis_timezone=case["timezone"],
        interpretation_topic=topic,
    )
    assert "error" not in result
    layer = result["interpretation"]
    node = layer["topic_reading"]["qi_branch_timing_reference"]
    validate_branch_node(result, layer, node)
    labels = node["input_unit_labels"]
    assert [r["branch"] for r in labels["year"]] == [case["year_branch"]]
    assert [(r["id"], r["branch"]) for r in labels["month"]] == [
        ("seasonal_jie_month", case["jie_month_label"]),
        ("nominal_lunar_month", case["nominal_month_label"]),
    ]
    assert [r["branch"] for r in labels["day"]] == [case["civil_day_branch"]] + (
        [case["zi_start_alternative_branch"]]
        if case["zi_start_alternative_branch"]
        else []
    )
    assert [r["branch"] for r in labels["hour"]] == [case["hour_branch"]]
    assert node["input_label_branch_disagreement"]["month"] is (
        case["nominal_month_label"] != case["jie_month_label"]
    )


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("office", [None, False, True])
def test_counting_candidates_keep_own_bodies_and_common_original_input_clock(
    basis, office
):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "申",
            "line_sum_basis": basis,
        },
        interpretation_topic="reputation",
        season_month_branch="辰",
        day_qi_context={"label": "合成未日", "day_branch": "未"},
        reputation_context={"label": "合成在任", "currently_in_office": office},
    )
    ir = result["interpretation"]
    validate_branch_node(result, ir, ir["topic_reading"]["qi_branch_timing_reference"])
    for i, layer in enumerate(ir["casting_readings"]):
        node = layer["topic_clause"]["qi_branch_timing_reference"]
        validate_branch_node(
            result,
            layer,
            node,
            prefix=f"meihua.counting_variants.{i}",
            layer_path=f"interpretation.casting_readings.{i}",
        )
        assert (
            node["input_unit_labels"]["hour"][0]["branch_fact_path"]
            == "meihua.seed.hour_branch"
        )


@pytest.mark.parametrize(
    "topic", ["general", "planning", "weather", "travel", "meeting", "lost_property"]
)
def test_topic_does_not_switch_from_question_keywords(topic):
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "000111", "moving_line": 1},
        interpretation_topic=topic,
        question="求名求财辰月未日",
    )
    assert "error" not in result
    assert "qi_branch_timing_reference" not in (
        result["interpretation"].get("topic_reading") or {}
    )


def test_invalid_foreign_day_body_or_hour_input_binding_is_rejected():
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "申",
        },
        interpretation_topic="wealth",
        season_month_branch="辰",
        day_qi_context={"label": "合成辰日", "day_branch": "辰"},
    )
    original = result["meihua"]
    layer = deepcopy(result["interpretation"])
    layer["day_qi"]["calendar_candidates"][0]["roles"][0][
        "fact_path"
    ] = "another_cast.body_trigram"
    with pytest.raises(ValueError):
        _reading(
            original,
            original,
            layer,
            "wealth",
            fact_prefix="meihua",
            layer_path="interpretation",
            clause_path="interpretation.topic_reading",
        )
    original = deepcopy(original)
    original["seed"]["parameters"]["hour_branch"] = "子"
    with pytest.raises(ValueError):
        _reading(
            original,
            original,
            result["interpretation"],
            "wealth",
            fact_prefix="meihua",
            layer_path="interpretation",
            clause_path="interpretation.topic_reading",
        )

    foreign_cast = deepcopy(result["meihua"])
    foreign_cast["seasonal_strength"] = None
    with pytest.raises(ValueError):
        _reading(
            result["meihua"],
            foreign_cast,
            result["interpretation"],
            "wealth",
            fact_prefix="meihua",
            layer_path="interpretation",
            clause_path="interpretation.topic_reading",
        )
