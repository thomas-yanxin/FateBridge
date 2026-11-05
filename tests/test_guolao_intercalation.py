"""Independent leap label, civil-vs-instant counterexample and missing inputs."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_intercalation as c

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-intercalation-v1"
SOURCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.fixture(scope="module")
def worked():
    return c.gujin_fixed_qice_months(F(SOURCE["worked_input_zhongji_days"]))


def synthetic():
    # An independent synthetic cycle: 12 civil months, no missing principal qi.
    return tuple(F(".9") + i * F("29.5") for i in range(15)), tuple(
        F(".1") + i * F("30.436875") for i in range(13)
    )


def test_worked_intercalary_label_matches_independent_original_transcription(worked):
    assignment = worked["month_assignment"]
    ref = SOURCE["independent_reference"]
    assert assignment["month_count"] == 13
    assert assignment["leap_month_number"] == ref["month_number"] == 4
    leap = [m for m in assignment["months"] if m["is_leap_month"]]
    assert len(leap) == 1
    assert leap[0]["length_days"] == ref["length_days"] == 29
    assert leap[0]["lunation_index"] == 6
    assert ref["evidence_level"] == "digital_transcription_not_facsimile_collated"
    assert not ref["all_months_or_conjunction_times_accepted"]


def test_full_cycle_has_complete_ordered_months_and_shared_boundaries(worked):
    rows = worked["month_assignment"]["months"]
    assert [r["month_number"] for r in rows] == [
        11,
        12,
        1,
        2,
        3,
        4,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
    ]
    assert [r["length_days"] for r in rows] == [
        30,
        30,
        29,
        29,
        30,
        29,
        29,
        30,
        30,
        29,
        30,
        30,
        29,
    ]
    assert sum(r["length_days"] for r in rows) == 384
    assert [i for r in rows for i in r["principal_term_indices"]] == list(range(12))
    for a, b in zip(rows, rows[1:]):
        assert a["next_start_source_day_integer"] == b["start_source_day_integer"]
    assert not worked["complete_source_calendar_accepted"]
    assert not worked["civil_policy_historical_acceptance"]
    assert not worked["modern_epoch_calibrated"]
    assert not worked["used_in_native_birth_chart"]
    assert worked["modern_lunar_date"] is None


def test_actual_summer_solstice_precedes_conjunction_but_is_in_new_civil_month(worked):
    rows = worked["month_assignment"]["months"]
    qi = F(worked["solar_terms"][12]["source_day_counter_exact"])
    winter = F(worked["winter_source_day_counter_exact"])
    moon = winter + F(rows[7]["conjunction_offset_from_winter_days_exact"])
    assert qi < moon and qi // 1 == moon // 1
    assert rows[6]["principal_term_indices"] == []
    assert rows[6]["instant_interval_principal_term_indices_diagnostic"] == [6]
    assert rows[7]["principal_term_indices"] == [6]
    assert rows[7]["instant_interval_principal_term_indices_diagnostic"] == []
    assert rows[6]["civil_and_instant_membership_differ"]
    assert rows[7]["civil_and_instant_membership_differ"]
    assert worked["mean_leap_estimate"]["candidate_leap_month_number"] == 5
    assert worked["mean_leap_estimate"]["candidate_empty_lunation_index"] == 7
    assert not worked["mean_leap_estimate"]["accepted_as_final_month"]


@pytest.mark.parametrize(
    "position,leap",
    [("before_midnight", 5), ("midnight", 4), ("before_moon", 4), ("at_moon", 4)],
)
def test_summer_qi_both_sides_exact_midnight_and_same_day_conjunction(
    worked, position, leap
):
    winter = F(worked["winter_source_day_counter_exact"])
    moons = tuple(
        winter + F(x["research_conjunction_offset_from_winter_days_exact"])
        for x in worked["conjunction_candidates"]
    )
    terms = [
        F(x["source_day_counter_exact"])
        for x in worked["solar_terms"]
        if x["is_principal_term"]
    ]
    epsilon = F(1, 10**20)
    options = {
        "before_midnight": F(moons[7] // 1) - epsilon,
        "midnight": F(moons[7] // 1),
        "before_moon": moons[7] - epsilon,
        "at_moon": moons[7],
    }
    terms[6] = options[position]
    result = c.assign_civil_sui(moons, tuple(terms))
    assert result["status"] == "assigned_under_explicit_civil_mean_qi_policy"
    assert result["leap_month_number"] == leap


def test_no_leap_synthetic_cycle_and_winter_before_same_day_new_moon():
    moons, qi = synthetic()
    assert qi[0] < moons[0] and qi[0] // 1 == moons[0] // 1
    result = c.assign_civil_sui(moons, qi)
    assert result["month_count"] == 12 and result["leap_month_number"] is None
    assert result["months"][0]["principal_term_indices"] == [0]
    assert (
        result["months"][0]["instant_interval_principal_term_indices_diagnostic"] == []
    )
    assert [m["month_number"] for m in result["months"]] == [11, 12, *range(1, 11)]


def test_missing_unused_neighbor_does_not_invalidate_available_cycle():
    moons, qi = synthetic()
    result = c.assign_civil_sui((*moons[:-1], None), qi)
    assert result["status"] == "assigned_under_explicit_civil_mean_qi_policy"
    assert result["missing_conjunction_indices"] == [14]


@pytest.mark.parametrize(
    "index,reason",
    [
        (0, "winter_civil_day_not_bracketed_by_known_adjacent_conjunctions"),
        (6, "missing_required_conjunction_boundary"),
        (13, "winter_civil_day_not_bracketed_by_known_adjacent_conjunctions"),
    ],
)
def test_required_missing_boundary_stays_unassigned(index, reason):
    moons, qi = synthetic()
    missing = tuple(None if i == index else t for i, t in enumerate(moons))
    result = c.assign_civil_sui(missing, qi)
    assert result["status"] == "unresolved"
    assert result["reason"] == reason
    assert result["months"] == []


def test_31_day_month_is_reported_without_repair():
    moons, qi = synthetic()
    moons = tuple(t + F("1.2") if i == 6 else t for i, t in enumerate(moons))
    result = c.assign_civil_sui(moons, qi)
    assert result["reason"] == "source_month_length_outside_29_or_30_not_repaired"
    assert any(m["length_days"] == 31 for m in result["months"])
    assert all(m["month_number"] is None for m in result["months"])


def test_double_principal_term_does_not_select_a_convenient_leap_month():
    moons, qi = synthetic()
    conflicting = (qi[0], F("29.9"), *qi[2:])
    result = c.assign_civil_sui(moons, conflicting)
    assert (
        result["reason"] == "principal_term_pattern_not_unique_for_this_mean_qi_policy"
    )
    assert all(m["month_number"] is None for m in result["months"])


@pytest.mark.parametrize("step", [F(26), F(33)])
def test_non_12_or_13_cycle_rejected(step):
    _, qi = synthetic()
    result = c.assign_civil_sui(tuple(F(".9") + i * step for i in range(17)), qi)
    assert result["reason"] == "winter_cycle_has_neither_12_nor_13_months"


@pytest.mark.parametrize("bad", [0.0, 0, True, "116147.0196", None])
def test_raw_input_never_coerced(bad):
    with pytest.raises(TypeError):
        c.gujin_fixed_qice_months(bad)


@pytest.mark.parametrize(
    "delta,has_leap,index",
    [(F(-1, 10**15), False, None), (F(), True, 12), (F(1, 10**15), True, 12)],
)
def test_exact_mean_leap_threshold_does_not_apply_floor_plus_one(
    delta, has_leap, index
):
    month, month_run = F("29.530593"), F(".906282")
    runyu = month - 12 * month_run + delta
    middle = runyu - F("20.205") + month
    estimate = c.gujin_fixed_qice_months(middle)["mean_leap_estimate"]
    assert estimate["has_leap_by_printed_run_limit"] is has_leap
    assert estimate["candidate_empty_lunation_index"] == index
    assert estimate["candidate_leap_month_number"] == (10 if has_leap else None)


def test_negative_zhongji_not_upper_reckoning():
    with pytest.raises(ValueError):
        c.gujin_fixed_qice_months(F(-1))


def test_assembler_rejects_residues_duplicates_unsorted_and_inexact_inputs():
    moons, qi = synthetic()
    for a, b in [
        (tuple(t % 60 for t in moons), qi),
        (moons, (qi[0], qi[0], *qi[2:])),
        (tuple(reversed(moons)), qi),
    ]:
        with pytest.raises(ValueError):
            c.assign_civil_sui(a, b)
    with pytest.raises(TypeError):
        c.assign_civil_sui(list(moons), qi)
    with pytest.raises(TypeError):
        c.assign_civil_sui((0.0, *moons[1:]), qi)
    with pytest.raises(ValueError):
        c.assign_civil_sui(moons, qi[:-1])


def test_all_four_entry_dates_match_original_without_using_mean_month_slots():
    result = c.gujin_four_extras_calendar(F("116147.0196"))
    for key, month, day in [
        ("purple", 1, 25),
        ("apogee", 3, 8),
        ("rahu", 3, 12),
        ("ketu", 3, 14),
    ]:
        factor = result["factors"][key]
        date = factor["source_calendar_date_under_named_policy"]
        assert (date["month_number"], date["day"], date["is_leap_month"]) == (
            month,
            day,
            False,
        )
        assert factor["modern_lunar_date"] is None


@pytest.mark.parametrize(
    "position,month,day",
    [
        ("before_midnight", 4, 29),
        ("midnight", 5, 1),
        ("before_moon", 5, 1),
        ("after_cycle", None, None),
    ],
)
def test_entry_event_assignment_searches_civil_months(
    worked, monkeypatch, position, month, day
):
    winter = F(worked["winter_source_day_counter_exact"])
    row = worked["month_assignment"]["months"][7]
    midnight = F(row["start_source_day_integer"])
    event = {
        "before_midnight": midnight - F(1, 10**20),
        "midnight": midnight,
        "before_moon": winter
        + F(row["conjunction_offset_from_winter_days_exact"])
        - F(1, 10**20),
        "after_cycle": F(
            worked["month_assignment"]["months"][-1]["next_start_source_day_integer"]
        ),
    }[position]
    monkeypatch.setattr(c, "gujin_fixed_qice_months", lambda _: worked)
    monkeypatch.setattr(
        c,
        "four_extras_source_days",
        lambda _: {
            "factors": {
                "synthetic": {"days_until_next_entry_exact": str(event - winter)}
            }
        },
    )
    factor = c.gujin_four_extras_calendar(F("116147.0196"))["factors"]["synthetic"]
    date = factor["source_calendar_date_under_named_policy"]
    if month is None:
        assert date is None and factor["status"] == "outside_or_unresolved_cycle"
    else:
        assert (date["month_number"], date["day"]) == (month, day)


def test_missing_printed_conjunction_propagates_to_months_and_all_four_dates(
    monkeypatch,
):
    original = c.gujin_table_conjunction

    def missing(middle, index):
        result = original(middle, index)
        if index == 6:
            result["research_conjunction_offset_from_winter_days_exact"] = None
        return result

    monkeypatch.setattr(c, "gujin_table_conjunction", missing)
    result = c.gujin_four_extras_calendar(F("116147.0196"))
    assert (
        result["calendar"]["month_assignment"]["reason"]
        == "missing_required_conjunction_boundary"
    )
    assert all(
        f["source_calendar_date_under_named_policy"] is None
        for f in result["factors"].values()
    )


@pytest.mark.parametrize(
    "elapsed,gap", [(99, F(".01")), (100, F(".0001")), (318, F(".0003"))]
)
def test_cli_preserves_fixed_qice_and_reports_independent_year_accumulation(
    capsys, monkeypatch, elapsed, gap
):
    monkeypatch.setattr(
        sys, "argv", ["audit_guolao_intercalation.py", "--elapsed-years", str(elapsed)]
    )
    assert (
        runpy.run_path(str(ROOT / "scripts/audit_guolao_intercalation.py"))["main"]()
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    diagnostic = result["year_accumulation_diagnostic"]
    assert F(diagnostic["printed_24_qice_minus_that_increment_days_exact"]) == gap
    assert not diagnostic["qice_rescaled_or_endpoint_forced"]
    assert F(result["qice_days_exact"]) * 24 == F("365.2425")


def test_profile_constants_not_silently_rescaled(tmp_path, monkeypatch):
    data = json.loads(c.DATA.read_bytes())
    data["qice_days"] = "15.218425"
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(c, "DATA", path)
    with pytest.raises(ValueError):
        c.gujin_fixed_qice_months(F("116147.0196"))
