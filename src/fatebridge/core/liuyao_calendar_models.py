"""Month sensitivity from completed same-run solar paths, without oracle data."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Sequence

from .almanac import BAZI_MONTH_START_TERMS, SolarTerm, get_solar_terms_for_year
from .analytic_solar import MODEL_ID

SCOPE = (
    "只比较本次实际完成的交气路径；十二节才换月，中气不换月。"
    "两路时刻沿用原交气记录声明的民用时标约定。"
    "月令相关判断沿用本次采用月支，原生路径的另一月支仅说明模型选择敏感性。"
    "模型差值不是误差上界或准确率，也未修复原生Moshier、重排另一完整卦盘或证明预测有效。"
)


def _selected_record(term: SolarTerm) -> dict[str, Any]:
    details = term.solar_model_details or {}
    return {
        "name": term.name,
        "month_branch": BAZI_MONTH_START_TERMS[term.name],
        "datetime_utc": term.moment.astimezone(timezone.utc).isoformat(),
        "julian_day_tt": details.get("selected_crossing_jd_tt"),
        "ephemeris_model": term.ephemeris_model,
        "role": "selected_calculation",
        "native_retflags": list(term.ephemeris_retflags),
    }


def _native_record(term: SolarTerm) -> dict[str, Any] | None:
    if term.resolution_provider == "swisseph" and term.ephemeris_model in {
        "moshier",
        "swieph",
        "jpl",
    }:
        return {**_selected_record(term), "role": "selected_native_calculation"}
    details = term.solar_model_details or {}
    model = details.get("native_choice_probe_model")
    text = details.get("native_choice_probe_datetime_utc")
    jd = details.get("native_choice_probe_jd_tt")
    if model not in {"moshier", "swieph", "jpl"} or not isinstance(text, str):
        return None
    if (
        isinstance(jd, bool)
        or not isinstance(jd, (int, float))
        or not math.isfinite(jd)
    ):
        return None
    try:
        clock = datetime.fromisoformat(text)
        if clock.utcoffset() is None:
            return None
    except ValueError:
        return None
    return {
        "name": term.name,
        "month_branch": BAZI_MONTH_START_TERMS[term.name],
        "datetime_utc": clock.astimezone(timezone.utc).isoformat(),
        "julian_day_tt": jd,
        "ephemeris_model": model,
        "role": "completed_native_choice_probe",
        "native_retflags": list(details.get("native_choice_probe_retflags", [])),
    }


def _bracket(
    rows: list[dict[str, Any]], instant: datetime
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    ordered = sorted(rows, key=lambda row: datetime.fromisoformat(row["datetime_utc"]))
    before = None
    for row in ordered:
        if datetime.fromisoformat(row["datetime_utc"]) <= instant:
            before = row
        elif before is not None:
            return before, row
    return None


def month_model_comparison(
    moment: datetime,
    timezone_name: str,
    month_context: dict[str, Any],
    *,
    terms: Sequence[SolarTerm] | None = None,
) -> dict[str, Any] | None:
    """Compare completed paths only; missing probes do not mean agreement.

    Native-only results do not start an alternate analytic calculation. When a
    selected analytic boundary exists, reuse the same cached surrounding years
    already needed by the primary calendar. All records remain actual instants.
    """
    if not any(
        month_context.get(key, {}).get("ephemeris_model") == MODEL_ID
        for key in ("start_term", "next_term")
    ):
        return None
    if moment.utcoffset() is None:
        raise ValueError("Month model comparison requires an aware instant")
    instant = moment.astimezone(timezone.utc)
    years = range(moment.year - 1, moment.year + 2)
    if terms is None:
        terms = [
            term
            for year in years
            for term in get_solar_terms_for_year(year, timezone_name)
        ]
    monthly = [term for term in terms if term.name in BAZI_MONTH_START_TERMS]
    selected = [_selected_record(term) for term in monthly]
    native: list[dict[str, Any]] = []
    missing = []
    active = []
    for term, chosen in zip(monthly, selected):
        probe = _native_record(term)
        if probe is None:
            missing.append(f"{term.moment.year}:{term.name}")
            continue
        native.append(probe)
        chosen_passed = datetime.fromisoformat(chosen["datetime_utc"]) <= instant
        probe_passed = datetime.fromisoformat(probe["datetime_utc"]) <= instant
        if chosen_passed != probe_passed:
            details = term.solar_model_details or {}
            active.append(
                {
                    "name": term.name,
                    "selected": chosen,
                    "native": probe,
                    "selected_has_passed": chosen_passed,
                    "native_has_passed": probe_passed,
                    "selected_minus_native_seconds_tt": details.get(
                        "selected_minus_native_seconds_tt"
                    ),
                }
            )
    selected_bracket = _bracket(selected, instant)
    native_bracket = _bracket(native, instant)
    result: dict[str, Any] = {
        "status": "not_compared_incomplete_native_probes",
        "calculation_month_branch": month_context["branch"],
        "comparison_utc": instant.isoformat(),
        "compared_month_boundaries": len(native),
        "missing_native_probes": missing,
        "coverage_complete": not missing
        and {(term.moment.year, term.name) for term in monthly}
        == {(year, name) for year in years for name in BAZI_MONTH_START_TERMS},
        "selected_models": sorted({row["ephemeris_model"] for row in selected}),
        "native_models": sorted({row["ephemeris_model"] for row in native}),
        "active_boundary_differences": active,
        "scope": SCOPE,
    }
    if (
        not result["coverage_complete"]
        or selected_bracket is None
        or native_bracket is None
    ):
        return result
    chosen_before, chosen_after = selected_bracket
    native_before, native_after = native_bracket
    full_records = {
        (term.name, term.moment.astimezone(timezone.utc).isoformat()): term.as_dict()
        for term in monthly
    }
    result["primary_context_consistent"] = all(
        full_records[(row["name"], row["datetime_utc"])] == month_context[key]
        for row, key in ((chosen_before, "start_term"), (chosen_after, "next_term"))
    )
    if not result["primary_context_consistent"]:
        result.update(
            status="not_compared_primary_boundaries_changed",
            coverage_complete=False,
            active_boundary_differences=[],
        )
        return result
    if chosen_before["month_branch"] != month_context["branch"]:
        raise RuntimeError("Primary month and same-run selected boundary disagree")
    changed = native_before["month_branch"] != month_context["branch"]
    result.update(
        status=(
            "month_differs_between_completed_paths"
            if changed
            else "same_month_in_completed_paths"
        ),
        month_changed=changed,
        native_month_branch=native_before["month_branch"],
        selected_previous_boundary=chosen_before,
        selected_next_boundary=chosen_after,
        native_previous_boundary=native_before,
        native_next_boundary=native_after,
    )
    return result
