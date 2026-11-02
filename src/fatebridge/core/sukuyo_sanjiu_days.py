"""Personal-day clauses; preserve volume, action stage and another saying."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_sanjiu_days.json"


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def personal_day_witnesses(relation: str) -> dict[str, Any]:
    captured = load_source(SOURCE)
    bundle = captured.data
    record = next(
        (row for row in bundle["relation_witnesses"] if row["relation"] == relation),
        None,
    )
    if record is None:
        raise ValueError("未知的三九日关系")
    return {
        "ruleset_id": bundle["id"],
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": captured.sha256,
        **deepcopy(record),
        "priority_clause": deepcopy(bundle["priority_clause"]),
        "priority_clause_applied_to_aggregate": False,
        "scope": bundle["scope"],
    }
