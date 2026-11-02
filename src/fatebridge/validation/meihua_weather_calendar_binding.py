"""Bind stored study lunar labels to a frozen bilingual HKO transcription.

This adds published-date evidence to the unchanged mechanical reader. It does
not call a production calendar, infer a solar-term month, read rain outcomes,
or authenticate a historical source release time or astronomical instant.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from datetime import date
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from .meihua_weather_trace_binding import (
    STUDY_PINS,
    audit_bound_weather_study,
    bound_weather_label,
)

PROFILE_SHA256 = "a011490181cc98fa58dfb9a7fb425265abcd36ed98aaa554eaecbdd1749109b1"
_FIELDS = ("year", "month", "day", "is_leap_month")
_POLICY = {
    "year_boundary": "lunar_new_year",
    "day_boundary": "local_midnight",
    "date_basis": "selected_zone_civil_date",
    "timezone": "Asia/Hong_Kong",
    "leap_month_rule": "repeat_nominal_month_number",
}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("meihua/weather-calendar-hko-v1.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
        raise ValueError("Frozen weather calendar reference content changed")
    profile: dict[str, Any] = json.loads(raw)
    if (
        profile["id"] != "meihua_weather_hko_lunar_labels_v1"
        or profile["version"] != "1.0.0"
        or len(profile["dates"]) != 1824
        or profile["coverage"]["start"] != "2022-01-03"
        or profile["coverage"]["end"] != "2026-12-31"
    ):
        raise ValueError("Unknown or incomplete weather calendar reference")
    return profile


def _expect(actual: Any, expected: Any, path: str) -> None:
    # JSON comparison distinguishes true/1 and 2025/2025.0, unlike Python ==.
    render = lambda value: json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    if render(actual) != render(expected):
        raise ValueError(f"Published lunar date binding mismatch: {path}")


def published_lunar_date_reference(issue_date: date) -> dict[str, Any]:
    """Return an isolated selected reference, including its row/month provenance."""
    profile = _profile()
    key = issue_date.isoformat()
    if key not in profile["dates"]:
        raise ValueError("Issue date is outside the frozen HKO reference coverage")
    row = deepcopy(profile["dates"][key])
    names = {
        row["source_row"]["english_file"],
        row["source_row"]["chinese_file"],
        row["month_anchor"]["english_file"],
        row["month_anchor"]["chinese_file"],
    }
    return {
        "reference_id": profile["id"],
        "version": profile["version"],
        "profile_sha256": PROFILE_SHA256,
        "issue_date": key,
        **row,
        "sources": [
            deepcopy(source)
            for source in profile["sources"]
            if source["file_name"] in names
        ],
        "year_label_convention": profile["year_label_convention"],
        "leap_flag_provenance": profile["leap_flag_provenance"],
    }


def verify_hko_lunar_date_labels(record: dict[str, Any]) -> dict[str, Any]:
    """Verify the issue-day label subset, not merely the stored labels' agreement."""
    try:
        inputs = record["input"]
        _expect(inputs["analysis_timezone"], "Asia/Hong_Kong", "input.timezone")
        parts = [inputs["analysis_" + key] for key in ("year", "month", "day")]
        if any(type(value) is not int for value in parts):
            raise ValueError("Issue date requires literal integer year/month/day")
        reference = published_lunar_date_reference(date(*parts))
        expected = {key: reference[key] for key in _FIELDS}
        for field in ("calendar_actual", "calendar_expected"):
            _expect({key: record[field][key] for key in _FIELDS}, expected, field)
        policy = {
            **_POLICY,
            "lunar_year": expected["year"],
            "is_leap_month": expected["is_leap_month"],
        }
        _expect(
            {key: record["calendar_policy"][key] for key in policy},
            policy,
            "calendar_policy.selected_date_fields",
        )
        return {
            "verifier_id": "meihua_weather_hko_lunar_binding_v1",
            "published_lunar_date_labels_verified": True,
            "verified_calendar_fields": list(_FIELDS),
            "verified_policy_fields": list(policy),
            "reference": reference,
            "independent_of_production_calendar_execution": True,
            "shared_publisher_is_not_independent_astronomical_observation": True,
            "civil_instant_authenticated": False,
            "solar_term_month_or_season_authenticated": False,
            "historical_reference_release_time_authenticated": False,
            "independent_astronomical_accuracy_established": False,
            "predictive_efficacy_established": False,
        }
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Incomplete or malformed lunar date binding evidence") from exc


def calendar_bound_weather_label(record: dict[str, Any]) -> dict[str, Any]:
    """Keep the old label and mechanical receipt; add the external date binding."""
    calendar = verify_hko_lunar_date_labels(record)
    result = bound_weather_label(record)
    return {**result, "calendar_verification": calendar}


def audit_calendar_bound_weather_study(directory: Path) -> dict[str, Any]:
    """Require the entire original sealed study, then verify every issue-day label."""
    directory = directory.resolve()
    mechanical = audit_bound_weather_study(directory)
    original = (directory / "generated/evidence.jsonl").resolve()
    compressed = (directory / "generated/evidence.jsonl.gz").resolve()
    if not original.is_relative_to(directory) or not compressed.is_relative_to(
        directory
    ):
        raise ValueError("Study evidence path escapes directory")
    if original.exists() == compressed.exists():
        raise ValueError("Supply exactly one original or lossless evidence file")
    selected = original if original.exists() else compressed
    opener = open if selected == original else gzip.open
    digest = hashlib.sha256()
    count = 0
    issue_dates: set[str] = set()
    with opener(selected, "rb") as stream:
        for raw in stream:
            digest.update(raw)
            row = json.loads(raw)
            verified = verify_hko_lunar_date_labels(row)
            issue_dates.add(verified["reference"]["issue_date"])
            count += 1
    if digest.hexdigest() != STUDY_PINS["generated/evidence.jsonl"]:
        raise ValueError("Original evidence changed during date-label verification")
    for name, expected in STUDY_PINS.items():
        if name == "generated/evidence.jsonl":
            continue
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Study evidence path escapes directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original study changed during date-label verification")
    if count != mechanical["evidence_records"] or len(issue_dates) != 1004:
        raise ValueError("Retain all original evidence records and issue dates")
    return {
        **mechanical,
        "verifier_id": "meihua_weather_hko_calendar_binding_v1",
        "mechanical_verifier_id": mechanical["verifier_id"],
        "published_lunar_date_binding": {
            "all_selected_date_labels_verified": True,
            "evidence_records": count,
            "unique_issue_dates": len(issue_dates),
            "issue_date_range": [min(issue_dates), max(issue_dates)],
            "profile_sha256": PROFILE_SHA256,
            "verified_calendar_fields": list(_FIELDS),
            "calendar_scope": "issue civil date in Hong Kong, not target-date labels",
            "civil_instant_authenticated": False,
            "solar_term_month_or_season_authenticated": False,
            "historical_reference_release_time_authenticated": False,
            "independent_astronomical_accuracy_established": False,
        },
        "original_mechanical_report": mechanical,
        "new_real_world_observations": 0,
    }
