"""Original Si/Yin/Shen exclusion is a qualifier, never an outcome verdict."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_roles import classical

BASE = Path(__file__).parent / "fixtures/liuyao_penalty_v20"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_original_scoped_penalty_and_growth_exclusion(case):
    result = classical(case)
    i = case["position"] - 1
    penalty = result["penalty_conditions"]["lines"][i]
    assert penalty["condition_match"] is case["expected_penalty_presence"]
    assert (
        result["growth_conditions"]["lines"][i]["condition_match"]
        is case["expected_qualified_growth"]
    )
    if penalty["condition_match"] is not False:
        assert penalty["effect_condition_match"] is None
    if case["day_ganzhi"].endswith("寅") and penalty["branch"] == "巳":
        assert result["growth_conditions"]["lines"][i]["position_match"] is True
        assert (
            result["growth_conditions"]["lines"][i]["raw_day_element_relation"]
            == "生爻"
        )
        strength = result["classical_assessment"]["lines"][i]["strength"]
        if penalty["condition_match"] is True:
            assert not any(
                a["location"] == "day" and a["branch"] == "寅"
                for a in strength["supports"]
            )
            assert strength["is_supported"] is not True
            assert any(
                a.get("harm_condition_match", True) is None
                for a in strength["oppositions"]
            )


def test_other_parent_transformation_does_not_supply_hidden_or_visible_si():
    result = classical(
        next(c for c in CASES if c["id"] == "other-parent-changed-shen-not-borrowed")
    )
    rows = result["penalty_conditions"]["lines"]
    assert rows[1]["condition_match"] is False and rows[4]["condition_match"] is True
    assert any(
        a["position"] == 5 and a["branch"] == "申" for a in rows[1]["ignored_actors"]
    )


def test_pending_dark_motion_is_not_a_confirmed_penalty_or_free_growth():
    result = classical(next(c for c in CASES if c["id"] == "pending-dark-shen"))
    assert result["lines"][4]["activity_condition_match"] is None
    row = result["penalty_conditions"]["lines"][1]
    assert row["condition_match"] is None
    assert result["growth_conditions"]["lines"][1]["condition_match"] is None
    assert not any(
        a["location"] == "day" and a["branch"] == "寅"
        for a in result["classical_assessment"]["lines"][1]["strength"]["supports"]
    )


def test_qualified_role_growth_uses_same_condition_and_keeps_raw_formula():
    result = classical(CASES[0])
    role = next(r for r in result["role_effects"]["lines"] if r["position"] == 2)
    assert role["atom_values"]["day_growth_peak"] is True
    assert role["conditional_atom_values"]["day_growth_peak"] is False
    item = next(
        r for r in role["supporting_conditions"] if r["rule_id"] == "ji_support_4"
    )
    assert item["matched"] is True and item["conditional_matched"] is False


def test_original_source_freeze_and_separate_quotation_correction():
    from fatebridge.core.liuyao_penalty import PROFILE
    from scripts.build_liuyao_penalty_profile import build

    assert build() == PROFILE
    frozen = json.loads((BASE / "freeze.json").read_text())
    for name, digest in frozen["sha256"].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert len(CASES) == 10
    assert (
        PROFILE["quotation_errata"]["old_quote"]
        != PROFILE["quotation_errata"]["new_quote"]
    )


def test_unadjudicated_penalty_alone_cannot_prove_a_controlled_source_failed():
    from fatebridge.core.liuyao_generation import generation_sources

    # This directly isolates the error path: an unresolved penalty is not an
    # independently confirmed controlling actor. Other gates remain in force.
    row = dict(position=1, branch="巳", element="火", change=True)
    condition = dict(
        activity="明动", binding_cues=[], monthly_strength=dict(monthly_supported=False)
    )
    observation = dict(
        supports=[],
        pending_supports=[],
        possible_supports=[],
        harms=[dict(location="day", harm_condition_match=None, grounded=False)],
    )
    result = generation_sources(
        lines=[row],
        conditions=[condition],
        observations={1: observation},
        grounded=set(),
        month="申",
        day_ganzhi="甲寅",
    )[1]
    assert result["condition_match"] is None


def test_line_only_triad_does_not_invent_a_monthly_counteractor():
    case = json.loads((BASE / "attribution-case.json").read_text())
    frozen = json.loads((BASE / "attribution-freeze.json").read_text())
    assert (
        hashlib.sha256((BASE / "attribution-case.json").read_bytes()).hexdigest()
        == frozen["case_sha256"]
    )
    result = classical(case)
    p = case["position"] - 1
    penalty = result["penalty_conditions"]["lines"][p]
    assert penalty["condition_match"] is True
    assert {a["location"] for a in penalty["actors"]} == {"visible", "changed"}
    assert (
        sorted({a["branch"] for a in penalty["actors"]})
        == case["expected_actor_branches"]
    )
    harm = next(
        a
        for a in result["classical_assessment"]["lines"][p]["strength"]["oppositions"]
        if "penalty_source_path" in a
    )
    assert harm["location"] == case["expected_opposition_location"]
    assert harm["branch"] == case["expected_opposition_branch"]
    assert harm["pattern_actor_branches"] == case["expected_actor_branches"]
    assert harm["grounded"] is False and harm["harm_condition_match"] is None
