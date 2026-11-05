"""Dining conditions, cross-chapter control, source variants and own candidates."""

import hashlib
import json
from copy import deepcopy

import pytest

from fatebridge.core.meihua_dining import dining_qualifications, dining_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.meihua_dining_reference import (
    CASES,
    EXPECTED,
    FOLDER,
    GEOMETRY,
    validate,
)


def test_frozen_source_and_arithmetic_precede_new_dining_production():
    p = json.loads((FOLDER / "manifest.json").read_bytes())
    assert not p["new_dining_production_implemented_before_freeze"]
    assert (
        p["reused_geometries"] == 384
        and p["month_contexts"] == 4992
        and p["new_real_world_observations"] == 0
    )
    assert (
        len(CASES) == len({(r["code"], r["line"], r["month"]) for r in CASES}) == 4992
    )
    for name, digest in p["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(
    "case", CASES, ids=lambda r: f"{r['code']}-{r['line']}-{r['month']}"
)
def test_all_4992_reused_geometries_and_month_states_keep_source_and_actual_direct_control(
    case,
):
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="dining",
        season_month_branch=case["month"],
    )
    validate(result)


@pytest.mark.parametrize("probe", ["control_disagreement", "presence_disagreement"])
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("month", [None, "子", "辰"])
def test_each_candidate_uses_its_own_mutual_changed_symbols_and_source_control(
    probe, basis, month
):
    ref = json.loads((FOLDER / "manual-candidate-probes.json").read_bytes())[probe]
    result = calculate_meihua_cast(
        casting={**ref["casting"], "line_sum_basis": basis},
        interpretation_topic="dining",
        season_month_branch=month,
    )
    validate(result)
    expected = {r["basis"]: r for r in ref["candidates"]}
    rows = result["interpretation"]["casting_readings"]
    assert {r["line_sum_basis"] for r in rows} == set(expected) and rows[0][
        "line_sum_basis"
    ] == basis
    for row in rows:
        wanted = expected[row["line_sum_basis"]]
        assert (
            row["moving_line"],
            row["body"],
            row["use"],
            row["body_use_relation"],
        ) == (wanted["line"], wanted["body"], wanted["use"], wanted["relation"])
    assert rows[0]["topic_clause"]["quote"] == rows[1]["topic_clause"]["quote"]
    assert (
        rows[0]["topic_clause"]["chapter_qualifications"]["symbols"]
        != rows[1]["topic_clause"]["chapter_qualifications"]["symbols"]
    )


def test_one_named_controller_is_enough_without_a_many_threshold():
    case = next(
        r
        for r in GEOMETRY
        if any(len(v["controller_pairs"]) == 1 for v in r["symbols"].values())
    )
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="dining",
    )
    validate(result)
    assert any(
        len(s["actual_direct_controller_pairs"]) == 1
        and s["direct_control_condition_in_selected_scope"]
        for s in result["interpretation"]["topic_reading"]["chapter_qualifications"][
            "symbols"
        ]
    )


def test_a_controller_itself_controlled_is_preserved_without_recursive_reactivation():
    case = next(
        r
        for r in GEOMETRY
        if any(
            p["controller_itself_controlled_by_roles"]
            for v in r["symbols"].values()
            for p in v["controller_pairs"]
        )
    )
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="dining",
        season_month_branch="子",
    )
    validate(result)
    assert any(
        p["controller_itself_controlled_by_roles"]
        for s in result["interpretation"]["topic_reading"]["chapter_qualifications"][
            "symbols"
        ]
        for p in s["actual_direct_controller_pairs"]
    )


def test_weak_fire_does_not_disable_the_selected_fire_controls_food_sentence():
    case = next(r for r in GEOMETRY if r["symbols"]["food"]["direct_control_condition"])
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="dining",
        season_month_branch="子",
    )
    validate(result)
    q = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    s = next(s for s in q["symbols"] if s["symbol"] == "food")
    assert s["direct_control_condition_in_selected_scope"]
    strengths = {
        r["role"]: r["strength"]
        for r in result["meihua"]["seasonal_strength"]["trigrams"]
    }
    assert all(
        strengths[p["controller_role"]] == "衰"
        for p in s["actual_direct_controller_pairs"]
    )


