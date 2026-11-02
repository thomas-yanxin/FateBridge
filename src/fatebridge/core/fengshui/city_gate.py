"""Shen's adjacent-palace, same-yuan, reverse-flight city-gate calculation.

The reference period is explicitly selected. Historical natal charts and their
replacement mode never change. Published anecdotes are not efficacy evidence.
"""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .city_gate_inputs import CityGateObservation, CityGateRequest
from .directions import rule_data, wrap9


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            (Path(__file__).parents[2] / "data/fengshui/city-gate-v1.json").read_text()
        ),
    )


def city_gate_provenance() -> Dict[str, Any]:
    data = _bundle()
    return {
        **deepcopy(data["ruleset"]),
        "sources": [
            dict(source_id=k, **deepcopy(data["sources"][k]))
            for k in data["ruleset"]["source_ids"]
        ],
    }


def _conjunction(values: List[Optional[bool]]) -> Optional[bool]:
    return False if False in values else None if None in values else True


def _form(observation: Optional[CityGateObservation]) -> Dict[str, Any]:
    if observation is None:
        return {
            "status": "not_requested",
            "condition_match": None,
            "scope": "no_site_observation_supplied",
        }
    facts = observation.model_dump(mode="json")
    water = observation.water_present
    if water is None and any(
        getattr(observation, name) is True
        for name in (
            "sole_opening_with_water",
            "three_way_water_junction_present",
            "water_reflects_towards_site",
        )
    ):
        water = True
    if (
        observation.multiple_openings_present is True
        or observation.water_present is False
    ):
        match: Optional[bool] = False
        patterns: Dict[str, Optional[bool]] = {}
    else:
        patterns = {
            "encircled_sole_water_opening": _conjunction(
                [
                    observation.encircling_form_present,
                    observation.sole_opening_with_water,
                ]
            ),
            "reflecting_three_way_water": _conjunction(
                [
                    water,
                    observation.three_way_water_junction_present,
                    observation.water_reflects_towards_site,
                    (
                        None
                        if observation.multiple_openings_present is None
                        else not observation.multiple_openings_present
                    ),
                ]
            ),
        }
        match = (
            True
            if True in patterns.values()
            else None if None in patterns.values() else False
        )
    image = observation.observation_basis == "image_observed"
    return {
        "rule_id": "shen_city_gate_v1.observed_water_patterns",
        "source_ids": ["G1", "G2"],
        "status": (
            "candidate_only"
            if image
            else (
                "needs_confirmation"
                if match is None
                else (
                    "selected_pattern_matched"
                    if match
                    else "selected_pattern_not_matched"
                )
            )
        ),
        "pattern_matches": patterns,
        "derived_water_present": water,
        "water_presence_basis": (
            "explicit"
            if observation.water_present is not None
            else "implied_by_positive_water_fact" if water is True else "unknown"
        ),
        "raw_pattern_match": match,
        "condition_match": None if image else match,
        "candidate_only": image,
        "evidence": facts,
        "scope": "selected_text_patterns_only_not_complete_form_quality_or_reality_verdict",
    }


def analyze_city_gate(
    config: CityGateRequest,
    orientations: List[Dict[str, Any]],
    registry: Dict[str, Any],
) -> Dict[str, Any]:
    period = config.reference_period_number
    path = rule_data("flight_path")
    directions = rule_data("directions")
    ring = list(directions)
    mountains = registry["mountains"]
    by_name = {m["name"]: m for m in mountains}
    base = {d: wrap9(period + i) for i, d in enumerate(path)}
    observations = {o.mountain: o for o in config.observations}
    ambiguous = len(orientations) > 1
    candidates = []
    used = set()
    for orientation in orientations:
        facing = orientation["facing"]
        gates = []
        index = ring.index(facing["direction"])
        for side, direction in (
            ("counterclockwise", ring[(index - 1) % 8]),
            ("clockwise", ring[(index + 1) % 8]),
        ):
            physical = next(
                m
                for m in mountains
                if m["direction"] == direction and m["yuan"] == facing["yuan"]
            )
            seed = base[direction]
            home = period if seed == 5 else seed
            # At period 5 the outer base palaces never contain star 5.
            assert home != 5
            mapped = by_name[registry["star_home_mountains"][str(home)][facing["yuan"]]]
            reverse = mapped["polarity"] == "yin"
            flight = {
                d: wrap9(seed + (-i if reverse else i)) for i, d in enumerate(path)
            }
            numeric_match = reverse and flight[direction] == period
            pair = sorted(
                (
                    directions[facing["direction"]]["palace_number"],
                    directions[direction]["palace_number"],
                )
            )
            form = _form(observations.get(physical["name"]))
            if physical["name"] in observations:
                used.add(physical["name"])
            gates.append(
                {
                    "direction": direction,
                    "side": side,
                    "mountain": deepcopy(physical),
                    "same_yuan": facing["yuan"],
                    "seed_star_number": seed,
                    "five_yellow_borrowed_reference_period": seed == 5,
                    "home_star_number": home,
                    "mapped_mountain": mapped["name"],
                    "mapped_polarity": mapped["polarity"],
                    "flight": "reverse" if reverse else "forward",
                    "gate_chart": flight,
                    "star_at_gate": flight[direction],
                    "reference_star_reaches_gate_by_reverse_flight": numeric_match,
                    "fixed_luoshu_pair": pair,
                    "hetu_generation_pair": pair in [[1, 6], [2, 7], [3, 8], [4, 9]],
                    "classification_scope": "generation_pair_fact_not_universal_zhengma_or_strength_ranking",
                    "form_assessment": form,
                    "combined_condition_match": (
                        None
                        if ambiguous
                        or form.get("candidate_only")
                        or form["condition_match"] is None
                        else bool(numeric_match and form["condition_match"])
                    ),
                    "rule_id": "shen_city_gate_v1.same_yuan_reverse_flight",
                    "source_ids": ["G1", "G2"],
                }
            )
        candidates.append(
            {
                **deepcopy(orientation),
                "candidate_only": ambiguous,
                "reference_period_number": period,
                "period_chart": base,
                "gates": gates,
            }
        )
    missing = []
    if not orientations:
        missing.append("city_gate.confirmed_magnetic_house_facing")
    elif ambiguous:
        missing.append("city_gate.unambiguous_facing_mountain")
    for c in candidates:
        for gate in c["gates"]:
            if gate["form_assessment"]["status"] in {
                "candidate_only",
                "needs_confirmation",
            }:
                missing.append(
                    f"city_gate.observations.{gate['mountain']['name']}.source_pattern_confirmation"
                )
    return {
        "status": "partial" if missing else "complete",
        "calculation_status": "complete" if orientations else "partial",
        "reference_period_context": {
            "number": period,
            "evidence": config.period_evidence,
            "source": "explicit_caller_input",
            "scope": "independent_city_gate_period_not_natal_reset",
        },
        "ruleset": city_gate_provenance(),
        "candidates": candidates,
        "missing_inputs": list(dict.fromkeys(missing)),
        "unmatched_observations": [
            {
                "mountain": m,
                "evidence": observations[m].evidence,
                "status": "not_same_yuan_adjacent_gate_of_supplied_facing_candidates",
            }
            for m in observations
            if m not in used
        ],
        "overall_auspiciousness": "not_produced",
        "limitations": deepcopy(_bundle()["limitations"]),
    }
