"""Pinned external predicates and primary-text facts, not formed-chart labels."""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from fatebridge.core.bazi.bazi_pattern_facts import (
    analyze_special_patterns,
    check_hidden_patterns,
)

DATA = Path(__file__).resolve().parents[1] / "data/bazi_pattern_facts_v1"
POSITIONS = ("year", "month", "day", "hour")


@pytest.fixture(scope="module")
def reference():
    raw = gzip.decompress((DATA / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (DATA / "reference.json.sha256").read_text().strip()
    )
    value = json.loads(raw)
    assert value["primary"] == json.loads((DATA / "source-rules.json").read_text())
    return value


def test_all_branch_assignments_match_independent_hidden_pairs_and_arch_predicate(
    reference,
) -> None:
    assert len(reference["arch_cases"]) == 12**4
    elements = {
        frozenset(pair): element
        for pair, element in reference["primary"][
            "stem_combination_candidate_elements"
        ].items()
    }
    for case in reference["arch_cases"]:
        branches = case["branches"]
        pillars = dict(zip(POSITIONS, zip("甲丙戊庚", branches)))
        actual = check_hidden_patterns(pillars)
        expected = []
        for i, j in itertools.combinations(range(4), 2):
            pairs = reference["hidden_pair_matrix"][branches[i] + branches[j]]
            if pairs:
                expected.append(
                    {
                        "pillars": [POSITIONS[i], POSITIONS[j]],
                        "branches": [branches[i], branches[j]],
                        "stem_pairs": [
                            {
                                **pair,
                                "candidate_element": elements[frozenset(pair["stems"])],
                            }
                            for pair in pairs
                        ],
                    }
                )
            else:
                pass
        assert actual["hidden_stem_combinations"] == expected
        assert [
            {
                "positions": [POSITIONS.index(name) for name in row["pillars"]],
                "group_kind": row["group_kind"],
                "arched": row["arched"],
            }
            for row in actual["arch_combinations"]
        ] == [
            {key: value for key, value in row.items() if key != "reference_output"}
            for row in case["arch"]
        ]
        for row in actual["arch_combinations"]:
            assert row["arched"] not in branches
            assert row["formation_status"] == "not_adjudicated"
            assert row["visible_element_stems"] == [
                {"pillar": name, "stem": pillars[name][0]}
                for name in POSITIONS
                if reference["stem_elements"][pillars[name][0]]
                == row["candidate_element"]
            ]


def test_all_branch_categories_match_primary_memberships(reference) -> None:
    for case in reference["arch_cases"]:
        branches = case["branches"]
        pillars = dict(zip(POSITIONS, zip("甲丙戊庚", branches)))
        actual = analyze_special_patterns(pillars)
        for label, members in reference["primary"]["branch_groups"].items():
            positions = [
                name for name, branch in zip(POSITIONS, branches) if branch in members
            ]
            group = actual["branch_groups"][label]
            assert group["pillars"] == positions
            assert group["count"] == len(positions)
            assert group["complete"] == (set(branches) == set(members))
            assert group["all_pillars"] == (len(positions) == 4)
            assert all(
                actual["branch_attributes"][name]["type"] == label for name in positions
            )


def test_visible_element_facts_keep_each_stem_and_position(reference) -> None:
    # The exhaustive branch queue uses four fixed stems; add both polarities
    # of every element, including the water stems absent from that queue.
    for stem, position in itertools.product(reference["stems"], POSITIONS):
        pillars = {
            "year": ("甲", "申"),
            "month": ("甲", "辰"),
            "day": ("甲", "午"),
            "hour": ("甲", "丑"),
        }
        pillars[position] = (stem, pillars[position][1])
        actual = check_hidden_patterns(pillars)
        row = next(
            row
            for row in actual["arch_combinations"]
            if row["pillars"] == ["year", "month"] and row["group_kind"] == "三合"
        )
        assert row["visible_element_stems"] == (
            [{"pillar": position, "stem": stem}]
            if reference["stem_elements"][stem] == "水"
            else []
        )


def test_all_day_clock_references_keep_day_list_separate_from_actual_lighting(
    reference,
) -> None:
    for index, hour in itertools.product(range(60), [None, *range(24)]):
        day = reference["stems"][index % 10] + reference["branches"][index % 12]
        pillars = {
            "year": ("甲", "子"),
            "month": ("丙", "寅"),
            "day": (day[0], day[1]),
            "hour": ("庚", "申"),
        }
        actual = analyze_special_patterns(pillars, hour)
        required = reference["primary"]["noble_days"].get(day)
        assert actual["noble_day"] == (required is not None)
        assert actual["kui_gang"] == (day in reference["primary"]["kui_gang_days"])
        info = actual["noble_day_reference"]
        assert info["required_lighting"] == required
        assert info["clock_hour"] == hour
        assert info["actual_lighting_status"] == "not_adjudicated"
        assert info["formation_status"] == (
            "not_adjudicated" if required else "not_applicable"
        )
        assert "noble_day_type" not in actual
        if hour is None or required is None:
            assert info["clock_matches_required"] is None
        else:
            pass


def test_source_day_hour_arch_pairs_and_all_year_month_fillings(reference) -> None:
    pairs = {
        (row["day"], row["hour"]): row for row in reference["primary"]["arch_lu_gui"]
    }
    assert len(pairs) == 10
    for day_index, hour_index in itertools.product(range(60), repeat=2):
        day = reference["stems"][day_index % 10] + reference["branches"][day_index % 12]
        hour = (
            reference["stems"][hour_index % 10] + reference["branches"][hour_index % 12]
        )
        pillars = {
            "year": ("甲", "子"),
            "month": ("丙", "寅"),
            "day": (day[0], day[1]),
            "hour": (hour[0], hour[1]),
        }
        actual = check_hidden_patterns(pillars)["arch_lu_gui"]
        assert bool(actual) == ((day, hour) in pairs)
    for (day, hour), rule in pairs.items():
        for year, month in itertools.product(reference["branches"], repeat=2):
            pillars = {
                "year": ("甲", year),
                "month": ("丙", month),
                "day": (day[0], day[1]),
                "hour": (hour[0], hour[1]),
            }
            actual = check_hidden_patterns(pillars)["arch_lu_gui"]
            assert len(actual) == 1
            row = actual[0]
            assert row["kind"] == rule["kind"]
            assert row["arched"] == rule["target"]
            assert row["target_present_at"] == [
                name for name in POSITIONS if pillars[name][1] == rule["target"]
            ]
            assert row["status"] == (
                "excluded_by_filled_target"
                if rule["target"] in (year, month)
                else "not_adjudicated"
            )


def test_labeled_clock_reference_preserves_the_frozen_legacy_computation() -> None:
    for row in json.loads((DATA / "legacy-clock.json").read_text())["cases"]:
        day = row["day"]
        pillars = {
            "year": ("甲", "子"),
            "month": ("丙", "寅"),
            "day": (day[0], day[1]),
            "hour": ("庚", "申"),
        }
        actual = analyze_special_patterns(pillars, row["hour"])
        assert actual["noble_day_reference"]["clock_matches_required"] == row["matches"]
        assert (
            actual["noble_day_reference"]["actual_lighting_status"] == "not_adjudicated"
        )


def test_source_lu_pairs_and_visible_stems_do_not_create_transformation(
    reference,
) -> None:
    for a, b, sa, sb in reference["primary"]["lu_stem_pairs"]:
        pillars = {
            "year": ("甲", a),
            "month": ("乙", b),
            "day": ("戊", "戌"),
            "hour": ("庚", "酉"),
        }
        actual = check_hidden_patterns(pillars)
        assert {
            "pillars": ["year", "month"],
            "branches": [a, b],
            "stems": [sa, sb],
            "source_ref": "sanming_siku_branch_relations",
        } in actual["lu_stem_pair_references"]
        assert actual["effect_status"] == "not_adjudicated"

    pillars = {
        "year": ("甲", "寅"),
        "month": ("乙", "辰"),
        "day": ("戊", "卯"),
        "hour": ("庚", "子"),
    }
    actual = check_hidden_patterns(pillars)
    assert not any(row["arched"] == "卯" for row in actual["arch_combinations"])
    # The old hardcoded 子辰 label was unsupported; the actual 戊／癸 fact remains.
    assert any(
        row["pillars"] == ["month", "hour"]
        and any(pair["stems"] == ["戊", "癸"] for pair in row["stem_pairs"])
        for row in actual["hidden_stem_combinations"]
    )
