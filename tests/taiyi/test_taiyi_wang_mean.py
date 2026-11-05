"""Wang calendar diagnostics must preserve unknowns, source bytes and failures."""

from __future__ import annotations

import hashlib
import json
import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from fatebridge.validation.wang_mean_calendar import phase_in_month, wang_mean_window
from scripts.taiyi.audit_taiyi_wang_mean import (
    CORPUS,
    ROOT,
    audit,
    select_identity,
    verify_sources,
)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return audit()


def window(year: int = 504, **overrides: Any) -> dict[str, Any]:
    return wang_mean_window(
        year,
        **{
            "moon_year_shift": -1,
            "middle_term_assignment": "civil_day",
            "initial_quotient_encoding": "completed_days",
            **overrides,
        },
    )


def test_civil_day_and_exact_boundary_are_distinct() -> None:
    begin, end, qi = Fraction(100, 3), Fraction(190, 3), Fraction(63)
    assert not phase_in_month(qi, begin, end, assignment="civil_day")
    assert phase_in_month(qi, begin, end, assignment="exact_fraction")
    assert phase_in_month(begin, begin, end, assignment="exact_fraction")
    assert not phase_in_month(end, begin, end, assignment="exact_fraction")


@pytest.mark.parametrize(
    "override",
    [
        {"nominal_ce_year": True},
        {"nominal_ce_year": 0},
        {"moon_year_shift": True},
        {"moon_year_shift": -2},
        {"middle_term_assignment": "auto"},
        {"initial_quotient_encoding": "best_fit"},
    ],
)
def test_no_implicit_or_nonintegral_parameters(override: dict[str, Any]) -> None:
    parameters = {
        "nominal_ce_year": 504,
        "moon_year_shift": -1,
        "middle_term_assignment": "civil_day",
        "initial_quotient_encoding": "completed_days",
        **override,
    }
    with pytest.raises(ValueError):
        wang_mean_window(**parameters)


def test_wrong_year_phase_never_gets_month_labels() -> None:
    value = window(moon_year_shift=0)
    assert not value["initial_contains_winter"]
    assert not value["term_enumeration_covers_window"]
    assert value["unknown_middle_term_slots"]
    assert set(value["unknown_middle_term_slots"]).isdisjoint(
        value["empty_middle_term_slots"]
    )
    assert not value["conditional_month_identities_known"]
    assert all(
        r["month"] is None and r["is_leap_month"] is None for r in value["records"]
    )


def test_adjacent_windows_keep_one_continuous_mean_moon_counter() -> None:
    values = [window(y) for y in range(501, 507)]
    assert [w["window_month_count"] for w in values] == [12, 13, 12, 12, 13, 12]
    for previous, following in zip(values, values[1:]):
        assert (
            previous["next_initial_accumulated_months"]
            == following["initial_accumulated_months"]
        )
        last = previous["records"][-1]
        first = following["records"][0]
        assert last["raw_quotient"] + last["next_month_days"] == first["raw_quotient"]


def test_rounded_leap_increment_is_not_adjudicated_calendar() -> None:
    value = window(505)
    assert value["chapter_remainder"] == 576
    assert value["printed_step_twelve_month_increment"] == {
        "numerator": 6051,
        "denominator": 25,
    }
    assert value["exact_chapter_twelve_month_excess"] == 242
    assert [
        r["step"] for r in value["printed_20_17_arithmetic"] if r["chapter_carry"]
    ] == [5]
    assert not value["source_leap_clause_adjudicated"]
    assert all(
        not r["leap_month_label_adjudicated"] for r in value["printed_20_17_arithmetic"]
    )


def test_unknown_identity_never_borrows_ordinary_month() -> None:
    ordinary = select_identity(
        window(502)["records"], {"lunar_year": 502, "month": 4, "is_leap_month": False}
    )
    assert ordinary is not None
    wanted = {"lunar_year": 502, "month": 4, "is_leap_month": True}
    assert select_identity(window(502)["records"], wanted) is None


