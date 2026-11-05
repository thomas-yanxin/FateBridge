"""Source-bound head identities, including centre stems and rejected Wu shortcuts."""

import json
import shutil
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.metaphysics import qimen as engine
from fatebridge.core.metaphysics.common import sexagenary_text
from fatebridge.core.qimen_combinations import build_combinations
from fatebridge.validation.qimen import audit_head_dependent_examples
from tests.qimen.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v5"
MANIFEST = json.loads((BUNDLE / "sources-and-cases.json").read_text())
HEAD_RULES = {d["rule_id"] for d in MANIFEST["definitions"]}


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["id"])
def test_six_frozen_source_examples_use_the_actual_palace_and_head(monkeypatch, case):
    b = fixed_board(monkeypatch, case)
    palace = next(p for p in b["palaces"] if p["trigram"] == case["palace"])
    for field, expected in case["observations"].items():
        assert palace[field] == expected
    match = next(
        p
        for p in b["patterns"]
        if p["name"] == case["name"] and p["palace"] == palace["name"]
    )
    assert match["source_scan_pages"]
    if case["rule_id"] in HEAD_RULES:
        binding = match["qualification"]["identity_binding"]
        assert binding["scope"] == "current_hour_xun"
        assert binding["xun_head"] == b["xun_head"]
        assert (
            binding["hidden_stem"] == b["rule_trace"][0]["outputs"]["zhifu_heaven_stem"]
        )
        assert not binding["fixed_wu_substitution_allowed"]
        assert not binding["independent_outcome_evidence"]
        assert not match["qualification"]["outcome_inference_allowed"]


def test_source_audit_does_not_pass_deferred_day_jia_or_whole_book():
    report = audit_head_dependent_examples(BUNDLE)
    assert (report["case_count"], report["matched_case_count"]) == (6, 6)
    assert report["literal_pair_definitions_checked"] == 2
    assert report["disagreements"] == []
    assert report["deferred_unpassed_count"] == 1
    assert report["deferred_source_readings"][0]["day"] == "甲申"
    assert not report["whole_book_conformance_established"]
    assert not report["non_jiazi_source_examples_independently_verified"]
    assert not report["real_world_efficacy_validated"]


def test_non_jiazi_head_is_not_lost_by_a_fixed_wu_shortcut(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "丙子"}, day="甲子")
    assert b["day_xun_head"] == "甲子"
    assert b["xun_head"] == "甲戌"
    bird = next(p for p in b["patterns"] if p["rule_id"] == "flying_bird_enters_cave")
    dragon = next(p for p in b["patterns"] if p["rule_id"] == "dragon_returns_head")
    assert (bird["palace"], bird["facts"]["earth_stem"]) == ("坤二宫", "己")
    assert (dragon["palace"], dragon["facts"]["heaven_stem"]) == ("艮八宫", "己")
    assert dragon["facts"]["door"] == "杜门"
    assert dragon["qualification"]["overall_judgment"] == "requires_whole_board"


def test_bing_wu_pairs_outside_current_xun_do_not_acquire_these_names(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "乙亥"})
    assert b["xun_head"] == "甲戌"
    assert any(
        ("丙" in p["heaven_stems"] and "戊" in p["earth_stems"])
        or ("戊" in p["heaven_stems"] and "丙" in p["earth_stems"])
        for p in b["palaces"]
    )
    assert not any(
        p["rule_id"] in {"flying_bird_enters_cave", "dragon_returns_head"}
        for p in b["patterns"]
    )


def test_hosted_ren_is_in_both_flight_structures_without_becoming_main_stem(
    monkeypatch,
):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "丙午"})
    assert b["zhifu"]["star"] == "天禽"
    by_name = {p["name"]: p for p in b["palaces"]}
    bird = next(p for p in b["patterns"] if p["rule_id"] == "flying_bird_enters_cave")
    dragon = next(p for p in b["patterns"] if p["rule_id"] == "dragon_returns_head")
    assert bird["facts"]["earth_stem"] == "壬"
    assert by_name[bird["palace"]]["earth_stem"] != "壬"
    assert dragon["facts"]["heaven_stem"] == "壬"
    assert by_name[dragon["palace"]]["heaven_stem"] != "壬"
    assert dragon["qualification"]["identity_binding"]["native_raw_trigram"] == "中"


