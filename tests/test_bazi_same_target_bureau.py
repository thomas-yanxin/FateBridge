"""Source-supported complete formations, with unchanged competing-pair controls."""

import itertools
import math
from fractions import Fraction

import pytest

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.complete_bureaus import complete_bureau_snapshot_lines
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from tests.bazi_formation_reference import (
    BRANCHES,
    FULL,
    ORDER,
    PAIRS,
    affiliations,
)
from tests.bazi_strength_reference_v3 import assert_current_assessment_arithmetic
from tests.test_strength_v2 import pillars

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
    assert result["method_id"] == "season_root_revelation_relations_v12"
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
    current = ElementAnalysis.analyze_day_master_strength(chart)["assessment"]
    assert current["punishment_resolution_policy"] == (
        "completed_combination_unique_pair_resolution_v2"
    )
    assert affiliations(tuple(chart[position][1] for position in ORDER)) == []
    assert not any(
        row["status"] == "same_target_affiliation_only" for row in current["relations"]
    )
    assert_current_assessment_arithmetic(text.split(), current)


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
