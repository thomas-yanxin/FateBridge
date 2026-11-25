"""Finite column and pair facts against pinned independent implementations."""

import hashlib
import itertools
import json
from pathlib import Path

import pytest

from fatebridge.core.bazi.bazi_pattern_facts import (
    check_pillar_pair_patterns,
    check_pillar_patterns,
)

POSITIONS = ("year", "month", "day", "hour")
DATA = Path(__file__).resolve().parents[1] / "data/bazi_pillar_facts_v1"


@pytest.fixture(scope="module")
def reference():
    raw = (DATA / "reference.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == (DATA / "reference.json.sha256").read_text().strip()
    )
    return json.loads(raw)


def test_all_120_column_assignments_at_every_position(reference) -> None:
    for position in POSITIONS:
        for literal, expected in reference["column_matrix"].items():
            pillars = dict(zip(POSITIONS, [("甲", "子")] * 4))
            pillars[position] = (literal[0], literal[1])
            # An arbitrary mapping insertion order must not change physical positions.
            result = check_pillar_patterns(dict(reversed(list(pillars.items()))))
            assert [r["pillar"] for r in result["pillars"]] == list(POSITIONS)
            actual = result["pillars"][POSITIONS.index(position)]
            assert actual == {
                "pillar": position,
                "stem": literal[0],
                "branch": literal[1],
                **expected,
            }


def test_all_valid_ordered_pillar_pairs_at_each_of_six_position_pairs(
    reference,
) -> None:
    pairs = list(itertools.combinations(POSITIONS, 2))
    for left, right in pairs:
        for a, b in itertools.product(reference["sexagenary_pillars"], repeat=2):
            pillars = dict(zip(POSITIONS, [("甲", "子")] * 4))
            pillars[left] = (a[0], a[1])
            pillars[right] = (b[0], b[1])
            result = check_pillar_pair_patterns(pillars)
            assert [r["pillars"] for r in result["pairs"]] == [list(p) for p in pairs]
            actual = result["pairs"][pairs.index((left, right))]
            assert actual == {
                "pillars": [left, right],
                "pillar_content": [a, b],
                "identical": a == b,
                "stem_four_clash": reference["stem_four_clash_matrix"][a[0] + b[0]],
                "branch_six_clash": reference["branch_six_clash_matrix"][a[1] + b[1]],
                "stem_relation": reference["stem_relation_matrix"][a[0] + b[0]],
            }


def test_source_counterexamples_keep_principal_hidden_and_clash_definitions_apart() -> (
    None
):
    pillars = dict(
        year=("戊", "子"), month=("壬", "午"), day=("丁", "丑"), hour=("乙", "巳")
    )
    day = check_pillar_patterns(pillars)["pillars"][2]
    assert day["principal_relation"] == "generates"
    assert (
        next(r for r in day["hidden_relations"] if r["stem"] == "辛")["relation"]
        == "controls"
    )
    pair = check_pillar_pair_patterns(pillars)["pairs"][0]
    assert pair["branch_six_clash"] is True and pair["stem_four_clash"] is False
    assert pair["stem_relation"] == "controls"
    pillars["year"] = ("癸", "亥")
    pair = check_pillar_pair_patterns(pillars)["pairs"][2]
    assert pair["pillar_content"] == ["癸亥", "乙巳"]
    assert pair["branch_six_clash"] is True and pair["stem_four_clash"] is False
    assert pair["stem_relation"] == "generates"
