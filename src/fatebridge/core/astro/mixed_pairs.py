"""Mixed natal/directed midpoint pairs under one declared uniform solar arc.

Witte1925 pp53-54 motivates mixed layers. This finite catalogue is our explicit
algebraic reconstruction, not a transcription of every original direction or
transit. Arc-invariant relations are retained separately from timing-dependent
geometry. No source event assertions or interpretation keywords are imported.
"""

from __future__ import annotations

import math
from fractions import Fraction
from itertools import combinations, product
from typing import Any, Collection, Mapping

RULESET = "hamburg_mixed_pair_uniform_arc_v1"
SOURCE = {
    "id": "witte1925_directions_planetary_pictures",
    "author": "Alfred Witte",
    "title": "Direktionen und Planetenbilder, Astrologische Rundschau XVII/2, May1925, pp52-55",
    "sections": ["p53: sum symmetry; p54: mixed radix and directed factors"],
    "scope": "Motivation for named mixed-layer algebra only; no original clock key, complete method or event assertions accepted",
}


def _finite(value: float | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Mixed-pair coordinates require finite numbers")
    return Fraction(value)


def unavailable_mixed_pairs(
    reason: str, *, uncertainty_minutes: float | None = None
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "ruleset_id": RULESET,
        "profile": None,
        "contact_counts": None,
        "birth_time_sensitivity": {
            "status": "unavailable",
            "uncertainty_minutes": uncertainty_minutes,
            "sample_count": None,
            "computed_arc_sample_count": None,
            "unavailable_arc_sample_count": None,
            "summary": None,
            "continuous_interval_proven": False,
        },
        "sources": [SOURCE],
    }


def mixed_pair_geometry(
    longitudes: Mapping[str, float],
    arc_degrees: float | Fraction,
    *,
    orb_degrees: float = 1.0,
    hypothetical_ids: Collection[str] = (),
    max_contacts_per_field: int | None = None,
) -> dict[str, Any]:
    """All mixed-pair layer assignments for four distinct factor names.

    Each unordered four-factor set has three unordered pair partitions. At
    least one pair must mix natal and directed factors. The 12 layerings then
    fall into three residual groups with midpoint-arc coefficients -1/2,0,1/2.
    Every group's four assignments are retained; none is four independent hits.
    Pure natal/directed pairs remain in the existing biwheel catalogue.
    """
    arc, orb = _finite(arc_degrees) % 360, _finite(orb_degrees)
    if not 0 <= orb <= 5:
        raise ValueError("Mixed-pair inclusive orb must be within0..5 degrees")
    if any(type(name) is not str or not name for name in longitudes):
        raise ValueError("Mixed-pair factor names must be nonempty strings")
    values = {name: _finite(value) % 360 for name, value in longitudes.items()}
    values_f = {name: float(val) for name, val in values.items()}
    arc_f = float(arc)
    orb_exact_f = float(orb)
    boundary_lo = orb_exact_f - 1e-8
    boundary_hi = orb_exact_f + 1e-8
    patterns: dict[int, list[tuple[int, ...]]] = {-1: [], 0: [], 1: []}
    for bits in product((0, 1), repeat=4):
        if bits[0] != bits[1] or bits[2] != bits[3]:
            patterns[bits[0] + bits[1] - bits[2] - bits[3]].append(bits)
    pattern_items = tuple(
        (
            numerator,
            numerator * 0.5,
            float(numerator * 0.5) * arc_f,
            layer_patterns,
        )
        for numerator, layer_patterns in patterns.items()
    )
    dials: dict[str, dict[str, Any]] = {
        str(period): {
            "period_degrees": period,
            "arc_dependent_contacts": [],
            "arc_invariant_contacts": [],
        }
        for period in (90, 45)
    }
    partition_count = 0
    unique = set()
    zero_arc = arc == 0
    for a, b, c, d in combinations(sorted(values), 4):
        va, vb, vc, vd = values_f[a], values_f[b], values_f[c], values_f[d]
        for names, diff_f in (
            ((a, b, c, d), (va + vb - vc - vd) * 0.5),
            ((a, c, b, d), (va + vc - vb - vd) * 0.5),
            ((a, d, b, c), (va + vd - vb - vc) * 0.5),
        ):
            partition_count += 1
            first, second, third, fourth = names
            contains_hyp: bool | None = None
            for numerator, coeff_f, coeff_arc_f, layer_patterns in pattern_items:
                raw_f = diff_f + coeff_arc_f
                for period in (90, 45):
                    half_p = period * 0.5
                    delta_f = (raw_f + half_p) % period - half_p
                    abs_df = abs(delta_f)
                    if abs_df > boundary_hi:
                        continue
                    if abs_df >= boundary_lo:
                        difference = (
                            values[first]
                            + values[second]
                            - values[third]
                            - values[fourth]
                        ) / 2
                        raw = difference + Fraction(numerator, 2) * arc
                        delta = (raw + Fraction(period, 2)) % period - Fraction(
                            period, 2
                        )
                        if abs(delta) > orb:
                            continue
                        delta_out = float(delta)
                    else:
                        delta_out = delta_f
                    if contains_hyp is None:
                        contains_hyp = any(n in hypothetical_ids for n in names)
                    assignments = [
                        {
                            name: "solar_arc" if bit else "natal"
                            for name, bit in zip(names, bits)
                        }
                        for bits in layer_patterns
                    ]
                    row = {
                        "rule_id": RULESET,
                        "id_a": first,
                        "id_b": second,
                        "id_c": third,
                        "id_d": fourth,
                        "equation": f"({first}+{second})/2=({third}+{fourth})/2; apply each factor_layers assignment",
                        "signed_orb": delta_out,
                        "orb": abs(delta_out),
                        "midpoint_arc_coefficient": coeff_f,
                        "arc_invariant": numerator == 0,
                        "factor_layer_assignments": assignments,
                        "represented_layer_assignment_count": len(assignments),
                        "contains_hypothetical": contains_hyp,
                        "zero_arc_groups_coincide": zero_arc,
                    }
                    field = (
                        "arc_invariant_contacts"
                        if numerator == 0
                        else "arc_dependent_contacts"
                    )
                    dials[str(period)][field].append(row)
                    unique.add((*names, numerator))
    counts = {}
    for key, dial in dials.items():
        dependent, invariant = (
            dial["arc_dependent_contacts"],
            dial["arc_invariant_contacts"],
        )
        total_dependent = len(dependent)
        total_invariant = len(invariant)
        counts[key] = {
            "arc_dependent_relation_groups": total_dependent,
            "arc_invariant_relation_groups": total_invariant,
            "represented_layer_assignments": 4 * (total_dependent + total_invariant),
        }
        if max_contacts_per_field is not None:
            dependent.sort(key=lambda r: (r["orb"], r["equation"]))
            invariant.sort(key=lambda r: (r["orb"], r["equation"]))
            dependent = dependent[:max_contacts_per_field]
            invariant = invariant[:max_contacts_per_field]
            dial["arc_dependent_contacts"] = dependent
            dial["arc_invariant_contacts"] = invariant
        dial["arc_dependent_returned_count"] = len(dependent)
        dial["arc_dependent_total_count"] = total_dependent
        dial["arc_invariant_returned_count"] = len(invariant)
        dial["arc_invariant_total_count"] = total_invariant
    return {
        "status": "computed",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "profile": {
            "solar_arc_degrees": float(arc),
            "orb_degrees": float(orb),
            "factor_count": len(values),
            "four_distinct_factor_names_required": True,
            "pair_partitions_tested_per_dial": partition_count,
            "residual_groups_tested_per_dial": 3 * partition_count,
            "layer_assignments_represented_per_dial": 12 * partition_count,
            "coefficient_formula": "(directed_count_left-directed_count_right)/2; delta=(A+B-C-D)/2+coefficient*solar_arc modulo dial",
            "arc_invariant_means": "Uniform solar arc cancels from the relative relation; this is not a timing trigger",
            "grouping_policy": "Four equivalent layer assignments retained per residual group; side and within-pair permutations deduplicated; groups and dials are not independent evidence",
            "birth_time_contact_sensitivity": "not_assessed_for_this_catalogue",
        },
        "dials": dials,
        "contact_counts": counts,
        "unique_relation_groups_across_dials": len(unique),
        "birth_time_sensitivity": {
            "status": "not_assessed",
            "uncertainty_minutes": None,
            "sample_count": None,
            "computed_arc_sample_count": None,
            "unavailable_arc_sample_count": None,
            "summary": None,
            "continuous_interval_proven": False,
        },
        "sources": [SOURCE],
        "full_original_method_accepted": False,
    }
