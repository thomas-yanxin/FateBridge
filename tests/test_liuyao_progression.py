"""Original progression clauses, frozen structures and horizon counterexamples."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.liuyao_progression import PROFILE
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.requests.divination import SixYaoRequest
from scripts.build_liuyao_progression_profile import build
from tests.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parent / "fixtures/liuyao_progression_v8"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]
ERRATA = json.loads((REFERENCE / "errata.json").read_text(encoding="utf-8"))["cases"]


def test_progression_reference_was_frozen_before_implementation():
    from fatebridge.core.liuyao_evidence import ADVANCES

    assert build() == PROFILE
    assert ADVANCES == dict(PROFILE["advance_pairs"])
    frozen = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, digest in frozen["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_progression_conditions_follow_the_frozen_original_structures(case):
    result = conditional_case(
        {**case, "focus_line": case["position"]},
        event_horizon=case.get("event_horizon"),
    )
    progress = result["lines"][case["position"] - 1]["progress_conditions"]
    assert progress["structural_pair"] == case["expected_pair"]
    expected = ERRATA.get(case["id"], case)
    if case["id"] in ERRATA:
        # Report these separately; never rewrite the frozen initial oracle.
        assert case["month_branch"] == "寅"
        assert "申" in (
            result["classical_assessment"]["lines"][case["position"] - 1]["branch"],
            result["lines"][case["position"] - 1]["progress_conditions"][
                "changed_branch"
            ],
        )
        assert progress["state"] != case["expected_state"]
    assert progress["state"] == expected["expected_state"]
    assert progress["condition_now"] is expected["expected_now"]
    assert len(progress["clauses"]) == 4
    assert progress["adjudication"] == "progression_conditions_only"
    assert "score" not in progress and "predicted_success" not in progress


def test_same_element_transformation_cannot_supply_its_own_independent_root():
    # Synthetic winter-metal counterexample; no original event or civil year.
    case = {
        "base_code": "011100",
        "changed_code": "011110",
        "month_branch": "亥",
        "day_ganzhi": "丙寅",
        "focus_line": 5,
    }
    result = conditional_case(case)
    strength = result["classical_assessment"]["lines"][4]["strength"]
    assert strength["is_supported"] is not True
    assert all(s["location"] != "changed" for s in strength["supports"])
    # Seasonal weakness does not silence an actual moving control relation.
    result = conditional_case({**CASES[-1], "focus_line": 5})
    assert any(
        e["source_kind"] == "base"
        and e["source_position"] == 5
        and e["target_position"] == 2
        and e["relation"] == "克爻"
        for e in result["interaction_edges"]
    )


@pytest.mark.parametrize(
    "base,changed,state,now",
    [
        ("011100", "011110", "advance_waits_for_strength", None),
        ("111110", "111100", "retreat_weak_now", True),
    ],
)
def test_unassisted_winter_metal_does_not_bootstrap_progression(
    base, changed, state, now
):
    result = conditional_case(
        {
            "base_code": base,
            "changed_code": changed,
            "month_branch": "亥",
            "day_ganzhi": "丙寅",
            "focus_line": 5,
        }
    )
    progress = result["lines"][4]["progress_conditions"]
    assert progress["state"] == state and progress["condition_now"] is now
    assert progress["original_strength_basis"] == "unassisted_seasonal_branch_only"


def test_raw_role_predicates_are_preserved_but_progress_atoms_are_conditional():
    # Same source structure; line 5 metal is Yuan for line 4 Hai water.
    case = {**CASES[1], "focus_line": 4}
    result = conditional_case(case, event_horizon="near")
    role = next(r for r in result["role_effects"]["lines"] if r["position"] == 5)
    assert role["atom_values"]["retreat"] is True
    assert role["progress_atom_values"]["retreat"] is False
    assert role["progress_source_path"].endswith(".lines.4.progress_conditions")
    retreat = next(
        r for r in role["obstructing_conditions"] if "retreat" in str(r["predicate"])
    )
    # The original Chapter Ten predicate also requires weakness; preserve it.
    assert retreat["matched"] is False
    assert retreat["progress_adjusted_matched"] is False

    winter = conditional_case(
        {**CASES[0], "focus_line": 2, "month_branch": "亥", "day_ganzhi": "丙寅"}
    )
    yuan = next(r for r in winter["role_effects"]["lines"] if r["position"] == 5)
    advancing = next(
        r for r in yuan["supporting_conditions"] if "advance" in str(r["predicate"])
    )
    assert yuan["atom_values"]["advance"] is True
    assert yuan["progress_atom_values"]["advance"] is None
    assert advancing["matched"] is True
    assert advancing["progress_adjusted_matched"] is None


def test_timing_days_does_not_supply_a_missing_horizon():
    case = {**CASES[3], "focus_line": 5}
    for days in (0, 60):
        result = conditional_case(case, timing_days=days)
        progress = result["lines"][4]["progress_conditions"]
        assert progress["event_horizon"] is None
        assert progress["state"] == "requires_event_horizon"
        assert progress["condition_now"] is None


@pytest.mark.parametrize("value", ["short", "", 1, True])
def test_horizon_is_an_explicit_enum_on_schema_and_direct_builder(value):
    payload = {"date": "2026-08-10", "time": "12:00:00", "event_horizon": value}
    with pytest.raises(ValidationError):
        SixYaoRequest(**payload)
    with pytest.raises(ValueError, match="event_horizon"):
        build_sixyao_result(**payload)


def test_static_projection_branches_do_not_gain_progression_conditions():
    result = conditional_case({**CASES[0], "focus_line": 5})
    assert all(
        "progress_conditions" not in r for r in result["lines"] if r["position"] != 5
    )


def test_progress_models_allow_partial_fields_without_sibling_requirements():
    from fatebridge.core.output_liuyao_conditions import (
        ProgressClause,
        ProgressConditions,
    )

    assert (
        ProgressConditions.model_validate({"state": "requires_event_horizon"}).state
        == "requires_event_horizon"
    )
    assert (
        ProgressClause.model_validate({"status": "unresolved"}).status == "unresolved"
    )
