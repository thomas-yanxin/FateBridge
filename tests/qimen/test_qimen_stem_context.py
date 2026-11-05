"""Literal day rules, honest Jia comparisons, and preserved printed conflicts."""

import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.qimen import _qimen_stem_context_lines
from fatebridge.core.metaphysics import qimen as engine
from fatebridge.core.metaphysics.common import sexagenary_text
from fatebridge.core.qimen_stem_context import build_stem_context
from fatebridge.validation.qimen import audit_day_stem_collation
from tests.qimen.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v6"
DAY_RULES = {"hidden_day_stem", "flying_day_stem"}


def test_literal_ji_day_block_matches_the_printed_fourth_palace(monkeypatch):
    board = fixed_board(
        monkeypatch, {"dun": "阴遁", "ju": 5, "hour": "丙寅"}, day="己巳"
    )
    context = board["stem_context"]["day"]
    assert context["status"] == "literal_stem_resolved"
    assert context["effective_stem"] == "己"
    match = next(p for p in board["patterns"] if p["rule_id"] == "hidden_day_stem")
    assert match["palace"] == "巽四宫"
    assert (match["facts"]["heaven_stem"], match["facts"]["earth_stem"]) == ("庚", "己")
    assert match["qualification"]["source_aliases"] == ["日格", "日干格"]
    assert not match["qualification"]["independent_outcome_evidence"]
    assert not any(p["name"] in {"日格", "日干格"} for p in board["patterns"])


def test_actual_ji_day_flying_stem_uses_ji_instead_of_hour_head_wu(monkeypatch):
    board = fixed_board(
        monkeypatch, {"dun": "阳遁", "ju": 5, "hour": "壬申"}, day="己丑"
    )
    match = next(p for p in board["patterns"] if p["rule_id"] == "flying_day_stem")
    assert match["palace"] == "兑七宫"
    assert match["facts"]["heaven_stem"] == "己"
    assert (
        match["qualification"]["stem_identity"]["resolution_policy"]
        == "literal_day_stem"
    )
    assert board["rule_trace"][0]["outputs"]["zhifu_heaven_stem"] == "戊"
    assert (
        match["qualification"]["source_disagreements"][0]["case_id"]
        == "vol2-yang5-renshen-geng-palace"
    )


def test_unresolved_day_jia_keeps_both_candidates_without_selecting_the_match(
    monkeypatch,
):
    board = fixed_board(
        monkeypatch, {"dun": "阳遁", "ju": 5, "hour": "壬申"}, day="甲申"
    )
    day = board["stem_context"]["day"]
    own, hour = day["candidates"]
    assert (own["effective_stem"], hour["effective_stem"]) == ("庚", "戊")
    assert own["candidate_matches"]["hidden_day_stem"] == []
    assert hour["candidate_matches"]["hidden_day_stem"] == ["坤二宫"]
    assert day["status"] == "unresolved_jia_identity"
    assert day["effective_stem"] is None and day["adopted_candidate"] is None
    assert not any(c["adopted"] for c in day["candidates"])
    assert not any(p["rule_id"] in DAY_RULES for p in board["patterns"])
    assert "均未采纳" in _qimen_stem_context_lines(board)[0]
    assert "按日甲" in _qimen_stem_context_lines(board)[0]
    assert "按时旬" in _qimen_stem_context_lines(board)[0]
    diff = board["source_disagreements"][0]
    assert (diff["source_value"], diff["computed_value"]) == ("离", "坤")
    assert diff["supporting_source"]["source_value"] == "坤"


def test_equal_jia_candidates_do_not_certify_their_policy(monkeypatch):
    board = fixed_board(
        monkeypatch, {"dun": "阳遁", "ju": 5, "hour": "壬申"}, day="甲子"
    )
    day = board["stem_context"]["day"]
    assert len(day["candidates"]) == 2
    assert all(c["effective_stem"] == "戊" for c in day["candidates"])
    assert day["status"] == "unresolved_jia_identity"
    assert day["adopted_candidate"] is None


def test_hour_block_alias_does_not_set_whole_board_fuyin(monkeypatch):
    board = fixed_board(
        monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "乙酉"}, day="庚午"
    )
    match = next(p for p in board["patterns"] if p["rule_id"] == "hour_stem_block")
    assert match["facts"]["earth_stem"] == "乙"
    assert match["qualification"]["source_aliases"] == ["伏吟格"]
    assert not board["structure"]["stars_fuyin"]
    assert not board["structure"]["doors_fuyin"]


@pytest.mark.parametrize(
    "dun,number", [(d, n) for d in ["阳遁", "阴遁"] for n in range(1, 10)]
)
def test_source_claim_geng_leader_has_hour_block_in_all_ten_hours(dun, number):
    text = f'{dun}{"一二三四五六七八九"[number-1]}局上元'
    for index in range(20, 30):
        hour = sexagenary_text(index)
        leader = engine._qimen_zhifu_zhishi(hour, text, dun_type=dun)
        assert leader["zhifu_heaven_stem"] == "庚"
        palaces = engine._qimen_build_palaces(
            time_ganzhi=hour, ju_text=text, dun_type=dun, current_term="冬至"
        )
        context, patterns = build_stem_context(
            {"palaces": palaces, "day_ganzhi": "甲子", "time_ganzhi": hour},
            leader=leader,
            source="source",
        )
        matches = [p for p in patterns if p["rule_id"] == "hour_stem_block"]
        assert len(matches) == 1
        at = next(p for p in palaces if p["name"] == matches[0]["palace"])
        assert at["trigram"] == leader["star_gong"]
        assert context["hour"]["effective_stem"] in at["earth_stems"]


def test_source_collation_never_erases_preferred_conflict_or_supporting_variant():
    report = audit_day_stem_collation(BUNDLE)
    assert report["case_count"] == 6
    assert report["matched_observation_count"] == 3
    assert report["unadopted_candidate_reproduction_count"] == 1
    assert report["preferred_source_disagreements"] == [
        {
            "case_id": "vol2-yang5-renshen-geng-palace",
            "field": "heaven_geng_palace",
            "expected": "离",
            "actual": "坤",
        }
    ]
    assert report["supporting_source_disagreements"] == [
        {
            "case_id": "tushu705-shige-yichou-variant",
            "field": "heaven_geng_palace",
            "expected": "震",
            "actual": "兑",
        }
    ]
    assert not report["day_jia_rule_accepted"]
    assert not report["whole_book_conformance_established"]
    assert not report["real_world_efficacy_validated"]


@pytest.mark.parametrize("change", ["source", "case", "reference", "definition"])
def test_audit_refuses_reference_deletions_or_changed_image(tmp_path, change):
    shutil.copytree(BUNDLE, tmp_path / "qimen_classical_v6")
    shutil.copytree(
        BUNDLE.parent / "qimen_classical_v5", tmp_path / "qimen_classical_v5"
    )
    root = tmp_path / "qimen_classical_v6"
    path = root / "sources-and-stems.json"
    data = json.loads(path.read_text())
    if change == "source":
        f = root / "tushu705-p127.jpg"
        f.write_bytes(f.read_bytes() + b"changed")
    elif change == "case":
        data["cases"].pop()
    elif change == "reference":
        data["source_files"].pop()
    else:
        data["literal_definitions"].pop()
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹|六项|影印页|三条"):
        audit_day_stem_collation(root)
