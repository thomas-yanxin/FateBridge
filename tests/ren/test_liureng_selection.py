"""Independent finite selection fields; complete-source acceptance stays separate."""

import gzip
import json
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.liureng import (
    _liureng_upper_lower_relation,
    derive_selection,
)

REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1]
            / "fixtures/liureng-selection-reference-v1.json.gz"
        ).read_bytes()
    )
)
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def test_reference_retains_the_complete_finite_inputs_and_original_source_identities():
    pairs = REFERENCE["element_relations"]
    states = REFERENCE["selection_cases"]
    assert len(pairs) == len({(row["upper"], row["lower"]) for row in pairs}) == 264
    assert len(states) == len({(row["day"], row["offset"]) for row in states}) == 720
    assert sum(len(row["harm_counts"]) for row in states) == 169
    assert REFERENCE["selection_source"]["commit"] == (
        "2afe9194e3644d2ead5652ed8b366ae6c70d7087"
    )
    assert REFERENCE["element_source"]["source_commit"] == (
        "557a9ad3ced7b0551b4e623a63dc74536a190a7e"
    )


@pytest.mark.parametrize("case", REFERENCE["element_relations"])
def test_all_valid_upper_lower_identities_match_original_external_primitive(case):
    assert (
        _liureng_upper_lower_relation(case["upper"], case["lower"]) == case["relation"]
    )


@pytest.mark.parametrize(
    "case",
    REFERENCE["selection_cases"],
    ids=lambda case: f"{case['day']}-{case['offset']}",
)
def test_selection_lessons_transmissions_and_harm_counts_match_original_kernel(case):
    sky = {
        branch: BRANCHES[(index + case["offset"]) % 12]
        for index, branch in enumerate(BRANCHES)
    }
    actual = derive_selection(case["day"], sky)
    assert actual["branches"] == case["transmissions"]
    assert [
        [
            lesson["upper_branch"],
            case["day"][0] if lesson["index"] == 1 else lesson["lower_branch"],
        ]
        for lesson in actual["four_lessons"]
    ] == case["lessons"]
    paths = [
        candidate
        for trace in actual["rule_trace"]
        if trace["rule_id"] == "liuren.harm_paths"
        for candidate in trace["result"]["candidates"]
    ]
    assert [
        {
            "upper": path["upper_branch"],
            "lower": (
                case["day"][0]
                if path["lesson_index"] == 1
                else actual["four_lessons"][path["lesson_index"] - 1]["lower_branch"]
            ),
            "count": path["harm_count"],
        }
        for path in paths
    ] == case["harm_counts"]
