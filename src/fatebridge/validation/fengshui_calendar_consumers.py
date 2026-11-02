"""Full public-year decision audit using the unchanged independent TT corpus."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.fengshui.annual import annual_stars
from fatebridge.core.fengshui.bazhai import minggua
from fatebridge.core.fengshui.calendar import solar_term_resolution
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    HousePeriod,
    MingguaRequest,
    MonthlyRequest,
)
from fatebridge.core.fengshui.monthly import monthly_stars
from fatebridge.core.fengshui.xuankong import period_context
from fatebridge.validation.fengshui_solar_terms import (
    compare_resolution,
    validate_solar_terms_reference,
)

PROTOCOL_SHA256 = "7ac01f9dbc952c40e269ca02e3ce8f1eb41a9fa5613b33679c6e818b8e75d7f5"
MONTH_SOURCE_SHA256 = "d91185d7bcf93f424517225e8d8d62e4ddbe36c46f1aeef72b33251d52a286b4"
OFFSETS = {"C": 0, "NW": 1, "W": 2, "NE": 3, "S": 4, "N": 5, "SW": 6, "E": 7, "SE": 8}


def load_consumer_protocol(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Retain the before-execution consumer protocol and every year")
    return cast(dict[str, Any], json.loads(raw))


def load_literal_month_table(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MONTH_SOURCE_SHA256:
        raise ValueError("Retain the original literal 36 month numbers")
    return cast(dict[str, Any], json.loads(raw))


def expected_sides(row: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Use fixed chronological term indices, not the production selector."""
    index, year = row["term_index"], row["year"]
    if index not in range(0, 24, 2):
        raise ValueError("The declared decision queue contains the twelve jie only")
    after = (year - 1, 12) if index == 0 else (year, index // 2)
    y, m = after
    before = (y - 1, 12) if m == 1 else (y, m - 1)
    return before, after


def _instant(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("Reported clock needs its actual UTC offset")
    return result.astimezone(timezone.utc)


def check_consumer_observation(
    row: dict[str, Any],
    offset: int,
    moment: datetime,
    annual: dict[str, Any],
    monthly: dict[str, Any],
    literal: dict[str, Any],
    personal: dict[str, Any] | None = None,
    period: dict[str, Any] | None = None,
) -> list[str]:
    """Check decisions independently; do not call a producer or online guard."""
    errors: list[str] = []

    def check(value: bool, label: str) -> None:
        if not value:
            errors.append(label)

    before, after = expected_sides(row)
    selected = before if offset < 0 else after
    try:
        t = monthly["time_context"]
        check(
            _instant(t["local_moment"]) == moment.astimezone(timezone.utc),
            "monthly_query_binding",
        )
        if offset == 0:
            check(
                monthly["status"] == "partial" and not monthly["palaces"],
                "monthly_no_false_unique_plate",
            )
            check(
                t["solar_month_number"] is None and t["month_branch"] is None,
                "monthly_no_false_unique_month",
            )
            check(
                t["valid_from"] is None and t["valid_until"] is None,
                "monthly_no_false_unique_interval",
            )
            candidates = t["candidate_months"]
            identities = [
                (c["effective_solar_year"], c["solar_month_number"]) for c in candidates
            ]
            check(
                identities == [before, after], "monthly_complete_reference_candidates"
            )
            check(
                t["effective_solar_year"]
                == (before[0] if before[0] == after[0] else None),
                "monthly_effective_year_status",
            )
            p = t["provisional_interval"]
            check(
                _instant(p["valid_from"]) <= moment < _instant(p["valid_until"]),
                "monthly_provisional_interval_contains_query",
            )
            for c in candidates:
                check(
                    c["candidate_only"] is True
                    and _instant(c["valid_from"]) < _instant(c["valid_until"]),
                    "monthly_candidate_window",
                )
        else:
            check(monthly["status"] == "complete", "monthly_outer_complete")
            check(
                (t["effective_solar_year"], t["solar_month_number"]) == selected,
                "monthly_reference_side",
            )
            check(
                _instant(t["valid_from"]) <= moment < _instant(t["valid_until"]),
                "monthly_interval_contains_query",
            )
            branch = "子丑寅卯辰巳午未申酉戌亥"[(selected[0] - 4) % 12]
            group = next(
                g for g in literal["printed_center_columns"] if branch in g["branches"]
            )
            center = group["centers"][selected[1] - 1]
            check(
                monthly["year_branch"] == branch
                and monthly["center_star_number"] == center,
                "monthly_literal_center",
            )
            check(set(monthly["palaces"]) == set(OFFSETS), "monthly_palace_coverage")
            for direction, step in OFFSETS.items():
                n = monthly["palaces"][direction]["monthly_star_number"]
                check(
                    type(n) is int and n == (center - 1 + step) % 9 + 1,
                    "monthly_palace_" + direction,
                )
        at = annual["time_context"]
        uncertain_year = row["term_index"] == 2 and offset == 0
        if uncertain_year:
            check(
                annual["status"] == "partial" and not annual["palaces"],
                "annual_no_false_unique_plate",
            )
            check(
                at["effective_year"] is None
                and at["candidate_effective_years"] == [row["year"] - 1, row["year"]],
                "annual_reference_candidates",
            )
            check(
                at["valid_from"] is None and at["valid_until"] is None,
                "annual_no_false_unique_interval",
            )
        else:
            year = selected[0]
            check(
                annual["status"] == "complete" and annual["effective_year"] == year,
                "annual_reference_year",
            )
            check(
                _instant(at["valid_from"]) <= moment < _instant(at["valid_until"]),
                "annual_interval_contains_query",
            )
            center = (1864 - year) % 9 + 1
            check(
                type(annual["center_star_number"]) is int
                and annual["center_star_number"] == center,
                "annual_center",
            )
            for direction, step in OFFSETS.items():
                n = annual["palaces"][direction]["annual_star_number"]
                check(
                    type(n) is int and n == (center - 1 + step) % 9 + 1,
                    "annual_palace_" + direction,
                )
        if row["term_index"] == 2:
            check(
                personal is not None and period is not None,
                "all_lichun_consumers_present",
            )
            assert personal is not None and period is not None
            if offset == 0:
                check(
                    personal["status"] == "partial" and not personal["candidates"],
                    "minggua_no_false_unique_year",
                )
                check(
                    personal["time_context"]["effective_year"] is None,
                    "minggua_effective_year",
                )
                check(
                    period["effective_event_year"] is None
                    and period["candidate_effective_event_years"]
                    == [row["year"] - 1, row["year"]],
                    "period_event_year_candidates",
                )
                indices = sorted(
                    {(y - 1864) // 20 for y in (row["year"] - 1, row["year"])}
                )
                numbers = [i % 9 + 1 for i in indices]
                check(
                    period["candidate_period_numbers"] == numbers,
                    "period_candidate_numbers",
                )
                check(
                    period["number"] == (numbers[0] if len(numbers) == 1 else None),
                    "period_unique_number_status",
                )
            else:
                check(
                    personal["status"] == "complete"
                    and personal["time_context"]["effective_year"] == selected[0],
                    "minggua_reference_year",
                )
                check(
                    period["effective_event_year"] == selected[0]
                    and period["number"] == ((selected[0] - 1864) // 20) % 9 + 1,
                    "period_reference_year_and_number",
                )
    except (KeyError, ValueError, TypeError, IndexError, StopIteration, AssertionError):
        errors.append("missing_or_malformed_consumer_evidence")
    return errors


def audit_calendar_consumers(
    reference: dict[str, Any],
    protocol: dict[str, Any],
    literal: dict[str, Any],
    *,
    configuration: str,
    output: Callable[[dict[str, Any]], None] | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    validate_solar_terms_reference(reference)
    raw = (json.dumps(protocol, ensure_ascii=False, indent=2) + "\n").encode()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256 or configuration not in {
        "de440",
        "moshier",
    }:
        raise ValueError(
            "Require the full fixed consumer protocol and named configuration"
        )
    rows = [
        r
        for r in reference["rows"]
        if 1801 <= r["year"] <= 2199 and r["term_index"] % 2 == 0
    ]
    if len(rows) != 4788:
        raise ValueError("No year or sectional term may be dropped")
    counts: Counter[str] = Counter()
    failures = []
    numerical_failures = []
    actual_models: Counter[str] = Counter()
    max_difference = 0.0
    for r in rows:
        resolution = solar_term_resolution(r["year"], r["term"], "UTC")
        numerical = compare_resolution(r, resolution)
        model = resolution.get("ephemeris_model")
        actual_models[str(model)] += 1
        expected_model = (
            "fatebridge_de440_solar_v1" if configuration == "de440" else "moshier"
        )
        if model != expected_model:
            raise ValueError(
                "Actual model differs from the declared control configuration"
            )
        d = numerical["civil_roundtrip_difference_seconds_tt"]
        if d is not None:
            max_difference = max(max_difference, abs(d))
        if not numerical["within_tolerance"]:
            numerical_failures.append(
                {"year": r["year"], "term": r["term"], "difference_seconds_tt": d}
            )
        for offset in protocol["query_offsets_seconds_tt"]:
            target = r["jd_tt"] + offset / 86400
            moment = datetime_from_tt(target)
            actual_tt = ephemeris_time(moment).jd_tt
            errors = []
            if actual_tt is None or abs(actual_tt - target) * 86400 > 0.001:
                errors.append("query_clock_roundtrip")
            a = annual_stars(AnnualRequest(query_at=moment, timezone_name="UTC"))
            m = monthly_stars(MonthlyRequest(query_at=moment, timezone_name="UTC"))
            personal = period = None
            counts.update(annual=1, monthly=1)
            if r["term_index"] == 2:
                personal = minggua(
                    MingguaRequest(
                        birth_at=moment, timezone_name="UTC", gender_convention="male"
                    )
                )
                period = period_context(
                    HousePeriod(
                        basis="construction_completion",
                        event_at=moment,
                        timezone_name="UTC",
                        evidence="Synthetic fixed astronomical reference query; not a real house",
                    )
                )
                counts.update(minggua=1, period=1)
            errors.extend(
                check_consumer_observation(
                    r, offset, moment, a, m, literal, personal, period
                )
            )
            record = {
                "year": r["year"],
                "term": r["term"],
                "term_index": r["term_index"],
                "reference_jd_tt": r["jd_tt"],
                "offset_seconds_tt": offset,
                "query_utc": moment.isoformat(),
                "query_jd_tt": actual_tt,
                "actual_model": model,
                "crossing_difference_seconds_tt": d,
                "monthly_status": m["status"],
                "annual_status": a["status"],
                "monthly_year": m["time_context"]["effective_solar_year"],
                "monthly_number": m["time_context"]["solar_month_number"],
                "errors": errors,
            }
            if errors:
                failures.append(record)
            counts["queries"] += 1
            if output:
                output(record)
        if r["term_index"] == 22 and progress:
            progress(
                {
                    "last_year": r["year"],
                    "counts": dict(counts),
                    "consumer_failure_count": len(failures),
                    "numeric_failure_count": len(numerical_failures),
                }
            )
    complete = (
        counts["queries"] == 14364
        and counts["annual"] == counts["monthly"] == 14364
        and counts["minggua"] == counts["period"] == 1197
    )
    return {
        "protocol_id": protocol["id"],
        "configuration": configuration,
        "reference_events": len(rows),
        "observations": dict(counts),
        "full_declared_queue_completed": complete,
        "actual_models": dict(actual_models),
        "consumer_failures": failures,
        "consumer_decisions_passed": complete and not failures,
        "numeric_tolerance_seconds_unchanged": 1.0,
        "numeric_failures": numerical_failures,
        "maximum_civil_roundtrip_crossing_difference_seconds_tt": max_difference,
        "all_numeric_and_consumer_checks_passed": complete
        and not failures
        and not numerical_failures,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
        "absolute_observed_utc_accuracy_established": False,
        "scope": protocol["scope"],
    }
