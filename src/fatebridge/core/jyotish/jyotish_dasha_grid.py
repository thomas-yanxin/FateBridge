"""Period labels and correlated natal contexts on the existing birth-time grid.

This observer performs no ephemeris calls. Counts describe sampled coverage,
never probabilities; adjacent samples bracket possible label changes without
asserting continuous completeness or an exact change time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fatebridge.core.astro.sensitivity_grid import RecordedBirthSample
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.jyotish.jyotish import (
    divisional_chart,
    partition_longitudes,
)
from fatebridge.core.jyotish.jyotish_dasha_levels import vimshottari
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar


@dataclass(kw_only=True)
class PeriodBoundaryRange:
    earliest: UTCCalendar
    latest: UTCCalendar


def _segment(rows: list[dict[str, Any]], index: int, offset: float) -> None:
    """Keep noncontiguous appearances separate, even within one ruler pair."""
    if rows and rows[-1]["last_grid_index"] == index - 1:
        rows[-1].update(last_grid_index=index, last_offset_seconds=offset)
        rows[-1]["sample_count"] += 1
    else:
        rows.append(
            {
                "first_grid_index": index,
                "last_grid_index": index,
                "first_offset_seconds": offset,
                "last_offset_seconds": offset,
                "sample_count": 1,
            }
        )


def _numeric_range(
    ranges: dict[str, dict[str, float]], field_name: str, value: float | None
) -> None:
    if value is None:
        return
    else:
        bounds = ranges.setdefault(field_name, {"minimum": value, "maximum": value})
        bounds["minimum"] = min(bounds["minimum"], value)
        bounds["maximum"] = max(bounds["maximum"], value)


def _context(chart: dict[str, Any], planet: dict[str, Any]) -> dict[str, Any]:
    result = {
        "chart": f"D{chart['division']}",
        "coordinate_scope": chart["coordinate_scope"],
        "planet_id": planet["id"],
        "sign": planet["sign"],
        "house": planet["house"],
        "dignity": planet["dignity"],
        "owned_houses": [
            h["house"] for h in chart["houses"] if h["lord"] == planet["id"]
        ],
    }
    if "physical_state" in planet:
        physical = planet["physical_state"]
        degree = physical.get("degree_condition", {})
        orb = physical.get("combustion", {})
        result["d1_conditions"] = {
            "motion": physical["motion"],
            "longitude_motion_basis": physical.get("longitude_motion_context", {}).get(
                "rate_basis", "unspecified"
            ),
            "degree_zone": degree.get("degree_zone"),
            "baladi_avastha": degree.get("baladi_avastha", {}).get("state"),
            "solar_orb_status": orb.get("status"),
            "solar_orb_degrees": orb.get("orb_degrees"),
            "dispositor_relationship": planet.get("dispositor_relationship"),
            "scope": "same sampled D1; motion calculation bases remain separate context groups. Discrete conditions only, not complete strength",
        }
    else:
        pass
    if "native_position_interpretation" in planet:
        # Retain discrete source meanings in the grouping key. Continuous ray
        # geometry belongs to the source policy, otherwise every birth sample
        # would become a separate context even within one model interpretation.
        source = planet["native_position_interpretation"]
        result["native_position_interpretation"] = {
            key: source[key]
            for key in (
                "status",
                "unbent_ray_domain",
                "position_interpretation",
                "reason",
                "observational_accuracy_certified",
            )
            if key in source
        }
    else:
        pass
    return result


class DashaGrid:
    def __init__(
        self,
        analysis: datetime,
        year_basis: str,
        divisions: list[int] | None,
        dasha_depth: int = 2,
    ) -> None:
        self.analysis = analysis
        self.year_basis = year_basis
        self.dasha_depth = dasha_depth
        self.divisions = [1, *([9, 10] if divisions is None else divisions)]
        self.count = 0
        self.instants: set[TTInstant] = set()
        self.valid_instants: set[TTInstant] = set()
        self.omitted: list[dict[str, Any]] = []
        self.endpoint_samples: list[dict[str, Any]] = []
        self.endpoint_omitted: list[dict[str, Any]] = []
        self.variants: dict[tuple[str, ...], dict[str, Any]] = {}
        self.contexts: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
        self.transitions: list[dict[str, Any]] = []
        self.methods: set[str] = set()
        self.previous: tuple[float, tuple[str, ...]] | None = None

    def observe(
        self,
        offset: float,
        recorded: RecordedBirthSample,
        raw: dict[str, Any],
        endpoint_subset: bool = False,
    ) -> None:
        index = self.count
        self.count += 1
        epoch = recorded.epoch
        calendar_key = None
        if epoch.utc_datetime is not None:
            calendar_key = utc_calendar(epoch.utc_datetime)
        elif (
            not epoch.utc_is_leap_second
            and (point := recorded.nominal_calendar) is not None
        ):
            calendar_key = point.as_calendar()
        else:
            pass
        self.instants.add(recorded.tt)
        self.methods.add(raw["time_scale_context"]["method"])
        if calendar_key is None or utc_calendar(self.analysis) < calendar_key:
            omitted: dict[str, object] = {
                "offset_seconds": offset,
                "reason": (
                    "no_supported_birth_calendar_key"
                    if calendar_key is None
                    else "analysis_precedes_candidate_birth"
                ),
            }
            if calendar_key is None:
                omitted["physical_epoch"] = epoch.representation()
            else:
                pass
            self.omitted.append(omitted)
            if endpoint_subset:
                self.endpoint_omitted.append(omitted)
            else:
                pass
            self.previous = None
            return
        else:
            pass
        self.valid_instants.add(recorded.tt)
        period = vimshottari(
            calendar_key,
            raw["longitudes"]["Moon"],
            self.analysis,
            year_basis=self.year_basis,
            dasha_depth=self.dasha_depth,
        )
        if endpoint_subset:
            self.endpoint_samples.append(
                {
                    "offset_seconds": offset,
                    "birth_balance": period["birth_balance"],
                    "time_quantization": period["time_quantization"],
                    "current_major": period["current_major"],
                    "current_sub": period["current_sub"],
                    **(
                        {"subdivisions": period["subdivisions"]}
                        if self.dasha_depth > 2
                        else {}
                    ),
                }
            )
        else:
            pass
        key = (period["current_major"]["lord"], period["current_sub"]["lord"])
        if self.dasha_depth > 2:
            key = tuple(row["lord"] for row in period["subdivisions"]["current_levels"])
        else:
            pass
        row = self.variants.setdefault(
            key,
            {
                "major_lord": key[0],
                "sub_lord": key[1],
                **({"period_lord_chain": list(key)} if self.dasha_depth > 2 else {}),
                "sample_count": 0,
                "sample_segments": [],
                "period_boundary_ranges": {},
            },
        )
        row["sample_count"] += 1
        _segment(row["sample_segments"], index, offset)
        levels = [
            ("current_major", period["current_major"]),
            ("current_sub", period["current_sub"]),
        ]
        if self.dasha_depth > 2:
            levels.extend(
                (f"subdivisions.current_levels.{level_index}", level)
                for level_index, level in enumerate(
                    period["subdivisions"]["current_levels"][2:], 2
                )
            )
        else:
            pass
        boundary_ranges: dict[str, PeriodBoundaryRange] = row["period_boundary_ranges"]
        for level_path, level in levels:
            for boundary in ("start", "end"):
                instant = ZonedCalendar.from_isoformat(level[boundary]).utc
                bounds = boundary_ranges.setdefault(
                    f"{level_path}.{boundary}",
                    PeriodBoundaryRange(earliest=instant, latest=instant),
                )
                bounds.earliest = min(bounds.earliest, instant)
                bounds.latest = max(bounds.latest, instant)
        if self.previous is not None and self.previous[1] != key:
            self.transitions.append(
                {
                    "lower_birth_offset_seconds": self.previous[0],
                    "upper_birth_offset_seconds": offset,
                    "lower_stage": list(self.previous[1]),
                    "upper_stage": list(key),
                }
            )
        else:
            pass
        self.previous = (offset, key)
        groups = self.contexts.setdefault(key, {})
        longitudes = partition_longitudes(raw)
        for division in self.divisions:
            chart = divisional_chart(raw, division, partition_longitudes=longitudes)
            for planet in chart["planets"]:
                if planet["id"] not in key:
                    continue
                else:
                    pass
                context = _context(chart, planet)
                context["roles"] = [
                    role
                    for role, lord in zip(
                        ("major", "sub", "pratyantar", "sookshma", "prana", "deha"), key
                    )
                    if planet["id"] == lord
                ]
                signature = json.dumps(context, sort_keys=True)
                group = groups.setdefault(
                    signature,
                    {
                        **context,
                        "sample_count": 0,
                        "sample_segments": [],
                        "sampled_numeric_ranges": {},
                    },
                )
                group["sample_count"] += 1
                _segment(group["sample_segments"], index, offset)
                for leaf in ("longitude", "degree_in_sign"):
                    _numeric_range(group["sampled_numeric_ranges"], leaf, planet[leaf])
                physical = planet.get("physical_state", {})
                for leaf in (
                    "latitude",
                    "longitude_speed_degrees_per_day",
                    "longitude_speed_native_degrees_per_day",
                ):
                    _numeric_range(
                        group["sampled_numeric_ranges"],
                        f"physical_state.{leaf}",
                        physical.get(leaf),
                    )
                _numeric_range(
                    group["sampled_numeric_ranges"],
                    "physical_state.degree_condition.uchcha_bala.value",
                    physical.get("degree_condition", {})
                    .get("uchcha_bala", {})
                    .get("value"),
                )

    def result(self) -> dict[str, Any]:
        variants = []
        for key, row in self.variants.items():
            boundary_ranges: dict[str, PeriodBoundaryRange] = row[
                "period_boundary_ranges"
            ]
            variants.append(
                {
                    **row,
                    "period_boundary_ranges": {
                        field_name: {
                            "minimum": bounds.earliest.isoformat(),
                            "maximum": bounds.latest.isoformat(),
                        }
                        for field_name, bounds in boundary_ranges.items()
                    },
                    "natal_ruler_contexts": list(self.contexts[key].values()),
                }
            )
        if any(
            row["reason"] == "no_supported_birth_calendar_key" for row in self.omitted
        ):
            status = "partial_samples_without_calendar_key"
        elif self.omitted:
            status = "partial_samples_before_analysis"
        else:
            status = "sampled_full_birth_grid" if self.count else "not_assessed"
        return {
            **(
                {
                    "requested_dasha_depth": self.dasha_depth,
                    "stage_key_scope": "full selected period_lord_chain; each ruler context uses this same sampled birth",
                }
                if self.dasha_depth > 2
                else {}
            ),
            "status": status,
            "method": "Same recorded TT grid and Moon positions as india. Periods use the sample's supported nominal UTC calendar key.",
            "requested_sample_count": self.count,
            "evaluated_sample_count": self.count - len(self.omitted),
            "distinct_birth_instant_count": len(self.instants),
            "distinct_evaluated_birth_instant_count": len(self.valid_instants),
            "omitted_samples": self.omitted,
            "samples": self.endpoint_samples,
            "samples_scope": "Endpoint and center subset of the same periods evaluated for stage_variants.",
            "endpoint_subset_requested_count": len(self.endpoint_samples)
            + len(self.endpoint_omitted),
            "endpoint_subset_evaluated_count": len(self.endpoint_samples),
            "endpoint_subset_omitted_samples": self.endpoint_omitted,
            "stage_variants": variants,
            "adjacent_stage_change_brackets": self.transitions,
            "time_conversion_methods": sorted(self.methods),
            "natal_ruler_context_scope": "each context and its period label use the same sampled birth; join sample_segments by grid index, never combine unmatched alternatives. Top-level natal_ruler_context is nominal only.",
            "limitation": "离散网格覆盖，不保证所有中间边界；计数不是概率。运主组合不表示绝对起止相同；边界区间与度数范围是样本最小最大值，不是误差置信区间。区间跨零度时范围可能较宽。沿用名义UTC日期历时，不计闰秒标签；天文换算不是实测UT1。",
        }
