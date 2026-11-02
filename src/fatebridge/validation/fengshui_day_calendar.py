"""Test explicit calendar-selection hypotheses, without certifying a selector.

The observed day labels and term dates come from two astronomical institutions.
Neither institution supplies, or validates, a Feng Shui daily-star prediction.
"""

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core import almanac
from fatebridge.core.fengshui.calendar import solar_term_resolution
from fatebridge.validation.fengshui_day_hour import audit_day_hour_reference

_PALACES = dict(
    zip("中乾兌艮離坎坤震巽", ("C", "NW", "W", "NE", "S", "N", "SW", "E", "SE"))
)
_TERMS = (
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
)
_CAPTURE_NAMES = {"reference.json"} | {
    f"{source}-{year}.{extension}"
    for year in (2025, 2026)
    for source, extension in (("naoj-days", "html"), ("hko-calendar", "pdf"))
}


def load_day_calendar_reference(folder: Path) -> dict[str, Any]:
    hashes = json.loads((folder / "hashes.json").read_text())
    if set(hashes) != _CAPTURE_NAMES:
        raise ValueError("Incomplete independent calendar capture")
    for name, digest in hashes.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Independent calendar capture changed: {name}")
    reference = json.loads((folder / "reference.json").read_text())
    if not isinstance(reference, dict):
        raise ValueError("Calendar reference must be a JSON object")
    captured: list[dict[str, str]] = []
    for year in (2025, 2026):
        html = (folder / f"naoj-days-{year}.html").read_bytes().decode("euc-jp")
        rows = re.findall(
            r"<tr><td>(\d{4}/\d{2}/\d{2})</td>\s*<td>\d+</td>"
            r"\s*<td>[^<]+</td>\s*<td>"
            r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])</td>",
            html,
        )
        if len(rows) != 365:
            raise ValueError("NAOJ capture must contain its complete published year")
        captured.extend({"date": d.replace("/", "-"), "ganzhi": g} for d, g in rows)
    if captured != reference["days"]:
        raise ValueError("Day transcription differs from the captured NAOJ response")
    return reference


