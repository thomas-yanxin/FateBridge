"""Frozen activity/control constraints and rejected outward-control paths."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parent / "fixtures/liuyao_control_v9"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]
ERRATA = json.loads((REFERENCE / "errata.json").read_text(encoding="utf-8"))


def test_control_source_freeze_is_preserved():
    from fatebridge.core.liuyao_control import PROFILE
    from scripts.build_liuyao_control_profile import build

    assert build() == PROFILE
    freeze = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, digest in freeze["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_control_conditions(case):
    result = conditional_case(case)
    control = result["control_conditions"]
    by_pair = {
        (r["source_position"], r["target_position"]): r for r in control["controls"]
    }
    for source, target, expected in case["expected_controls"]:
        if case["id"] == ERRATA["case_id"] and [source, target] == ERRATA["pair"]:
            assert expected is True  # Initial frozen annotation retained as wrong.
            expected = ERRATA["corrected_condition_match"]
        row = by_pair[(source, target)]
        assert row["condition_match"] is expected
        assert row["status"]
        assert row["relation"] == "克爻"
    assert control["adjudication"] == "directed_control_conditions_only"
    assert "score" not in control and "predicted_success" not in control


def test_weak_moving_controller_does_not_require_its_own_strength_root():
    result = conditional_case(CASES[1])
    wood = result["classical_assessment"]["lines"][1]["strength"]
    metal = result["classical_assessment"]["lines"][4]["strength"]
    assert metal["is_supported"] is not True
    harm = next(o for o in wood["oppositions"] if o.get("position") == 5)
    assert harm["grounded"] is True
    assert harm["control_condition_match"] is True


def test_unrelated_move_does_not_erase_a_qualified_static_control_edge():
    result = conditional_case(CASES[2])
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 2
        and e["target_position"] == 3
        and e["relation"] == "克爻"
    )
    assert edge["control_condition_match"] is True


def test_injured_static_control_is_preserved_as_a_blocked_relation():
    result = conditional_case(CASES[1])
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 2
        and e["target_position"] == 3
        and e["relation"] == "克爻"
    )
    assert edge["control_condition_match"] is False
    assert edge["effect_status"] == "active_control_obstructs_static_control"
    earth = result["classical_assessment"]["lines"][2]["strength"]
    assert any(o["position"] == 2 for o in earth["blocked_oppositions"])
    assert all(o.get("position") != 2 for o in earth["oppositions"])


def test_dark_activation_cannot_borrow_an_unresolved_empty_moving_helper():
    result = conditional_case(CASES[3])
    # You is day-clashed, but its only raw helper is the empty, calendar-harmed Chou.
    assert result["lines"][4]["activity"] == "暗动条件匹配"
    assert result["lines"][4]["supporting_moving_positions"] == [3]
    assert result["lines"][4]["activity_condition_match"] is None
    row = next(
        r
        for r in result["control_conditions"]["controls"]
        if r["source_position"] == 5 and r["target_position"] == 2
    )
    assert row["condition_match"] is None
    # Isolate the no-day-clash counterfactual instead of erasing the frozen case.
    clear = conditional_case({**CASES[3], "day_ganzhi": "甲寅"})
    row = next(
        r
        for r in clear["control_conditions"]["controls"]
        if r["source_position"] == 2 and r["target_position"] == 6
    )
    assert row["condition_match"] is True


def test_role_conditions_preserve_raw_relation_and_apply_scoped_control_unknown():
    result = conditional_case({**CASES[6], "focus_line": 3})
    role = next(r for r in result["role_effects"]["lines"] if r["position"] == 2)
    assert role["atom_values"]["calendar_moving_controls"] is True
    assert role["conditional_atom_values"]["calendar_moving_controls"] is None
    rule = next(
        r
        for r in role["obstructing_conditions"]
        if "calendar_moving_controls" in str(r["predicate"])
    )
    # This clause also needs weakness; neither raw nor applied predicate may
    # skip that unresolved premise just because a control direction exists.
    assert rule["matched"] is None and rule["conditional_matched"] is None
    assert (
        rule["conditional_status"] == "requires_unresolved_control_or_other_conditions"
    )

    pending = conditional_case({**CASES[3], "focus_line": 2})
    metal = next(r for r in pending["role_effects"]["lines"] if r["position"] == 5)
    co_motion = next(
        r for r in metal["supporting_conditions"] if r["predicate"] == "chou_active"
    )
    assert co_motion["matched"] is True and co_motion["conditional_matched"] is None


def test_simultaneous_control_conditions_are_independent_of_input_iteration_order():
    from fatebridge.core.liuyao_control import build_control_conditions
    from fatebridge.core.liuyao_judgment import STAGES
    from tests.test_liuyao_conditions import mounted

    case = CASES[7]
    result = conditional_case(case)
    _, rows = mounted(case["base_code"], case["changed_code"])
    reversed_result = build_control_conditions(
        lines=list(reversed(rows)),
        conditions=list(reversed(result["lines"])),
        month=case["month_branch"],
        day_ganzhi=case["day_ganzhi"],
        stages=STAGES,
    )
    assert reversed_result == result["control_conditions"]


def test_directed_control_models_allow_partial_fields_without_siblings():
    from fatebridge.core.output_liuyao_control import ControlConditions, DirectedControl

    assert DirectedControl.model_validate(
        {"status": "active_to_active_requires_arbitration"}
    ).status
    assert ControlConditions.model_validate({"source_sha256": "x"}).source_sha256 == "x"
