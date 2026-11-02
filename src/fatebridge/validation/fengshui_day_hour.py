"""Collate printed day/hour grids without claiming a date-driven chart engine."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.fengshui.xuankong import _fly

_PALACES = {
    "中": "C",
    "乾": "NW",
    "兌": "W",
    "艮": "NE",
    "離": "S",
    "坎": "N",
    "坤": "SW",
    "震": "E",
    "巽": "SE",
}
_TABLE_TAILS = {
    "upper_yang": 0,
    "upper_yin": 0,
    "middle_yang": 6,
    "middle_yin": 6,
    "lower_yang": 12,
    "lower_yin": 12,
}
_STEMS = "甲乙丙丁戊己庚辛壬癸"
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def load_day_hour_reference(folder: Path) -> dict[str, Any]:
    """Validate the stored capture before interpreting any transcription."""
    hashes = json.loads((folder / "hashes.json").read_text(encoding="utf-8"))
    required = {"reference.json"} | {
        f"page-{page}.png" for page in (845, 847, 849, 851, 853, 855, 856, 857)
    }
    if set(hashes) != required:
        raise ValueError("Incomplete day/hour source capture manifest")
    for name, expected in hashes.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Day/hour source capture changed: {name}")
    reference = json.loads((folder / "reference.json").read_text(encoding="utf-8"))
    if not isinstance(reference, dict):
        raise ValueError("Day/hour reference must be a JSON object")
    return reference


def _grid(rows: Any) -> None:
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("Printed palace grid requires all nine rows")
    if any(
        not isinstance(row, str) or len(row) != 9 or set(row) != set(_PALACES)
        for row in rows
    ):
        raise ValueError("Every printed palace row requires nine distinct palaces")


def _stars(values: Any) -> None:
    if (
        not isinstance(values, list)
        or len(values) != 9
        or any(type(value) is not int for value in values)
        or set(values) != set(range(1, 10))
    ):
        raise ValueError("Printed star column requires the literal nine integers")


def _validate(reference: dict[str, Any]) -> list[str]:
    day_rows = reference["normal_ganzhi_rows"]
    if [len(row) for row in day_rows] != [9, 9, 9, 9, 9, 9, 6]:
        raise ValueError("Printed ganzhi grid requires every one of the sixty days")
    days = [day for row in day_rows for day in row]
    if days != [_STEMS[i % 10] + _BRANCHES[i % 12] for i in range(60)]:
        raise ValueError("Printed ganzhi day labels are not the sixty-day sequence")
    tables = reference["daily_tables"]
    if len(tables) != 6 or {table["id"] for table in tables} != set(_TABLE_TAILS):
        raise ValueError("All six named daily tables are required")
    for table in tables:
        if table["flight"] not in {"forward", "reverse"}:
            raise ValueError("Unknown printed flight direction")
        _grid(table["palace_rows"])
        if len(table["star_columns"]) != 3:
            raise ValueError("All three printed star columns are required")
        for values in table["star_columns"]:
            _stars(values)
        inverted = table["inverted_cells"]
        count = _TABLE_TAILS[table["id"]]
        if len(inverted) != count or {item["ganzhi"] for item in inverted} != set(
            days[60 - count :]
        ):
            raise ValueError("Printed inverted branch cells are incomplete")
        for cell in inverted:
            row, col = cell["row"], cell["column"]
            if (
                type(row) is not int
                or type(col) is not int
                or not 0 <= row < 7
                or not 0 <= col < len(day_rows[row])
            ):
                raise ValueError("Inverted branch has no printed cell position")
            expected_rank = 2 * (60 - count) - 1 - days.index(cell["ganzhi"])
            if row * 9 + col != expected_rank:
                raise ValueError(
                    "Inverted branch glyph does not follow the printed tail"
                )
        if len(table["header_keys"]) != 3 or any(
            key not in reference["calendar_header_clauses"]
            for key in table["header_keys"]
        ):
            raise ValueError("Printed calendar clauses are incomplete")
    hour = reference["hour_table"]
    _grid(hour["palace_rows"])
    if len(hour["groups"]) != 3:
        raise ValueError("All three printed day-branch groups are required")
    all_day_branches = "".join(
        group["printed_day_branches"] for group in hour["groups"]
    )
    if len(all_day_branches) != 12 or set(all_day_branches) != set(_BRANCHES):
        raise ValueError("Printed day groups must cover the twelve branches once")
    for group in hour["groups"]:
        rows = group["hour_rows"]
        hours = "".join(rows)
        if len(rows) != 9 or len(hours) != 12 or set(hours) != set(_BRANCHES):
            raise ValueError("Printed hour rows must cover all twelve hours once")
    for mode in ("yang", "yin"):
        _stars(hour["star_columns"][mode])
    return days


def audit_day_hour_reference(reference: dict[str, Any]) -> dict[str, Any]:
    """Check all supplied table positions, including the inverted terminal days.

    The arithmetic model has a *confirmed table and cycle* as input. It has no
    policy selecting these from a date, solar term or day/hour boundary. Its
    local turn reflects the inverted branch glyphs; it does not establish that
    every civil date should turn at that point or change its spatial flight.
    """
    days = _validate(reference)
    differences: list[dict[str, Any]] = []
    daily_cases = hourly_cases = ignored_tail = daily_forward = hourly_forward = 0
    flipped_tail_flight = 0
    counterexamples: list[dict[str, Any]] = []
    for table in reference["daily_tables"]:
        sign = 1 if table["flight"] == "forward" else -1
        inverted = {item["ganzhi"]: item for item in table["inverted_cells"]}
        cutoff = 179 - len(inverted)
        last_index = 59 - len(inverted)
        last_star = table["star_columns"][2][last_index % 9]
        if (
            table["last_ordinary_ganzhi"] != days[last_index]
            or table["last_ordinary_star"] != last_star
        ):
            differences.append({"table": table["id"], "kind": "prose_end_mismatch"})
        terminal_col = inverted[days[-1]]["column"] if inverted else 59 % 9
        terminal_star = table["star_columns"][2][terminal_col]
        next_star = (terminal_star - sign - 1) % 9 + 1 if inverted else terminal_star
        next_term = reference["calendar_header_clauses"][table["header_keys"][2]][
            "jiazi_after_following_term_uses"
        ]
        if (
            table["following_anchor_star"] != next_star
            or table["following_anchor_term"] != next_term
        ):
            differences.append({"table": table["id"], "kind": "prose_join_mismatch"})
        for cycle in range(3):
            for index, day in enumerate(days):
                cell = inverted.get(day) if cycle == 2 else None
                col = cell["column"] if cell is not None else index % 9
                expected = {
                    _PALACES[row[col]]: table["star_columns"][cycle][r]
                    for r, row in enumerate(table["palace_rows"])
                }
                elapsed = cycle * 60 + index
                # First inverted day repeats the extremal star. Subtracting
                # immediately would introduce a one-day error in the tail.
                effective = (
                    elapsed if elapsed <= cutoff else cutoff - (elapsed - cutoff - 1)
                )
                center = (table["star_columns"][0][0] + sign * effective - 1) % 9 + 1
                actual = _fly(center, sign == 1)
                where = {"table": table["id"], "cycle": cycle, "ganzhi": day}
                if actual != expected:
                    differences.append(
                        {**where, "expected": expected, "actual": actual}
                    )
                naive_center = (
                    table["star_columns"][0][0] + sign * elapsed - 1
                ) % 9 + 1
                if _fly(naive_center, sign == 1) != expected:
                    ignored_tail += 1
                    if len(counterexamples) < 8:
                        counterexamples.append(
                            {
                                **where,
                                "printed_center": expected["C"],
                                "ignoring_inverted_tail_center": naive_center,
                            }
                        )
                daily_forward += int(_fly(center, True) != expected)
                if elapsed > cutoff:
                    flipped_tail_flight += int(_fly(center, sign != 1) != expected)
                daily_cases += 1
    hour = reference["hour_table"]
    for mode, sign, starts in (("yang", 1, (1, 4, 7)), ("yin", -1, (9, 6, 3))):
        for group_index, group in enumerate(hour["groups"]):
            for index, branch in enumerate(_BRANCHES):
                row_index = next(
                    r
                    for r, branches in enumerate(group["hour_rows"])
                    if branch in branches
                )
                expected = {
                    _PALACES[glyph]: star
                    for glyph, star in zip(
                        hour["palace_rows"][row_index], hour["star_columns"][mode]
                    )
                }
                center = (starts[group_index] + sign * index - 1) % 9 + 1
                actual = _fly(center, sign == 1)
                if actual != expected:
                    differences.append(
                        {
                            "mode": mode,
                            "day_branches": group["printed_day_branches"],
                            "hour": branch,
                            "expected": expected,
                            "actual": actual,
                        }
                    )
                hourly_forward += int(_fly(center, True) != expected)
                hourly_cases += 1
    return {
        "audit_id": "shen_day_hour_literal_table_arithmetic_v1",
        "daily_table_pages": 6,
        "hour_table_pages": 1,
        "daily_confirmed_table_cycle_cases": daily_cases,
        "hour_confirmed_day_group_cases": hourly_cases,
        "palace_relations_checked": (daily_cases + hourly_cases) * 9,
        "local_prose_endpoint_and_join_checks": 12,
        "differences": differences,
        "table_arithmetic_and_shared_flight_conform": not differences,
        "countermodels": {
            "ignore_inverted_tail_mismatching_charts": ignored_tail,
            "always_forward_daily_mismatching_charts": daily_forward,
            "always_forward_hourly_mismatching_charts": hourly_forward,
            "flip_spatial_flight_in_inverted_tail_mismatching_charts": flipped_tail_flight,
            "examples": counterexamples,
        },
        "input_scope": "confirmed_printed_table_cycle_or_hour_group_not_civil_datetime",
        "calendar_table_selection_verified": False,
        "day_hour_boundary_policy_verified": False,
        "new_public_daily_or_hourly_tool": False,
        "whole_book_conformity_established": False,
        "independent_human_expert_review": False,
        "real_world_prediction_established": False,
        "included_in_complete_calendar_acceptance": False,
    }
