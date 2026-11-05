"""Frozen source directions, causal controls and competing root effects."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.storage_movement import storage_movement_effect
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.utils.data import STEM_ELEMENTS, get_shishen
from tests.test_strength_v2 import pillars, score

PATH = Path(__file__).parent / "data/bazi_storage_movement_v1/reference.json"
REFERENCE = json.loads(PATH.read_text())


def test_source_probes_remain_frozen_and_do_not_invent_complete_births():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == PATH.with_suffix(".sha256").read_text().strip()
    )
    assert len(REFERENCE["partial_source_examples"]) == 5
    assert "partial" in REFERENCE["annotation"]
    assert all("hour" not in case for case in REFERENCE["partial_source_examples"])


def test_classical_audit_fingerprints_the_actual_root_effect_implementation():
    from tests.test_bazi_classical_audit import audit

    result = audit.audit()
    name = "src/fatebridge/core/storage_movement.py"
    assert (
        result["source_fingerprints"][name]
        == hashlib.sha256((PATH.parents[3] / name).read_bytes()).hexdigest()
    )
    assert not result["summary"]["classical_acceptance_passed"]


@pytest.mark.parametrize("case", REFERENCE["partial_source_examples"])
def test_source_examples_preserve_earth_and_do_not_automatically_open_storage(case):
    branches = {"month": case["month_branch"], "other": case["other_branch"]}
    result = storage_movement_effect(
        branches, ["month", "other"], "六冲", case["day_stem"], 0.75
    )
    assert result is not None
    assert result["source"]["source_sha256"] == REFERENCE["source_sha256"]
    earth = [r for r in result["root_effects"] if r["element"] == "土"]
    assert all(r["event_retention_multiplier"] == 1 for r in earth)
    # A revealed 壬 can use a same-element 癸 root; never invent 壬 in 辰.
    assert get_shishen(case["day_stem"], case["revealed_stem"]) == case["revealed_role"]
    assert any(
        r["element"] == STEM_ELEMENTS[case["revealed_stem"]][0].value
        for r in result["root_effects"]
    )
    assert result["earth_energy_bonus"] == 0
    assert result["formation_status"] == "not_adjudicated"
    assert all(
        0 <= r["event_retention_multiplier"] <= 1 for r in result["root_effects"]
    )
    assert (
        result["numeric_magnitude_origin"]
        == "engineering_policy_not_classical_coefficient"
    )


@pytest.mark.parametrize(
    "branches,kind",
    [
        (["辰"], "六冲"),
        (["未", "戌"], "刑"),
        (["子", "午"], "六冲"),
        (["寅", "申"], "六冲"),
    ],
)
def test_lone_storage_or_other_relations_do_not_trigger_the_rule(branches, kind):
    mapping = dict(enumerate(branches))
    # Use stable names, without filling any unspecified pillars.
    named = {str(k): v for k, v in mapping.items()}
    assert storage_movement_effect(named, list(named), kind, "甲", 0.75) is None


def test_earth_clash_changes_water_not_every_hidden_root_or_earth_energy():
    text = "甲辰 丙戌 戊巳 庚寅"
    actual, control = score(text), score(text, clash_equal=1)
    assert actual["effective_elements"]["水"] < control["effective_elements"]["水"]
    for element in "土木火金":
        assert (
            actual["effective_elements"][element]
            == control["effective_elements"][element]
        )
    assert actual["roots"] == control["roots"]  # 戊日主的土根不因土冲统一减损。
    event = next(e for e in actual["relations"] if e["kind"] == "六冲")
    assert event["clash_mode"] == "storage_earth_movement"
    assert all(
        r["remaining_hidden_mass"] > 0 for r in event["storage_effect"]["root_effects"]
    )


def test_complete_earth_punishment_does_not_erase_soil_root():
    text = "甲丑 丙未 戊戌 庚亥"
    actual = score(text, clash_equal=1)
    control = score(text, clash_equal=1, punishment=1)
    assert actual["roots"] == control["roots"]
    assert actual["effective_elements"]["水"] < control["effective_elements"]["水"]
    event = next(e for e in actual["relations"] if e["kind"] == "刑")
    assert event["source_id"] == "ziping_storage_movement_v1"


def test_event_soil_protection_does_not_erase_actual_combination_binding():
    result = score("庚戌 癸丑 乙子 丁未")
    event = next(e for e in result["relations"] if e["kind"] == "刑")
    soil = next(
        r
        for r in event["storage_effect"]["root_effects"]
        if r["pillar"] == "month" and r["element"] == "土"
    )
    assert soil["event_retention_multiplier"] == 1
    assert soil["combined_loss_multiplier"] == 0.85
    assert any(
        e["kind"] == "六合" and e["status"] == "binding" for e in result["relations"]
    )


def test_repeat_clashes_do_not_multiply_water_loss_and_input_order_is_stable():
    text = "甲辰 丙戌 戊辰 庚寅"
    result = score(text)
    p = pillars(text)
    assert result == _evaluate(
        dict(reversed(list(p.items()))),
        ElementAnalysis.seasonal_phases(p["month"][1]),
        DEFAULT_POLICY,
    )
    for event in result["relations"]:
        if "storage_effect" not in event:
            continue
        for root in event["storage_effect"]["root_effects"]:
            if root["element"] == "水":
                assert root["combined_loss_multiplier"] == 0.75
    assert sum(b["remaining"] for b in result["branch_budgets"].values()) <= sum(
        b["initial"] for b in result["branch_budgets"].values()
    )
