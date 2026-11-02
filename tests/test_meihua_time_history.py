"""Recorded migration is checked before projection; wrong new facts must fail."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.services.divination import calculate_meihua_analysis
from tests.meihua_volume5_source_evolution import (
    reviewed_restore_old_time_fixture_view as restore_old_time_fixture_view,
)

FIXTURE = Path(__file__).parent / "fixtures"
TIMES = json.loads((FIXTURE / "meihua_day_qi_v1/time-boundaries12.json").read_bytes())
OLD = json.loads((FIXTURE / "meihua_day_qi_v1/old-time-outputs12.json").read_bytes())


@pytest.fixture(scope="module")
def readings():
    return [calculate_meihua_analysis(**r["input"]) for r in TIMES]


def verify(result, index):
    result = deepcopy(result)
    day = result["interpretation"].pop("day_qi")
    for parent, key in [
        (result, "summary"),
        (result["interpretation"], "comprehensive_judgement"),
    ]:
        assert parent[key].count(day["summary"]) == 1
        parent[key] = parent[key].replace(day["summary"], "", 1)
    result = restore_old_time_fixture_view(result)
    timing = result["interpretation"]["stage_emphasis"].pop("obstruction_timing")
    assert (
        timing["declared_scenario"]
        is timing["selected_clause_applies"]
        is timing["event_time"]
        is None
    )
    assert timing["summary"] == ""
    assert result == OLD[index]["output"]


def test_migration_policy_and_all_frozen_source_inputs_remain_pinned():
    folder = FIXTURE / "meihua_day_qi_migration_v1"
    freeze = json.loads((folder / "freeze.json").read_bytes())
    assert freeze["before_new_helper_and_test_edits"]
    assert freeze["full_original_failed_gate_preserved"]
    assert not freeze["production_changes"]
    assert (
        hashlib.sha256((folder / "policy.json").read_bytes()).hexdigest()
        == freeze["policy_sha256"]
    )
    for path, expected in freeze["reference_files"].items():
        # The original test is retained beside the frozen migration policy.
        p = (
            folder / "original-test_meihua_day_qi.py"
            if path == "tests/test_meihua_day_qi.py"
            else Path(__file__).parents[1] / path
        )
        assert hashlib.sha256(p.read_bytes()).hexdigest() == expected, path


@pytest.mark.parametrize("index", range(12))
def test_all_twelve_complete_old_outputs_after_explicit_current_checks(index, readings):
    verify(readings[index], index)


MUTATIONS = [
    "mixed_unknown",
    "mixed_true",
    "guessed_false_scenario",
    "guessed_true_scenario",
    "wrong_obstruction_body",
    "wrong_symbol_trigram",
    "wrong_symbol_quote",
    "wrong_symbol_path",
    "wrong_strength_status",
    "wrong_favorable_flag",
    "invented_net_verdict",
    "wrong_display",
    "wrong_template",
    "wrong_calendar_day",
    "wrong_symbol_source_profile",
    "wrong_strength_source_profile",
]


@pytest.mark.parametrize("mutation", MUTATIONS)
@pytest.mark.parametrize("index", range(12))
def test_projection_rejects_each_changed_fact_instead_of_hiding_it(
    index, mutation, readings
):
    result = deepcopy(readings[index])
    ir = result["interpretation"]
    stage = ir["stage_emphasis"]
    symbols = ir["trigram_relation_symbols"]
    strength = ir["seasonal_qualification"]["volume3_qualification"]
    if mutation == "mixed_unknown":
        stage["mixed_generation_control"]["full_clause_applies"] = None
    elif mutation == "mixed_true":
        stage["mixed_generation_control"]["full_clause_applies"] = True
    elif mutation.startswith("guessed_"):
        stage["mixed_generation_control"]["scenario_condition_met"] = (
            mutation == "guessed_true_scenario"
        )
    elif mutation == "wrong_obstruction_body":
        body = stage["obstruction_timing"]["original_body"]
        body["trigram"] = "乾" if body["trigram"] != "乾" else "坤"
    elif mutation == "wrong_symbol_trigram":
        node = symbols["selected"]["role_evaluations"][0]
        node["trigram"] = "乾" if node["trigram"] != "乾" else "坤"
    elif mutation == "wrong_symbol_quote":
        symbols["selected"]["role_evaluations"][0]["quote"] = "altered quote"
    elif mutation == "wrong_symbol_path":
        symbols["selected"]["role_evaluations"][0][
            "trigram_fact_path"
        ] = "meihua.use_trigram.element"
    elif mutation == "wrong_strength_status":
        strength["condition_checks"][0]["status"] = "altered_status"
    elif mutation == "wrong_favorable_flag":
        node = strength["auxiliary_checks"][0]
        node["favorable_clause_applies"] = node["favorable_clause_applies"] is not True
    elif mutation == "invented_net_verdict":
        strength["net_verdict"] = "guaranteed"
    elif mutation == "wrong_display":
        ir["moving_line_oracle"]["classical_yaoci_rendering"][
            "display_text"
        ] += "altered"
    elif mutation == "wrong_template":
        ir["moving_line_oracle"]["classical_yaoci_rendering"][
            "template_wikitext_sha256"
        ] = ("0" * 64)
    elif mutation == "wrong_calendar_day":
        calendar = result["calendar_context"]["lunar_calendar"]
        calendar["day_ganzhi"] = "甲子" if calendar["day_ganzhi"] != "甲子" else "乙丑"
    elif mutation == "wrong_symbol_source_profile":
        symbols["ruleset"]["rules"][0]["quote"] = "altered original"
    elif mutation == "wrong_strength_source_profile":
        strength["ruleset"]["rules"][0]["quote"] = "altered original"
    else:
        raise AssertionError("Unknown test mutation")
    with pytest.raises(AssertionError):
        verify(result, index)
