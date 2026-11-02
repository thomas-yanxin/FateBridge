"""Full-cohort TT comparison and source-faithful minute-label parsing.

The one-second gate is a comparison with a supplied reference, not a claim
of absolute civil-clock precision, independent observations or prediction.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_naoj_minute_label(date_label: str, clock_label: str) -> dict[str, Any]:
    """Retain a source's end-of-day notation without inventing a UTC instant."""
    if not isinstance(date_label, str) or not re.fullmatch(
        r"[0-9]{4}/[0-9]{2}/[0-9]{2}", date_label
    ):
        raise ValueError("Expected the explicit NAOJ YYYY/MM/DD date label")
    if not isinstance(clock_label, str) or not re.fullmatch(
        r"(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00", clock_label
    ):
        raise ValueError("Expected an HH:MM label; only exact24:00 ends the day")
    endofday = clock_label == "24:00"
    try:
        nominal = datetime.strptime(
            date_label + " " + ("00:00" if endofday else clock_label),
            "%Y/%m/%d %H:%M",
        ) + timedelta(days=int(endofday))
    except (ValueError, OverflowError) as error:
        raise ValueError(
            "Invalid or unrepresentable reference calendar label"
        ) from error
    return {
        "raw_date_label": date_label,
        "raw_clock_label": clock_label,
        "end_of_day_24_00": endofday,
        "nominal_display_datetime": nominal.isoformat(),
        "displayed_unit": "minute",
        "rounding_rule_authenticated": False,
        "actual_error_interval_seconds": None,
        "one_second_precision_testable_from_this_label": False,
        "is_authenticated_UTC_instant": False,
        "scope": "Nominal label normalization only; retain the separately declared time scale and Delta T. Do not interpret the rollover as a measured event date.",
    }


def read_solar_tt_reference(
    path: Path, *, expected_sha256: str
) -> dict[tuple[int, int], dict[str, Any]]:
    """Verify supplied bytes and all required1900..2100 term IDs before calls."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise ValueError("Use a previously recorded lowercase SHA-256")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("Solar reference differs from its recorded commitment")

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON keys make a reference ambiguous")
            result[key] = value
        return result

    data = json.loads(content, object_pairs_hook=unique_keys)
    if not isinstance(data, dict) or data.get("production_imports") is not False:
        raise ValueError("Reference must explicitly declare its collector provenance")
    values = data.get("rows")
    if not isinstance(values, list):
        raise ValueError("Reference must retain explicit term rows")
    indexed = {}
    for row in values:
        if not isinstance(row, dict):
            raise ValueError("Invalid solar reference row")
        year, index, longitude, tt = (
            row.get(key) for key in ["year", "index", "longitude", "jd_tt"]
        )
        if (
            type(year) is not int
            or type(index) is not int
            or not 0 <= index < 24
            or type(longitude) not in {int, float}
            or longitude != (285 + 15 * index) % 360
            or not isinstance(tt, (int, float))
            or isinstance(tt, bool)
            or not math.isfinite(tt)
        ):
            raise ValueError("Invalid term ID, target longitude or finite TT epoch")
        if (year, index) in indexed:
            raise ValueError("Duplicate solar term IDs cannot increase coverage")
        indexed[(year, index)] = row
    required = {(year, index) for year in range(1900, 2101) for index in range(24)}
    if not required <= indexed.keys():
        raise ValueError("All4824supported1900..2100 solar terms are required")
    if path.read_bytes() != content:
        raise ValueError("Solar reference changed during its input check")
    return indexed


def audit_solar_seconds(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    """Keep the original one-second TT gate and the complete supported cohort."""
    reference = read_solar_tt_reference(path, expected_sha256=expected_sha256)
    from fatebridge.core.almanac import SOLAR_TERM_NAMES, get_solar_terms_for_year
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.validation.meihua_runtime_guard import (
        capture_calendar_runtime,
        verify_calendar_runtime,
    )
    from fatebridge.validation.meihua_source_guard import (
        capture_package_sources,
        verify_package_sources,
    )

    package = Path(__file__).resolve().parents[1]
    source = capture_package_sources(package)
    runtime = capture_calendar_runtime()
    rows: list[dict[str, Any]] = []
    providers: Counter[str] = Counter()
    clocks: Counter[str] = Counter()
    for year in range(1900, 2101):
        terms = get_solar_terms_for_year(year, "UTC+08:00")
        if len(terms) != 24 or [t.name for t in terms] != list(SOLAR_TERM_NAMES):
            raise ValueError("Every actual public term is required exactly once")
        for index, term in enumerate(terms):
            clock = ephemeris_time(term.moment)
            actual = clock.jd_tt
            if actual is None or not math.isfinite(actual):
                raise ValueError("An actual finite TT epoch is required for every term")
            target = reference[(year, index)]["jd_tt"]
            delta = (actual - target) * 86400
            providers[term.ephemeris_model] += 1
            clocks[clock.method] += 1
            rows.append(
                {
                    "year": year,
                    "index": index,
                    "term": term.name,
                    "actual_datetime_with_offset": term.moment.isoformat(),
                    "actual_jd_tt": actual,
                    "reference_jd_tt": target,
                    "difference_seconds_tt": delta,
                    "within_one_second_TT_reference_gate": abs(delta) <= 1.0,
                }
            )
    verify_package_sources(package, source)
    verify_calendar_runtime(runtime)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Solar reference changed during the full audit")
    failures = [r for r in rows if not r["within_one_second_TT_reference_gate"]]
    return {
        "audit_id": "meihua_full_supported_solar_TT_seconds_v1",
        "reference_sha256": expected_sha256,
        "reference_file_commitment_verified": True,
        "reference_collector_authenticity_or_independence_authenticated": False,
        "supported_years": [1900, 2100],
        "required_and_actual_unique_solar_terms": len(rows),
        "TT_reference_gate_seconds": 1.0,
        "TT_reference_gate_met": not failures,
        "failed_term_count": len(failures),
        "maximum_absolute_difference_seconds_tt": max(
            abs(r["difference_seconds_tt"]) for r in rows
        ),
        "actual_models": dict(providers),
        "actual_clock_methods": dict(clocks),
        "source_guard": source,
        "runtime_guard": runtime,
        "rows": rows,
        "actual_physical_observations_added": 0,
        "absolute_civil_time_accuracy_established": False,
        "predictive_efficacy_established": False,
        "scope": "Complete solar-boundary software comparison to supplied committed TT reference. Not verification of new moons, unknown civil clocks, leap predictions, full calendar conformance or real-world predictions. A minute-display match is not a one-second test.",
    }
