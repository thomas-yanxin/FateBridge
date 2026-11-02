"""Independent HKO minute/day anchors around an IANA repeated civil hour."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import (
    get_adjacent_solar_terms,
    get_bazi_month_boundaries,
    get_day_ganzhi,
    get_solar_terms_for_year,
)
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
from fatebridge.utils.timezones import parse_timezone_name


def audit_clock_fold(directory: Path) -> dict[str, Any]:
    reference = json.loads((directory / "reference.json").read_text())
    disagreements: list[dict[str, Any]] = []

    def check(ok: bool, category: str, case: Any) -> None:
        if not ok:
            disagreements.append({"category": category, "case": case})

    for source in reference["source_files"]:
        check(
            hashlib.sha256((directory / source["file"]).read_bytes()).hexdigest()
            == source["sha256"],
            "source_hash",
            source["file"],
        )
    anchor = reference["term_anchor"]
    published = datetime.fromisoformat(anchor["at"])
    term = next(
        t
        for t in get_solar_terms_for_year(published.year, reference["zone"])
        if t.name == anchor["name"]
    )
    error = abs((utc_instant(term.moment) - utc_instant(published)).total_seconds())
    check(error <= anchor["tolerance_seconds"], "term_anchor", anchor)
    day = reference["day_anchor"]
    day_date = datetime.fromisoformat(day["date"])
    check(
        get_day_ganzhi(day_date.year, day_date.month, day_date.day) == day["ganzhi"],
        "day_anchor",
        day,
    )
    for case in reference["clock_probes"]:
        local = datetime.fromisoformat(case["utc"]).astimezone(
            parse_timezone_name(reference["zone"])
        )
        check(
            local.isoformat() == case["local"] and local.fold == case["fold"],
            "iana_clock",
            case,
        )
        check(
            get_adjacent_solar_terms(local, reference["zone"])[0].name == case["term"],
            "term_order",
            case,
        )
        check(
            get_bazi_month_boundaries(local, reference["zone"])[2]
            == case["month_branch"],
            "month_order",
            case,
        )
        offset = local.utcoffset()
        assert offset is not None
        result = calculate_qimen_analysis(
            analysis_year=local.year,
            analysis_month=local.month,
            analysis_day=local.day,
            analysis_hour=local.hour,
            analysis_minute=local.minute,
            analysis_timezone=reference["zone"],
            analysis_utc_offset=format_utc_offset(offset),
            use_true_solar_time=False,
            qimen_options={"ju_method": "chaibu"},
        )
        check(
            result.get("qimen", {}).get("ju_term") == case["term"], "qimen_term", case
        )
    return {
        "source_id": reference["id"],
        "hko_source": reference["hko_url"],
        "iana_source": reference["iana_url"],
        "independent_calendar_reference_count": 2,
        "iana_derived_clock_probes": len(reference["clock_probes"]),
        "term_error_seconds": error,
        "term_tolerance_seconds": anchor["tolerance_seconds"],
        "disagreements": disagreements,
        "whole_history_accuracy_established": False,
        "real_world_efficacy_validated": False,
    }
