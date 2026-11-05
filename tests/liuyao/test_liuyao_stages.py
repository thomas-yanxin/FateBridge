"""Frozen partial-knowledge queries do not invent missing fire positions."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.liuyao.build_profile import build_profile
from tests.liuyao.test_liuyao_conditions import mounted
from tests.liuyao.test_liuyao_hidden_reception import hidden_case

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_stages_v15"
FROZEN = json.loads((REFERENCE / "cases.json").read_text())
ERRATA = json.loads((REFERENCE / "input-errata.json").read_text())


def corrected(case):
    correction = next(
        (e for e in ERRATA["input_corrections"] if e["case_id"] == case["id"]), None
    )
    return {**case, **correction["corrected_input"]} if correction else case


def test_stage_profile_and_original_table_bytes_are_frozen():
    from fatebridge.core.liuyao_stages import PROFILE, STAGES

    assert PROFILE == build_profile("stage")
    assert STAGES["火"] == {"寅": "长生", "戌": "墓"}
    for name, digest in json.loads((REFERENCE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    for name, digest in json.loads(
        (REFERENCE / "input-errata-freeze.json").read_text()
    )["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", FROZEN["queries"], ids=lambda c: c["id"])
def test_hand_derived_phase_queries_preserve_true_false_and_unknown(case):
    from fatebridge.core.liuyao_stages import STAGES, query_stage

    result = query_stage(
        STAGES, case["element"], case["branch"], case["expected_stages"]
    )
    assert result["condition_match"] is case["expected"]
    assert result["query_complete"] is (case["expected"] is not None)
    assert result["table_complete"] is (case["element"] != "火")


@pytest.mark.parametrize("case", FROZEN["cases"], ids=lambda c: c["id"])
def test_hidden_stage_positions_and_query_specific_admission(case):
    result = hidden_case(corrected(case))
    hidden = result["hidden_conditions"][0]
    phases = hidden["stage_conditions"]
    assert (
        phases["hidden_tomb_cessation"]["condition_match"]
        is case["expected_hidden_stage"]
    )
    assert (
        phases["flying_tomb_cessation"]["condition_match"]
        is case["expected_flying_stage"]
    )
    assert phases["has_relevant_unknown"] is case["expected_relevant_unknown"]
    assert hidden["reception"]["condition_match"] is case["expected_reception"]
    legacy = next(
        c
        for c in hidden["obstructing_conditions"]
        if c["rule_id"] == "hidden_tomb_cessation"
    )
    assert legacy["qualified_matched"] is case["expected_hidden_stage"]
    if hidden["branch"] == "午":
        assert legacy["matched"] is None  # Historical raw flag is unchanged.
        assert hidden["table_gaps"]  # The global source gap remains visible.


def test_verified_fire_tomb_dominates_other_unknown_positions_without_certifying_entry():
    hidden = hidden_case(FROZEN["cases"][-1])["hidden_conditions"][0]
    group = hidden["stage_conditions"]["hidden_tomb_cessation"]
    assert group["condition_match"] is True
    assert group["all_queries_resolved"] is False
    assert any(q["condition_match"] is None for q in group["queries"])
    assert (
        "hidden_tomb_or_cessation_position_not_adjudicated"
        in hidden["reception"]["pending_reasons"]
    )
    assert hidden["reception"]["condition_match"] is None


def test_noncontrolling_fire_flying_unknown_is_diagnostic_and_pressure_unknown_is_relevant():
    no_pressure = hidden_case(FROZEN["cases"][3])["hidden_conditions"][0]
    pressure = hidden_case(corrected(FROZEN["cases"][9]))["hidden_conditions"][0]
    assert no_pressure["stage_conditions"]["ignored_unknown_groups"] == [
        "flying_tomb_cessation"
    ]
    assert no_pressure["reception"]["condition_match"] is True
    assert pressure["stage_conditions"]["ignored_unknown_groups"] == []
    assert pressure["reception"]["condition_match"] is None


def test_all_hidden_inputs_match_the_manually_identified_pure_palace_position():
    assert len(ERRATA["input_corrections"]) == 2
    for raw in FROZEN["cases"]:
        case = corrected(raw)
        info, rows = mounted(case["base_code"], case["changed_code"])
        pure = ERRATA["expected_palace_pure_code"][case["base_code"]]
        pure_info, pure_rows = mounted(pure, pure)
        assert info["current_palace"] == pure_info["current_palace"]
        assert pure_rows[case["focus_line"] - 1]["branch"] == case["hidden_branch"]
        assert rows[case["focus_line"] - 1]["branch"] == case["flying_branch"]
        assert pure_rows[case["focus_line"] - 1]["liuqin"] not in {
            r["liuqin"] for r in rows
        }


@pytest.mark.parametrize(
    "element,branch,targets",
    [("气", "子", ["墓"]), ("火", "辰", ["死"]), ("木", "A", ["墓"])],
)
def test_unpublished_phases_and_invalid_symbols_are_rejected(element, branch, targets):
    from fatebridge.core.liuyao_stages import STAGES, query_stage

    with pytest.raises(ValueError):
        query_stage(STAGES, element, branch, targets)
