"""Bounded current-day void-fill license for directed control only."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-void-control-v31.json")
    .read_text(encoding="utf-8")
)
ROOT = "liuyao_evidence.conditional_analysis.control_conditions.void_fill_qualification"


def current_void_fill_control(
    row: dict[str, Any],
    facts: dict[str, Any],
    oppositions: list[dict[str, Any]],
    day: str,
) -> bool:
    """The same day may activate a void static source while controlling it."""
    return bool(
        not row["change"]
        and facts["is_xunkong"]
        and facts["is_day_clash"]
        and not facts["is_month_clash"]
        and oppositions
        and all(
            a["location"] == "day"
            and a["branch"] == day
            and a["reason"] == "日月克爻"
            and a.get("harm_condition_match", True) is True
            for a in oppositions
        )
    )


def qualification_evidence() -> dict[str, Any]:
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_sha256=PROFILE["source"]["sha256"],
        source_urls=[
            PROFILE["source"]["url"] + "#page=" + str(c["pdf_page"])
            for c in PROFILE["clauses"]
        ],
        clauses=deepcopy(PROFILE["clauses"]),
        precedence=PROFILE["precedence"],
        scope=PROFILE["scope"],
    )
