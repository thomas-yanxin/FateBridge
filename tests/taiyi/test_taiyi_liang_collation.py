"""Frozen two-edition source constraints must survive partial numeric agreement."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from scripts.taiyi.audit_taiyi_liang_collation import (
    BOARD_FIELDS,
    CORPUS,
    FREEZE_SHA256,
    ROOT,
    audit,
    compare_board,
    source_position_counts,
    verify_sources,
)


@pytest.fixture(scope="module")
def report():
    return audit()


def test_source_values_were_frozen_before_new_numeric_comparisons():
    frozen = verify_sources()
    assert len(frozen["files"]) == 7
    assert len(frozen["prior_sources"]) == 16
    assert frozen["new_board_comparisons_before_freeze"] == 0
    assert frozen["new_date_or_residue_comparisons_before_freeze"] == 0
    assert not frozen["editions_are_independent_observations"]
    assert frozen["independent_human_reviewers"] == 0
    reading = json.loads((CORPUS / "readings.json").read_text())
    assert reading["case"]["original_day"] == 8
    assert reading["case"]["corrected_day"] == 9
    assert reading["case"]["original_in_cycle"] == 21
    assert reading["case"]["shoushi_in_cycle"] == 22
    assert "二十二日" in reading["transcription"]["shoushi_remainder"]
    assert reading["board"]["shiji"] == "卯"
    assert len(reading["board"]) == len(BOARD_FIELDS) == 10


@pytest.mark.parametrize("update_manifest", [False, True])
def test_cannot_make_disputed_position_pass_by_rewriting_source(
    tmp_path, update_manifest
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "readings.json"
    reading = json.loads(path.read_text())
    reading["board"]["shiji"] = "酉"
    path.write_text(json.dumps(reading))
    if update_manifest:
        frozen = json.loads((corpus / "freeze.json").read_text())
        frozen["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="V31"):
        verify_sources(corpus)


def test_prior_calendar_is_pinned_too(tmp_path):
    prior_root = tmp_path / "root"
    freeze = verify_sources()
    for name in freeze["prior_sources"]:
        target = prior_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    path = prior_root / "tests/fixtures/taiyi_jinjing_v28/liang-504-months.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="liang-504-months"):
        verify_sources(root=prior_root)


def test_full_355_day_calendar_not_replaced_by_one_matching_day(report):
    cohort = report["calendar_cohort"]
    assert cohort["month_first_anchors"] == 13
    assert cohort["complete_months"] == 12
    assert cohort["days"] == len(cohort["records"]) == 355
    assert cohort["mismatches"] == []
    rows = report["xing_date_claims_against_printed_calendar"]
    assert [r["day"] for r in rows] == [1, 8, 9]
    assert [r["day_ganzhi"] for r in rows] == ["丙子", "癸未", "甲申"]
    assert [r["matches_xing_day_label"] for r in rows] == [True, False, True]
    assert rows[1]["gregorian"] == "0504-07-07"
    assert rows[2]["gregorian"] == "0504-07-08"
    tokens = report["jinjing_date_token_evidence"]
    assert tokens["year_token_alone_does_not_supply_a_day"]
    assert tokens["by_edition"]["siku"]["explicit_day_ganzhi"] is None
    assert tokens["by_edition"]["ncl_ming"]["explicit_day_ganzhi"] == "甲申"
    assert tokens["earlier_unqualified_absence_claim_corrected"]
    assert not report["original_jinjing_day8_overwritten"]


def test_matching_counts_do_not_hide_the_differing_upstream_position(report):
    literal = report["all_six_candidate_comparisons"][0]
    board = literal["board"]
    assert literal["accumulation"] == 707501061
    assert literal["division360"] == [1965280, 261]
    assert literal["division60_of_remainder"] == [4, 21]
    assert board["matching_fields"] == 9 and board["required_fields"] == 10
    assert not board["full_board_matches"]
    failures = [r for r in board["observations"] if not r["matches"]]
    assert failures == [
        {"field": "shiji", "source": "卯", "actual": "酉", "matches": False}
    ]
    assert all(
        r["matches"]
        for r in board["observations"]
        if r["field"] in {"main_count", "guest_count"}
    )


@pytest.mark.parametrize("field", BOARD_FIELDS)
def test_cannot_drop_any_of_the_ten_source_fields(field):
    expected = json.loads((CORPUS / "readings.json").read_text())["board"]
    expected.pop(field)
    with pytest.raises(ValueError, match="ten source fields"):
        compare_board(707501061, expected)


def test_all_old_failed_hypotheses_and_plus_one_remain_visible(report):
    rows = report["all_six_candidate_comparisons"]
    assert [r["accumulation"] for r in rows] == [
        707501061,
        707501062,
        707501413,
        707501443,
        707501059,
        707501089,
    ]
    assert [r["board"]["matching_fields"] for r in rows] == [9, 0, 3, 1, 3, 0]
    assert all(r["board"]["required_fields"] == 10 for r in rows)
    assert all(not r["board"]["full_board_matches"] for r in rows)
    assert rows[0]["source_absolute"] is True
    assert all(not r["source_absolute"] for r in rows[1:])
    assert not report["source_full_corrected_accumulation_stated"]
    assert len(report["all_four_retained_formula_hypotheses"]) == 4


def test_numbering_conventions_remain_hypotheses_without_silent_selection(report):
    rows = report["all_six_candidate_comparisons"]
    assert [r["ganzhi"] for r in rows[0]["day_numbering_hypotheses"]] == [
        "乙酉",
        "甲申",
    ]
    assert [r["ganzhi"] for r in rows[1]["day_numbering_hypotheses"]] == [
        "丙戌",
        "乙酉",
    ]
    assert all(len(row["day_numbering_hypotheses"]) == 2 for row in rows)
    assert [
        r["hypothetical_ganzhi"] for r in report["in_cycle_numbering_hypotheses"]
    ] == ["乙酉", "甲申", "丙戌", "乙酉"]
    assert report["source_calendar_identity"].startswith("not_adjudicated")


def test_source_position_diagnostic_does_not_overwrite_the_source(report):
    expected = json.loads((CORPUS / "readings.json").read_text())["board"]
    initial = copy.deepcopy(expected)
    result = source_position_counts(expected)
    assert expected == initial
    assert result == report["source_position_recalculation"]
    assert result["required_fields"] == 6 and result["matching_fields"] == 3
    guest = [r for r in result["observations"] if r["field"].startswith("guest_")]
    assert [r["source"] for r in guest] == [7, 7, 1]
    assert [r["from_source_position"] for r in guest] == [29, 9, 7]
    trace = result["count_traces"]["guest"]
    assert trace["path"][0]["palace"] == "卯"
    assert trace["terminal_palace"] == "子" and trace["terminal_excluded"]
    assert sum(p["value"] for p in trace["path"]) == 29


def test_spatial_agreement_cannot_certify_event_claims_or_full_classic(report):
    geometry = report["post_freeze_spatial_diagnostic"]
    actual = geometry["actual_wenchang_pressure"]
    assert len(actual) == 1
    assert actual[0]["variant"] == "外宫迫"
    assert actual[0]["basis"][0]["value"] == "艮"
    assert actual[0]["basis"][1]["value"] == "子"
    assert report["independent_new_ancient_cases"] == 0
    assert report["new_complete_dated_classical_cases_passed"] == 0
    assert not report["production_calendar_installed_or_changed"]
    assert not report["whole_calendar_acceptance_passed"]
    assert not report["whole_classic_acceptance_passed"]
    assert not report["whole_goal_complete"]


def test_direct_audit_cli_keeps_failure_exit_and_writes_full_report(tmp_path):
    path = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/taiyi/audit_taiyi_liang_collation.py"),
            "--output",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""
    value = json.loads(path.read_text())
    assert value["freeze_sha256"] == FREEZE_SHA256
    assert len(value["all_six_candidate_comparisons"]) == 6
    assert not value["whole_goal_complete"]
