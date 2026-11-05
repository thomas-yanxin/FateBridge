"""Existing dates, complete source cohorts and retained calendar conflicts."""

import hashlib
import json
import shutil

import pytest

from scripts.taiyi.audit_taiyi_calendar_context import (
    CORPUS,
    FREEZE_SHA256,
    audit,
    compare_chronology,
    compare_event,
    verify_sources,
)


@pytest.fixture(scope="module")
def report():
    return audit()


def event(ganzhi, *, leap=False, shuo=False):
    return {
        "id": "synthetic-control",
        "month": 1,
        "is_leap_month": leap,
        "ganzhi": ganzhi,
        "explicit_shuo": shuo,
    }


def month(*, length=29, first="甲子"):
    return {
        "month": 1,
        "is_leap_month": False,
        "length": length,
        "first_ganzhi": first,
        "start_day_in_year": 0,
    }


@pytest.mark.parametrize(
    "ganzhi,length,day,exists",
    [
        ("甲子", 29, 1, True),
        ("壬辰", 29, 29, True),
        ("癸巳", 29, 30, False),
        ("癸巳", 30, 30, True),
        ("甲午", 30, 31, False),
        ("癸亥", 30, 60, False),
    ],
)
def test_counter_candidates_do_not_create_nonexistent_dates(
    ganzhi, length, day, exists
):
    row = compare_event(event(ganzhi), [month(length=length)])
    assert row["candidate_day_number"] == day
    assert row["date_exists"] is exists
    assert row["joint_source_date_satisfied"] is exists
    assert row["day_number"] == (day if exists else None)
    assert row["day_position_in_year"] == (day - 1 if exists else None)


def test_cycle_wrap_and_explicit_shuo_are_different_requirements():
    wrapped = compare_event(event("甲子"), [month(first="癸亥")])
    assert wrapped["day_number"] == 2 and wrapped["date_exists"]
    required_first = compare_event(event("甲子", shuo=True), [month(first="癸亥")])
    assert required_first["date_exists"]
    assert required_first["explicit_shuo_satisfied"] is False
    assert required_first["joint_source_date_satisfied"] is False
    first = compare_event(event("癸亥", shuo=True), [month(first="癸亥")])
    assert first["explicit_shuo_satisfied"] and first["joint_source_date_satisfied"]


@pytest.mark.parametrize(
    "rows,reason", [([], "missing_month"), ([month(), month()], "ambiguous_month")]
)
def test_missing_or_ambiguous_month_has_no_fabricated_day(rows, reason):
    row = compare_event(event("甲子"), rows)
    assert row["reason"] == reason and not row["date_exists"]
    assert row["day_position_in_year"] is None and row["day_number"] is None


def test_leap_month_does_not_fall_back_to_regular_month_with_the_same_number():
    row = compare_event(event("甲子", leap=True), [month()])
    assert row["reason"] == "missing_month" and not row["joint_source_date_satisfied"]


@pytest.mark.parametrize("length", [0, 28, 31, 29.0, True])
def test_invalid_month_length_is_not_accepted(length):
    with pytest.raises(ValueError, match="29 or30"):
        compare_event(event("甲子"), [month(length=length)])


def test_chronology_distinguishes_reversal_equality_and_missing_dates():
    rows = []
    for i, position in enumerate([3, 1, 1, None, 10]):
        rows.append({"source": {"id": str(i)}, "day_position_in_year": position})
    edges = compare_chronology(rows)
    assert [e["nondecreasing"] for e in edges] == [False, True, None, None]
    assert [e["days_between"] for e in edges] == [-2, 0, None, None]
    assert len(edges) == 4


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_source_months_cannot_be_emended_to_improve_a_candidate(
    tmp_path, rewrite_manifest
):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    path = target / "readings.json"
    reading = json.loads(path.read_text())
    reading["cohorts"][2]["events"][0]["month"] = 4
    path.write_text(json.dumps(reading))
    if rewrite_manifest:
        frozen = json.loads((target / "freeze.json").read_text())
        frozen["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="V37"):
        verify_sources(target)


def test_complete_declared_passages_and_original_month_words_are_retained(report):
    frozen = verify_sources()
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    assert len(frozen["files"]) == 40 and len(frozen["prior_sources"]) == 76
    reading = json.loads((CORPUS / "readings.json").read_text())
    assert not reading["blinded"] and reading["independent_human_reviews"] == 0
    assert [len(c["events"]) for c in reading["cohorts"]] == [20, 21, 1]
    for cohort in reading["cohorts"][:2]:
        dates = cohort["events"]
        assert dates[0]["month_token"] == "四月" and dates[0]["ganzhi"] == "丙寅"
        leap = [r for r in dates if r["is_leap_month"]]
        assert [r["ganzhi"] for r in leap] == ["丁酉", "壬寅"]
        assert all(r["month_token"] == "閏月" for r in leap)
        assert all(
            r["month_number_basis"] == "inferred_after_fourth_before_fifth"
            for r in leap
        )
        assert [r["ganzhi"] for r in dates if r["month"] == 5] == ["乙亥", "戊子"]
    biography = reading["cohorts"][2]["events"][0]
    assert (biography["month_token"], biography["ganzhi"]) == ("五月", "甲辰")
    assert report["source_date_observations"] == 42


def test_all_candidates_keep_every_source_observation_and_chronology_edge(report):
    for candidate in report["calendar_comparisons"]:
        assert [c["required_date_observations"] for c in candidate["cohorts"]] == [
            20,
            21,
            1,
        ]
        assert sum(c["chronology_edges_required"] for c in candidate["cohorts"]) == 39
        for cohort in candidate["cohorts"]:
            assert len(cohort["observations"]) == cohort["required_date_observations"]
            assert len(cohort["chronology"]) == cohort["chronology_edges_required"]
            assert (
                sum(
                    cohort[key]
                    for key in [
                        "chronology_edges_satisfied",
                        "chronology_edges_contradicted",
                        "chronology_edges_unknown",
                    ]
                )
                == cohort["chronology_edges_required"]
            )
            for row in cohort["observations"]:
                if not row["date_exists"]:
                    assert (
                        row["day_number"] is None
                        and row["day_position_in_year"] is None
                    )
        assert not candidate["all_three_selected_passages_compatible"]
    assert not report["any_candidate_satisfies_all_selected_passages"]
    assert not report["calendar_selected_by_fit"]
    assert not report["month_label_or_source_emendation_adjudicated"]
    assert not report["source_reading_is_independent_expert_review"]
    assert not report["chronicle_observations_are_independent_taiyi_cases"]
    assert (
        report["new_complete_dated_taiyi_cases_passed"]
        == report["new_model_invocations"]
        == 0
    )
    assert (
        not report["production_calendar_changed"] and not report["whole_goal_complete"]
    )
