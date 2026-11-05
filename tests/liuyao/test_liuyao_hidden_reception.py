"""Preimplementation hidden-target cases, separate from real event validity."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.liuyao.test_liuyao_conditions import conditional_case, mounted

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_hidden_v14"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]
ERRATA = json.loads((REFERENCE / "errata.json").read_text())["corrections"]


def hidden_case(case):
    from fatebridge.core.liuyao_judgment import kinship
    from fatebridge.core.liuyao_relations import ELEMENTS

    info, _ = mounted(case["base_code"], case["changed_code"])
    hidden = dict(
        position=case["focus_line"],
        branch=case["hidden_branch"],
        element=ELEMENTS[case["hidden_branch"]],
        liuqin=kinship(info["current_palace_element"], ELEMENTS[case["hidden_branch"]]),
        flying_branch=case["flying_branch"],
    )
    return conditional_case(case, hidden=[hidden], focus_kind="hidden")


def test_hidden_reception_cases_and_original_remain_frozen():
    from fatebridge.core.liuyao_hidden import PROFILE
    from scripts.liuyao.build_liuyao_hidden_profile import build

    assert PROFILE == build()
    for name, digest in json.loads((REFERENCE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    for name, digest in json.loads((REFERENCE / "errata-freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_hidden_reception_uses_its_own_branch_and_qualified_sources(case):
    result = hidden_case(case)
    hidden = result["hidden_conditions"][0]
    reception = hidden["reception"]
    corrected = next((e for e in ERRATA if e["case_id"] == case["id"]), None)
    expected = corrected["corrected_value"] if corrected else case["expected_reception"]
    assert reception["condition_match"] is expected
    assert (
        reception["flying_generation"]["condition_match"]
        is case["expected_flying_generation"]
    )
    assert reception["status"] and reception["source_path"]
    assert hidden["branch"] == case["hidden_branch"]
    assert hidden["flying_branch"] == case["flying_branch"]
    legacy = next(
        c
        for c in hidden["supporting_conditions"]
        if c["rule_id"] == "flying_generates_hidden"
    )
    # Raw direction is retained; qualification must not call void/broken flying ready.
    assert legacy["qualified_matched"] is case["expected_flying_generation"]
    assert "raw_relation_match" in legacy
    assert (
        reception["adjudication"] == "listed_reception_conditions_not_final_emergence"
    )


def test_hidden_route_keeps_pending_reception_and_does_not_borrow_flying_row():
    from tests.liuyao.test_liuyao_routing import CASES as ROUTE_CASES
    from tests.liuyao.test_liuyao_routing import routing_case

    result = routing_case(ROUTE_CASES[10])
    for route in result["routing_conditions"]["routes"]:
        stage = next(c for c in route["conditions"] if c["id"] == "focus_reception")
        assert stage["matched"] is None
        assert stage["source_paths"][0].endswith("hidden_conditions.0.reception")
        assert stage["reason"] != "hidden_target_reception_not_adjudicated"


def test_alternative_calendar_support_does_not_turn_void_flying_into_a_source():
    hidden = hidden_case(CASES[2])["hidden_conditions"][0]
    assert hidden["reception"]["condition_match"] is True
    assert hidden["reception"]["flying_generation"]["condition_match"] is None
    assert "calendar_support" in hidden["reception"]["support_reasons"]
    assert (
        "flying_void_or_month_break_release" in hidden["reception"]["support_reasons"]
    )


def test_frozen_annotation_error_is_explicit_and_possible_controller_is_retained():
    assert len(ERRATA) == 2 and CASES[3]["expected_reception"] is True
    result = hidden_case(CASES[3])
    assert (
        mounted(CASES[3]["base_code"], CASES[3]["changed_code"])[1][2]["branch"] == "酉"
    )
    assert result["lines"][2]["activity_condition_match"] is None
    assert result["hidden_conditions"][0]["reception"][
        "possible_control_positions"
    ] == [3]


def test_static_flying_exception_keeps_ordinary_source_pending_and_its_own_pointer():
    result = hidden_case(CASES[6])
    flying = result["hidden_conditions"][0]["reception"]["flying_generation"]
    assert flying["condition_match"] is True
    assert flying["source_generation_condition_match"] is None
    assert (
        flying["source_generation_status"]
        == "static_outside_current_all_static_generation_scope"
    )
    assert result["generation_conditions"]["sources"][1]["condition_match"] is None
    assert flying["source_path"].endswith(
        "hidden_conditions.0.reception.flying_generation"
    )


def test_day_combination_cannot_be_erased_to_call_hidden_unrooted():
    result = hidden_case(CASES[8])
    gate = result["hidden_conditions"][0]["reception"]
    assert CASES[8]["expected_reception"] is False
    assert gate["condition_match"] is None
    assert "日合扶起条件" in gate["calendar_support_reasons"]
    assert gate["blocking_reasons"] == []
    assert "flying_control_requires_global_resolution" in gate["pending_reasons"]


def test_defeated_other_generator_does_not_cancel_month_supported_static_flying():
    from tests.liuyao.test_liuyao_void import classical

    result = classical(
        dict(
            base_code="111001",
            changed_code="111000",
            month="寅",
            # Synthetic nonvoid counterpart: the older 甲辰 case has 寅卯空.
            day_ganzhi="甲午",
            focus_line=2,
            focus_kind="hidden",
            hidden=[
                dict(
                    position=2,
                    branch="午",
                    element="火",
                    liuqin="父母",
                    flying_branch="寅",
                )
            ],
        )
    )
    h = result["hidden_conditions"][0]
    raw = next(
        c
        for c in h["supporting_conditions"]
        if c["rule_id"] == "flying_generates_hidden"
    )
    assert raw["matched"] is True and raw["qualified_matched"] is True
    assert h["reception"]["flying_generation"]["condition_match"] is True
    assert result["generation_conditions"]["sources"][1]["condition_match"] is None
    assert h["reception"]["condition_match"] is None  # Fire table gap remains.
