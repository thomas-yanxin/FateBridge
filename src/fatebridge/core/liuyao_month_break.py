"""Same-day value qualifies the month-only opposition, not every other harm."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_relations import BRANCHES

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-month-break-v24.json")
    .read_text(encoding="utf-8")
)


def raw_month_break(branch: str, month: str) -> bool:
    return (BRANCHES.index(branch) - BRANCHES.index(month)) % 12 == 6


def day_value_exception(branch: str, month: str, day: str) -> bool:
    return raw_month_break(branch, month) and branch == day


def month_opposition_applies(branch: str, month: str, day: str) -> bool:
    """Only the month's present opposition; other actors remain independent."""
    return raw_month_break(branch, month) and not day_value_exception(
        branch, month, day
    )


def observation(branch: str, month: str, day: str) -> dict[str, Any]:
    return {
        "branch": branch,
        "raw_month_break": raw_month_break(branch, month),
        "day_branch": day,
        "day_value_exception": day_value_exception(branch, month, day),
        "calendar_month_opposition": month_opposition_applies(branch, month, day),
        "source_url": PROFILE["source"]["url"] + "#page=68",
    }


def build_month_break_conditions(
    lines: list[dict[str, Any]],
    assessment: dict[str, Any],
    month: str,
    day: str,
    selected: dict[str, Any] | None,
    hidden: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = []
    for row in lines:
        p = row["position"]
        original = observation(row["branch"], month, day)
        other = deepcopy(assessment["lines"][p - 1]["strength"]["oppositions"])
        original.update(
            position=p,
            retained_other_oppositions=other,
            status=(
                "other_conditions_require_resolution"
                if original["day_value_exception"] and other
                else (
                    "day_value_month_opposition_excluded"
                    if original["day_value_exception"]
                    else "no_day_value_exception"
                )
            ),
            changed=(
                observation(row["changed_branch"], month, day)
                if row["change"]
                else None
            ),
            source_path=f"liuyao_evidence.conditional_analysis.month_break_conditions.lines.{p-1}",
        )
        rows.append(original)
    return {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": PROFILE["source"]["url"] + "#page=68",
        "source_sha256": PROFILE["source"]["sha256"],
        "clauses": deepcopy(PROFILE["clauses"]),
        "lines": rows,
        "hidden": [
            {
                "position": h["position"],
                "hidden": observation(h["branch"], month, day),
                "flying": observation(lines[h["position"] - 1]["branch"], month, day),
            }
            for h in hidden or []
        ],
        "focus": (
            deepcopy(rows[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        "scope": "原月破位置保留；同支日建只解除所列月令反制。额外明暗动克、回头克、合绊等独立保留，不能从本项豁免推出全局不破、旺相或现实成败。变支只核实际本位，伏飞各核自身。",
    }
