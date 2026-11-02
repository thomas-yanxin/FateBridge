"""Bind stored weather-study month/season labels to published solar minutes.

The minute guard is an explicit software assumption, not a publisher confidence
interval, rounding rule or authentication of an unrounded astronomical instant.
The original mechanical/date readers, labels and prediction gates are retained.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from .meihua_weather_calendar_binding import (
    audit_calendar_bound_weather_study,
    calendar_bound_weather_label,
)
from .meihua_weather_trace_binding import STUDY_PINS

PROFILE_SHA256 = "bd523604ed0209712f75d481da5b2a9f63cce19fcc03ce643b40f2da8d5c4dda"
_OFFSET = timezone(timedelta(hours=8))
_MINUTE = timedelta(minutes=1)
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("meihua/weather-solar-minutes-hko-v1.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
        raise ValueError("Frozen weather solar-minute reference content changed")
    profile: dict[str, Any] = json.loads(raw)
    if (
        profile["id"] != "meihua_weather_hko_solar_minutes_v1"
        or profile["version"] != "1.0.0"
        or len(profile["terms"]) != 144
        or {r["year"] for r in profile["terms"]} != set(range(2022, 2028))
        or profile["binding_policy"]["guard_seconds_each_side_of_printed_minute"] != 60
    ):
        raise ValueError("Unknown or incomplete selected solar-minute reference")
    return profile


def published_solar_month_context(moment: datetime) -> dict[str, Any]:
    """Read two adjacent minor terms, retaining uncertain/unsupported minutes.

    A declared minute denotes [start,start+60s). Published minute centres get a
    predeclared ±60s software guard. No unprinted seconds are reconstructed.
    This modern fixed-offset comparison is not an independent civil-clock test.
    """
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ValueError("An explicit aware issue minute is required")
    local = moment.astimezone(_OFFSET)
    if local.second or local.microsecond:
        raise ValueError("Retain literal minute resolution; do not truncate seconds")
    profile = _profile()
    boundaries = [r for r in profile["terms"] if r["kind"] == "minor_month_boundary"]
    instants = [datetime.fromisoformat(r["printed_datetime"]) for r in boundaries]
    end = local + _MINUTE
    overlaps = [
        deepcopy(row)
        for row, instant in zip(boundaries, instants, strict=True)
        if local < instant + _MINUTE and end > instant - _MINUTE
    ]
    result = {
        "reference_id": profile["id"],
        "version": profile["version"],
        "profile_sha256": PROFILE_SHA256,
        "supplied_datetime": moment.isoformat(),
        "issue_minute_at_reference_offset": local.isoformat(),
        "issue_minute_end_exclusive": end.isoformat(),
        "binding_policy": deepcopy(profile["binding_policy"]),
        "status": "outside_two_anchor_coverage",
        "month_branch": None,
        "research_season": None,
        "start_term": None,
        "end_term": None,
        "overlapping_boundary_guards": overlaps,
        "sources": [],
        "unrounded_instant_authenticated": False,
        "civil_instant_independently_authenticated": False,
        "historical_source_release_time_authenticated": False,
        "exact_astronomical_accuracy_established": False,
        "predictive_efficacy_established": False,
    }
    if overlaps:
        result["status"] = "boundary_resolution_insufficient"
        return result
    previous = [i for i, instant in enumerate(instants) if instant <= local]
    if not previous or previous[-1] + 1 == len(boundaries):
        return result
    index = previous[-1]
    start, following = boundaries[index : index + 2]
    if not (
        local >= instants[index] + _MINUTE and end <= instants[index + 1] - _MINUTE
    ):
        raise ValueError("A returned month must be wholly outside both guards")
    branch = start["declared_month_branch_after"]
    names = {start["source_file"], following["source_file"]}
    result.update(
        status="published_minute_context_bound",
        month_branch=branch,
        research_season=profile["binding_policy"]["season_by_branch"][branch],
        start_term=deepcopy(start),
        end_term=deepcopy(following),
        sources=[deepcopy(s) for s in profile["sources"] if s["file_name"] in names],
    )
    return result


def _expect(actual: Any, expected: Any, path: str) -> None:
    render = lambda v: json.dumps(
        v, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    if render(actual) != render(expected):
        raise ValueError(f"Published solar context binding mismatch: {path}")


def verify_published_solar_issue_context(record: dict[str, Any]) -> dict[str, Any]:
    """Check the selected original study's month and two season scenarios only."""
    try:
        inputs = record["input"]
        _expect(inputs["analysis_timezone"], "Asia/Hong_Kong", "input.timezone")
        keys = ("year", "month", "day", "hour", "minute")
        parts = [inputs["analysis_" + key] for key in keys]
        if any(type(value) is not int for value in parts):
            raise ValueError("Issue clock requires literal integer minute fields")
        reference = published_solar_month_context(
            datetime(parts[0], parts[1], parts[2], parts[3], parts[4], tzinfo=_OFFSET)
        )
        if (
            record["computed_issue_month_branch"] not in _BRANCHES
            or not isinstance(record["computed_issue_month_branch"], str)
            or len(record["computed_issue_month_branch"]) != 1
        ):
            raise ValueError("Invalid stored issue month branch")
        scenario = record["scenario"]
        if scenario not in {"calendar_season_supplied", "season_not_supplied"}:
            raise ValueError("Retain the two original study season scenarios")
        context = inputs.get("weather_context")
        if context is None:
            context = {}
        if not isinstance(context, dict):
            raise ValueError("Malformed original study weather context")
        _expect(context.get("many_min_count"), None, "original_protocol.many_min_count")
        _expect(
            context.get("prior_condition"), None, "original_protocol.prior_condition"
        )
        complete = reference["status"] == "published_minute_context_bound"
        if complete:
            _expect(
                record["computed_issue_month_branch"],
                reference["month_branch"],
                "computed_issue_month_branch",
            )
            _expect(
                context.get("season"),
                (
                    reference["research_season"]
                    if scenario == "calendar_season_supplied"
                    else None
                ),
                "input.weather_context.season",
            )
        elif scenario == "season_not_supplied":
            _expect(context.get("season"), None, "input.weather_context.season")
        return {
            "verifier_id": "meihua_weather_hko_solar_context_binding_v1",
            "published_solar_context_verified_under_declared_guard": complete,
            "reference": reference,
            "scenario": scenario,
            "month_branch_fact_path": "computed_issue_month_branch",
            "season_fact_path": "input.weather_context.season",
            "original_research_season_mapping_retained": True,
            "independent_of_production_calendar_execution": True,
            "shared_publisher_is_not_independent_astronomical_observation": True,
            "solar_term_month_or_season_authenticated": False,
            "civil_instant_authenticated": False,
            "historical_reference_release_time_authenticated": False,
            "independent_astronomical_accuracy_established": False,
            "predictive_efficacy_established": False,
        }
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError(
            "Incomplete or malformed solar context binding evidence"
        ) from exc


