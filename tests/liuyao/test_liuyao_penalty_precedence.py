"""Frozen cross-clause priority; raw relations do not certify Yin support."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.liuyao.test_liuyao_roles import classical

BASE = Path(__file__).parents[1] / "fixtures/liuyao_penalty_precedence_v21"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]
ERRATA = json.loads((BASE / "expectation-errata.json").read_text())
CASES = [
    {
        **c,
        **{
            k: v
            for k, v in ERRATA["corrections"].get(c["id"], {}).items()
            if k.startswith("expected_")
        },
    }
    for c in CASES
] + [ERRATA["supplemental_case"]]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_yin_generation_priority(case):
    result = classical(case)
    i = case["position"] - 1
    context = result["penalty_conditions"]["lines"][i]
    assert context["condition_match"] is case["expected_presence"]
    assert context["yin_generation_allowed"] is case["expected_yin_permission"]
    assert context["effect_condition_match"] is (
        False if case["expected_presence"] is False else None
    )
    strength = result["classical_assessment"]["lines"][i]["strength"]
    if case["expected_yin_permission"] is not True:
        assert not any(a["branch"] == "寅" for a in strength["supports"])
    if case["id"].startswith("own-yin"):
        back = result["back_generation_conditions"]["sources"][i]
        assert back["is_back_generation"] is True
        assert back["changed_relation"] == "生爻"
        assert back["condition_match"] is case["expected_yin_permission"]
        assert back["penalty_source_path"] == context["source_path"]
        if case["id"] != "own-yin-month-break-also":
            assert back["raw_condition_match"] is True
        else:
            assert back["raw_condition_match"] is None
        source = result["generation_conditions"]["sources"][i]
        assert source["back_generation_condition"] is case["expected_yin_permission"]
    if case["id"].startswith("moving-yin"):
        pair = next(
            g
            for g in result["generation_conditions"]["generations"]
            if g["source_position"] == 2 and g["target_position"] == 5
        )
        assert pair["target_yin_generation_allowed"] is case["expected_yin_permission"]
        if case["expected_yin_permission"] is False:
            assert pair["benefit_now"] is False
            # Exclusion belongs to this Si target, not a universal source ban.
            assert (
                pair["condition_match"]
                is result["generation_conditions"]["sources"][1]["condition_match"]
            )


def test_precedence_source_and_cases_are_immutable():
    for name, digest in json.loads((BASE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    from fatebridge.core.liuyao_penalty import PROFILE

    assert (
        hashlib.sha256((BASE / "expectation-errata.json").read_bytes()).hexdigest()
        == json.loads((BASE / "expectation-errata-freeze.json").read_text())["sha256"]
    )
    assert (
        hashlib.sha256((BASE / "cases.json").read_bytes()).hexdigest()
        == ERRATA["original_cases_sha256"]
    )
    assert PROFILE["precedence"]["source_sha256"] == PROFILE["source"]["sha256"]
    assert PROFILE["precedence"]["not_adjudicated"]


def test_routing_does_not_reuse_a_target_excluded_yin_credit():
    result = classical(
        dict(
            base_code="100011",
            changed_code="010011",
            month="午",
            day_ganzhi="庚申",
            focus_line=5,
        )
    )
    route = next(
        r for r in result["routing_conditions"]["routes"] if r["positions"] == [1, 2, 5]
    )
    gate = next(c for c in route["conditions"] if c["id"] == "yuan_generation")
    assert gate["matched"] is False
    assert gate["reason"] == "target_yin_generation_excluded"
    assert route["condition_match"] is False
