"""Compare categorical and strength evidence across the recorded birth-time grid."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Protocol

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.sensitivity_grid import RecordedBirthSample
from fatebridge.core.jyotish.jyotish_ashtakavarga import SampleGrid as AshtakavargaGrid
from fatebridge.core.jyotish.jyotish_balas import (
    DirectionalResolution,
    other_balas,
    resolve_directional_strength,
)
from fatebridge.core.jyotish.jyotish_charts import GRAHAS, partition_longitudes
from fatebridge.core.jyotish.jyotish_clock import birth_grid
from fatebridge.core.jyotish.jyotish_dasha_levels import nakshatra
from fatebridge.core.jyotish.jyotish_kala import temporal_balas
from fatebridge.core.jyotish.jyotish_sources import (
    PositionCalculation,
    SourceComparison,
)
from fatebridge.core.jyotish.jyotish_sthana import SthanaResolution, resolve_sthana
from fatebridge.core.jyotish.jyotish_vargas import varga_sign


class PositionSampleObserver(Protocol):
    def __call__(self, offset_seconds: float, positions: dict[str, Any], /) -> None: ...


class DashaGridObserver(Protocol):
    def observe(
        self,
        offset: float,
        recorded: RecordedBirthSample,
        raw: dict[str, Any],
        endpoint_subset: bool,
    ) -> None: ...


def birth_sensitivity(
    birth: AstroBirthInfo,
    *,
    birth_time_uncertainty_minutes: float | None,
    raw: dict[str, Any],
    charts: dict[str, Any],
    nominal_longitudes: dict[str, float | Fraction],
    sthana_resolution: SthanaResolution,
    directional: DirectionalResolution,
    additional_balas: dict[str, Any],
    solar_context: dict[str, Any],
    source_comparison: SourceComparison,
    nominal_source_index: int,
    calculate_positions: PositionCalculation,
    node_mode: str,
    ephemeris_policy: str,
    cheshta_model: str,
    saptavargaja_profile: str,
    drekkana_profile: str,
    sample_observer: PositionSampleObserver | None,
    dasha_grid: DashaGridObserver | None,
) -> dict[str, Any]:
    sensitivity: dict[str, Any] = {
        "status": "not_assessed",
        "uncertainty_minutes": birth_time_uncertainty_minutes,
        "scope": "birth instant uncertainty; coordinates and ruleset held fixed",
        "limitation": "未给不确定范围不表示出生时刻精确；分盘上升与宫位对时刻敏感。",
    }
    if birth_time_uncertainty_minutes is not None:
        ashtakavarga_grid = AshtakavargaGrid(list(charts))
        source_samples = []
        grid = birth_grid(birth, birth_time_uncertainty_minutes, ephemeris_policy)
        if grid.clock_interval:
            sensitivity["clock_interval"] = grid.clock_interval
            sensitivity["scope"] = (
                "Recorded solar-wall endpoints on the physical TT axis; coordinates and ruleset held fixed"
            )
        seen: dict[str, dict[str, set]] = {
            name: {p: set() for p in ["Ascendant", *GRAHAS]} for name in charts
        }
        condition_samples: dict[str, set] = {p: set() for p in GRAHAS[:7]}
        bala_samples: dict[str, list[float]] = {p: [] for p in GRAHAS[:7]}
        sampled_fallback = set(raw["ephemeris_quality"]["fallback_bodies"])
        sampled_future_time_assumption = raw["time_scale_context"][
            "future_leap_seconds_assumed_unchanged"
        ]
        strength_samples: dict[str, dict[str, list[float]]] = {
            p: {key: [] for key in values}
            for p, values in sthana_resolution.summary.items()
        }
        dig_samples: dict[str, list[float]] = {p: [] for p in GRAHAS[:7]}
        drik_samples: dict[str, dict[str, list[float]]] = {}
        temporal_samples: dict[str, dict[str, dict[str, list[float]]]] = {
            "kala_bala": {},
            "cheshta_bala": {},
            "yuddha_bala": {},
        }
        time_lord_samples: dict[str, set[str]] = {
            key: set()
            for key in (
                "tribhaga_bala",
                "abda_bala",
                "masa_bala",
                "dina_bala",
                "hora_bala",
            )
        }
        moon_nature_samples = set()
        solar_bracket_states: dict[tuple[str, str], int] = {}
        motion_model_samples = set()
        war_state_samples = set()
        nak_samples: dict[str, dict[tuple, int]] = {
            p: {} for p in ["Ascendant", *GRAHAS]
        }
        moon_samples = []
        last_index = len(grid.samples) - 1
        nominal_epoch = grid.samples[grid.nominal_index][1].epoch
        for index, (offset, recorded) in enumerate(grid.samples):
            at_nominal_epoch = recorded.epoch is nominal_epoch
            sample = (
                raw
                if at_nominal_epoch
                else calculate_positions(
                    birth,
                    recorded.epoch,
                    node_mode,
                    ephemeris_policy,
                    cheshta_model,
                )
            )
            source_index = (
                nominal_source_index
                if at_nominal_epoch
                else source_comparison.add(sample)
            )
            source_samples.append(
                {
                    "offset_seconds": offset,
                    "source_index": source_index,
                    "utc_label": recorded.epoch.utc_label,
                    "utc_is_leap_second": recorded.epoch.utc_is_leap_second,
                }
            )
            endpoint_subset = index in {0, grid.nominal_index, last_index}
            if dasha_grid is not None:
                dasha_grid.observe(offset, recorded, sample, endpoint_subset)
            if sample_observer is not None:
                sample_observer(offset, sample)
            ashtakavarga_grid.observe(offset, sample)
            sample_longitudes = (
                nominal_longitudes if at_nominal_epoch else partition_longitudes(sample)
            )
            for name in charts:
                d = int(name[1:])
                asc_sign = varga_sign(sample["ascendant"], d)
                seen[name]["Ascendant"].add((asc_sign, 1))
                for p in GRAHAS:
                    sign = varga_sign(sample_longitudes[p], d)
                    seen[name][p].add((sign, (sign - asc_sign) % 12 + 1))
            for p, lon in {
                **sample_longitudes,
                "Ascendant": sample["ascendant"],
            }.items():
                star = nakshatra(lon)
                label = (star["index"], star["name"], star["lord"], star["pada"])
                nak_samples[p][label] = nak_samples[p].get(label, 0) + 1
            sampled_fallback.update(sample["ephemeris_quality"]["fallback_bodies"])
            sampled_future_time_assumption |= sample["time_scale_context"][
                "future_leap_seconds_assumed_unchanged"
            ]
            sample_sthana_resolution = (
                sthana_resolution
                if at_nominal_epoch
                else resolve_sthana(
                    sample["longitudes"],
                    sample["ascendant"],
                    saptavargaja_profile,
                    drekkana_profile,
                )
            )
            sample_directional = (
                directional
                if at_nominal_epoch
                else resolve_directional_strength(
                    sample["longitudes"], sample["ascendant"], sample["midheaven"]
                )
            )
            sampled_balas = (
                additional_balas
                if at_nominal_epoch
                else other_balas(sample, directional=sample_directional)
            )
            if not at_nominal_epoch:
                sampled_balas.update(
                    temporal_balas(
                        sample,
                        solar_context,
                        birth.longitude,
                        sthana=sample_sthana_resolution,
                        dig=sample_directional,
                    )
                )
            solar_state = sampled_balas["kala_bala"]["solar_context"]
            bracket_state = (
                solar_state["sunrise_day_status"],
                solar_state["active_arc_status"],
            )
            solar_bracket_states[bracket_state] = (
                solar_bracket_states.get(bracket_state, 0) + 1
            )
            for p, value in sampled_balas["dig_bala"]["summary"].items():
                dig_samples[p].append(value)
            moon_nature_samples.add(
                tuple(sampled_balas["drik_bala"]["nature_context"]["moon_options"])
            )
            motion_model_samples.add(
                sampled_balas["cheshta_bala"]["model_context"]["status"]
            )
            war = sampled_balas["kala_bala"]["components"]["yuddha_bala"]
            war_state_samples.add(
                tuple(
                    (tuple(pair["planets"]), pair["status"], pair["winner"])
                    for pair in war["pairs"]
                )
            )
            for scenario, data in sampled_balas["drik_bala"]["scenarios"].items():
                bucket = drik_samples.setdefault(scenario, {p: [] for p in GRAHAS[:7]})
                for p, value in data["summary"].items():
                    bucket[p].append(value)
            for key in temporal_samples:
                component = war if key == "yuddha_bala" else sampled_balas[key]
                for scenario, values in component["scenarios"].items():
                    bucket = temporal_samples[key].setdefault(
                        scenario, {p: [] for p in GRAHAS[:7]}
                    )
                    for p, value in values.items():
                        if value is not None:
                            bucket[p].append(value)
            for key in time_lord_samples:
                time_lord_samples[key].add(
                    sampled_balas["kala_bala"]["components"][key]["ruler"]
                    or "not_available"
                )
            for p, values in sample_sthana_resolution.summary.items():
                for key, value in values.items():
                    strength_samples[p][key].append(value)
            for p in GRAHAS[:7]:
                state = sample["physical_states"][p]
                degree = state["degree_condition"]
                condition_samples[p].add(
                    (
                        degree["degree_zone"],
                        degree["baladi_avastha"]["state"],
                        state["motion"],
                        state.get("combustion", {}).get("status", "not_applicable"),
                        state.get("longitude_motion_context", {}).get(
                            "rate_basis", "unspecified"
                        ),
                    )
                )
                bala_samples[p].append(degree["uchcha_bala"]["value"])
            if endpoint_subset:
                moon_samples.append(
                    {
                        "offset_seconds": offset,
                        "longitude": sample["longitudes"]["Moon"],
                        "utc_label": recorded.epoch.utc_label,
                        "utc_is_leap_second": recorded.epoch.utc_is_leap_second,
                    }
                )
        alternatives = {
            name: {
                p: [{"sign": SIGNS[s], "house": h} for s, h in sorted(values)]
                for p, values in points.items()
                if len(values) > 1
            }
            for name, points in seen.items()
        }
        condition_alternatives = {
            p: [
                {
                    "degree_zone": zone,
                    "baladi_avastha": age,
                    "motion": motion,
                    "solar_orb_status": orb_status,
                    "longitude_motion_basis": basis,
                }
                for zone, age, motion, orb_status, basis in sorted(values)
            ]
            for p, values in condition_samples.items()
            if len(values) > 1
        }
        discrete_strength_alternatives = {
            p: {
                key: sorted(set(values))
                for key, values in components.items()
                if key
                in {
                    "saptavargaja_bala",
                    "ojayugma_bala",
                    "kendradi_bala",
                    "drekkana_bala",
                }
                and len(set(values)) > 1
            }
            for p, components in strength_samples.items()
        }
        discrete_strength_alternatives = {
            p: values for p, values in discrete_strength_alternatives.items() if values
        }
        nak_alternatives = {
            p: [
                {
                    "index": index,
                    "name": name,
                    "lord": lord,
                    "pada": pada,
                    "sample_count": count,
                }
                for (index, name, lord, pada), count in sorted(options.items())
            ]
            for p, options in nak_samples.items()
            if len(options) > 1
        }
        sensitivity.update(
            {
                "status": (
                    "changes_detected"
                    if any(alternatives.values())
                    or condition_alternatives
                    or discrete_strength_alternatives
                    or len(moon_nature_samples) > 1
                    or len(motion_model_samples) > 1
                    or len(war_state_samples) > 1
                    or len(solar_bracket_states) > 1
                    or nak_alternatives
                    or any(len(values) > 1 for values in time_lord_samples.values())
                    else "no_change_on_sample_grid"
                ),
                "method": "Recorded TT grid including endpoints and supplied instant; max 30 SI seconds between physical samples",
                "sample_count": len(grid.samples),
                "ashtakavarga_variants": ashtakavarga_grid.result(),
                "alternatives": alternatives,
                "nakshatra_alternatives": nak_alternatives,
                "nakshatra_sampled_points": list(nak_samples),
                "nakshatra_sample_scope": "Nakshatra, ruler and Pada use the same recorded TT grid. Counts describe sampled coverage only.",
                "physical_condition_alternatives": condition_alternatives,
                "dig_bala_sample_ranges": {
                    p: {"minimum": min(values), "maximum": max(values)}
                    for p, values in dig_samples.items()
                },
                "drik_bala_scenario_sample_ranges": {
                    scenario: {
                        p: {
                            "minimum": min(values),
                            "maximum": max(values),
                            "sample_count": len(values),
                        }
                        for p, values in planets.items()
                    }
                    for scenario, planets in drik_samples.items()
                },
                "drik_moon_nature_options_on_grid": [
                    list(options) for options in sorted(moon_nature_samples)
                ],
                "cheshta_model_statuses_on_grid": sorted(motion_model_samples),
                "yuddha_states_on_grid": [
                    [
                        {"planets": list(planets), "status": status, "winner": winner}
                        for planets, status, winner in state
                    ]
                    for state in sorted(war_state_samples, key=repr)
                ],
                "additional_bala_sample_scope": "directional continuous ranges and conditional Drik branches on the same UTC grid; Naisargika coefficients are constant. Branch counts are coverage, not probabilities.",
                "temporal_bala_scenario_sample_ranges": {
                    key: {
                        scenario: {
                            p: {
                                "minimum": min(values),
                                "maximum": max(values),
                                "sample_count": len(values),
                            }
                            for p, values in planets.items()
                            if values
                        }
                        for scenario, planets in scenarios.items()
                    }
                    for key, scenarios in temporal_samples.items()
                },
                "time_lord_alternatives": {
                    key: sorted(values)
                    for key, values in time_lord_samples.items()
                    if len(values) > 1
                },
                "solar_bracket_states_on_grid": [
                    {
                        "sunrise_day_status": sunrise,
                        "active_arc_status": arc,
                        "sample_count": count,
                    }
                    for (sunrise, arc), count in sorted(solar_bracket_states.items())
                ],
                "solar_bracket_scope": "Same recorded TT grid; component dependencies are independent. Counts describe sampled coverage only.",
                "sthana_discrete_component_alternatives": discrete_strength_alternatives,
                "status_scope": "categorical states including Nakshatra/Pada, war pair candidates/decisions and discrete positional components; continuous strengths are reported in sample ranges",
                "uchcha_bala_sample_range": {
                    p: {
                        "minimum": min(values),
                        "maximum": max(values),
                        "unit": "virupa",
                    }
                    for p, values in bala_samples.items()
                },
                "sampled_ephemeris_fallback_bodies": sorted(sampled_fallback),
                "source_comparison": {
                    **source_comparison.result(),
                    "sample_source_indices": source_samples,
                },
                "sampled_future_leap_seconds_assumed_unchanged": sampled_future_time_assumption,
                "sthana_bala_sample_ranges": {
                    p: {
                        key: {"minimum": min(values), "maximum": max(values)}
                        for key, values in components.items()
                    }
                    for p, components in strength_samples.items()
                },
                "moon_samples": moon_samples,
            }
        )
    return sensitivity