def _validate(reference: dict[str, Any]) -> None:
    days = reference["days"]
    expected_dates = [
        (date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(730)
    ]
    if [row["date"] for row in days] != expected_dates:
        raise ValueError("Require every published day in 2025 and 2026, in order")
    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    labels = [row["ganzhi"] for row in days]
    if any(g not in cycle for g in labels):
        raise ValueError("Invalid printed day ganzhi")
    offset = cycle.index(labels[0])
    if any(g != cycle[(offset + i) % 60] for i, g in enumerate(labels)):
        raise ValueError("Published day labels are not continuous")
    terms = reference["terms"]
    if len(terms) != 48 or [
        (date.fromisoformat(t["date"]).year, t["term"]) for t in terms
    ] != [(y, t) for y in (2025, 2026) for t in _TERMS]:
        raise ValueError("Require all 48 distinct, ordered published solar terms")
    if [t["date"] for t in terms] != sorted(t["date"] for t in terms):
        raise ValueError("Published solar terms are not chronologically ordered")
    if (reference["probe_start"], reference["probe_end"]) != (
        "2026-01-01",
        "2026-12-31",
    ):
        raise ValueError("Do not shorten the declared civil-date probe")


def _printed_chart(
    table: dict[str, Any], elapsed: int, days: list[str]
) -> dict[str, Any]:
    cycle, index = divmod(elapsed, 60)
    inverted = (
        next((c for c in table["inverted_cells"] if c["ganzhi"] == days[index]), None)
        if cycle == 2
        else None
    )
    column = inverted["column"] if inverted else index % 9
    return {
        "table": table["id"],
        "source_page": table["page"],
        "cycle": cycle,
        "ganzhi": days[index],
        "inverted_cell": inverted is not None,
        "palaces": {
            _PALACES[row[column]]: table["star_columns"][cycle][rank]
            for rank, row in enumerate(table["palace_rows"])
        },
    }


def audit_calendar_selection_hypotheses(
    reference: dict[str, Any], printed: dict[str, Any]
) -> dict[str, Any]:
    """Compare actual calendars and expose where two incomplete policies fail.

    For this experiment only, entry-jie *civil dates* are inclusive. Observed
    Jiazi days are classified by the printed early-entry clauses. Policy A
    takes only the latest Jiazi and the first column. Policy B retains full
    180-day windows, provided every elapsed column's Jiazi heading agrees.
    A counterexample rejects the policy as sufficient; it is not evidence of
    a contradiction in the book, or a license to select its other candidate.
    """
    _validate(reference)
    table_check = audit_day_hour_reference(printed)
    if not table_check["table_arithmetic_and_shared_flight_conform"]:
        raise ValueError("Cannot research dates with a nonconforming printed table")
    day_differences = []
    for observed in reference["days"]:
        d = date.fromisoformat(observed["date"])
        actual = almanac.get_day_ganzhi(d.year, d.month, d.day)
        if actual != observed["ganzhi"]:
            day_differences.append({**observed, "engine_ganzhi": actual})
    term_differences = []
    term_resolutions = []
    for observed in reference["terms"]:
        resolution = solar_term_resolution(
            int(observed["date"][:4]), observed["term"], "Asia/Hong_Kong"
        )
        term_resolutions.append({**observed, **resolution})
        if resolution["moment"][:10] != observed["date"]:
            term_differences.append({**observed, "engine_moment": resolution["moment"]})

    clauses = printed["calendar_header_clauses"]
    # E.g. the winter heading's following 立春 sends Jiazi to 雨水.
    term_to_header = {c["terms"][0]: key for key, c in clauses.items()}
    entry_to_header = {
        c["following_term"]: term_to_header[c["jiazi_after_following_term_uses"]]
        for c in clauses.values()
    }
    entries = [
        (date.fromisoformat(t["date"]), entry_to_header[t["term"]])
        for t in reference["terms"]
        if t["term"] in entry_to_header
    ]
    tables = {t["header_keys"][0]: t for t in printed["daily_tables"]}
    anchors = []
    for observed in reference["days"]:
        if observed["ganzhi"] != "甲子":
            continue
        d = date.fromisoformat(observed["date"])
        eligible = [e for e in entries if e[0] <= d]
        if eligible:
            anchors.append((d, eligible[-1][1]))
    by_date = dict(anchors)
    days = [g for row in printed["normal_ganzhi_rows"] for g in row]
    covered_cells = set()
    ambiguity = []
    gaps = []
    daily_rows = []
    for observed in reference["days"]:
        if not reference["probe_start"] <= observed["date"] <= reference["probe_end"]:
            continue
        d = date.fromisoformat(observed["date"])
        preceding = [(a, key) for a, key in anchors if a <= d]
        anchor, key = preceding[-1]
        latest = _printed_chart(tables[key], (d - anchor).days, days)
        covered_cells.add((latest["table"], latest["cycle"], latest["ganzhi"]))
        candidates = []
        for a, header in preceding:
            elapsed = (d - a).days
            if elapsed >= 180:
                continue
            table = tables[header]
            if any(
                by_date.get(a + timedelta(days=60 * i)) != table["header_keys"][i]
                for i in range(elapsed // 60 + 1)
            ):
                continue
            chart = _printed_chart(table, elapsed, days)
            if chart["ganzhi"] != observed["ganzhi"]:
                raise ValueError("Observed date does not match its table day label")
            candidates.append({"anchor_date": a.isoformat(), **chart})
        distinct = {tuple(sorted(c["palaces"].items())) for c in candidates}
        row = {
            **observed,
            "latest_first_column": latest,
            "full_window_candidates": candidates,
            "distinct_full_charts": len(distinct),
            "source_certified_selection": False,
        }
        daily_rows.append(row)
        if len(distinct) > 1:
            ambiguity.append(row)
        if not distinct:
            gaps.append(observed["date"])
    unseen_inverted = [
        {"table": t["id"], "cycle": 2, "ganzhi": cell["ganzhi"]}
        for t in printed["daily_tables"]
        for cell in t["inverted_cells"]
        if (t["id"], 2, cell["ganzhi"]) not in covered_cells
    ]
    return {
        "protocol": reference["protocol"],
        "independent_published_day_cases": len(reference["days"]),
        "day_ganzhi_differences": day_differences,
        "independent_published_term_date_cases": len(reference["terms"]),
        "term_date_differences": term_differences,
        "term_resolutions": term_resolutions,
        "astronomical_acceptance_scope": "published_civil_dates_only_not_second_precision_or_fengshui_selection",
        "civil_dates_probed": len(daily_rows),
        "candidate_policy_scope": "explicit_unverified_hypotheses_not_source_certified_alternatives",
        "hypothesis_civil_day_policy": "entry_jie_date_inclusive_no_hour_or_solar_time",
        "latest_first_column": {
            "distinct_printed_day_cells_reached": len(covered_cells),
            "of_total_printed_day_cells": 1080,
            "unreached_inverted_cells": unseen_inverted,
            "complete_table_coverage": False,
        },
        "retained_full_windows": {
            "ambiguous_civil_dates": len(ambiguity),
            "uncovered_civil_dates": gaps,
            "sufficient_for_unique_selection": not ambiguity and not gaps,
            "ambiguity_witness": next(
                (r for r in ambiguity if r["date"] == "2026-06-19"),
                ambiguity[0] if ambiguity else None,
            ),
        },
        "daily_hypothesis_results": daily_rows,
        "independent_calendar_comparison_passed": not day_differences
        and not term_differences,
        "calendar_table_selection_verified": False,
        "day_hour_boundary_policy_verified": False,
        "included_in_complete_calendar_acceptance": False,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
    }
