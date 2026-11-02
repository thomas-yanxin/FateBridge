"""All printed leader rows are retained, including source-rule disagreements."""

import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.qimen import (
    _render_qimen_source_disagreements,
)
from fatebridge.validation.qimen import audit_numeric_tables
from tests.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parent / "fixtures/qimen_classical_v3"
MANIFEST = json.loads((BUNDLE / "sources-and-tables.json").read_text())


def test_complete_eighteen_tables_preserve_all_1080_rows_and_both_disagreements():
    report = audit_numeric_tables(BUNDLE)
    assert report["table_count"] == 18
    assert report["case_count"] == 1080
    assert report["numeric_palace_observation_count"] == 2160
    assert report["leader_heading_pairs"] == 108
    assert report["matched_case_count"] == 1078
    assert sum(r["case_count"] for r in report["tables"]) == 1080
    assert report["disagreements"] == [
        {
            "dun": "阴遁",
            "ju": 9,
            "hour": "庚辰",
            "table_scan_page": 67,
            "table_half": "upper",
            "column_xun": "甲戌",
            "field": "raw_door_gong",
            "expected": "1",
            "actual": "2",
        },
        {
            "dun": "阴遁",
            "ju": 4,
            "hour": "癸亥",
            "table_scan_page": 69,
            "table_half": "lower",
            "column_xun": "甲寅",
            "field": "raw_door_gong",
            "expected": "9",
            "actual": "8",
        },
    ]
    assert report["status"] == "incomplete_with_disagreements"
    assert not report["whole_book_conformance_established"]
    assert not report["whole_board_conformance_established"]
    cross = report["cross_digital_file_collation"]
    assert len(cross["cases"]) == 2
    assert not cross["independent_digital_lineage_established"]
    assert (
        report["case_count"] == 1080
    )  # Cross-copy readings do not inflate the cohort.


@pytest.mark.parametrize("deletion", ["table", "column", "hour", "duplicate"])
def test_audit_refuses_reduced_or_duplicated_reference_coverage(tmp_path, deletion):
    shutil.copytree(BUNDLE, tmp_path / "reference")
    path = tmp_path / "reference/sources-and-tables.json"
    data = json.loads(path.read_text())
    if deletion == "table":
        data["tables"].pop()
    elif deletion == "column":
        data["tables"][0]["palace_pairs"].pop()
    elif deletion == "hour":
        data["tables"][0]["palace_pairs"][0] = "11"
    else:
        data["tables"][0] = data["tables"][1]
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="十八局|六旬|十时"):
        audit_numeric_tables(tmp_path / "reference")


@pytest.mark.parametrize(
    "filename", [MANIFEST["excerpt_file"], "cadal-06056497-p118.jpg"]
)
def test_audit_refuses_changed_source_even_if_numeric_annotations_still_match(
    tmp_path, filename
):
    shutil.copytree(BUNDLE, tmp_path / "reference")
    source = tmp_path / "reference" / filename
    source.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="指纹"):
        audit_numeric_tables(tmp_path / "reference")


@pytest.mark.parametrize(
    "ju,hour,case_id,expected,computed",
    [
        (9, "庚辰", "vol4-yin9-gengchen-door", "坎", "坤"),
        (4, "癸亥", "vol4-yin4-guihai-door", "离", "艮"),
    ],
)
def test_live_board_retains_printed_palace_without_overriding_calculation(
    monkeypatch, ju, hour, case_id, expected, computed
):
    board = fixed_board(monkeypatch, {"dun": "阴遁", "ju": ju, "hour": hour})
    d = board["source_disagreements"][0]
    assert d["case_id"] == case_id
    assert (d["source_value"], d["computed_value"]) == (expected, computed)
    assert board["rule_trace"][0]["outputs"]["raw_door_gong"] == computed
    lines = _render_qimen_source_disagreements(board)
    assert f"原文{expected}，本盘{computed}" in lines[0]
    assert "不判已符合原典" in lines[0]


def test_vol4_yin3_table_supports_leader_move_without_erasing_vol2_door_conflict(
    monkeypatch,
):
    table = next(t for t in MANIFEST["tables"] if t["dun"] == "阴遁" and t["ju"] == 3)
    # Printed column 甲申, ninth hour 壬辰: star 8 / door 2, BEFORE centre hosting.
    assert table["palace_pairs"][2].split()[8] == "82"
    assert table["leader_door_codes"][2] == "休"
    board = fixed_board(monkeypatch, {"dun": "阴遁", "ju": 3, "hour": "壬辰"})
    leader = board["rule_trace"][0]["outputs"]
    assert (leader["raw_star_gong"], leader["raw_door_gong"]) == ("艮", "坤")
    li = next(p for p in board["palaces"] if p["trigram"] == "离")
    assert li["door"] == "开门"
    assert board["source_disagreements"][0]["source_value"] == "杜门"
    assert board["source_disagreements"][0]["supporting_source"]["raw_door_palace"] == 2
    de_shi = next(p for p in board["patterns"] if p["name"] == "三奇得使")
    assert (
        board["source_disagreements"] == de_shi["qualification"]["source_disagreements"]
    )


def test_centre_five_stays_raw_five_in_the_reference():
    table = next(t for t in MANIFEST["tables"] if t["dun"] == "阳遁" and t["ju"] == 1)
    assert table["palace_pairs"][4].split()[0] == "55"  # 甲辰, 天禽/死门.
    assert table["leader_star_codes"][4] == "禽"
