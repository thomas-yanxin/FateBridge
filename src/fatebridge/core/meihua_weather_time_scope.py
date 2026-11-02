"""Keep source dayparts distinct without inventing dated weather windows."""

from __future__ import annotations

from typing import Any

SCOPES = ("unspecified", "morning", "evening")
CONTRASTS = (("clear", "rain"), ("rain", "rain_stopping"), ("clear", "cloudy"))


def compare_weather_time_scopes(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare raw symbols, with their qualifications retained in each group.

    An unspecified scope does not mean all day. Distinct source dayparts do not
    establish a shared calendar date, numeric hours, or a verified forecast.
    """
    by_scope: dict[str, list[dict[str, Any]]] = {scope: [] for scope in SCOPES}
    for row in traces:
        scope = row["time_scope"]
        if scope not in by_scope:
            raise ValueError("Unknown weather source time scope")
        if row["status"] == "matched":
            by_scope[scope].append(row)

    def ids(scope: str, tag: str) -> list[str]:
        return sorted(r["rule_id"] for r in by_scope[scope] if tag in r["tags"])

    def same_scope(scope: str) -> list[dict[str, Any]]:
        return [
            {
                "tags": [a, b],
                "time_scope": scope,
                "rule_ids_by_tag": {a: ids(scope, a), b: ids(scope, b)},
                "policy": "retain_both_no_vote_or_priority",
                "relationship": (
                    "time_relation_unspecified"
                    if scope == "unspecified"
                    else "same_source_daypart_different_symbols"
                ),
            }
            for a, b in CONTRASTS
            if ids(scope, a) and ids(scope, b)
        ]

    def cross_scope(left: str, right: str, relationship: str) -> list[dict[str, Any]]:
        rows = []
        for a, b in CONTRASTS:
            for first, second in ((a, b), (b, a)):
                left_ids, right_ids = ids(left, first), ids(right, second)
                if left_ids and right_ids:
                    rows.append(
                        {
                            "tags": [a, b],
                            "time_scopes": [left, right],
                            "tags_by_scope": {left: first, right: second},
                            "rule_ids_by_scope": {left: left_ids, right: right_ids},
                            "relationship": relationship,
                        }
                    )
        return rows

    groups = []
    for scope, rows in by_scope.items():
        if not rows:
            continue
        groups.append(
            {
                "time_scope": scope,
                "rule_ids": [r["rule_id"] for r in rows],
                "raw_tags": sorted({tag for r in rows for tag in r["tags"]}),
                "qualified_tags": sorted(
                    {
                        tag
                        for r in rows
                        for tag in r["effective_tags"]
                        if tag not in r["conditional_tags"]
                    }
                ),
                "conditional_tags": sorted(
                    {tag for r in rows for tag in r["conditional_tags"]}
                ),
                "controlled_tags": sorted(
                    {tag for r in rows for tag in r["controlled_tags"]}
                ),
            }
        )
    return {
        "basis": "raw_matched_symbols_with_per_rule_qualifications_retained",
        "groups": groups,
        "unspecified_time_conflicts": same_scope("unspecified"),
        "same_daypart_conflicts": [
            *same_scope("morning"),
            *same_scope("evening"),
        ],
        "separated_daypart_pairs": cross_scope(
            "morning", "evening", "distinct_source_dayparts_no_shared_date_assumed"
        ),
        "unresolved_time_relations": [
            *cross_scope("unspecified", "morning", "unspecified_scope_not_all_day"),
            *cross_scope("unspecified", "evening", "unspecified_scope_not_all_day"),
        ],
        "has_explicit_daypart_readings": bool(
            by_scope["morning"] or by_scope["evening"]
        ),
        "policy": {
            "daypart_labels_source": "explicit_original_words_only",
            "target_calendar_date": None,
            "local_clock_intervals": None,
            "dawn_or_sunset_mapping": None,
            "unspecified_does_not_mean_all_day": True,
            "automatic_priority_or_intersection": False,
            "display_order_is_event_chronology": False,
            "single_weather_forecast": None,
        },
        "predictive_efficacy_established": False,
    }