@pytest.mark.parametrize("hour", [0, 23])
def test_new_topic_does_not_recast_the_calendar_or_original_hexagram(hour):
    args = {
        "analysis_year": 2026,
        "analysis_month": 2,
        "analysis_day": 16,
        "analysis_hour": hour,
        "analysis_timezone": "Asia/Shanghai",
    }
    before = calculate_meihua_analysis(**args)
    after = calculate_meihua_analysis(**args, interpretation_topic="dining")
    validate(after)
    for key in [
        "seed",
        "base_hexagram",
        "changed_hexagram",
        "mutual_hexagram",
        "body_trigram",
        "use_trigram",
        "stage_relations",
        "seasonal_strength",
        "calendar_policy",
        "rule_trace",
    ]:
        assert before["meihua"][key] == after["meihua"][key]


def test_dining_words_never_select_a_new_chapter_by_themselves():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "000000", "moving_line": 1},
        question="飲食，有酒有食，赴宴",
    )
    assert result["interpretation"]["interpretation_topic"] == "general"


@pytest.mark.parametrize(
    "mutation",
    [
        "emend_身",
        "apply_generation",
        "many_threshold",
        "cancel_control",
        "physical_food",
        "borrowed_summary",
        "wrong_pair",
        "wrong_absence",
        "select_person",
    ],
)
def test_reference_rejects_source_emendation_missing_qualification_or_physical_claim(
    mutation,
):
    ref = json.loads((FOLDER / "manual-candidate-probes.json").read_bytes())[
        "control_disagreement"
    ]
    result = calculate_meihua_cast(
        casting=ref["casting"], interpretation_topic="dining"
    )
    rows = result["interpretation"]["casting_readings"]
    q = rows[1]["topic_clause"]["chapter_qualifications"]
    if mutation == "emend_身":
        q["generation_reference"]["quote"] = "兌坎生體酒肉醉飽"
    elif mutation == "apply_generation":
        q["generation_reference"]["full_source_clause_applies"] = True
    elif mutation == "many_threshold":
        q["symbols"][1]["many_threshold_required_by_selected_control_sentence"] = True
    elif mutation == "cancel_control":
        q["symbols"][1]["direct_control_condition_in_selected_scope"] = False
    elif mutation == "physical_food":
        q["symbols"][1]["real_food_or_drink_available"] = True
    elif mutation == "wrong_pair":
        q["symbols"][1]["actual_direct_controller_pairs"][0]["target_role"] = "use"
    elif mutation == "wrong_absence":
        q["absence_reference"]["neither_symbol_present_in_selected_scope"] = True
    elif mutation == "select_person":
        q["food_and_people_references"]["actual_attendees"] = ["inferred person"]
    else:
        rows[0]["traditional_judgement"] = rows[1]["traditional_judgement"]
    with pytest.raises(AssertionError):
        validate(result)


def test_profile_copy_cannot_mutate_future_source_clauses():
    data = dining_ruleset()
    data["generation_reference"]["quote"] = "forged"
    assert dining_ruleset()["generation_reference"]["quote"] == "兌坎生身酒肉醉飽"


def test_a_control_graph_from_another_candidate_is_rejected():
    ref = json.loads((FOLDER / "manual-candidate-probes.json").read_bytes())[
        "control_disagreement"
    ]
    result = calculate_meihua_cast(
        casting=ref["casting"], interpretation_topic="dining"
    )
    row = result["interpretation"]["casting_readings"][0]
    other = result["interpretation"]["casting_readings"][1]
    with pytest.raises(ValueError, match="this candidate"):
        dining_qualifications(
            result["meihua"]["counting_variants"][0],
            row["stage_relations"],
            other["internal_countercontrol"],
            fact_prefix="meihua.counting_variants.0",
            interpretation_prefix="interpretation.casting_readings.0",
        )
