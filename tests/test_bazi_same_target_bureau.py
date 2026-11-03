"""Source-supported complete formations, with unchanged competing-pair controls."""

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.complete_bureaus import complete_bureau_snapshot_lines
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate, evaluate_strength_policy
from tests.fixtures.bazi_same_target_bureau_v1.reference_geometry import (
    BRANCHES,
    FULL,
    ORDER,
    PAIRS,
    affiliations,
)
from tests.test_strength_v2 import pillars

FIXTURE = Path(__file__).parent / "fixtures/bazi_same_target_bureau_v1"
POSITIVES = [
    ("ZP31-XUAN", "己卯 辛未 壬寅 辛亥", "三合", ["year", "month", "hour"]),
    ("FJ-03", "甲寅 乙亥 乙卯 癸未", "三合", ["month", "day", "hour"]),
    ("FJ-06", "丁卯 甲辰 甲寅 乙亥", "三会", ["year", "month", "day"]),
    ("DTCW1947-MX-02", "癸卯 丙辰 甲寅 乙亥", "三会", ["year", "month", "day"]),
]


@pytest.mark.parametrize("case,text,kind,seats", POSITIVES)
def test_primary_complete_formation_survives_same_target_affiliate(
    case, text, kind, seats
):
    chart = pillars(text)
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    result = strength["assessment"]
    full = next(r for r in result["relations"] if r["kind"] == kind)
    assert full["positions"] == seats
    assert full["status"] in {"binding", "conditioned_transformation"}, case
    (pair,) = [
        r for r in result["relations"] if r["status"] == "same_target_affiliation_only"
    ]
    assert pair["primary_formation"] == {
        "kind": kind,
        "positions": seats,
        "target": "木",
    }
    assert pair["additional_budget"] == 0.0 and pair["calculation_effect"] == "none"
    assert set(pair["outside_positions"]).isdisjoint(seats)
    assert result["method_id"] == "season_root_revelation_relations_v11"
    assert "附合" in "\n".join(complete_bureau_snapshot_lines(result))
    natal = build_natal_evidence(chart, strength)
    BaziEvidenceChain.model_validate(natal)
    passage = natal["classical_passage_relations"]
    assert passage["effective_passage"] == "not_adjudicated"
    assert [r["receipt"] for r in passage["events"]] == result["relations"]
    # The full formation consumes precisely its physical seats once. The extra
    # branch must not be transformed, bound, or made a synthetic physical root.
    for position, budget in result["branch_budgets"].items():
        physical = sum(
            r["remaining_mass"]
            for r in result["hidden_stem_ledger"]
            if r["pillar"] == position
        )
        synthetic = sum(
            r["mass"]
            for r in result["combination_contributions"]
            if r["pillar"] == position
        )
        assert math.isclose(physical + synthetic, budget["remaining"], abs_tol=1e-12)
        assert budget["remaining"] <= budget["initial"] + 1e-12
    exact = result["threshold_arithmetic"]["energies_exact"]
    assert all(
        math.isclose(
            float(Fraction(q)), result["effective_elements_unrounded"][e], abs_tol=1e-12
        )
        for e, q in exact.items()
    )


@pytest.mark.parametrize(
    "text",
    [
        "丁卯 丙寅 辛亥 庚寅",
        "壬寅 辛亥 甲寅 己巳",
        "甲申 乙酉 丙戌 丁辰",
        "甲寅 丙午 戊戌 乙亥",
    ],
)
def test_pair_only_clashing_and_different_target_controls_retain_current_receipts(text):
    chart = pillars(text)
    phases = ElementAnalysis.seasonal_phases(chart["month"][1])
    old = _evaluate(
        chart, phases, DEFAULT_POLICY, stem_effect_mode="precise_binding_only_v1"
    )
    current = evaluate_strength_policy(chart, phases, DEFAULT_POLICY)
    assert current.pop("punishment_resolution_policy") == (
        "completed_combination_unique_pair_resolution_v2"
    )
    assert current == old


def test_all_20736_branch_seatings_against_independent_literal_oracle():
    from fatebridge.core.formation_affiliations import partition_affiliations

    count = matches = 0
    for branches in itertools.product(BRANCHES, repeat=4):
        # Construct the production input independently, including contained pairs
        # to test that the helper itself does not reinterpret them as affiliations.
        candidates = []
        for kind, letters, target in FULL:
            seats = tuple(ORDER[i] for i, b in enumerate(branches) if b in letters)
            if set(branches[ORDER.index(p)] for p in seats) == set(letters):
                candidates.append((kind, seats, target))
        for i in range(3):
            target = PAIRS.get(frozenset(branches[i : i + 2]))
            if target is not None:
                candidates.append(("六合", ORDER[i : i + 2], target))
        full_sets = [set(c[1]) for c in candidates if len(c[1]) >= 3]
        candidates = [
            c
            for c in candidates
            if len(c[1]) >= 3 or not any(set(c[1]) <= s for s in full_sets)
        ]
        active, actual = partition_affiliations(candidates, dict(zip(ORDER, branches)))
        expected = affiliations(branches)
        normalized = [
            (
                tuple(ORDER.index(p) for p in r["positions"]),
                r["primary_formation"]["kind"],
                tuple(ORDER.index(p) for p in r["primary_formation"]["positions"]),
                r["target"],
            )
            for r in actual
        ]
        assert normalized == expected, branches
        assert len(active) + len(actual) == len(candidates)
        assert all(
            r["additional_budget"] == 0 and r["calculation_effect"] == "none"
            for r in actual
        )
        count += 1
        matches += bool(actual)
    assert count == 20736 and matches > 0


def test_legacy_default_and_original_test_gate_remain_explicit():
    chart = pillars("甲寅 丙午 戊戌 乙卯")
    phase = ElementAnalysis.seasonal_phases("午")
    legacy = _evaluate(chart, phase, DEFAULT_POLICY)
    assert (
        next(r for r in legacy["relations"] if r["kind"] == "三合")["status"]
        == "contested_or_clashed"
    )
    current = evaluate_strength_policy(chart, phase, DEFAULT_POLICY)
    assert (
        next(r for r in current["relations"] if r["kind"] == "三合")["status"]
        == "conditioned_transformation"
    )
    assert (
        DEFAULT_POLICY.binding == 0.85
        and DEFAULT_POLICY.transformation_transfer == 0.80
    )
    assert DEFAULT_POLICY.strong_share == 0.60 and DEFAULT_POLICY.weak_share == 0.40


def test_source_plan_and_independent_oracle_were_frozen_before_production_edit():
    import hashlib

    plan = FIXTURE / "source-review-and-adoption-first.json"
    assert (
        hashlib.sha256(plan.read_bytes()).hexdigest()
        == plan.with_suffix(".json.sha256").read_text().strip()
    )
    assert (
        hashlib.sha256((FIXTURE / "reference_geometry.py").read_bytes()).hexdigest()
        == json.loads(plan.read_text())["independent_geometry_sha256"]
    )
