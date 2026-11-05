"""Check complete frozen historical passages against three fixed calendars.

These source observations are related narratives, not independent Taiyi cases.
No calendar is selected by fit and no original month is silently emended.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.validation.yuanjia_calendar import yuanjia_mean_year
from scripts.taiyi.audit_taiyi_day_epoch import julian_jdn

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_calendar_context_v37"
FREEZE_SHA256 = "9540b3fdbdbda3f644d8f032bf2ead04814d64ac2880af8a87f0c22695b37bda"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]


def read_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"V37 source object required: {path.name}")
    return data


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V37 pinned source freeze changed")
    frozen = read_json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V37 source or prior evidence changed: {name}")
    return frozen


def compare_event(
    event: dict[str, Any], months: list[dict[str, Any]]
) -> dict[str, Any]:
    """Require an existing date before assigning a chronological position."""
    selected = [
        m
        for m in months
        if (m["month"], m["is_leap_month"]) == (event["month"], event["is_leap_month"])
    ]
    result: dict[str, Any] = {
        "source": event,
        "matching_months": len(selected),
        "candidate_day_number": None,
        "day_number": None,
        "date_exists": False,
        "explicit_shuo_satisfied": None,
        "day_position_in_year": None,
        "joint_source_date_satisfied": False,
    }
    if len(selected) != 1:
        result["reason"] = "missing_month" if not selected else "ambiguous_month"
        return result
    month = selected[0]
    if type(month["length"]) is not int or month["length"] not in (29, 30):
        raise ValueError("A complete historical month must have29 or30 days")
    day = (CYCLE.index(event["ganzhi"]) - CYCLE.index(month["first_ganzhi"])) % 60 + 1
    exists = day <= month["length"]
    result.update(
        candidate_day_number=day,
        day_number=day if exists else None,
        date_exists=exists,
        explicit_shuo_satisfied=(
            (day == 1 if exists else None) if event["explicit_shuo"] else None
        ),
        day_position_in_year=month["start_day_in_year"] + day - 1 if exists else None,
        joint_source_date_satisfied=exists and (not event["explicit_shuo"] or day == 1),
        reason="existing_date" if exists else "ganzhi_outside_month",
    )
    return result


def compare_chronology(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Missing dates make an edge unknown, never a fabricated success."""
    edges = []
    for before, after in zip(observations, observations[1:]):
        first, last = before["day_position_in_year"], after["day_position_in_year"]
        edges.append(
            {
                "before": before["source"]["id"],
                "after": after["source"]["id"],
                "nondecreasing": (
                    last >= first if first is not None and last is not None else None
                ),
                "days_between": (
                    last - first if first is not None and last is not None else None
                ),
            }
        )
    return edges


def candidates(root: Path) -> list[dict[str, Any]]:
    rows = read_json(
        root / "tests/fixtures/taiyi_jinjing_v35/historical-months-initial.json"
    )["months"]
    first = next(r for r in rows if r["lunar_year"] == 502)
    start = julian_jdn(first["julian_start"])
    printed = []
    for row, following in zip(rows, rows[1:]):
        if row["lunar_year"] != 502:
            continue
        begin, end = (
            julian_jdn(row["julian_start"]),
            julian_jdn(following["julian_start"]),
        )
        printed.append(
            {
                "month": row["month"],
                "is_leap_month": row["is_leap_month"],
                "length": end - begin,
                "first_ganzhi": CYCLE[row["printed_cycle_base"]],
                "start_day_in_year": begin - start,
            }
        )
    values: list[dict[str, Any]] = [{"id": "printed_501_505_table", "months": printed}]
    anchor = read_json(root / "tests/fixtures/taiyi_jinjing_v35/readings.json")[
        "year_anchor"
    ]
    elapsed = anchor["elapsed_years_from_upper_epoch"] + 502 - anchor["ce_year"]
    for assignment in ("civil_day", "exact_fraction"):
        year = yuanjia_mean_year(elapsed, middle_term_assignment=assignment)
        begin = year["records"][0]["day_within_ji"]
        values.append(
            {
                "id": "yuanjia_" + assignment,
                "months": [
                    {
                        "month": row["month"],
                        "is_leap_month": row["is_leap_month"],
                        "length": row["next_month_days"],
                        "first_ganzhi": row["first_ganzhi"],
                        "start_day_in_year": row["day_within_ji"] - begin,
                    }
                    for row in year["records"]
                ],
            }
        )
    return values


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    reading = read_json(corpus / "readings.json")
    calendars = candidates(root)
    if [c["id"] for c in calendars] != reading["three_fixed_calendar_candidates"]:
        raise ValueError("V37 must retain all three predeclared candidates in order")
    comparisons = []
    for calendar in calendars:
        cohorts = []
        for cohort in reading["cohorts"]:
            observations = [
                compare_event(e, calendar["months"]) for e in cohort["events"]
            ]
            chronology = compare_chronology(observations)
            cohorts.append(
                {
                    "source_id": cohort["source_id"],
                    "observations": observations,
                    "required_date_observations": len(observations),
                    "existing_dates": sum(o["date_exists"] for o in observations),
                    "joint_source_date_observations_satisfied": sum(
                        o["joint_source_date_satisfied"] for o in observations
                    ),
                    "chronology": chronology,
                    "chronology_edges_required": len(chronology),
                    "chronology_edges_satisfied": sum(
                        e["nondecreasing"] is True for e in chronology
                    ),
                    "chronology_edges_contradicted": sum(
                        e["nondecreasing"] is False for e in chronology
                    ),
                    "chronology_edges_unknown": sum(
                        e["nondecreasing"] is None for e in chronology
                    ),
                    "complete_selected_passage_compatible": all(
                        o["joint_source_date_satisfied"] for o in observations
                    )
                    and all(e["nondecreasing"] is True for e in chronology),
                }
            )
        comparisons.append(
            {
                **calendar,
                "cohorts": cohorts,
                "all_three_selected_passages_compatible": all(
                    c["complete_selected_passage_compatible"] for c in cohorts
                ),
            }
        )
    return {
        "source_freeze_sha256": FREEZE_SHA256,
        "frozen_new_files": len(frozen["files"]),
        "prior_pinned_files": len(frozen["prior_sources"]),
        "source_date_observations": reading["total_event_date_observations"],
        "source_cohorts": [
            {"source_id": c["source_id"], "date_observations": len(c["events"])}
            for c in reading["cohorts"]
        ],
        "calendar_comparisons": comparisons,
        "any_candidate_satisfies_all_selected_passages": any(
            c["all_three_selected_passages_compatible"] for c in comparisons
        ),
        "calendar_selected_by_fit": False,
        "month_label_or_source_emendation_adjudicated": False,
        "source_reading_is_independent_expert_review": False,
        "chronicle_observations_are_independent_taiyi_cases": False,
        "new_complete_dated_taiyi_cases_passed": 0,
        "new_model_invocations": 0,
        "production_calendar_changed": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "All42 frozen date observations and all39 chronology edges per candidate. Related source narratives remain separate, including impossible dates and unassessed edges. No calendar selection, emendation, absolute epoch proof or whole Taiyi acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
