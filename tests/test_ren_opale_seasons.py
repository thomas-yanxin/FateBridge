"""Frozen source completeness and clock diagnostics cannot erase older failures."""

import copy
import importlib.util
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ren_opale", ROOT / "scripts/audit_ren_opale_seasons.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_complete_source_annotations_and_overlapping_denominators():
    ref = AUDIT.reference()
    assert {k: len(v) for k, v in ref.items()} == {
        "seasons": 504,
        "documented_tt": 244,
        "source_clock_tt": 288,
    }
    assert len({r["id"] for rows in ref.values() for r in rows}) == 504
    for year in range(1900, 2026):
        rows = [r for r in ref["seasons"] if r["year"] == year]
        assert [r["term"] for r in rows] == list(AUDIT.EVENTS.values())
        assert {r["timescale"] for r in rows} == {"UT1" if year < 1972 else "UTC"}
    # An independently printed label, not a production-generated expectation.
    row = next(r for r in ref["seasons"] if r["id"] == "1955-VernalEquinox")
    assert row["published_label"] == "1955-03-21T09:35:04"
    clock = next(r for r in ref["source_clock_tt"] if r["id"] == row["id"])
    assert clock["tt_minus_ut1_seconds"] == 30.466894942
    assert clock["expected_tt_label"] == "1955-03-21T09:35:34.466895"


@pytest.mark.parametrize("name", AUDIT.FROZEN)
@pytest.mark.parametrize("change", ["source", "freeze", "inventory"])
def test_frozen_references_reject_edits_resealing_and_extra_files(
    tmp_path, name, change
):
    target = tmp_path / name
    shutil.copytree(AUDIT.FIXTURES / name, target)
    path = (
        target
        / {
            "source": "reference.json",
            "freeze": "freeze.json",
            "inventory": "extra.json",
        }[change]
    )
    path.write_text(path.read_text() + " " if path.exists() else "{}")
    with pytest.raises(ValueError, match="OPALE"):
        AUDIT.frozen(target, AUDIT.FROZEN[name])


@pytest.mark.parametrize(
    "change", ["omitted", "duplicate", "wrong_scale", "wrong_year", "aware_label"]
)
def test_raw_seasons_refuse_a_pruned_or_relabelled_cohort(change):
    data = json.loads(
        (AUDIT.FIXTURES / "ren_opale_seasons_v1/historical-ut1.json").read_text()
    )
    if change == "omitted":
        data["response"]["data"].pop(220)
    elif change == "duplicate":
        data["response"]["data"][1] = data["response"]["data"][0]
    elif change == "wrong_scale":
        data["response"]["timescale"] = "UTC"
    elif change == "wrong_year":
        data["request"]["year"] = 1901
    else:
        data["response"]["data"][0]["date"] += "+00:00"
    with pytest.raises(ValueError):
        AUDIT.season_cases(data, 1900, 1972, "UT1", "historical-ut1.json")


def synthetic_clock(moment):
    """A mechanism-only clock; not an astronomical reference."""
    jd = AUDIT.julian_day(
        moment.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    )
    return SimpleNamespace(jd_tt=jd, jd_ut1=jd, method="synthetic_test_only")


@pytest.mark.parametrize(
    "seconds, passed", [(1, True), (-1, True), (1.000001, False), (-1.000001, False)]
)
def test_original_one_second_threshold_and_utc_offset_are_literal(seconds, passed):
    case = next(r for r in AUDIT.reference()["seasons"] if r["timescale"] == "UTC")
    utc = datetime.fromisoformat(case["published_label"]).replace(tzinfo=timezone.utc)
    moment = (utc + timedelta(seconds=seconds)).astimezone(timezone(timedelta(hours=8)))
    actual = {
        (case["year"], case["term"]): {
            "actual": moment.isoformat(),
            "provider": "swisseph",
        }
    }
    report = AUDIT.comparison([case], actual, "seasons", synthetic_clock)
    assert report["compared_count"] == 1
    assert report["comparisons"][0]["difference_seconds"] == seconds
    assert report["all_comparisons_passed"] is passed


@pytest.mark.parametrize(
    "route, count", [("seasons", 504), ("documented_tt", 244), ("source_clock_tt", 288)]
)
def test_missing_production_events_keep_the_full_declared_denominator(route, count):
    report = AUDIT.comparison(AUDIT.reference()[route], {}, route, synthetic_clock)
    assert report["expected_count"] == count and report["compared_count"] == 0
    assert len(report["calculation_errors"]) == count
    assert report["maximum_absolute_difference_seconds"] is None
    assert not report["all_comparisons_passed"]


@pytest.mark.parametrize("kind", ["naive", "fallback", "nonfinite", "exception"])
def test_unusable_calculations_remain_errors(kind):
    cases = AUDIT.reference()["source_clock_tt"][:1]
    case = cases[0]
    actual = {
        (case["year"], case["term"]): {
            "actual": case["ut1_label"] + ("" if kind == "naive" else "+00:00"),
            "provider": "fallback" if kind == "fallback" else "swisseph",
        }
    }

    def convert(moment):
        if kind == "exception":
            raise RuntimeError("clock unavailable")
        clock = synthetic_clock(moment)
        if kind == "nonfinite":
            clock.jd_tt = float("nan")
        return clock

    report = AUDIT.comparison(cases, actual, "source_clock_tt", convert)
    assert report["expected_count"] == len(report["calculation_errors"]) == 1
    assert not report["all_comparisons_passed"]


def test_later_tt_diagnostics_cannot_overwrite_the_original_minute_gate():
    pmo = {
        "expected_count": 3024,
        "minute_criterion": {"max_absolute_difference_seconds": 30},
        "comparisons": [],
        "minute_failure_count": 21,
        "all_performed_comparisons_passed": False,
    }
    preserved = copy.deepcopy(pmo)
    report = AUDIT.assemble(pmo, AUDIT.reference(), synthetic_clock)
    assert report["original_pmo"] == preserved and pmo == preserved
    assert not report["all_performed_comparisons_passed"]
    assert (
        not report["goal_complete"]
        and not report["full_supported_calendar_domain_certified"]
    )
    assert (
        report["new_unique_astronomical_events"] == report["physical_observations"] == 0
    )
    assert report["unique_astronomical_events_across_all_routes"] == 3024
    assert report["model_invocations"] == 0
    assert not report["criterion_is_source_accuracy_guarantee"]
    for key, value in [
        ("expected_count", 3003),
        ("minute_criterion", {"max_absolute_difference_seconds": 31}),
    ]:
        changed = dict(pmo, **{key: value})
        with pytest.raises(ValueError, match="original complete PMO"):
            AUDIT.assemble(changed, AUDIT.reference(), synthetic_clock)
