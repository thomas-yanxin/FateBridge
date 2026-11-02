"""Period labels and correlated natal contexts on the existing birth-time grid.

This observer performs no ephemeris calls. Counts describe sampled coverage,
never probabilities; adjacent samples bracket possible label changes without
asserting continuous completeness or an exact change time.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fatebridge.core.jyotish import divisional_chart, vimshottari


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


def _range(row: dict[str, Any], name: str, value: Any) -> None:
    if value is None:
        return
    current = row.setdefault(name, {"minimum": value, "maximum": value})
    current["minimum"] = min(current["minimum"], value)
    current["maximum"] = max(current["maximum"], value)


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
    return result


class DashaGrid:
    def __init__(
        self,
        birth: datetime,
        analysis: datetime,
        year_basis: str,
        divisions: list[int] | None,
        dasha_depth: int = 2,
    ) -> None:
        self.birth = birth
        self.analysis = analysis
        self.year_basis = year_basis
        self.dasha_depth = dasha_depth
        self.divisions = [1, *([9, 10] if divisions is None else divisions)]
        self.count = 0
        self.instants: set[datetime] = set()
        self.valid_instants: set[datetime] = set()
        self.omitted: list[dict[str, Any]] = []
        self.variants: dict[tuple[str, ...], dict[str, Any]] = {}
        self.contexts: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
        self.transitions: list[dict[str, Any]] = []
        self.methods: set[str] = set()
        self.previous: tuple[float, tuple[str, ...]] | None = None

    def observe(self, offset: float, raw: dict[str, Any]) -> None:
        index = self.count
        self.count += 1
        shifted = self.birth + timedelta(seconds=offset)
        self.instants.add(shifted)
        self.methods.add(raw["time_scale_context"]["method"])
        if self.analysis < shifted:
            self.omitted.append(
                {
                    "offset_seconds": offset,
                    "reason": "analysis_precedes_candidate_birth",
                }
            )
            self.previous = None
            return
        self.valid_instants.add(shifted)
        period = vimshottari(
            shifted,
            raw["longitudes"]["Moon"],
            self.analysis,
            year_basis=self.year_basis,
            dasha_depth=self.dasha_depth,
        )
        key = (period["current_major"]["lord"], period["current_sub"]["lord"])
        if self.dasha_depth > 2:
            key = tuple(row["lord"] for row in period["subdivisions"]["current_levels"])
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
        for level in ("current_major", "current_sub"):
            for boundary in ("start", "end"):
                _range(
                    row["period_boundary_ranges"],
                    f"{level}.{boundary}",
                    period[level][boundary],
                )
        if self.dasha_depth > 2:
            for level_index, deeper in enumerate(
                period["subdivisions"]["current_levels"][2:], 2
            ):
                for boundary in ("start", "end"):
                    _range(
                        row["period_boundary_ranges"],
                        f"subdivisions.current_levels.{level_index}.{boundary}",
                        deeper[boundary],
                    )
        if self.previous is not None and self.previous[1] != key:
            self.transitions.append(
                {
                    "lower_birth_offset_seconds": self.previous[0],
                    "upper_birth_offset_seconds": offset,
                    "lower_stage": list(self.previous[1]),
                    "upper_stage": list(key),
                }
            )
        self.previous = (offset, key)
        groups = self.contexts.setdefault(key, {})
        for division in self.divisions:
            chart = divisional_chart(raw, division)
            for planet in chart["planets"]:
                if planet["id"] not in key:
                    continue
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
                    _range(group["sampled_numeric_ranges"], leaf, planet[leaf])
                physical = planet.get("physical_state", {})
                for leaf in (
                    "latitude",
                    "longitude_speed_degrees_per_day",
                    "longitude_speed_native_degrees_per_day",
                ):
                    _range(
                        group["sampled_numeric_ranges"],
                        f"physical_state.{leaf}",
                        physical.get(leaf),
                    )
                _range(
                    group["sampled_numeric_ranges"],
                    "physical_state.degree_condition.uchcha_bala.value",
                    physical.get("degree_condition", {})
                    .get("uchcha_bala", {})
                    .get("value"),
                )

    def result(self) -> dict[str, Any]:
        variants = []
        for key, row in self.variants.items():
            variants.append(
                {**row, "natal_ruler_contexts": list(self.contexts[key].values())}
            )
        return {
            **(
                {
                    "requested_dasha_depth": self.dasha_depth,
                    "stage_key_scope": "full selected period_lord_chain; each ruler context uses this same sampled birth",
                }
                if self.dasha_depth > 2
                else {}
            ),
            "status": (
                "partial_samples_before_analysis"
                if self.omitted
                else "sampled_full_birth_grid" if self.count else "not_assessed"
            ),
            "method": "same UTC birth grid as india: endpoints, center and max30-second step; no extra ephemeris calls",
            "requested_sample_count": self.count,
            "evaluated_sample_count": self.count - len(self.omitted),
            "distinct_birth_instant_count": len(self.instants),
            "distinct_evaluated_birth_instant_count": len(self.valid_instants),
            "omitted_samples": self.omitted,
            "stage_variants": variants,
            "adjacent_stage_change_brackets": self.transitions,
            "time_conversion_methods": sorted(self.methods),
            "natal_ruler_context_scope": "each context and its period label use the same sampled birth; join sample_segments by grid index, never combine unmatched alternatives. Top-level natal_ruler_context is nominal only.",
            "limitation": "离散网格覆盖，不保证所有中间边界；计数不是概率。运主组合不表示绝对起止相同；边界区间与度数范围是样本最小最大值，不是误差置信区间。区间跨零度时范围可能较宽。沿用名义UTC日期历时，不计闰秒标签；天文换算不是实测UT1。",
        }
