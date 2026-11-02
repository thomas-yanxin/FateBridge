"""Named original generation conditions remain distinct from global strength."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parent / "fixtures/liuyao_generation_v11"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]
ERRATA = json.loads((REFERENCE / "errata.json").read_text())["records"]


def annotated_case(case):
    for erratum in ERRATA:
        if case["id"] != erratum["case_id"]:
            continue
        if "original_inputs" in erratum:
            for field, value in erratum["original_inputs"].items():
                assert case[field] == value
            return {**case, **erratum["corrected_inputs"]}
        assert case["expected_benefit"] is erratum["original_expected_benefit"]
        return {**case, "expected_benefit": erratum["corrected_expected_benefit"]}
    return case


def test_generation_reference_is_frozen_and_packaged():
    from fatebridge.core.liuyao_generation import PROFILE
    from scripts.build_liuyao_generation_profile import build

    assert build() == PROFILE
    for name, digest in json.loads((REFERENCE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_source_can_generate_and_target_can_receive_are_separate(case):
    case = annotated_case(case)
    result = conditional_case(case)
    generation = result["generation_conditions"]
    pair = next(
        p
        for p in generation["generations"]
        if p["source_position"] == case["source_position"]
        and p["target_position"] == case["target_position"]
    )
    assert pair["condition_match"] is case["expected_generation"]
    assert pair["benefit_now"] is case["expected_benefit"]
    assert pair["status"] and pair["target_status"]
    assert pair["source_path"] and pair["source_url"]


def test_original_huan_source_keeps_calendar_injury_without_losing_generation():
    detail = conditional_case(CASES[1])
    source = detail["classical_assessment"]["lines"][5]["strength"]
    target = detail["classical_assessment"]["lines"][2]["strength"]
    assert source["is_supported"] is None
    assert any(h["location"] == "day" for h in source["oppositions"])
    assert any(
        a["position"] == 6 and a["generation_condition_match"] is True
        for a in target["supports"]
    )
    edge = next(
        e
        for e in detail["interaction_edges"]
        if e["source_kind"] == "base"
        and (e["source_position"], e["target_position"]) == (6, 3)
    )
    assert edge["effect_status"] == "conditional"
    assert edge["generation_condition_match"] is True and edge["benefit_now"] is True
    assert edge["generation_status"] and edge["target_reception_status"]


def test_rootless_target_keeps_the_incoming_direction_but_not_confirmed_benefit():
    detail = conditional_case(annotated_case(CASES[2]))
    focus = detail["classical_assessment"]["focus"]["strength"]
    assert focus["is_failing"] is True
    assert any(
        a["position"] == 5 and a["target_reception_condition"] is False
        for a in focus["blocked_supports"]
    )


def test_nonvoid_counterfactual_retains_generation_without_overriding_frozen_day():
    detail = conditional_case({**CASES[10], "day_ganzhi": "丁巳"})
    pair = next(
        g
        for g in detail["generation_conditions"]["generations"]
        if (g["source_position"], g["target_position"]) == (4, 2)
    )
    assert pair["condition_match"] is True and pair["benefit_now"] is True
