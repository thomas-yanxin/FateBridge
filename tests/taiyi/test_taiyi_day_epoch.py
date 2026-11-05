"""Frozen historical calendar, unselected epoch hypotheses and literal rules."""

import copy
import hashlib
import json
import shutil

import pytest

from fatebridge.validation.taiyi_epoch import (
    accumulation_hypothesis,
    sexagenary_hypothesis,
)
from scripts.taiyi.audit_taiyi_day_epoch import (
    CORPUS,
    audit,
    calendar_cohort,
    verify_sources,
)


def test_complete_frozen_year_and_raw_readings_are_bound_before_comparisons():
    freeze = verify_sources()
    assert freeze["new_calendar_candidate_comparisons_before_freeze"] == 0
    assert len(freeze["files"]) == 11
    data = json.loads((CORPUS / "liang-504-months.json").read_text())
    assert len(data["months"]) == 13
    assert data["source"]["western_calendar"] == "julian"
    assert data["source"]["printed_page"] == 101


def test_summary_page_correction_keeps_initial_location_and_actual_native_page():
    report = audit()
    errata = report["key_summary_location_correction"]
    assert errata["original"] == 42 and errata["corrected"] == 43
    assert errata["correct_source_file"] == "key-page43.png"
    assert errata["numeric_expectations_or_hypothesis_grades_changed"] is False


@pytest.mark.parametrize("update_freeze", [False, True])
def test_cannot_change_calendar_or_acceptance_by_rewriting_local_hashes(
    tmp_path, update_freeze
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    p = corpus / "liang-504-months.json"
    x = json.loads(p.read_text())
    x["months"][5]["julian_month_start"] = "0504-06-30"
    p.write_text(json.dumps(x))
    if update_freeze:
        f = corpus / "freeze.json"
        x = json.loads(f.read_text())
        x["files"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        f.write_text(json.dumps(x))
    with pytest.raises(ValueError, match="V28"):
        verify_sources(corpus)


@pytest.mark.parametrize("mutation", ["drop_month", "month_length"])
def test_full_month_cohort_cannot_be_reduced_to_one_matching_day(mutation):
    x = json.loads((CORPUS / "liang-504-months.json").read_text())
    if mutation == "drop_month":
        x["months"].pop(0)
    else:
        x["months"][0]["printed_month_length"] -= 1
    with pytest.raises(ValueError, match="V28"):
        calendar_cohort(x)


def test_full_year_respects_printed_week_cycle_and_original_erroneous_label():
    x = audit()
    cohort = x["calendar_cohort"]
    assert cohort["month_first_anchors"] == 13 and cohort["complete_months"] == 12
    assert cohort["days"] == len(cohort["records"]) == 355
    assert cohort["mismatches"] == []
    assert x["initial_derived_weekday"] == 3 and x["corrected_derived_weekday"] == 1
    assert x["source_glyphs_changed_by_correction"] is False
    assert x["selected_calendar_case"] == {
        "month": 6,
        "day": 8,
        "gregorian": "0504-07-07",
        "day_ganzhi": "癸未",
        "weekday_sunday_zero": 1,
    }
    assert all(x["selected_calendar_checks"].values())
    assert {r["ganzhi"] for r in x["original_accumulation_day_labels"]} == {
        "甲申",
        "乙酉",
    }
    assert all(
        not r["matches_printed_Liang_day"]
        for r in x["original_accumulation_day_labels"]
    )
    assert x["source_calendar_identity"].startswith("not_adjudicated")
    assert not x["whole_calendar_acceptance_passed"] and not x["whole_goal_complete"]


def test_all_original_four_hypotheses_and_both_conventions_stay_in_report():
    x = audit()
    new = x["all_four_V27_hypotheses"]
    assert len(new) == 4
    assert [r["minus_original_accumulation"] for r in new] == [352, 382, -2, 28]
    assert all(len(r["sexagenary_conventions"]) == 2 for r in new)
    assert x["hypotheses_matching_original_accumulation"] == 0
    assert x["hypothesis_convention_pairs_matching_Liang_day"] == 1
    assert x["new_complete_dated_classical_cases_passed"] == 0
    assert x["production_calendar_installed_or_changed"] is False


def test_supplied_accumulation_replay_does_not_certify_date_bridge_or_other_book():
    x = audit()
    r = x["given_accumulation_replay"]
    assert r["original_accumulation"] == 707501061
    assert r["division360"] == [1965280, 261]
    assert r["division60_of_remainder"] == [4, 21]
    assert (r["taiyi_number"], r["wenchang_palace"]) == (8, "艮")
    public = x["public_current_day_profile"]
    assert public["calendar_rules"]["day_profile"] == "key_day_winter_jiazi_v1"
    assert public["calendar_rules"]["counter"] == 200
    assert public["counter_comparison_to_Jinjing_applicable"] is False
    controls = x["key_jishen_deductive_controls"]
    assert len(controls) == 24 and all(r["matches"] for r in controls)
    assert x["key_jishen_historical_yin_examples"] == 0


def test_hypothesis_keeps_floor_remainders_and_explicit_offsets():
    inputs = dict(
        year_accumulation=1937060,
        chapter_years=657,
        chapter_months=8126,
        month_numerator=1447,
        day_denominator=49,
        month_offset=7,
        day_offset=7,
    )
    before = copy.deepcopy(inputs)
    r = accumulation_hypothesis(**inputs)
    assert inputs == before
    assert (r["completed_months"], r["chapter_remainder"]) == (23958218, 334)
    assert r["candidate_accumulation"] == 707501059
    assert sexagenary_hypothesis(707501059, jiazi_origin=0) == "癸未"
    assert sexagenary_hypothesis(707501059, jiazi_origin=1) == "壬午"


@pytest.mark.parametrize(
    "field,value",
    [
        ("year_accumulation", True),
        ("chapter_years", 0),
        ("chapter_months", 0),
        ("month_numerator", -1),
        ("day_denominator", 0),
        ("month_offset", -1),
        ("day_offset", False),
        ("day_offset", 7.5),
    ],
)
def test_invalid_hypothesis_inputs_never_become_inferred_calendar_parameters(
    field, value
):
    params = dict(
        year_accumulation=1937060,
        chapter_years=657,
        chapter_months=8126,
        month_numerator=1447,
        day_denominator=49,
        month_offset=7,
        day_offset=7,
    )
    params[field] = value
    with pytest.raises(ValueError, match="Explicit integral"):
        accumulation_hypothesis(**params)


@pytest.mark.parametrize(
    "accumulation,origin", [(0, 0), (True, 1), (1, True), (1, 2), (1, "0")]
)
def test_invalid_ganzhi_conventions_are_rejected(accumulation, origin):
    with pytest.raises(ValueError, match="explicit Jiazi"):
        sexagenary_hypothesis(accumulation, jiazi_origin=origin)
