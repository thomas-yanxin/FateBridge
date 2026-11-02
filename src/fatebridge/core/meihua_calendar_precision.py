"""Expose named publisher uncertainty without changing or choosing lunar labels."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("meihua/calendar-precision-v1.json")
        .read_text(encoding="utf-8")
    )
    if raw["id"] != "meihua_calendar_precision_v1" or raw["version"] != "1.0.0":
        raise ValueError("Unknown Mei Hua calendar-precision profile")
    if len(raw["events"]) != 3:
        raise ValueError("Retain all three named HKO new-moon uncertainties")
    for event in raw["events"]:
        start = date.fromisoformat(event["published_new_moon_date"])
        end = date.fromisoformat(event["published_next_month_start"])
        if (
            event["review_start"] != (start - timedelta(days=1)).isoformat()
            or event["review_end_exclusive"] != end.isoformat()
            or (end - start).days not in (29, 30)
            or event["alternate_calendar_computed"] is not False
        ):
            raise ValueError("Inconsistent published-month review scope")
    return raw


def calendar_label_precision(solar_date: date) -> dict[str, Any]:
    """Report a conservative review scope, never an alternative calendar.

    The previous date is included because the publisher does not choose an
    earlier/later direction. The following published month anchor bounds the
    software review window under the explicitly fixed-other-anchors assumption.
    These bounds are not physical confidence intervals published by HKO.
    """
    profile = _profile()
    events = [
        deepcopy(event)
        for event in profile["events"]
        if date.fromisoformat(event["review_start"])
        <= solar_date
        < date.fromisoformat(event["review_end_exclusive"])
    ]
    in_scope = (
        date.fromisoformat(profile["calendar_scope"]["start"])
        <= solar_date
        <= date.fromisoformat(profile["calendar_scope"]["end"])
    )
    return {
        "profile_id": profile["id"],
        "version": profile["version"],
        "selected_civil_date": solar_date.isoformat(),
        "status": (
            "named_month_start_review_required"
            if events
            else (
                "no_named_boundary_in_review_window"
                if in_scope
                else "outside_hko_annual_table_scope"
            )
        ),
        "source": deepcopy(profile["source"]),
        "source_scope": profile["source_scope"],
        "review_scope_policy": deepcopy(profile["review_scope_policy"]),
        "matched_events": events,
        "calculation_policy": "retain_current_published_labels_no_alternate_recast",
        "date_label_revision_may_change_month_day_and_cast": bool(events),
        "absence_of_named_event_certifies_exactness": False,
        "exact_astronomical_accuracy_established": False,
        "predictive_efficacy_established": False,
    }