def test_duplicate_identity_stays_unknown() -> None:
    row = window()["records"][2]
    wanted = {k: row[k] for k in ("lunar_year", "month", "is_leap_month")}
    assert select_identity([row, row.copy()], wanted) is None


def test_two_encodings_couple_number_to_day_name() -> None:
    elapsed = window()["records"][0]["counter_view"]
    numbered = window(initial_quotient_encoding="one_based_day_number")["records"][0][
        "counter_view"
    ]
    assert elapsed["value"] == numbered["value"]
    assert elapsed["completed_days"] == numbered["completed_days"] + 1
    assert elapsed["day_ganzhi"] != numbered["day_ganzhi"]
    assert not elapsed["source_encoding_adjudicated"]


def test_all_axes_and_full_failed_cohort_retained(result: dict[str, Any]) -> None:
    assert len(result["conditional_series"]) == 8
    for s in result["conditional_series"]:
        assert len(s["source_month_comparisons"]) == 63
        assert len(s["source_days"]) == 1831
        assert not s["whole_observed_cohort_matches"]
        assert not s["target_given_number_and_day_match"]
    assert not result["whole_calendar_acceptance_passed"]
    assert not result["whole_goal_complete"]
    assert not result["calendar_selected_by_fit"]
    assert result["new_complete_dated_taiyi_cases_passed"] == 0


def test_missing_leap_month_is_unknown_for_every_day(result: dict[str, Any]) -> None:
    series = next(
        s
        for s in result["conditional_series"]
        if s["moon_year_shift"] == -1
        and s["middle_term_assignment"] == "civil_day"
        and s["initial_quotient_encoding"] == "completed_days"
    )
    missing = [
        d
        for d in series["source_days"]
        if d["year"] == 502 and d["month"] == 4 and d["is_leap_month"]
    ]
    assert len(missing) == 30
    assert all(d["actual"] is None and d["ordinal_exists"] is None for d in missing)
    assert all(not d["full_lunar_date_matches"] for d in missing)


def test_nonexistent_thirtieth_day_does_not_count_as_valid_match(
    result: dict[str, Any],
) -> None:
    series = next(
        s
        for s in result["conditional_series"]
        if s["moon_year_shift"] == -1
        and s["middle_term_assignment"] == "civil_day"
        and s["initial_quotient_encoding"] == "completed_days"
    )
    false_dates = [
        d
        for d in series["source_days"]
        if d["day_label_matches"] and d["ordinal_exists"] is False
    ]
    assert false_dates
    assert all(d["day"] == 30 and not d["full_lunar_date_matches"] for d in false_dates)
    assert series["matching_complete_lunar_dates"] < series["matching_day_labels"]


def test_both_leap_readings_remain_distinct(result: dict[str, Any]) -> None:
    leaps = {}
    for s in result["conditional_series"]:
        if (
            s["moon_year_shift"] == -1
            and s["initial_quotient_encoding"] == "completed_days"
        ):
            leaps[s["middle_term_assignment"]] = [
                r["month"] for w in s["conditional_leaps"] for r in w["leaps"]
            ]
    assert leaps == {"civil_day": [5, 2], "exact_fraction": [6, 3]}


def test_sources_and_previous_reports_still_match_pins() -> None:
    frozen = verify_sources()
    assert len(frozen["prior_sources"]) == 35
    assert len(frozen["files"]) == 2


def test_source_and_manifest_cannot_be_rewritten_together(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    reading = corpus / "readings.json"
    reading.write_text("{}\n")
    freeze = json.loads((corpus / "freeze.json").read_text())
    freeze["files"]["readings.json"] = hashlib.sha256(reading.read_bytes()).hexdigest()
    (corpus / "freeze.json").write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="pinned source freeze changed"):
        verify_sources(corpus, root=ROOT)
