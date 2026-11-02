"""Literal overlapping anti-Huagong and phase-specific positional evidence."""

import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import (
    build_snapshot_text,
    gua_lines,
    judge,
    solar_term,
    solar_term_huagong,
)
from fatebridge.core.heluo_qi import RULESET_ID
from fatebridge.core.output_numerology import HeluoJudge
from tests.test_heluo_worked_depth import REFERENCE as WORKED
from tests.test_heluo_worked_depth import calculate_case

ROOT = Path(__file__).parent / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "qi-reference.json").read_text())
TERMS = [(t, row) for row in REFERENCE["quarter_probes"] for t in row["terms"]]


def source_result(case_id, term):
    case = next(c for c in WORKED["cases"] if c["id"] == case_id)
    p = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
    chart = calculate_case(case)
    return chart, judge(chart, p, p["month"][1], solar_term_huagong(term, False))


@pytest.mark.parametrize("term,expected", TERMS, ids=[t for t, _ in TERMS])
@pytest.mark.parametrize("earth", [False, True])
def test_literal_overlapping_windows_across_all_term_labels(term, expected, earth):
    result = solar_term_huagong(term, earth)
    assert result["hg"] == expected["hg"] + (["坤", "艮"] if earth else [])
    assert result["fh"] == expected["fh"] + (["乾", "兌"] if earth else [])
    if term in REFERENCE["quarter_probes"][1]["terms"]:
        assert result["fanhua_rule_ids"][:2] == ["winter_to_summer_li", "spring_xun"]


def test_literal_clauses_and_frozen_witnesses_do_not_claim_independent_review():
    manifest = json.loads((ROOT / "qi-manifest.json").read_text())
    assert len(manifest["images"]) == 13
    for image in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert len(REFERENCE["direct_fanhua_clauses"]) == 4
    assert REFERENCE["new_original_worked_horoscopes"] == 0
    assert not REFERENCE["independent_second_review_completed"]


@pytest.mark.parametrize(
    "probe", REFERENCE["source_four_pillar_phase_probes"], ids=lambda c: c["case_id"]
)
def test_original_hexagrams_have_separate_direct_and_nuclear_phase_matches(probe):
    _, result = source_result(probe["case_id"], probe["term"])
    qi = result["qi_phases"]
    assert qi["ruleset_id"] == RULESET_ID
    for row in qi["phases"]:
        match = row["matches"]["huagong"]
        assert match["direct_body_ids"] == probe["huagong"][row["phase"] + "_direct"]
        assert match["nuclear_body_ids"] == probe["huagong"][row["phase"] + "_nuclear"]
    transition = next(t for t in qi["transitions"] if t["kind"] == "huagong")
    assert transition["change"] == probe["huagong"]["change"]
    assert qi["birth_instant_utc"] is None
    assert qi["candidate_basis"] == "explicit_candidates_without_birth_instant"
    assert qi["complete_assessment"] is False
    HeluoJudge.model_validate(result)


def test_union_hides_the_loss_and_does_not_verify_the_printed_trigram():
    chart, result = source_result("yihai_bailu", "白露")
    assert result["huagong"]["present"] == ["離"]  # Union alone misses the loss.
    a, b = result["qi_phases"]["phases"]
    assert a["matches"]["huagong"]["present"] is True
    assert b["matches"]["huagong"]["present"] is False
    conflict = REFERENCE["literal_definition_disagreements"][0]
    assert conflict["literal_huagong_trigram"] == "乾"
    assert conflict["definition_huagong_trigrams"] == ["離"]
    assert conflict["literal_huagong_trigram"] not in result["huagong"]["guas"]
    text = build_snapshot_text(chart, result, None)
    assert "先后天合并：" in text and "先天·天水訟" in text and "后天·澤天夬" in text
    assert "下互離" in text and "化工離：无" in text


def test_gained_nuclear_huagong_does_not_become_a_direct_match():
    # Rule-derived from the original Kun initial-six -> Yu example at PDF62.
    p = {"year": "乙未", "month": "丁卯", "day": "甲子", "hour": "乙丑"}
    chart = {
        "xian": {"name": "坤為地", "lines": [0] * 6, "yuan": 1},
        "hou": {"name": "雷地豫", "lines": gua_lines("震", "坤"), "yuan": 4},
        "tian": 25,
        "di": 30,
        "yangLing": True,
    }
    qi = judge(chart, p, "卯", solar_term_huagong("冬至", False))["qi_phases"]
    a, b = qi["phases"]
    assert a["matches"]["huagong"]["present"] is False
    assert b["matches"]["huagong"]["direct_body_ids"] == []
    assert b["matches"]["huagong"]["nuclear_body_ids"] == ["hou.upper_nuclear"]
    assert (
        next(t for t in qi["transitions"] if t["kind"] == "huagong")["change"]
        == "gained"
    )


def test_empty_explicit_targets_never_turn_into_month_branch_candidates():
    chart, original = source_result("yihai_bailu", "白露")
    case = WORKED["cases"][1]
    p = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
    result = judge(chart, p, "卯", {"hg": [], "fh": []})
    assert result["huagong"] == {"guas": [], "present": []}
    for row in result["qi_phases"]["phases"]:
        assert row["matches"]["huagong"]["present"] is None
        assert row["matches"]["fanhua"]["present"] is None
    assert all(
        t["change"] == "not_evaluated"
        for t in result["qi_phases"]["transitions"]
        if t["kind"] in {"huagong", "fanhua"}
    )


@pytest.mark.parametrize(
    "override",
    [
        {},
        {"hg": "離", "fh": []},
        {"hg": ["错"], "fh": []},
        {"hg": [[]], "fh": []},
        {"hg": [], "fh": None},
    ],
)
def test_malformed_explicit_targets_are_not_silently_replaced(override):
    chart, _ = source_result("yihai_bailu", "白露")
    p = dict(zip(("year", "month", "day", "hour"), WORKED["cases"][1]["pillars"]))
    with pytest.raises(ValueError, match="显式化工"):
        judge(chart, p, "卯", override)


def test_phase_evidence_does_not_share_mutable_positions_with_body_evidence():
    _, result = source_result("gengwu_zhao", "處暑")
    original = copy.deepcopy(result["deTi"])
    result["qi_phases"]["phases"][0]["bodies"][0]["line_positions"][0] = 6
    assert result["deTi"] == original
    bad = copy.deepcopy(result)
    bad["qi_phases"]["complete_assessment"] = True
    with pytest.raises(ValidationError):
        HeluoJudge.model_validate(bad)


HKO = json.loads((ROOT.parent / "calendar_hko_v1/reference.json").read_text())
BOUNDARIES = [c for c in HKO["cases"] if c["term"] in {"春分", "夏至", "秋分", "冬至"}]
BEFORE_AFTER = {
    "春分": (["離"], ["離", "巽"]),
    "夏至": (["離", "巽"], ["坎"]),
    "秋分": (["坎"], ["艮"]),
    "冬至": (["艮"], ["離"]),
}


@pytest.mark.parametrize("case", BOUNDARIES, ids=lambda c: f"{c['year']}-{c['term']}")
def test_overlapping_fanhua_has_real_external_before_after_brackets(case):
    at = datetime.fromisoformat(case["at"])
    for delta, expected in zip((-2, 2), BEFORE_AFTER[case["term"]]):
        moment = at + timedelta(minutes=delta)
        result = solar_term(
            moment.year,
            moment.month,
            moment.day,
            "Asia/Hong_Kong",
            birth_datetime=moment,
        )
        assert result["fh"] == expected
