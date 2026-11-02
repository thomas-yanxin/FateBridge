"""Conjunctive rules, retained source exceptions and frozen scan observations."""

import json
from pathlib import Path

import pytest

from fatebridge.validation.qimen import audit_scan_examples
from tests.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parent / "fixtures/qimen_classical_v2"
SCAN = json.loads((BUNDLE / "sources-and-cases.json").read_text())


def patterns(board, name):
    return [p for p in board["patterns"] if p["name"] == name]


@pytest.mark.parametrize("case", SCAN["cases"], ids=lambda c: c["id"])
def test_scan_observations_keep_the_disagreement_visible(case):
    report = audit_scan_examples(BUNDLE)
    row = next(r for r in report["rows"] if r["id"] == case["id"])
    if case["id"] == "de-shi-yin3-renchen":
        assert row["status"] == "disagreement"
        assert row["discrepancies"] == [
            {
                "trigram": "离",
                "field": "door",
                "expected": "杜门",
                "actual": "开门",
                "mode": "equals",
            }
        ]
        assert report["status"] == "incomplete"
        assert not report["whole_book_conformance_established"]
    else:
        assert row["discrepancies"] == []


@pytest.mark.parametrize("hour", ["庚午", "己卯", "戊子", "丁酉", "丙午", "乙卯"])
def test_jade_gate_reads_actual_value_door_and_earth_ding(monkeypatch, hour):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": hour})
    p = patterns(b, "玉女守门")
    assert len(p) == 1 and p[0]["palace"] == "兑七宫"
    assert p[0]["facts"]["door"] == b["zhishi"]["door"]
    at = next(r for r in b["palaces"] if r["name"] == p[0]["palace"])
    assert "丁" in at["earth_stems"]
    assert p[0]["qualification"]["outcome_inference_allowed"] is False


def test_arbitrary_door_or_heaven_ding_is_not_jade_gate(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "丁卯"})
    assert any(
        "丁" in p["heaven_stems"] or "丁" in p["earth_stems"] for p in b["palaces"]
    )
    assert not patterns(b, "玉女守门")


def test_de_shi_does_not_erase_adverse_pair_or_required_condition(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 9, "hour": "庚午"})
    de = next(
        p
        for p in patterns(b, "三奇得使")
        if p["facts"]["heaven_stem"] == "乙" and p["facts"]["earth_stem"] == "辛"
    )
    assert de["palace"] == "震三宫"
    assert de["qualification"]["same_palace_conflicts"] == ["青龙逃走"]
    assert de["qualification"]["same_xun_leader_required"]
    assert not de["qualification"]["condition_observed"]
    assert any(p["palace"] == de["palace"] for p in patterns(b, "青龙逃走"))


def test_same_xun_leader_exception_is_observed_from_its_real_hosted_palace(monkeypatch):
    # 阳三局，甲申庚在中，天禽寄地乙于坤；辛卯随时干至乾，
    # 乙与寄庚同到地辛宫，乙辛得使/逃走结构与本旬天禽同宫。
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 3, "hour": "辛卯"})
    de = next(
        p
        for p in patterns(b, "三奇得使")
        if p["facts"]["heaven_stem"] == "乙" and p["facts"]["earth_stem"] == "辛"
    )
    assert de["palace"] == b["zhifu"]["palace"] == "乾六宫"
    assert b["zhifu"]["star"] == "天禽"
    assert de["qualification"]["condition_observed"]
    assert de["qualification"]["same_palace_conflicts"] == ["青龙逃走"]
    assert de["qualification"]["overall_judgment"] == "requires_whole_board"


@pytest.mark.parametrize(
    "ju,hour,name,palace",
    [
        (4, "乙酉", "天遁", "坎一宫"),
        (-6, "庚申", "天遁", "离九宫"),
        (1, "辛卯", "地遁", "坤二宫"),
        (-9, "丙寅", "地遁", "艮八宫"),
        (7, "丙子", "人遁", "乾六宫"),
    ],
)
def test_three_dun_structures_match_the_selected_scan_examples(
    monkeypatch, ju, hour, name, palace
):
    b = fixed_board(
        monkeypatch, {"dun": "阳遁" if ju > 0 else "阴遁", "ju": abs(ju), "hour": hour}
    )
    assert any(p["palace"] == palace for p in patterns(b, name))


def test_heaven_dun_example_does_not_hide_its_door_pressure(monkeypatch):
    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 4, "hour": "乙酉"})
    p = next(p for p in patterns(b, "天遁") if p["palace"] == "坎一宫")
    assert p["qualification"]["blocking_rule_names"] == ["门迫"]
    assert not p["qualification"]["condition_observed"]
    assert p["qualification"]["outcome_inference_allowed"] is False


