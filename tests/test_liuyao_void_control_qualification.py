"""Current void filling licenses scoped control without deleting day control."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_roles import classical

BASE = Path(__file__).parent / "fixtures/liuyao_void_control_v31"
CASES = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))["cases"]


def pair(result, case):
    return next(
        x
        for x in result["control_conditions"]["controls"]
        if (x["source_position"], x["target_position"])
        == (case["source_position"], case["target_position"])
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_control_truth(case):
    result = classical(case)
    assert pair(result, case)["condition_match"] is case["expected_control"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_qualification_is_separate_from_remaining_controls(case):
    result = classical(case)
    p = pair(result, case)
    assert (
        p["source_void_fill_control_condition"]
        is case["expected_void_fill_control_qualification"]
    )
    assert (
        p["source_void_fill_used"] is case["expected_void_fill_control_qualification"]
    )
    if p["source_void_fill_used"]:
        assert p["source_rescue_used"] is False
        assert any(
            h["location"] == "day" and h["branch"] == case["day_ganzhi"][1]
            for h in p["source_calendar_oppositions"]
        )
        assert (
            result["clash_conditions"]["lines"][case["source_position"] - 1][
                "day_void_fill_condition"
            ]
            is True
        )
        assert (
            result["void_conditions"]["lines"][case["source_position"] - 1][
                "is_xunkong"
            ]
            is True
        )
    if case["id"] == "same-edition-author-qian":
        assert p["source_calendar_supported"] is False
        assert (
            result["classical_assessment"]["lines"][1]["strength"]["is_supported"]
            is not True
        )
        # The v30 questioner-generation oracle stays withdrawn. This new
        # source condition is for directed control, not a generation license.
        assert result["generation_conditions"]["sources"][1]["condition_match"] is False
        edge = next(
            e
            for e in result["interaction_edges"]
            if e["source_kind"] == "base"
            and e["source_position"] == 2
            and e["target_position"] == 3
        )
        assert edge["control_condition_match"] is True
        route = next(
            x
            for x in result["routing_conditions"]["routes"]
            if x["positions"] == [2, 4, 3]
        )
        assert route["condition_match"] is not True
    if case["id"] == "additional-moving-metal":
        assert p["source_competing_active_controls"]
        assert p["condition_match"] is None
    if case["id"] == "target-actually-moving":
        assert p["status"] == "active_to_active_requires_arbitration"
    if case["id"] == "own-back-control-retained":
        assert p["status"] == "back_control_obstructs_outgoing_candidate"


def test_frozen_author_clause_and_case_protocol():
    from fatebridge.core.liuyao_void_control import PROFILE
    from scripts.build_liuyao_void_control_profile import build

    assert build() == PROFILE
    for n, h in json.loads((BASE / "freeze.json").read_text(encoding="utf-8"))[
        "sha256"
    ].items():
        assert hashlib.sha256((BASE / n).read_bytes()).hexdigest() == h
    assert PROFILE["clauses"][0]["speaker"] == "予曰之后作者答语"


def test_partial_false_does_not_require_qualification_siblings():
    from fatebridge.core.output_liuyao_control import DirectedControl

    assert (
        DirectedControl.model_validate(
            {"source_void_fill_control_condition": False}
        ).source_void_fill_control_condition
        is False
    )
