"""Missing source days leave some construction constraints independently known.

These are symbolic counterfactuals, not recovered historical birthdays. P33
already conflicts at the day-independent month-general layer; P45 has multiple
possible day stems. Neither observation selects a day or changes 46/16/2.
"""

import json
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from scripts.ren.audit_jinkou_construction_diagnosis import audit, reference
from scripts.ren.audit_ren_classical import make_seed

SOURCE = Path(__file__).parents[1] / "fixtures/jinkou_patterns_v1/cases.json"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = tuple(STEMS[i % 10] + BRANCHES[i % 12] for i in range(60))

# Read from the original rows; arithmetic below is hand-derived from the
# literal monthly general, hour and ground. No production number is an oracle.
CASES = (
    {
        "id": "P33",
        "day": None,
        "hour": "酉",
        "lunar_month": 12,
        "positions": ["戊", "勾陈", "卯", "寅"],
        "month_general": "子",
        "derived_general": "巳",  # 子 + 寅 - 酉 = 巳 (mod twelve).
        "human_day_stems": {"乙", "庚"},
        "full_default_candidates": set(),
    },
    {
        "id": "P45",
        "day": None,
        "hour": "申",
        "lunar_month": 4,
        "positions": ["壬", "六合", "寅", "寅"],
        "month_general": "申",
        "derived_general": "寅",  # 申 + 寅 - 申 = 寅.
        "human_day_stems": {"丁", "壬"},
        "full_default_candidates": {
            "丁丑",
            "丁卯",
            "丁巳",
            "丁未",
            "丁酉",
            "丁亥",
            "壬子",
            "壬寅",
            "壬辰",
            "壬午",
            "壬申",
            "壬戌",
        },
    },
)


@pytest.mark.parametrize("expected", CASES, ids=lambda c: c["id"])
def test_missing_day_still_has_strict_partial_constraints(expected):
    # This verifies the existing source pins, including the original images,
    # without replacing either source day's frozen None.
    reference()
    originals = json.loads(SOURCE.read_text())["cases"]
    assert len(originals) == 64
    original = next(row for row in originals if row["id"] == expected["id"])
    for field in ("day", "hour", "lunar_month", "positions"):
        assert original[field] == expected[field]

    observed_general = set()
    human_day_stems = set()
    full_candidates = {"default": set(), "day": set(), "night": set()}
    for day in CYCLE:
        # The seed supplies only symbolic pillars. Its internal date is never
        # used as evidence for the unknown original date or lunar month.
        for mode, explicit in (("default", None), ("day", True), ("night", False)):
            board = build_jinkou_board(
                make_seed({"day": day, "hour": original["hour"]}),
                {"month_general": {"branch": expected["month_general"]}},
                di_fen=original["positions"][3],
                is_diurnal_override=explicit,
            )
            human = board["rows"][0]["content"]
            general = board["rows"][2]["content"]
            god = board["overview"]["guishen"]["name"]
            observed_general.add(general)
            if human == original["positions"][0]:
                human_day_stems.add(day[0])
            if [human, god, general, original["positions"][3]] == original["positions"]:
                full_candidates[mode].add(day)
    assert observed_general == {expected["derived_general"]}
    assert human_day_stems == expected["human_day_stems"]
    assert full_candidates == {
        "default": expected["full_default_candidates"],
        "day": expected["full_default_candidates"],
        "night": set(),
    }
    assert original["day"] is None


def test_partial_constraints_do_not_regrade_or_complete_the_original_cohort():
    report = audit()
    assert (
        report["counts"]["original_denominator"],
        report["counts"]["original_matched"],
        report["counts"]["original_not_matched"],
        report["counts"]["missing_days"],
    ) == (64, 46, 16, 2)
    missing = [row for row in report["rows"] if row["original_matched"] is None]
    assert [row["id"] for row in missing] == ["P33", "P45"]
    assert all(row["status"] == "missing_source_day" for row in missing)
    assert report["source_emendations"] == 0
    assert not report["original_classical_acceptance_passed"]
