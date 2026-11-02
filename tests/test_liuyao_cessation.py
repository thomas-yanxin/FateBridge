"""Same-edition earth/Si exception; no inference from raw phase to efficacy."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.liuyao_cessation import PROFILE, _independent_sources
from scripts.build_liuyao_cessation_profile import build
from tests.test_liuyao_roles import classical

BASE = Path(__file__).parent / "fixtures/liuyao_cessation_v17"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


def test_frozen_same_edition_clauses_and_cases():
    assert build() == PROFILE
    for name, digest in json.loads((BASE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert len(CASES) == 9


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_earth_cessation_contexts(case):
    result = classical(case)
    detail = result["cessation_conditions"]
    row = detail["lines"][case["position"] - 1]
    assert row["branch"] == case["branch"]
    assert row["changed"]["branch"] == case["changed_branch"]
    query = row[case["query"]]
    assert query["position_match"] is case["expected_position_match"]
    assert query["condition_match"] is case["expected_condition"]
    assert query["actual_cessation_adjudicated"] is False
    assert row["total_rootlessness_established"] is False
    for support in row["independent_supports"]:
        for proof in [support, *support.get("independence_proof", [])]:
            value = {"liuyao_evidence": {"conditional_analysis": result}}
            for part in proof["support_fact_path"].split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            if "anchor" in proof:
                assert value == proof["anchor"]
            elif "qualification" in proof:
                assert value == proof["qualification"]
            else:
                assert value == {
                    k: v
                    for k, v in proof.items()
                    if k not in ("support_fact_path", "independence_proof")
                }
    if "expected_changed_adverse" in case:
        role = next(
            r
            for r in result["role_effects"]["lines"]
            if r["position"] == case["position"]
        )
        assert (
            role["conditional_atom_values"]["changed_adverse"]
            is case["expected_changed_adverse"]
        )
        assert role["cessation_source_path"] == row["source_path"]
        if "expected_role_rule" in case:
            assert role["role"] == "忌神"
            rule = next(
                r
                for r in role["obstructing_conditions"]
                if r["rule_id"] == "ji_obstruction_6"
            )
            assert rule["conditional_matched"] is case["expected_role_rule"]


def test_support_exception_does_not_rewrite_the_raw_position_or_clause():
    r = classical(CASES[0])
    role = next(x for x in r["role_effects"]["lines"] if x["position"] == 6)
    raw = next(
        x for x in role["obstructing_conditions"] if x["rule_id"] == "ji_obstruction_6"
    )
    assert role["atom_values"]["changed_adverse"] is True
    assert role["progress_atom_values"]["changed_adverse"] is True
    assert raw["matched"] is True and raw["conditional_matched"] is None
    assert r["lines"][5]["changed_stage"] == "绝"
    assert role["conditional_atom_values"]["back_generate"] is True


def test_queried_changed_si_cannot_prove_its_own_generation_exception():
    row = classical(CASES[2])["cessation_conditions"]["lines"][5]
    assert row["independent_support_present"] is False
    assert any(
        a["location"] == "changed"
        and a["branch"] == "巳"
        and a["exclusion"] == "queried_si_cannot_self_certify"
        for a in row["excluded_self_or_unqualified_supports"]
    )
    assert row["changed"]["condition_match"] is None


def test_static_peer_support_is_not_relabelled_as_moving_support_in_this_clause():
    row = classical(CASES[4])["cessation_conditions"]["lines"][2]
    assert row["independent_support_present"] is False
    assert any(
        a["location"] == "visible" for a in row["excluded_self_or_unqualified_supports"]
    )
    assert row["oppositions"]


def test_moving_control_still_blocks_a_confirmed_exception():
    row = classical(CASES[8])["cessation_conditions"]["lines"][5]
    assert row["independent_support_present"] is True
    assert any(
        a["location"] == "visible" and a["position"] == 2 for a in row["oppositions"]
    )
    assert row["changed"]["status"] == "earth_support_and_opposition_require_review"


def dependency_cycle():
    # An abstract but element-consistent 土→金→水→木→火→土 support
    # graph. The only initial anchor is the queried earth's own changed Si.
    branches = ["戌", "申", "子", "寅", "午", "辰"]
    elements = ["土", "金", "水", "木", "火", "土"]
    lines = [
        dict(position=p, branch=b, element=e, change=True)
        for p, (b, e) in enumerate(zip(branches, elements), 1)
    ]
    previous = [5, 1, 2, 3, 4, None]
    assessed = []
    for p, source in enumerate(previous, 1):
        supports = (
            []
            if source is None
            else [
                dict(
                    location="visible",
                    position=source,
                    branch=branches[source - 1],
                    benefit_now=True,
                    source_grounded=True,
                )
            ]
        )
        if p == 1:
            supports.append(
                dict(
                    location="changed",
                    position=1,
                    branch="巳",
                    back_generation_condition=True,
                )
            )
        assessed.append(dict(strength=dict(supports=supports, oppositions=[])))
    return lines, [{} for _ in lines], {"lines": assessed}


def test_qualified_support_cycle_does_not_become_an_independent_anchor():
    lines, conditions, assessed = dependency_cycle()
    assert _independent_sources(1, lines, conditions, assessed) == {}


def test_independent_calendar_anchor_can_support_a_multi_step_path():
    lines, conditions, assessed = dependency_cycle()
    assessed["lines"][2]["strength"]["supports"].append(
        dict(location="month", position=None, branch="子", reason="外部月令同类支持")
    )
    proofs = _independent_sources(1, lines, conditions, assessed)
    assert set(proofs) == {3, 4, 5}
    assert proofs[5][0]["anchor"]["location"] == "month"
    assert all(
        step["position"] != 1 and step.get("source_position") != 1
        for proof in proofs.values()
        for step in proof
    )


def test_another_earth_changed_si_is_not_a_new_independent_anchor():
    lines, conditions, assessed = dependency_cycle()
    assessed["lines"][5]["strength"]["supports"].append(
        dict(
            location="changed", position=6, branch="巳", back_generation_condition=True
        )
    )
    assert _independent_sources(1, lines, conditions, assessed) == {}
