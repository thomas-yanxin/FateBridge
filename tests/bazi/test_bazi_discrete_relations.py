"""Pinned external tables and raw relations, separate from force adjudication."""

import json
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.classical_stages import twelve_life_stage
from fatebridge.core.rules import BaZiRules
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    get_hour_branch,
    get_nayin,
    get_ten_god,
)
from tests.support.transports import SPECS, business, rest, surface_calls

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/bazi_discrete_relations_v1.json").read_text()
)
POSITIONS = ("year", "month", "day", "hour")


@pytest.mark.parametrize(
    "table", ["ten_gods", "nayin", "hidden_stems", "life_stages", "hour_branches"]
)
def test_complete_discrete_tables_equal_pinned_external_reference(table):
    for key, expected in REFERENCE[table].items():
        if table == "ten_gods":
            actual = get_ten_god(*key).value
        elif table == "nayin":
            actual = get_nayin(*key)
        elif table == "hidden_stems":
            actual = BRANCH_HIDDEN_STEMS[key]
        elif table == "life_stages":
            actual = twelve_life_stage(*key)
        else:
            actual = get_hour_branch(int(key))
        assert actual == expected, (table, key, actual, expected)


def test_all_stem_assignments_preserve_pairs_without_claiming_transformation():
    # Synthetic algebraic assignments, not 10,000 valid calendar charts.
    # Candidate elements: 秘本子平真诠 PDF17–18; original scans reviewed.
    candidate_elements = dict(
        zip(
            (frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")),
            "土金水木火",
        )
    )
    for stems in product(REFERENCE["stems"], repeat=4):
        chart = {p: (s, "子") for p, s in zip(POSITIONS, stems)}
        result = BaZiRules.check_stem_patterns(chart)
        assert result["pair_scope"] == "adjacent_visible_stems"
        assert result["transformation_status"] == "not_adjudicated"
        for kind, table in [
            ("combinations", "stem_combinations"),
            ("clashes", "stem_clashes"),
        ]:
            expected = [
                [POSITIONS[i], POSITIONS[i + 1]]
                for i in range(3)
                if REFERENCE[table].get(stems[i]) == stems[i + 1]
            ]
            assert [r["pillars"] for r in result[kind]] == expected
        for combination in result["combinations"]:
            assert (
                combination["candidate_element"]
                == candidate_elements[frozenset(combination["stems"])]
            )
            assert combination["name"] == "".join(combination["stems"]) + "相合"
            assert "transform" not in combination


def test_all_branch_assignments_equal_external_liuhe_liuchong_pairs():
    # Other branch relations and whole-chart effects require their own sources.
    for branches in product(REFERENCE["branches"], repeat=4):
        chart = {p: ("甲", b) for p, b in zip(POSITIONS, branches)}
        harmony = check_harmony_patterns(chart)
        clash = check_clash_patterns(chart)
        for rows, table in [
            (harmony["six_harmony"], "branch_combinations"),
            (clash["six_clash"], "branch_clashes"),
        ]:
            expected = {
                frozenset((a, b))
                for a, b in REFERENCE[table].items()
                if a in branches and b in branches
            }
            assert {frozenset(row) for row in rows} == expected
            assert len(rows) == len(expected)


@pytest.mark.parametrize("year,month,day", [(1984, 5, 10), (1998, 6, 1), (1999, 6, 1)])
def test_raw_combination_and_nayin_facts_across_public_transports(
    year, month, day, surface_calls
):
    payload = dict(
        name="虚构离散规则回归",
        gender="男",
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=8,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        analysis_year=2026,
        analysis_month=11,
        analysis_day=11,
    )
    response, protocol, code, cli = surface_calls(
        SPECS["bazi_birth"],
        payload,
        params={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(cli) == business(protocol.structured_content)
    patterns = result["bazi_birth"]["patterns"]["stems"]
    assert patterns["transformation_status"] == "not_adjudicated"
    if year == 1984:
        assert [c["pillars"] for c in patterns["combinations"]] == [
            ["year", "month"],
            ["month", "day"],
        ]
        assert all(c["candidate_element"] == "土" for c in patterns["combinations"])
        assert all("合化" not in c["name"] for c in patterns["combinations"])
    else:
        assert "城头土" in result["snapshot_text"]
        assert "城墙土" not in json.dumps(result, ensure_ascii=False)
