"""Read frozen source cases without converting exposure or unknowns into passes."""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

ORDER = ("year", "month", "day", "hour")


def pillar_values(case: Mapping[str, Any]) -> list[str]:
    raw = case["pillars"]
    values = [raw[k] for k in ORDER] if isinstance(raw, dict) else list(raw)
    if len(values) != 4 or any(
        not isinstance(p, str)
        or len(p) != 2
        or p[0] not in HEAVENLY_STEMS
        or p[1] not in EARTHLY_BRANCHES
        for p in values
    ):
        raise ValueError("Literal source pillars are malformed; do not guess a repair")
    return values


def input_consistency(values: list[str]) -> dict[str, Any]:
    """Check modern internal formulas, never infer a historical birth instant."""
    positions = [
        (HEAVENLY_STEMS.index(p[0]), EARTHLY_BRANCHES.index(p[1])) for p in values
    ]
    year, month, day, hour = positions
    expected_month = HEAVENLY_STEMS[(2 * (year[0] % 5) + 2 + (month[1] - 2) % 12) % 10]
    expected_hour = HEAVENLY_STEMS[(2 * (day[0] % 5) + hour[1]) % 10]
    checks = {
        "sexagenary_pairs": all(s % 2 == b % 2 for s, b in positions),
        "month_stem_matches_recorded_year": values[1][0] == expected_month,
        "hour_stem_matches_recorded_day": values[3][0] == expected_hour,
    }
    return {
        **checks,
        "all_three_modern_checks_match": all(checks.values()),
        "expected_month_stem_under_modern_rule": expected_month,
        "expected_hour_stem_under_modern_rule": expected_hour,
        "zi_hour_clock_and_day_boundary_unresolved": hour[1] == 0,
        "literal_source_changed": False,
        "historical_birth_datetime_verified": False,
        "scope": "五虎遁、五鼠遁及六十甲子内部关系核对；不认证录文、公历出生瞬间、子时口径或节后日序，不修改源柱。",
    }


def input_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row["pillars"])].append(
            {
                "group": row["group"],
                "id": row["id"],
                "label_status": row["label_status"],
                "expected_strength": row["expected_strength"],
            }
        )
    return {
        "distinct_four_pillar_inputs": len(grouped),
        "overlapping_input_records": len(rows) - len(grouped),
        "repeated_inputs": [
            {"pillars": list(p), "observations": v}
            for p, v in grouped.items()
            if len(v) > 1
        ],
        "conflicting_body_annotations": [
            {"pillars": list(p), "observations": v}
            for p, v in grouped.items()
            if len({r["expected_strength"] for r in v if r["expected_strength"]}) > 1
        ],
        "deduplication_scope": "Exact input index only; identical source examples and editions may still overlap semantically even when one pillar differs. Neither records nor distinct inputs are independent trials.",
    }
