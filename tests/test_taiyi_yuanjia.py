"""Complete printed cohort, source pins and unresolved leap-month labels."""

import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction

import pytest

from fatebridge.validation.yuanjia_calendar import yuanjia_mean_year
from scripts.audit_taiyi_yuanjia import (
    CORPUS,
    FREEZE_SHA256,
    ROOT,
    audit,
    verify_sources,
)


@pytest.fixture(scope="module")
def report():
    return audit()


def test_source_freeze_retains_complete_page_and_known_prior_evidence():
    frozen = verify_sources()
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    assert len(frozen["files"]) == 10 and len(frozen["prior_sources"]) == 58
    assert not frozen["blinded"]
    assert not frozen["new_yuanjia_implementation_before_freeze"]
    assert frozen["new_executed_yuanjia_comparisons_before_freeze"] == 0
    source = json.loads((CORPUS / "historical-months-initial.json").read_text())
    assert len(source["months"]) == 63
    assert source["months"][-1]["role"] == "exclusive_end_sentinel"
    assert {r["lunar_year"] for r in source["months"][:-1]} == set(range(501, 506))
    reading = json.loads((CORPUS / "readings.json").read_text())
    assert reading["moon_multiply_literal"] == "以通數乘積分為朔積分"
    assert "積月" in reading["moon_multiply_transcription_variant"]
    assert reading["constants"]["large_month_small_remainder_threshold"] == 353


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_leap_four_oracle_cannot_be_replaced_by_a_better_matching_month(
    tmp_path, rewrite_manifest
):
    target = tmp_path / "source"
    shutil.copytree(CORPUS, target)
    path = target / "historical-months-initial.json"
    rows = json.loads(path.read_text())
    old = next(
        r for r in rows["months"] if r["lunar_year"] == 502 and r["is_leap_month"]
    )
    assert old["month"] == 4
    old["month"] = 5
    path.write_text(json.dumps(rows))
    if rewrite_manifest:
        freeze = json.loads((target / "freeze.json").read_text())
        freeze["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="V35"):
        verify_sources(target)


def test_printed443_two_epoch_anchors_agree(report):
    anchor = report["source_anchor_check"]
    assert (
        anchor["actual_elapsed_years_within_ji"]
        == anchor["expected_elapsed_years_within_ji"]
        == 231
    )
    assert anchor["actual_ji_ganzhi"] == anchor["expected_ji_ganzhi"] == "甲午"


@pytest.mark.parametrize(
    "elapsed,ji,within",
    [
        (0, "甲子", 0),
        (608, "甲戌", 0),
        (1216, "甲申", 0),
        (1824, "甲午", 0),
        (2432, "甲辰", 0),
        (3040, "甲寅", 0),
        (3648, "甲子", 0),
    ],
)
def test_all_six_ji_origins_and_yuan_wrap_are_kept(elapsed, ji, within):
    row = yuanjia_mean_year(elapsed, middle_term_assignment="civil_day")
    assert row["ji_ganzhi"] == ji
    assert row["elapsed_years_within_ji"] == within
    assert row["records"][0]["first_ganzhi"] == ji
    assert row["records"][0]["day_within_ji"] == 0
    assert not row["absolute_julian_epoch_proved"]


@pytest.mark.parametrize("elapsed", [-1, True, 1.0, "231", None])
def test_counter_refuses_implicit_year_coercion(elapsed):
    with pytest.raises(ValueError, match="integral elapsed"):
        yuanjia_mean_year(elapsed, middle_term_assignment="civil_day")


@pytest.mark.parametrize("assignment", [None, "auto", "best_match"])
def test_qi_assignment_must_be_explicit(assignment):
    with pytest.raises(ValueError, match="Explicit Yuanjia"):
        yuanjia_mean_year(5703, middle_term_assignment=assignment)


def test_a_complete_chapter_has_source235_months_and7_intercalations():
    # A structural arithmetic control, not19 additional historical observations.
    years = [
        yuanjia_mean_year(i, middle_term_assignment="civil_day") for i in range(19)
    ]
    assert sum(r["month_count"] for r in years) == 235
    assert sum(r["chapter_leap_year"] for r in years) == 7


def test_full63_firsts62_lengths_and1831_days_are_not_a_whole_calendar_pass(report):
    assert report["source_calendar_reconstruction_checks_match"]
    assert len(report["source_calendar_controls"]) == 63
    for series in report["yuanjia_calendar_series"]:
        assert len(series["years"]) == 5 and len(series["months"]) == 62
        assert series["matching_firsts_including_sentinel"] == 63
        assert series["matching_month_lengths"] == 62
        assert (
            series["matching_day_labels"]
            == series["required_days"]
            == len(series["days"])
            == 1831
        )
        assert all(d["ordinal_exists"] for d in series["days"])
        assert not series["all_observed_months_and_days_match"]
        assert not series["absolute_julian_epoch_proved"]
        assert not series["source_assignment_selected_by_fit"]
        for row in series["months"]:
            actual = row["actual"]
            assert actual["large_from_printed353_threshold"] == (
                row["reference_month_days"] == 30
            )


def test_502_leap_disagreement_cannot_be_hidden_by_all_matching_day_phases(report):
    civil, exact = report["yuanjia_calendar_series"]
    assert [s["matching_month_identities"] for s in (civil, exact)] == [60, 59]
    assert [s["matching_complete_lunar_dates"] for s in (civil, exact)] == [1772, 1742]
    for series, leap_month, missing_days in [(civil, 5, 59), (exact, 6, 89)]:
        differences = [d for d in series["days"] if not d["full_lunar_date_matches"]]
        assert len(differences) == missing_days
        assert {d["year"] for d in differences} == {502}
        assert all(
            d["day_label_matches"] and not d["month_identity_matches"]
            for d in differences
        )
        candidate = next(y["calculated"] for y in series["years"] if y["year"] == 502)
        actual_leap = next(r for r in candidate["records"] if r["is_leap_month"])
        assert actual_leap["month"] == leap_month
        assert candidate["nominal_leap_count_raw"] == 5
        assert not candidate["nominal_count_is_adjudicated_month_or_slot"]
        assert not candidate["middle_term_assignment_adjudicated"]
        printed_leap = next(
            r["source"]
            for r in series["months"]
            if r["source"]["lunar_year"] == 502 and r["source"]["is_leap_month"]
        )
        assert printed_leap["month"] == 4


def test_505_leap_two_is_retained_alongside_the_502_failure(report):
    for series in report["yuanjia_calendar_series"]:
        year = next(r["calculated"] for r in series["years"] if r["year"] == 505)
        assert year["nominal_leap_count_raw"] == 1
        leap = next(r for r in year["records"] if r["is_leap_month"])
        assert leap["month"] == 2
        assert all(
            r["month_identity_matches"]
            for r in series["months"]
            if r["source"]["lunar_year"] == 505
        )


def test_504_former_carry_disagreement_is_a_different_calendar_not_a_wang_patch(report):
    civil = report["yuanjia_calendar_series"][0]
    rows = [r for r in civil["months"] if r["source"]["lunar_year"] == 504]
    assert [r["actual"]["small_remainder"] for r in rows[:3]] == [709, 356, 3]
    assert [r["actual"]["next_month_days"] for r in rows[:3]] == [30, 30, 29]
    assert rows[0]["actual"]["first_ganzhi"] == "戊申"
    means = report["mean_month_comparison"]
    assert Fraction(**means["wang_minus_yuanjia_days"]) == Fraction(1, 36848)
    assert not means["equal_calendar_or_epoch_identity_proved"]
    assert not report["wang_constants_or_original_day_changed"]
    assert not report["new_public_calendar_installed"]


def test_all_old_day8_day9_and_board_failures_remain_in_the_pinned_report(report):
    evidence = report["previous_v34_evidence"]
    old_bytes = (ROOT / evidence["path"]).read_bytes()
    assert hashlib.sha256(old_bytes).hexdigest() == evidence["sha256"]
    old = json.loads(old_bytes)
    assert len(old["date_encoding_candidates"]) == 48
    assert (
        sum(len(r["counter_comparisons"]) for r in old["date_encoding_candidates"])
        == 96
    )
    assert (
        old["original_observed_joint_matches"]
        == old["xing_observed_joint_matches"]
        == 0
    )
    assert (
        report["new_independent_taiyi_cases"]
        == report["new_complete_dated_classical_cases_passed"]
        == 0
    )
    assert not report["whole_goal_complete"]


def test_direct_and_module_entrypoints_keep_failure_exit_and_identical_report(tmp_path):
    results = []
    for entry in (
        [str(ROOT / "scripts/audit_taiyi_yuanjia.py")],
        ["-m", "scripts.audit_taiyi_yuanjia"],
    ):
        path = tmp_path / f"report{len(results)}.json"
        result = subprocess.run(
            [sys.executable, *entry, "--output", str(path)],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 1 and not result.stderr
        results.append(path.read_bytes())
    assert results[0] == results[1]
