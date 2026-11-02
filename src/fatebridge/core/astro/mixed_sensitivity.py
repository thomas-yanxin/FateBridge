"""Exact finite-grid mixed-pair evaluation, reusing same-run native facts.

All dyadic input floats share one integer lattice. This changes neither their
values nor the inclusive orb policy. The entire declared domain is evaluated;
the detailed ledger is sparse, with absent and unknown unlisted groups counted
separately. Grid frequencies are not probabilities or continuous bounds.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import combinations, product
from typing import Any, Mapping, Sequence

from fatebridge.core.astro.mixed_pairs import _finite
from fatebridge.core.astro.reference_angles import (
    UNRESOLVED_REFERENCE_BASES,
    reference_angle_basis,
)
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "hamburg_mixed_pair_sampled_sensitivity_v1"


def _unresolved(names: Sequence[str], definition: Mapping[str, Any] | None) -> set[str]:
    return {
        name
        for name in names
        if reference_angle_basis(definition, name) in UNRESOLVED_REFERENCE_BASES
    }


def mixed_pair_sensitivity(
    geometry: Mapping[str, Any],
    nominal_longitudes: Mapping[str, float],
    uncertainty: Mapping[str, Any],
    solar_samples: Sequence[Mapping[str, Any]],
    *,
    nominal_angle_definition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate all nominal and sample relations; never select on outcomes.

    An unavailable solar arc limits only coefficients +/-1/2. The coefficient0
    relative relation can be evaluated from natal factors without substituting
    any arc or claiming computed directed coordinates. Unresolved physical
    references remain unknown even when a backend convention yields a number.
    """
    result: dict[str, Any] = {
        "ruleset_id": RULESET,
        "status": uncertainty["status"],
        "uncertainty_minutes": uncertainty["uncertainty_minutes"],
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "summary": None,
        "sample_count": None,
        "computed_arc_sample_count": None,
        "unavailable_arc_sample_count": None,
        "scope": "Entire declared four-distinct-name mixed-pair domain on the supplied finite birth-time grid only; physical-reference availability kept separate from formal backend matches",
    }
    if uncertainty["status"] != "sampled":
        return result
    native = uncertainty["samples"]
    if (
        not native
        or len(native) != uncertainty["sample_count"]
        or len(native) != len(solar_samples)
    ):
        raise ValueError(
            "Mixed sensitivity requires every same-run native and solar sample"
        )
    names = sorted(nominal_longitudes)
    nominal = {n: _finite(v) % 360 for n, v in nominal_longitudes.items()}
    arc = _finite(geometry["profile"]["solar_arc_degrees"]) % 360
    orb = _finite(geometry["profile"]["orb_degrees"])
    if not 0 <= orb <= 5:
        raise ValueError("Mixed sensitivity requires the declared inclusive orb0..5")
    records, coordinates, arcs, unknown_names = [], [], [], []
    offsets: list[Fraction] = []
    for i, (sample, solar) in enumerate(zip(native, solar_samples)):
        offset = _finite(sample["offset_seconds"])
        if offset != _finite(solar["offset_seconds"]):
            raise ValueError("Native and solar sample offsets must match in order")
        if sample["effective_utc"] != solar.get("effective_utc") or _finite(
            sample["julian_day_tt"]
        ) != _finite(solar["julian_day_tt"]):
            raise EphemerisSourceError("mixed_pair_sample_epoch_mismatch")
        if offsets and offset <= offsets[-1]:
            raise ValueError(
                "Mixed sensitivity sample offsets must be unique and ordered"
            )
        offsets.append(offset)
        if set(sample["factor_longitudes"]) != set(names):
            raise ValueError("Mixed sensitivity sample factor set changed")
        coordinates.append(
            {n: _finite(sample["factor_longitudes"][n]) % 360 for n in names}
        )
        status = solar.get("status", "computed")
        if status not in ("computed", "unavailable"):
            raise ValueError("Mixed sensitivity has an unknown solar sample state")
        arcs.append(
            _finite(solar["solar_arc_degrees"]) % 360 if status == "computed" else None
        )
        unresolved = _unresolved(names, sample.get("angle_definition"))
        unknown_names.append(unresolved)
        records.append(
            {
                "sample_index": i,
                "offset_seconds": float(offset),
                "recorded_utc": sample["recorded_utc"],
                "effective_utc": sample["effective_utc"],
                "julian_day_tt": sample["julian_day_tt"],
                "factor_longitudes": dict(sample["factor_longitudes"]),
                "solar_arc_status": status,
                "solar_arc_degrees": (
                    solar.get("solar_arc_degrees") if status == "computed" else None
                ),
                "reason_code": solar.get("reason_code"),
                "unresolved_reference_names": sorted(unresolved),
                "native_sample_reference": f"midpoint_analysis.time_sensitivity.samples[{i}]",
                "solar_sample_reference": f"midpoint_analysis.solar_arc_analysis.birth_time_sensitivity.samples[{i}]",
            }
        )
    if Fraction(0) not in offsets:
        raise ValueError(
            "Mixed sensitivity must retain the nominal birth-time grid point"
        )
    # IEEE floats are dyadic rationals. Their denominators divide the largest
    # denominator, so one power-of-two lattice retains exact boundary sides.
    all_values = [*nominal.values(), arc, orb]
    all_values += [v for row in coordinates for v in row.values()]
    all_values += [v for v in arcs if v is not None]
    denominator = max(v.denominator for v in all_values)
    ticks = lambda v: v.numerator * (denominator // v.denominator)
    n = {key: ticks(v) for key, v in nominal.items()}
    sampled = [{key: ticks(v) for key, v in row.items()} for row in coordinates]
    sampled_arcs = [ticks(v) if v is not None else None for v in arcs]
    nominal_arc, bound = ticks(arc), ticks(orb) * 2
    count = len(native)
    nominal_unknown = _unresolved(names, nominal_angle_definition)
    dials: dict[str, dict[str, Any]] = {
        str(period): {
            "period_degrees": period,
            "contacts": [],
            "all_group_status_counts": Counter(),
            "unlisted_no_observed_hit_counts": Counter(),
        }
        for period in (90, 45)
    }
    patterns = {
        k: [
            bits
            for bits in product((0, 1), repeat=4)
            if (bits[0] != bits[1] or bits[2] != bits[3])
            and bits[0] + bits[1] - bits[2] - bits[3] == k
        ]
        for k in (-1, 0, 1)
    }
    partitions = 0
    for a, b, c, d in combinations(names, 4):
        for keys in ((a, b, c, d), (a, c, b, d), (a, d, b, c)):
            partitions += 1
            aa, bb, cc, dd = keys
            base = n[aa] + n[bb] - n[cc] - n[dd]
            bases = [row[aa] + row[bb] - row[cc] - row[dd] for row in sampled]
            reference_known = [not set(keys).intersection(u) for u in unknown_names]
            nominal_known = not set(keys).intersection(nominal_unknown)
            for numerator in (-1, 0, 1):
                for period in (90, 45):
                    turn = period * 2 * denominator
                    half = turn // 2
                    residual = lambda v: (v + half) % turn - half
                    nominal_hit = abs(residual(base + numerator * nominal_arc)) <= bound
                    present, unknown, backend_hits, known_orbs = [], [], [], []
                    evaluated = 0
                    for i, (value, sample_arc) in enumerate(zip(bases, sampled_arcs)):
                        # At coefficient0 the arc is neither required nor read.
                        if numerator == 0:
                            tick = value
                        else:
                            if sample_arc is None:
                                unknown.append(i)
                                continue
                            tick = value + numerator * sample_arc
                        delta = residual(tick)
                        evaluated += 1
                        hit = abs(delta) <= bound
                        if hit:
                            backend_hits.append(i)
                        if not reference_known[i]:
                            unknown.append(i)
                        else:
                            known_orbs.append(abs(delta))
                            if hit:
                                present.append(i)
                    absent = count - len(present) - len(unknown)
                    state = (
                        "varies_across_samples"
                        if present and absent
                        else (
                            "underdetermined"
                            if unknown
                            else (
                                "present_at_every_sample"
                                if len(present) == count
                                else "absent_at_every_sample"
                            )
                        )
                    )
                    dial = dials[str(period)]
                    dial["all_group_status_counts"][state] += 1
                    if not nominal_hit and not backend_hits:
                        dial["unlisted_no_observed_hit_counts"][state] += 1
                        continue
                    dial["contacts"].append(
                        {
                            "id_a": aa,
                            "id_b": bb,
                            "id_c": cc,
                            "id_d": dd,
                            "midpoint_arc_coefficient": numerator / 2,
                            "arc_invariant": numerator == 0,
                            "arc_required_for_relative_condition": numerator != 0,
                            "factor_layer_assignments": [
                                {
                                    name: "solar_arc" if bit else "natal"
                                    for name, bit in zip(keys, bits)
                                }
                                for bits in patterns[numerator]
                            ],
                            "nominal_backend_condition": nominal_hit,
                            "nominal_condition": nominal_hit if nominal_known else None,
                            "sampled_status": state,
                            "assessment_complete": not unknown,
                            "present_sample_indices": present,
                            "known_absent_sample_count": absent,
                            "unknown_sample_indices": unknown,
                            "backend_hit_sample_indices": backend_hits,
                            "backend_evaluable_sample_count": evaluated,
                            "minimum_known_sampled_orb_degrees": (
                                float(Fraction(min(known_orbs), 2 * denominator))
                                if known_orbs
                                else None
                            ),
                            "maximum_known_sampled_orb_degrees": (
                                float(Fraction(max(known_orbs), 2 * denominator))
                                if known_orbs
                                else None
                            ),
                        }
                    )
    summaries = {}
    for key, dial in dials.items():
        dial["all_group_status_counts"] = dict(dial["all_group_status_counts"])
        dial["unlisted_no_observed_hit_counts"] = dict(
            dial["unlisted_no_observed_hit_counts"]
        )
        summaries[key] = {
            "evaluated_relation_groups": partitions * 3,
            "listed_observed_or_nominal_contact_groups": len(dial["contacts"]),
            "all_group_status_counts": dial["all_group_status_counts"],
            "unlisted_no_observed_hit_counts": dial["unlisted_no_observed_hit_counts"],
        }
    result.update(
        status=(
            "partial"
            if any(v is None for v in arcs) or any(unknown_names) or nominal_unknown
            else "sampled"
        ),
        sample_count=count,
        computed_arc_sample_count=sum(v is not None for v in arcs),
        unavailable_arc_sample_count=sum(v is None for v in arcs),
        nominal_sample_index=offsets.index(Fraction(0)),
        nominal_unresolved_reference_names=sorted(nominal_unknown),
        exact_lattice_denominator_power=denominator.bit_length() - 1,
        summary=summaries,
        samples=records,
        dials=dials,
        ledger_policy="List every nominal or backend-hit relation group; unlisted groups have no observed formal hit and retain separate absent/undetermined counts. Known absent indices are the sample-index complement of present and unknown indices. No unlisted group is presumed absent when a required arc/reference is unavailable.",
        arc_policy="Coefficient0 evaluates natal relative geometry without requiring or substituting an arc; directed coordinates outside the arc domain remain unavailable",
        interval={
            key: uncertainty[key]
            for key in (
                "recorded_interval_start_utc",
                "recorded_interval_end_utc",
                "maximum_recorded_sample_gap_seconds",
                "represented_radius_seconds",
                "clock_policy",
                "input_clock_basis",
                "recorded_interval_start_clock",
                "recorded_interval_end_clock",
                "requested_clock_radius_seconds",
            )
            if key in uncertainty
        },
    )
    return result
