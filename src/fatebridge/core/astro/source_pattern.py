"""Qualified Udo1996 source conditions, separate from backend conventions.

Only the published Mars+Jupiter-Zeus=MC direct condition is assessed. A
symbolic solar arc does not resolve an unresolved natal meridian reference.
No ephemeris is queried and no coordinate or two-degree policy is fitted.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Mapping, Sequence

from fatebridge.core.astro.reference_angles import (
    UNRESOLVED_REFERENCE_BASES,
    reference_angle_basis,
)
from fatebridge.utils.errors import EphemerisSourceError


def source_pattern_sample(
    values: Mapping[str, float],
    definition: Mapping[str, Any] | None = None,
    *,
    solar_arc_degrees: float = 0.0,
) -> dict[str, Any]:
    """Actual condition and separately labelled formal backend calculation."""
    try:
        if definition is not None and (
            not isinstance(definition, Mapping)
            or (definition and not isinstance(definition.get("status"), str))
        ):
            raise ValueError("Reference definition requires a typed status")
        raw = [values[k] for k in ("Mars", "Jupiter", "Zeus", "Midheaven")]
        raw.append(solar_arc_degrees)
        if any(
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            for v in raw
        ):
            raise ValueError("Source coordinates must be finite numbers")
        mars, jupiter, zeus, natal_mc, arc = map(Fraction, raw)
        basis = reference_angle_basis(definition, "Midheaven")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise EphemerisSourceError("source_pattern_inputs") from error
    mc = (natal_mc + arc) % 360
    orb = abs((mars + jupiter - zeus - mc + 180) % 360 - 180)
    condition = orb <= 2
    resolved = basis not in UNRESOLVED_REFERENCE_BASES
    displayed_mc = min(float(mc), math.nextafter(360.0, 0.0))
    return {
        "condition_met": condition if resolved else None,
        "direct_orb_degrees": float(orb) if resolved else None,
        "midheaven_longitude": displayed_mc if resolved else None,
        "reference_geometry_resolved": resolved,
        "reference_angle_basis": {"Midheaven": basis} if basis else None,
        "backend_condition_met": condition,
        "backend_direct_orb_degrees": float(orb),
        "backend_midheaven_longitude": displayed_mc,
    }


def source_pattern_summary(
    samples: Sequence[Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Count known conditions, unresolved references and unavailable arcs.

    None denotes an unavailable direction, not an absent source condition.
    Existing fully resolved output remains unchanged. Extra diagnostics appear
    when a reference is unresolved, with every formal sample still retained.
    """
    if not samples:
        raise EphemerisSourceError("source_pattern_inputs")
    available = [s for s in samples if s is not None]
    present = sum(s["condition_met"] is True for s in available)
    absent = sum(s["condition_met"] is False for s in available)
    unknown = [
        i
        for i, s in enumerate(samples)
        if s is not None and not s["reference_geometry_resolved"]
    ]
    unavailable = len(samples) - len(available)
    orbs = [
        s["direct_orb_degrees"] for s in available if s["reference_geometry_resolved"]
    ]
    result: dict[str, Any] = {
        "sampled_status": (
            "underdetermined"
            if unknown or unavailable
            else (
                "present_at_every_sample"
                if present == len(samples)
                else (
                    "absent_at_every_sample" if not present else "varies_across_samples"
                )
            )
        ),
        "present_sample_count": present,
        "absent_sample_count": absent,
        "minimum_sampled_direct_orb_degrees": min(orbs) if orbs else None,
        "maximum_sampled_direct_orb_degrees": max(orbs) if orbs else None,
    }
    if unavailable:
        result.update(
            computed_sample_count=len(available),
            unavailable_sample_count=unavailable,
            orb_range_scope="computed_samples_only",
        )
    if unknown:
        backend_orbs = [s["backend_direct_orb_degrees"] for s in available]
        backend_present = sum(s["backend_condition_met"] for s in available)
        result.update(
            resolved_condition_sample_count=present + absent,
            unresolved_reference_sample_count=len(unknown),
            unresolved_reference_sample_indices=unknown,
            condition_by_sample=[
                s["condition_met"] if s is not None else None for s in samples
            ],
            orb_range_scope="resolved_reference_samples_only",
            backend_convention={
                "evaluable_sample_count": len(available),
                "present_sample_count": backend_present,
                "absent_sample_count": len(available) - backend_present,
                "condition_by_sample": [
                    s["backend_condition_met"] if s is not None else None
                    for s in samples
                ],
                "minimum_sampled_direct_orb_degrees": min(backend_orbs),
                "maximum_sampled_direct_orb_degrees": max(backend_orbs),
                "scope": "Formal meridian convention only; not resolved physical source conditions or independent evidence",
            },
        )
    return result
