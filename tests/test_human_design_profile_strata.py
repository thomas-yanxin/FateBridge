"""Synthetic source-accounting guard probes, not astronomical reference charts."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "profile_strata", ROOT / "scripts/check_human_design_profile_strata.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    plan, cases = {"cases": []}, []
    for gate in (1, 2):
        identifier = f"profile-{gate:02d}-1-3"
        birth = {
            "birth_year": 1981,
            "birth_month": 1,
            "birth_day": gate,
            "birth_hour": 0,
            "birth_minute": 0,
            "birth_timezone": "UTC",
        }
        utc = f"1981-01-{gate:02d}T00:00:00+00:00"
        plan["cases"].append(
            {"id": identifier, "birth_input": birth, "engine_utc": utc}
        )
        personality, design = ["1.1"] * 13, ["1.3"] * 13
        personality[0] = f"{gate}.1"
        cases.append(
            {
                "id": identifier,
                "birth_input": deepcopy(birth),
                "displayed_birth_utc": utc,
                "properties": {"Profile": "1/3"},
                "columns": {"personality": personality, "design": design},
            }
        )
    return plan, {
        "planet_order": list(MODULE.ORDER),
        "cases": cases,
        "planned_case_count": 2,
        "observed_case_count": 2,
        "missing_planned_ids": [],
        "collection_status": "complete",
    }


def test_observed_cells_are_checked_without_awarding_professional_acceptance():
    plan, cohort = fixture()
    result = MODULE.check_observed_strata(plan, cohort)
    assert result["status"] == "observed_strata_and_input_links_matched"
    assert result["matched_expected_strata"] == 2
    assert not result["all_three_axes_full_marks"]
    assert not result["authority_certified"]


def test_two_ids_and_a_complete_count_cannot_hide_one_repeated_observed_cell():
    plan, cohort = fixture()
    cohort["cases"][1]["columns"]["personality"][0] = "1.1"
    result = MODULE.check_observed_strata(plan, cohort)
    assert result["status"] == "not_achieved"
    assert result["missing_strata"] == [(2, "1/3")]
    assert result["duplicate_strata"] == [{"gate": 1, "profile": "1/3", "count": 2}]
    assert [row["id"] for row in result["cases"]] == [
        row["id"] for row in cohort["cases"]
    ]


@pytest.mark.parametrize(
    "change",
    ["profile", "earth_line", "utc", "birth", "body_order", "invalid_activation"],
)
def test_contradictory_source_fields_are_rejected_without_dropping_rows(change):
    plan, cohort = fixture()
    row = cohort["cases"][0]
    if change == "profile":
        row["properties"]["Profile"] = "1/4"
    elif change == "earth_line":
        row["columns"]["personality"][1] = "2.2"
    elif change == "utc":
        row["displayed_birth_utc"] = "1981-01-01T01:00:00+00:00"
    elif change == "birth":
        row["birth_input"]["birth_hour"] = 1
    elif change == "body_order":
        cohort["planet_order"][0:2] = ["Earth", "Sun"]
    else:
        row["columns"]["personality"][2] = "64.7"
    result = MODULE.check_observed_strata(plan, cohort)
    assert result["status"] == "not_achieved"
    assert len(result["cases"]) == 2 and result["all_supplied_rows_retained"]
    assert result["cases"][0]["errors"]


def test_partial_collection_cannot_claim_complete_by_editing_metadata():
    plan, cohort = fixture()
    cohort["cases"].pop()
    result = MODULE.check_observed_strata(plan, cohort)
    assert result["status"] == "not_achieved"
    assert result["missing_ids"] == ["profile-02-1-3"]
    assert not result["collection_metadata_consistent"]


def test_duplicate_and_reordered_ids_remain_visible():
    plan, cohort = fixture()
    cohort["cases"][1] = deepcopy(cohort["cases"][0])
    result = MODULE.check_observed_strata(plan, cohort)
    assert result["duplicate_ids"] == ["profile-01-1-3"]
    assert len(result["cases"]) == 2
    _, reordered = fixture()
    reordered["cases"].reverse()
    result = MODULE.check_observed_strata(plan, reordered)
    assert not result["ids_follow_original_prefix"]
    assert [row["id"] for row in result["cases"]] == [
        "profile-02-1-3",
        "profile-01-1-3",
    ]
