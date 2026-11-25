"""Independent literal tables, executed bureau predicates and explicit variants."""

import gzip
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from fatebridge.core.bazi.bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.bazi.bazi_evidence import cross_chart_relations

DATA = Path(__file__).resolve().parents[1] / "data/bazi_branch_facts_v1"
ORDER = ("year", "month", "day", "hour")


@pytest.fixture(scope="module")
def reference():
    raw = gzip.decompress((DATA / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (DATA / "reference.json.sha256").read_text().strip()
    )
    return json.loads(raw), json.loads((DATA / "convention.json").read_text())


def test_all20736_assignments_match_original_literal_bureaus_and_relation_tables(
    reference,
) -> None:
    external, convention = reference
    assert len(external["cases"]) == 12**4
    for case in external["cases"]:
        branches = case["branches"]
        present = set(branches)
        pillars = dict(zip(ORDER, zip("甲乙丙丁", branches)))
        harmony = check_harmony_patterns(pillars)
        clash = check_clash_patterns(pillars)
        full = set(case["distinct"]["three"])
        assert {"".join(r["branches"]) for r in harmony["three_harmony"]} == full
        assert all(
            r["formation_status"] == "not_adjudicated" and r["complete"] is True
            for r in harmony["three_harmony"]
        )
        expected_halves = {
            frozenset(pair)
            for pair, group in convention["selected_half_pairs"].items()
            if set(pair) <= present and group not in full
        }
        assert {
            frozenset(r["branches"]) for r in harmony["half_harmony"]
        } == expected_halves
        assert all(
            r["formation_status"] == "not_adjudicated" and r["complete"] is False
            for r in harmony["half_harmony"]
        )
        assert {frozenset(pair) for pair in harmony["six_harmony"]} == {
            frozenset(pair) for pair in external["six_harmony"] if set(pair) <= present
        }
        for key, attribute in [("six_clash", "冲"), ("six_harm", "害")]:
            assert {frozenset(pair) for pair in clash[key]} == {
                frozenset((a, external["branch_attributes"][a][attribute]))
                for a in present
                if external["branch_attributes"][a][attribute] in present
            }
        expected_edges = {
            (a, external["branch_attributes"][a]["刑"])
            for a in present
            if external["branch_attributes"][a]["刑"] in present
            and (external["branch_attributes"][a]["刑"] != a or branches.count(a) >= 2)
        }
        assert {
            (edge["from_branch"], edge["to_branch"])
            for punishment in clash["punishments"]
            for edge in punishment["directed_edges"]
        } == expected_edges
        assert all(
            r["effect_status"] == "not_adjudicated" for r in clash["punishments"]
        )
        for result in [harmony, clash]:
            assert {
                (branch, tuple(positions))
                for branch, positions in result["branch_positions"].items()
            } == {
                (
                    branch,
                    tuple(
                        ORDER[i] for i, value in enumerate(branches) if value == branch
                    ),
                )
                for branch in present
            }


def test_all144_ordered_cross_pairs_keep_exact_nominal_terms_and_peak_eligibility(
    reference,
) -> None:
    external, convention = reference
    half_pairs = {frozenset(pair) for pair in convention["selected_half_pairs"]}
    six_pairs = {frozenset(pair) for pair in external["six_harmony"]}
    for a, b in itertools.product(external["branches"], repeat=2):
        first = {p: ("甲", a) for p in ORDER}
        second = {p: ("庚", b) for p in ORDER}
        result = cross_chart_relations(first, second)
        pair = frozenset((a, b))
        harmonious = pair in six_pairs
        half = pair in half_pairs
        opposed = external["branch_attributes"][a]["冲"] == b
        harmed = external["branch_attributes"][a]["害"] == b
        for kind, present in (
            ("六合", harmonious),
            ("六冲", opposed),
            ("六害", harmed),
        ):
            assert sum(row["kind"] == kind for row in result["pairs"]) == 16 * present
        assert any(row["kind"] == "半合" for row in result["groups"]) is half
        target = external["branch_attributes"][a]["刑"]
        assert sum(
            row["source"].startswith("person1.")
            for row in result["directional_punishments"]
        ) == 16 * (target == b and a != b)


def test_all3796_representable_union_sets_apply_the_same_convention_to_merged_events(
    reference,
) -> None:
    external, convention = reference
    count = 0
    for size in range(1, 9):
        for members in itertools.combinations(external["branches"], size):
            count += 1
            present = set(members)
            assigned = list(members) + [members[-1]] * (8 - size)
            first = dict(zip(ORDER, zip("甲乙丙丁", assigned[:4])))
            second = dict(zip(ORDER, zip("戊己庚辛", assigned[4:])))
            result = cross_chart_relations(first, second)
            full = {
                group for group in external["triple_groups"] if set(group) <= present
            }
            halves = {
                frozenset(pair)
                for pair, group in convention["selected_half_pairs"].items()
                if set(pair) <= present and group not in full
            }
            assert {
                "".join(r["branches"]) for r in result["groups"] if r["kind"] == "三合"
            } == full
            assert {
                frozenset(r["branches"])
                for r in result["groups"]
                if r["kind"] == "半合"
            } == halves
    assert count == 3796


def test_external_virtual_member_variant_and_all12_half_table_are_retained(
    reference,
) -> None:
    external, convention = reference
    assert len(external["half_pairs_all_twelve"]) == 12
    assert len(convention["selected_half_pairs"]) == 8
    assert len(convention["arch_end_pairs"]) == 4
    case = next(row for row in external["cases"] if row["branches"] == "寅寅戌戌")
    assert "寅午戌" not in case["distinct"]["three"]
    assert "寅午戌" in case["same"]["three"] and "午" in case["same"]["gongs"]
    actual = check_harmony_patterns(dict(zip(ORDER, zip("甲甲甲甲", case["branches"]))))
    assert actual["three_harmony"] == actual["half_harmony"] == []
    assert external["same_stem_additional_reported_triples"] == 2816


def test_primary_name_variants_do_not_reverse_the_directed_chain() -> None:
    first = check_clash_patterns(dict(zip(ORDER, zip("甲乙丙丁", "寅巳申辰"))))
    full = next(r for r in first["punishments"] if r["type"] == "three_punishment")
    assert full["name"] == "无恩之刑"
    assert full["group_name_variants"] == ["无恩之刑", "恃势之刑"]
    assert full["directed_edges"] == [
        {"from_branch": "寅", "to_branch": "巳"},
        {"from_branch": "巳", "to_branch": "申"},
        {"from_branch": "申", "to_branch": "寅"},
    ]
    second = check_clash_patterns(dict(zip(ORDER, zip("甲乙丙丁", "丑戌未辰"))))
    full = next(r for r in second["punishments"] if r["type"] == "three_punishment")
    assert full["name"] == "恃势之刑"
    assert full["group_name_variants"] == ["恃势之刑", "无恩之刑"]