def test_tianqin_flying_palace_uses_hosted_instrument_instead_of_rui_main_stem(
    monkeypatch,
):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 5, "hour": "庚午"})
    assert b["zhifu"]["star"] == "天禽"
    pattern = next(p for p in b["patterns"] if p["rule_id"] == "flying_palace")
    at = next(p for p in b["palaces"] if p["name"] == pattern["palace"])
    assert at["star"] == "天芮" and at["hosted_stars"] == ["天禽"]
    assert at["heaven_stem"] != pattern["facts"]["heaven_stem"] == "戊"
    assert pattern["facts"]["earth_stem"] == "庚"


def test_hidden_palace_is_the_native_head_palace_not_the_moving_god(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 2, "hour": "壬申"})
    pattern = next(p for p in b["patterns"] if p["rule_id"] == "hidden_palace")
    assert pattern["palace"] == "坤二宫"
    assert pattern["palace"] != b["zhifu"]["palace"] == "乾六宫"


def test_favourable_name_cannot_erase_the_same_bing_geng_conflict(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "辛卯"})
    assert b["xun_head"] == "甲申"
    bird = next(p for p in b["patterns"] if p["rule_id"] == "flying_bird_enters_cave")
    assert bird["facts"]["earth_stem"] == "庚"
    assert "荧入太白" in bird["qualification"]["same_palace_conflicts"]
    at = [p for p in b["patterns"] if p["palace"] == bird["palace"]]
    assert any(p["name"] == "荧入太白" for p in at)
    de_shi = next(p for p in at if p["name"] == "三奇得使")
    assert not de_shi["qualification"]["condition_observed"]
    assert bird["qualification"]["overall_judgment"] == "requires_whole_board"


@pytest.mark.parametrize("dun,ju", list(product(["阳遁", "阴遁"], range(1, 10))))
def test_head_pattern_identity_and_uniqueness_across_1080_structural_boards(dun, ju):
    text = f'{dun}{"一二三四五六七八九"[ju-1]}局上元'
    for i in range(60):
        hour = sexagenary_text(i)
        leader = engine._qimen_zhifu_zhishi(hour, text, dun_type=dun)
        palaces = engine._qimen_build_palaces(
            time_ganzhi=hour, ju_text=text, dun_type=dun, current_term="冬至"
        )
        patterns = build_combinations(
            {"palaces": palaces, "time_ganzhi": hour},
            leader=leader,
            source="source",
            existing_patterns=[],
        )
        for rule_id in HEAD_RULES:
            matches = [p for p in patterns if p["rule_id"] == rule_id]
            assert len(matches) <= 1
            for pattern in matches:
                palace = next(p for p in palaces if p["name"] == pattern["palace"])
                binding = pattern["qualification"]["identity_binding"]
                assert pattern["facts"]["heaven_stem"] in palace["heaven_stems"]
                assert pattern["facts"]["earth_stem"] in palace["earth_stems"]
                if rule_id in {"flying_bird_enters_cave", "hidden_palace"}:
                    assert palace["trigram"] == binding["native_host_trigram"]
                    assert pattern["facts"]["earth_stem"] == leader["zhifu_heaven_stem"]
                else:
                    assert palace["trigram"] == leader["star_gong"]
                    assert (
                        pattern["facts"]["heaven_stem"] == leader["zhifu_heaven_stem"]
                    )


@pytest.mark.parametrize("change", ["source", "case", "duplicate", "deferred"])
def test_audit_refuses_changed_source_deleted_case_and_hidden_deferred_scope(
    tmp_path, change
):
    shutil.copytree(BUNDLE, tmp_path / "qimen_classical_v5")
    shutil.copytree(
        BUNDLE.parent / "qimen_classical_v2", tmp_path / "qimen_classical_v2"
    )
    root = tmp_path / "qimen_classical_v5"
    path = root / "sources-and-cases.json"
    data = json.loads(path.read_text())
    if change == "source":
        source = root / data["excerpt_file"]
        source.write_bytes(source.read_bytes() + b"changed")
    elif change == "case":
        data["cases"].pop()
    elif change == "duplicate":
        data["cases"][0] = data["cases"][1]
    else:
        data["deferred_source_readings"] = []
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹|六例|日甲"):
        audit_head_dependent_examples(root)