def test_corrupt_frozen_scan_cannot_be_used_as_verified_reference(tmp_path):
    (tmp_path / "sources-and-cases.json").write_text(json.dumps(SCAN))
    (tmp_path / SCAN["scan"]["excerpt_file"]).write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="指纹"):
        audit_scan_examples(tmp_path)


def test_scan_case_ledger_cannot_be_reduced_to_only_matching_examples():
    report = audit_scan_examples(BUNDLE)
    assert report["case_count"] == 19
    assert report["matched_case_count"] == 18
    assert report["disagreements"] == [
        {
            "case_id": "de-shi-yin3-renchen",
            "trigram": "离",
            "field": "door",
            "expected": "杜门",
            "actual": "开门",
            "mode": "equals",
        }
    ]
    assert report["status"] == "incomplete"


def test_snapshot_keeps_the_adverse_pair_and_unmet_condition(monkeypatch):
    from fatebridge.core.local_techniques.qimen import _render_qimen_pattern_line

    b = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 9, "hour": "庚午"})
    p = next(p for p in patterns(b, "三奇得使") if p["facts"]["heaven_stem"] == "乙")
    line = _render_qimen_pattern_line(p)
    assert "未满足" in line and "青龙逃走" in line and "本旬值符同临" in line
    assert "仍须合看全局" in line


def test_known_source_door_disagreement_stays_in_pattern_and_snapshot(monkeypatch):
    from fatebridge.core.local_techniques.qimen import _render_qimen_pattern_line

    b = fixed_board(monkeypatch, {"dun": "阴遁", "ju": 3, "hour": "壬辰"})
    p = next(p for p in patterns(b, "三奇得使") if p["palace"] == "离九宫")
    assert p["facts"]["door"] == "开门"
    assert p["qualification"]["source_disagreements"][0]["source_value"] == "杜门"
    line = _render_qimen_pattern_line(p)
    assert "原文杜门，本盘开门" in line


def test_provider_provenance_includes_the_next_year_at_late_zi(monkeypatch):
    from datetime import datetime
    from types import SimpleNamespace

    from fatebridge.core import qimen_evidence
    from fatebridge.core.metaphysics import qimen as engine
    from tests.test_qimen_depth import seed

    monkeypatch.setattr(
        engine,
        "_qimen_resolve_zhirun_meta",
        lambda **kwargs: {
            "current_term": "冬至",
            "dun_type": "阳遁",
            "yuan": "上元",
            "ju_number": 1,
        },
    )
    monkeypatch.setattr(
        qimen_evidence,
        "get_solar_terms_for_year",
        lambda year, *args: (
            SimpleNamespace(
                resolution_provider=(
                    "linear_1900_fallback" if year == 2027 else "swisseph"
                )
            ),
        ),
    )
    b = engine.build_qimen_board(seed(moment=datetime(2026, 12, 31, 23)))
    assert 2027 in b["calendar_policy"]["term_grid_years_observed"]
    assert b["calendar_policy"]["precision_status"] == "approximate"
    assert b["calendar_policy"]["solar_term_providers"] == [
        "linear_1900_fallback",
        "swisseph",
    ]


@pytest.mark.parametrize(
    "ju,hour,sky,earth,conflict,at",
    [
        (-6, "丙寅", "丙", "庚", "荧入太白", "巽四宫"),
        (-3, "壬申", "丁", "癸", "朱雀投江", "兑七宫"),
    ],
)
def test_other_two_classical_de_shi_exceptions_keep_the_adverse_match(
    monkeypatch, ju, hour, sky, earth, conflict, at
):
    b = fixed_board(monkeypatch, {"dun": "阴遁", "ju": abs(ju), "hour": hour})
    de = next(
        p
        for p in patterns(b, "三奇得使")
        if p["facts"]["heaven_stem"] == sky and p["facts"]["earth_stem"] == earth
    )
    assert de["palace"] == at
    assert de["qualification"]["same_palace_conflicts"] == [conflict]
    assert de["qualification"]["same_xun_leader_required"]
    assert not de["qualification"]["condition_observed"]
    assert any(p["palace"] == at for p in patterns(b, conflict))


def test_sanshi_snapshot_preserves_qimen_conflict_and_qualification():
    from fatebridge.services.divination import calculate_sanshiunited_analysis
    from fatebridge.services.metaphysics import calculate_qimen_analysis

    aggregate = calculate_sanshiunited_analysis(
        date="2026-01-25",
        time="12:00:00",
        zone="Asia/Hong_Kong",
        lat="31n13",
        lon="121e28",
        use_true_solar_time=False,
    )
    dedicated = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=25,
        analysis_hour=12,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
    )
    assert aggregate["qimen"]["patterns"] == dedicated["qimen"]["patterns"]
    assert "附加条件未满足" in aggregate["snapshot_text"]
    assert "同宫冲突：青龙逃走" in aggregate["snapshot_text"]
    assert aggregate["snapshot_text"] == aggregate["snapshot_export"]["export_text"]