def solar_calendar_bound_weather_label(record: dict[str, Any]) -> dict[str, Any]:
    """Keep old labels/receipts; incomplete minute evidence remains explicit."""
    solar = verify_published_solar_issue_context(record)
    original = calendar_bound_weather_label(record)
    return {**original, "solar_context_verification": solar}


def audit_solar_calendar_bound_weather_study(directory: Path) -> dict[str, Any]:
    """Preserve all original rows, uncertain results, failures and original gates."""
    directory = directory.resolve()
    original = audit_calendar_bound_weather_study(directory)
    candidates = [
        (directory / name).resolve()
        for name in ["generated/evidence.jsonl", "generated/evidence.jsonl.gz"]
    ]
    if (
        any(not p.is_relative_to(directory) for p in candidates)
        or sum(p.exists() for p in candidates) != 1
    ):
        raise ValueError(
            "Supply exactly one in-directory original/lossless evidence file"
        )
    selected = next(p for p in candidates if p.exists())
    opener = gzip.open if selected.suffix == ".gz" else open
    digest = hashlib.sha256()
    rows = []
    counts: Counter[str] = Counter()
    issue_dates: set[str] = set()
    with opener(selected, "rb") as stream:
        for index, raw in enumerate(stream):
            digest.update(raw)
            row = json.loads(raw)
            try:
                result = verify_published_solar_issue_context(row)
                reference = result["reference"]
                status = reference["status"]
                detail = {
                    "month_branch": reference["month_branch"],
                    "research_season": reference["research_season"],
                    "issue_minute": reference["issue_minute_at_reference_offset"],
                    "start_term": reference["start_term"],
                    "end_term": reference["end_term"],
                }
                issue_dates.add(reference["issue_minute_at_reference_offset"][:10])
            except ValueError as exc:
                status = "binding_mismatch"
                detail = {"error": str(exc)}
            counts[status] += 1
            rows.append(
                {
                    "index": index,
                    "target_date": row["date"],
                    "scenario": row["scenario"],
                    "status": status,
                    **detail,
                }
            )
    if digest.hexdigest() != STUDY_PINS["generated/evidence.jsonl"]:
        raise ValueError("Original evidence changed during solar context verification")
    for name, expected in STUDY_PINS.items():
        if name == "generated/evidence.jsonl":
            continue
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Original study changed during solar context verification")
    if len(rows) != original["evidence_records"]:
        raise ValueError("Retain all original evidence rows")
    return {
        **original,
        "verifier_id": "meihua_weather_hko_solar_calendar_binding_v1",
        "original_calendar_bound_report": original,
        "published_solar_context_binding": {
            "all_original_records_verified_under_declared_guard": counts[
                "published_minute_context_bound"
            ]
            == len(rows),
            "evidence_records": len(rows),
            "unique_issue_dates": len(issue_dates),
            "counts": dict(counts),
            "profile_sha256": PROFILE_SHA256,
            "binding_policy": deepcopy(_profile()["binding_policy"]),
            "records": rows,
            "unrounded_astronomical_instants_authenticated": False,
            "historical_reference_release_time_authenticated": False,
            "future_forecast_ledger_modified": False,
            "outcome_files_read": 0,
        },
        "new_real_world_observations": 0,
    }
