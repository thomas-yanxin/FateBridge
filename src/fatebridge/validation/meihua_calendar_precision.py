"""Audit publication caveats and frozen manual casts independently of scoring."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def audit_calendar_precision(directory: Path) -> dict[str, Any]:
    from fatebridge.services.divination import calculate_meihua_analysis
    from fatebridge.validation.meihua import hko_calendar_rows, read_source

    manifest = json.loads((directory / "manifest.json").read_text())
    for name, digest in manifest["frozen_files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Precision reference escapes frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen calendar-precision reference changed")
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/almanac.py",
        "core/lunar_1900_prefix.py",
        "core/lunar_supplement.py",
        "data/lunar_calendar_pmo_1900_prefix.json",
        "data/lunar_calendar_hko_2100.json",
        "core/calendar.py",
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_calendar_precision.py",
        "core/output_meihua.py",
        "services/divination.py",
        "data/meihua/calendar-precision-v1.json",
        "validation/meihua_calendar_precision.py",
    ]
    hashes = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in names
    }
    events = json.loads((directory / "events.json").read_text())["events"]
    if {r["published_new_moon_date"] for r in events} != {
        "2057-09-28",
        "2089-09-04",
        "2097-08-07",
    } or len(events) != 3:
        raise ValueError("Retain all three fixed named moon events")
    runtime = json.loads(
        (package / "data/meihua/calendar-precision-v1.json").read_text()
    )
    expected_events = [
        {k: v for k, v in e.items() if k not in {"annual_table_file", "annual_source"}}
        for e in events
    ]
    source_passed = runtime["events"] == expected_events
    source_text = (directory / "sources/hko-conversion.txt").read_text()
    source_passed = source_passed and all(
        t in source_text
        for t in ["2057年9月28日", "2089年9月4日", "2097年8月7日", "一日之差別"]
    )
    source_passed = (
        source_passed
        and runtime["source"]["raw_sha256"] == manifest["raw_source_sha256"]
    )
    source_rows = []
    for event in events:
        rows = hko_calendar_rows(
            read_source(directory / event["annual_table_file"]), event["annual_source"]
        )
        starts = [r for r in rows if r["day"] == 1]
        index = next(
            i
            for i, r in enumerate(starts)
            if r["date"].isoformat() == event["published_new_moon_date"]
        )
        actual = starts[index]
        source_rows.append(
            {
                "id": event["id"],
                "published_anchor_matches": (
                    actual["year"],
                    actual["month"],
                    actual["is_leap_month"],
                )
                == (
                    event["published_lunar_year"],
                    event["published_lunar_month"],
                    False,
                ),
                "next_published_anchor_matches": starts[index + 1]["date"].isoformat()
                == event["published_next_month_start"],
            }
        )

    cases = json.loads((directory / "cases.json").read_text())["cases"]
    mathematical = []
    for case in cases:
        y, m, d = map(int, case["date"].split("-"))
        result = calculate_meihua_analysis(
            analysis_year=y,
            analysis_month=m,
            analysis_day=d,
            analysis_hour=12,
            analysis_timezone="UTC+08:00",
        )
        if "error" in result:
            mathematical.append({"date": case["date"], "error": result})
            continue
        lunar = result["calendar_context"]["lunar_calendar"]
        cast = result["meihua"]
        actual = {
            "lunar": [lunar[k] for k in ["year", "month", "day", "is_leap_month"]],
            "year_branch": cast["seed"]["year_branch"],
            "moving_line": cast["seed"]["moving_line"],
            **{
                k + "_code": cast[k + "_hexagram"]["binary_code"]
                for k in ["base", "changed", "mutual"]
            },
        }
        expected = {k: case[k] for k in actual}
        mathematical.append(
            {
                "date": case["date"],
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )

    review_reports = []
    from datetime import date

    from fatebridge.core.meihua_calendar_precision import calendar_label_precision

    for case in json.loads((directory / "review-cases.json").read_text())["cases"]:
        actual = calendar_label_precision(date.fromisoformat(case["date"]))
        ids = [e["id"] for e in actual["matched_events"]]
        expected_ids = [case["event_id"]] if case["review_expected"] else []
        review_reports.append(
            {
                "date": case["date"],
                "matched_event_ids": ids,
                "passed": ids == expected_ids,
            }
        )
    unchanged_metadata = all(
        hashlib.sha256((package / name).read_bytes()).hexdigest() == digest
        for name, digest in hashes.items()
    )
    if not unchanged_metadata:
        raise ValueError("Source changed during calendar-precision audit")
    return {
        "audit_id": "meihua_calendar_precision_v4",
        "implementation_sha256": hashes,
        "reference_manifest_sha256": hashlib.sha256(
            (directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "source_caveat_and_event_integration_passed": source_passed,
        "published_month_anchors": source_rows,
        "manual_mathematical_cases": mathematical,
        "synthetic_review_window_cases": review_reports,
        "selected_checks_passed": source_passed
        and all(
            r["published_anchor_matches"] and r["next_published_anchor_matches"]
            for r in source_rows
        )
        and all(r.get("passed", False) for r in mathematical)
        and all(r["passed"] for r in review_reports),
        "lunar_labels_or_cast_arithmetic_changed": False,
        "review_scope_is_software_conservative_interval": True,
        "alternate_calendar_or_shift_direction_inferred": False,
        "solar_term_near_midnight_dates_certified": False,
        "full_astronomical_accuracy_established": False,
        "actual_model_runs": 0,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
