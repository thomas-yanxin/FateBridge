"""Twelve sectional solar months; a January date can belong to the prior year."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fatebridge.core import almanac
from fatebridge.utils.timezones import parse_timezone_name

from .calendar import (
    MOSHIER_BOUNDARY_GUARD_SECONDS,
    boundary_model_policy,
    boundary_uncertainty_reason,
    solar_term_resolution,
)

JIE = (
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
    "小寒",
)
MONTH_BRANCHES = tuple("寅卯辰巳午未申酉戌亥子丑")


def _next_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + step
    y, m = divmod(index, 12)
    return y, m + 1


def _boundary(year: int, month: int, zone: str) -> Dict[str, Any]:
    name = JIE[month - 1]
    civil_year = year + int(month == 12)
    return {
        "term_name": name,
        "civil_year": civil_year,
        **solar_term_resolution(civil_year, name, zone),
    }


def solar_month_context(
    effective_year: Optional[int],
    month_number: Optional[int],
    moment: Optional[datetime],
    zone: str,
) -> Dict[str, Any]:
    tz = parse_timezone_name(zone)
    local = moment.astimezone(tz) if moment is not None else None
    result: Dict[str, Any] = {
        "effective_solar_year": None,
        "solar_month_number": None,
        "month_branch": None,
        "timezone_name": zone,
        "local_moment": local.isoformat() if local is not None else None,
        "year_boundary": "lichun",
        "month_boundary": "twelve_jie_instants_not_zhongqi_lunar_or_gregorian_months",
        "interval_policy": "start_inclusive_end_exclusive",
    }
    if effective_year is None and local is None:
        return {**result, "input_basis": "missing"}
    if local is not None:
        # Sorting and membership use actual instants, never repeated wall-clock
        # labels or the civil month number. Include December on either side.
        boundaries = []
        for civil_year in range(local.year - 1, local.year + 2):
            for term in almanac.get_solar_terms_for_year(civil_year, zone):
                if term.name in JIE:
                    month = JIE.index(term.name) + 1
                    boundaries.append(
                        (
                            term.moment.astimezone(timezone.utc),
                            civil_year - int(month == 12),
                            month,
                        )
                    )
        boundaries.sort()
        _, effective_year, month_number = next(
            row
            for row in reversed(boundaries)
            if row[0] <= local.astimezone(timezone.utc)
        )
    assert effective_year is not None and month_number is not None
    next_year, next_month = _next_month(effective_year, month_number, 1)
    start = _boundary(effective_year, month_number, zone)
    end = _boundary(next_year, next_month, zone)
    result.update(
        effective_solar_year=effective_year,
        solar_month_number=month_number,
        month_branch=MONTH_BRANCHES[month_number - 1],
        input_basis="aware_datetime" if local is not None else "confirmed_solar_month",
        valid_from=start["moment"],
        valid_until=end["moment"],
        timing={
            "provider": "fatebridge.core.almanac.get_solar_terms_for_year",
            "start_resolution": start,
            "end_resolution": end,
            "precision_scope": "engine_computed_not_arbitrary_year_second_certification",
        },
        interval_scope="computed_interval_not_second_certification",
        precision_policy={
            "moshier_guard_seconds": MOSHIER_BOUNDARY_GUARD_SECONDS,
            "guard_scope": "operational_candidate_preservation_not_error_bound_or_accuracy_credit",
            "numeric_acceptance_gate_seconds": 1.0,
            "numeric_reference_protocol": "fengshui_monthly_jie_de440_tt_v1",
        },
    )
    model_policies = []
    for name, resolution in (("start", start), ("end", end)):
        policy = boundary_model_policy(resolution)
        if policy is not None:
            model_policies.append({"boundary": name, **policy})
    if model_policies:
        result["precision_policy"]["boundary_model_policies"] = model_policies
    if local is not None:
        candidates = {(effective_year, month_number)}
        uncertain = []
        for resolution, neighbor in (
            (start, _next_month(effective_year, month_number, -1)),
            (end, (next_year, next_month)),
        ):
            reason = boundary_uncertainty_reason(local, resolution)
            if reason is not None:
                candidates.add(neighbor)
                uncertain.append({**resolution, "uncertainty_reason": reason})
        if uncertain:
            resolutions = {
                (effective_year, month_number): start,
                (next_year, next_month): end,
            }

            def endpoint(year: int, month: int) -> Dict[str, Any]:
                key = (year, month)
                if key not in resolutions:
                    resolutions[key] = _boundary(year, month, zone)
                # Keep actual clock/model identity inline. Large per-root
                # analytical details live once in this same result, reachable
                # through the exact full record path even after projection.
                return {
                    **{
                        name: value
                        for name, value in resolutions[key].items()
                        if name != "solar_model_details"
                    },
                    "full_resolution_path": (
                        "layers.monthly_stars.time_context."
                        f"candidate_boundary_resolutions.{year}_{month}"
                    ),
                }

            intervals = []
            for year, month in sorted(candidates):
                left = endpoint(year, month)
                right = endpoint(*_next_month(year, month, 1))
                intervals.append(
                    {
                        "effective_solar_year": year,
                        "solar_month_number": month,
                        "month_branch": MONTH_BRANCHES[month - 1],
                        "candidate_only": True,
                        "valid_from": left["moment"],
                        "valid_until": right["moment"],
                        "start_resolution": left,
                        "end_resolution": right,
                    }
                )
            # The model-side window is useful provenance, not a confirmed
            # interval. Keep every possible month's actual endpoint sources.
            provisional = {
                key: result[key]
                for key in (
                    "effective_solar_year",
                    "solar_month_number",
                    "month_branch",
                    "valid_from",
                    "valid_until",
                )
            }
            result["timing"]["interval_basis"] = "provisional_solar_month"
            result.update(
                month_status="requires_confirmation",
                provisional_effective_solar_year=effective_year,
                provisional_solar_month_number=month_number,
                effective_solar_year=(
                    effective_year if len({y for y, m in candidates}) == 1 else None
                ),
                solar_month_number=None,
                month_branch=None,
                valid_from=None,
                valid_until=None,
                provisional_interval=provisional,
                candidate_months=intervals,
                candidate_boundary_resolutions={
                    f"{year}_{month}": resolution
                    for (year, month), resolution in resolutions.items()
                },
                uncertain_boundary_resolutions=uncertain,
                interval_scope="provisional_interval_until_boundary_confirmed",
            )
    return result
