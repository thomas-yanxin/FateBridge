"""Selected ecliptic constructions from Witte's Vergleichende Astrologie1924.

Only rotations and the four-point reflection system are reconstructed. The
printed Earth-house labels and event claims are not applied. Native same-run
factors supply every coordinate, including the tropical Aries Point in a
sidereal display; no ephemeris is queried here.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Mapping, TypedDict

from fatebridge.core.astro.reference_angles import (
    UNRESOLVED_REFERENCE_BASES,
    reference_angle_basis,
)
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "witte1924_comparative_ecliptic_geometry_v1"
SOURCE = {
    "id": "witte_1924_comparative_astrology",
    "author": "Alfred Witte",
    "title": "Vergleichende Astrologie, Astrologische Rundschau XVI/5, August1924, pp137-140",
    "url": "https://www.astrax.de/pdf/42_Vergleichende%20Astrologie%201924%20AstrRundschau%20137-140.pdf",
    "source_sha256": "58c6516caaf6eb9310abbbbf3b7378cccb22f16a49cfa5d3069a05aa48dd3832",
    "sections": [
        "p138: Uranus four-point reflection example",
        "p139: three printed rotations and two additional stated anchors",
    ],
    "scope": "Selected ecliptic constructions reconstructed by FateBridge; four printed numeric discrepancies retained separately; no Earth-house assignment, original event or mortality claims",
}
FRAMES = {
    "sun_capricorn": ("Sun", 270),
    "meridian_cancer": ("Midheaven", 90),
    "ascendant_libra": ("Ascendant", 180),
    "moon_cancer": ("Moon", 90),
    "node_libra": ("North Node", 180),
}


class _SampleTrack(TypedDict):
    resolved_sample_count: int
    unresolved_sample_indices: list[int]
    known: dict[str, list[Fraction]]
    backend: dict[str, list[Fraction]]


class _PointSpan(TypedDict):
    nominal_input_reference_geometry_resolved: bool
    resolved_sample_count: int
    unresolved_sample_count: int
    unresolved_sample_indices: list[int]
    known_sampled_signed_offsets_from_nominal: dict[str, dict[str, float]] | None
    backend_sampled_signed_offsets_from_nominal: dict[str, dict[str, float]] | None


def _number(value: Any) -> Fraction:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise EphemerisSourceError("comparative_geometry_inputs")
    return Fraction(value)


def _values(values: Mapping[str, float]) -> dict[str, Fraction]:
    if not isinstance(values, Mapping):
        raise EphemerisSourceError("comparative_geometry_inputs")
    required = {"Aries Point", *(a for a, _ in FRAMES.values())}
    if not required.issubset(values) or any(
        not isinstance(k, str) or not k for k in values
    ):
        raise EphemerisSourceError("comparative_geometry_inputs")
    return {name: _number(value) % 360 for name, value in sorted(values.items())}


def _display(value: Fraction) -> float:
    return min(float(value % 360), math.nextafter(360.0, 0.0))


def _basis(definition: Mapping[str, Any] | None, names: set[str]) -> dict[str, str]:
    return {
        name: value
        for name in sorted(names)
        if (value := reference_angle_basis(definition, name)) is not None
    }


def _resolved(bases: Mapping[str, str]) -> bool:
    return not any(value in UNRESOLVED_REFERENCE_BASES for value in bases.values())


def _system(
    value: Fraction, aries: Fraction, bases: dict[str, str], identity: bool
) -> tuple[dict[str, Any], dict[str, Fraction]]:
    exact = {
        "original": value % 360,
        "opposition": (value + 180) % 360,
        "solstitial_reflection": (2 * aries + 180 - value) % 360,
        "reflection_opposition": (2 * aries - value) % 360,
    }
    resolved = _resolved(bases)
    backend = {key: _display(v) for key, v in exact.items()}
    unique = len(set(exact.values()))
    return {
        "longitudes": backend if resolved else {key: None for key in exact},
        "backend_longitudes": None if resolved else backend,
        "input_reference_geometry_resolved": resolved,
        "reference_angle_basis": bases or None,
        "defined_anchor_identity": identity,
        "unique_point_count": unique if resolved else None,
        "backend_unique_point_count": unique,
    }, exact


def comparative_coordinates(
    values: Mapping[str, float], definition: Mapping[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Fraction]]]]:
    """Pure full-circle geometry and exact coordinates for sampled comparisons.

    A frame sends its anchor to AriesPoint+the author's tropical target. The
    anchor's own coordinate cancels algebraically and is assigned by definition;
    this never resolves the original physical ASC/MC or the frame orientation.
    """
    points = _values(values)
    aries = points["Aries Point"]
    radix, exact_radix = {}, {}
    for name, value in points.items():
        radix[name], exact_radix[name] = _system(
            value, aries, _basis(definition, {name}), False
        )
    frames, summary = {}, {}
    exact = {"radix": exact_radix}
    for key, (anchor, target) in FRAMES.items():
        target_value = (aries + target) % 360
        rotation = (target_value - points[anchor]) % 360
        anchor_basis = _basis(definition, {anchor})
        anchor_resolved = _resolved(anchor_basis)
        systems, exact_frame = {}, {}
        for name, value in points.items():
            identity = name == anchor
            # x-anchor cancels for the assigned anchor. Other factors retain
            # both their own reference qualification and that of the anchor.
            bases = _basis(definition, set() if identity else {name, anchor})
            systems[name], exact_frame[name] = _system(
                value + rotation, aries, bases, identity
            )
        known = sum(s["input_reference_geometry_resolved"] for s in systems.values())
        info = {
            "anchor_factor": anchor,
            "target_tropical_longitude": target,
            "target_display_longitude": _display(target_value),
            "rotation_degrees": _display(rotation) if anchor_resolved else None,
            "backend_rotation_degrees": None if anchor_resolved else _display(rotation),
            "anchor_input_reference_resolved": anchor_resolved,
            "anchor_reference_angle_basis": anchor_basis or None,
            "resolved_factor_system_count": known,
            "unresolved_factor_system_count": len(systems) - known,
        }
        frames[key] = {**info, "factor_systems": systems}
        summary[key] = info
        exact[key] = exact_frame
    partial = any(
        not row["input_reference_geometry_resolved"] for row in radix.values()
    ) or any(not info["anchor_input_reference_resolved"] for info in summary.values())
    return {
        "status": "partial" if partial else "computed",
        "radix_systems": radix,
        "frames": frames,
        "frame_summary": summary,
    }, exact


def _systems(coordinates: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "radix": coordinates["radix_systems"],
        **{
            key: frame["factor_systems"] for key, frame in coordinates["frames"].items()
        },
    }


def _offset(value: Fraction, nominal: Fraction) -> Fraction:
    return (value - nominal + 180) % 360 - 180


def _update(spans: dict[str, list[Fraction]], values: Mapping[str, Fraction]) -> None:
    for key, value in values.items():
        if key not in spans:
            spans[key] = [value, value]
        else:
            spans[key][0] = min(spans[key][0], value)
            spans[key][1] = max(spans[key][1], value)


def _display_spans(
    spans: Mapping[str, list[Fraction]],
) -> dict[str, dict[str, float]] | None:
    return {
        key: {"minimum": float(pair[0]), "maximum": float(pair[1])}
        for key, pair in spans.items()
    } or None


def build_comparative_geometry(
    layer: Mapping[str, Any], uncertainty: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive the selected constructions from the complete same-run factor grid."""
    sensitivity: dict[str, Any] = {
        "status": uncertainty["status"],
        "uncertainty_minutes": uncertainty["uncertainty_minutes"],
        "sample_count": None,
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "summary": None,
        "point_spans": None,
        "samples": None,
        "interval": {
            k: uncertainty[k]
            for k in (
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
            if k in uncertainty
        },
        "scope": "Finite sampled coordinates and offsets only; signed offsets lie in[-180,180), not a minimal covering arc or continuous bound. Every calculated four-point system is retained in samples.point_systems; native inputs and frame rotations permit independent replay without new queries.",
    }
    result: dict[str, Any] = {
        "status": "unavailable",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "profile": None,
        "radix_systems": None,
        "frames": None,
        "frame_summary": None,
        "birth_time_sensitivity": sensitivity,
        "sources": [SOURCE],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
        "limitations": [
            "Selected geometric reconstruction, not the complete original text, Earth-house assignment or original event/mortality claims",
            "All modern native factors reuse the same algebra; the printed source table contains only12 factors and does not interpret every modern hypothetical factor",
            "Rotations and mirrors are symbolic coordinates, not new physical sky observations; repeated points, frames and samples are not independent evidence",
            "An assigned anchor identity is fixed by definition and does not resolve the physical anchor or an unresolved frame orientation",
            "Four printed transformed rows remain uncoordinated under the declared nearest-arcminute rounding assumption; no printed value or input was fitted",
            "Unknown birth-time error is not zero; sampled spans do not establish continuous stability or real-world probabilities",
        ],
    }
    if layer["status"] != "computed":
        result["reason"] = layer.get("reason", "Native factors are unavailable")
        return result
    factors = layer["factors"]
    nominal_values = {row["id"]: row["longitude"] for row in factors}
    if len(nominal_values) != len(factors):
        raise EphemerisSourceError("comparative_geometry_inputs")
    nominal_values_exact = _values(nominal_values)
    definition = layer["profile"].get("angle_definition")
    coordinates, exact_nominal = comparative_coordinates(nominal_values, definition)
    result.update(coordinates)
    result["profile"] = {
        "native_factor_count": len(factors),
        "constructed_frame_count": len(FRAMES),
        "native_aries_point_longitude": _display(nominal_values_exact["Aries Point"]),
        "display_zodiac": layer["profile"].get("zodiac"),
        "cardinal_policy": "Tropical equinox/cardinals represented by the actual same-run Aries Point in the selected natal display",
        "rotated_aries_factor_policy": "Aries Point as an input factor is rotated like the other native factors; mirror axes always retain the unrotated native Aries Point from this profile",
        "rotation_formula": "factor-anchor+(AriesPoint+source_target) modulo360",
        "four_point_formula": "x, x+180, 2*AriesPoint+180-x, 2*AriesPoint-x modulo360",
        "source_natal_table_factor_count": 12,
        "native_factor_reference": "midpoint_analysis.factors",
        "exact_coordinate_policy": "Exact supplied IEEE inputs; unique counts precede float display, so a displayed pair may round to the same value",
        "node_anchor_policy": "Reuse the current native North Node (mean node in Germany); original1924 mean/true node mode is not established",
        "meridian_anchor_policy": "Use native Midheaven for the printed X birth-meridian reference; numerical-table reconstruction does not independently authenticate the original physical natal chart",
        "coordinates_are_new_observations": False,
    }
    if uncertainty["status"] != "sampled":
        return result
    samples = uncertainty.get("samples", [])
    count = uncertainty.get("sample_count")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not samples
        or len(samples) != count
    ):
        raise EphemerisSourceError("comparative_geometry_inputs")
    required_sample_keys = {
        "offset_seconds",
        "recorded_utc",
        "effective_utc",
        "julian_day_tt",
        "factor_longitudes",
    }
    if any(
        not isinstance(sample, Mapping) or not required_sample_keys.issubset(sample)
        for sample in samples
    ):
        raise EphemerisSourceError("comparative_geometry_inputs")
    offsets = [_number(sample["offset_seconds"]) for sample in samples]
    if offsets != sorted(set(offsets)) or Fraction(0) not in offsets:
        raise EphemerisSourceError("comparative_geometry_inputs")
    nominal_index = offsets.index(Fraction(0))
    zero = samples[nominal_index]
    if (
        _number(zero["julian_day_tt"]) != _number(layer["profile"]["julian_day_tt"])
        or _values(zero["factor_longitudes"]) != nominal_values_exact
        or zero.get("angle_definition") != definition
    ):
        raise EphemerisSourceError("comparative_geometry_inputs")
    nominal_systems = _systems(coordinates)
    tracks: dict[str, dict[str, _SampleTrack]] = {
        group: {
            name: {
                "resolved_sample_count": 0,
                "unresolved_sample_indices": [],
                "known": {},
                "backend": {},
            }
            for name in rows
        }
        for group, rows in nominal_systems.items()
    }
    headers = []
    partial_samples = 0
    for index, sample in enumerate(samples):
        values = sample["factor_longitudes"]
        if set(values) != set(nominal_values):
            raise EphemerisSourceError("comparative_geometry_inputs")
        _number(sample["julian_day_tt"])
        calculated, exact = comparative_coordinates(
            values, sample.get("angle_definition")
        )
        partial_samples += calculated["status"] == "partial"
        for group, rows in _systems(calculated).items():
            for name, row in rows.items():
                track = tracks[group][name]
                delta = {
                    key: _offset(value, exact_nominal[group][name][key])
                    for key, value in exact[group][name].items()
                }
                _update(track["backend"], delta)
                if row["input_reference_geometry_resolved"]:
                    track["resolved_sample_count"] += 1
                    if nominal_systems[group][name][
                        "input_reference_geometry_resolved"
                    ]:
                        _update(track["known"], delta)
                else:
                    track["unresolved_sample_indices"].append(index)
        headers.append(
            {
                "sample_index": index,
                "offset_seconds": sample["offset_seconds"],
                "recorded_utc": sample["recorded_utc"],
                "effective_utc": sample["effective_utc"],
                "julian_day_tt": sample["julian_day_tt"],
                "factor_longitudes": dict(values),
                "angle_definition": sample.get("angle_definition"),
                "frame_summary": calculated["frame_summary"],
                "point_systems": _systems(calculated),
                "native_sample_reference": f"midpoint_analysis.time_sensitivity.samples[{index}]",
            }
        )
    point_spans: dict[str, dict[str, _PointSpan]] = {}
    for group, rows in tracks.items():
        point_spans[group] = {}
        for name, track in rows.items():
            point_spans[group][name] = {
                "nominal_input_reference_geometry_resolved": nominal_systems[group][
                    name
                ]["input_reference_geometry_resolved"],
                "resolved_sample_count": track["resolved_sample_count"],
                "unresolved_sample_count": len(track["unresolved_sample_indices"]),
                "unresolved_sample_indices": track["unresolved_sample_indices"],
                "known_sampled_signed_offsets_from_nominal": _display_spans(
                    track["known"]
                ),
                "backend_sampled_signed_offsets_from_nominal": _display_spans(
                    track["backend"]
                ),
            }
    sensitivity.update(
        status=(
            "partial"
            if partial_samples or coordinates["status"] == "partial"
            else "sampled"
        ),
        sample_count=len(samples),
        nominal_sample_index=nominal_index,
        summary={
            "samples_with_unresolved_reference": partial_samples,
            "point_systems_per_sample": sum(
                len(rows) for rows in nominal_systems.values()
            ),
            "all_confirmed_samples_retained": True,
        },
        point_spans=point_spans,
        samples=headers,
    )
    return result
