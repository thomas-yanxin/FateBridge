"""Compare source-specific angular facts without inventing a common unit."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


def load_angle_source_reference(folder: Path) -> dict[str, Any]:
    manifest = json.loads((folder / "hashes.json").read_text(encoding="utf-8"))
    if set(manifest) != {"reference.json"}:
        raise ValueError("Keep the complete angular source reference")
    raw = (folder / "reference.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["reference.json"]:
        raise ValueError("Angular source transcription changed")
    reference = json.loads(raw)
    if not isinstance(reference, dict):
        raise ValueError("Angular source reference must be an object")
    return reference


def normalize_source_quantities(claim: dict[str, Any]) -> dict[str, Any]:
    """Require both an attested unit scale and origin, even for 'degrees'."""
    quantities = claim["quantities"]
    if not quantities or any(type(q) is not str for q in quantities):
        raise ValueError("Preserve source quantities as exact rational strings")
    numbers = [Fraction(q) for q in quantities]
    if any(q < 0 for q in numbers):
        raise ValueError("Angular distances cannot be negative")
    missing = []
    scale = claim["degrees_per_unit"]
    origin = claim["origin_offset_degrees"]
    for key, value in (("degrees_per_unit", scale), ("origin_offset_degrees", origin)):
        if value is None:
            missing.append(key)
        elif type(value) is not str:
            raise ValueError("Unit and origin must be exact strings or unknown")
    if scale is not None and Fraction(scale) <= 0:
        raise ValueError("Unit scale must be positive")
    if origin is not None and Fraction(origin) < 0:
        raise ValueError("Origin distance cannot be negative")
    return {
        "claim_id": claim["id"],
        "source_quantities": quantities,
        "source_unit_label": claim["unit_label"],
        "missing_normalization_facts": missing,
        "offsets_from_center_degrees_exact": (
            None
            if missing
            else [str(Fraction(origin) + n * Fraction(scale)) for n in numbers]
        ),
        # Normalizing a quantity does not settle > versus >=, exceptions,
        # water conditions or whether a range is one activation threshold.
        "complete_selection_condition_verified": False,
    }


def audit_angle_source_reference(reference: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.fengshui.xuankong import _selectors, natal_rules

    geometry = reference["wang_geometry"]
    circle, palace_count, per_palace, width, grids, grid_width, central = (
        geometry[key]
        for key in (
            "circle_degrees",
            "palace_count",
            "mountains_per_palace",
            "mountain_width_degrees",
            "grids_per_mountain",
            "grid_width_degrees",
            "central_width_degrees",
        )
    )
    if (
        any(
            type(n) is not int or n <= 0
            for n in (
                circle,
                palace_count,
                per_palace,
                width,
                grids,
                grid_width,
                central,
            )
        )
        or circle != palace_count * per_palace * width
        or width != grids * grid_width
        or central >= width
    ):
        raise ValueError("Retain internally consistent printed angular geometry")
    names = list(reference["clockwise_mountains"])
    groups = reference["source_mountain_groups"]
    entries = [(n, g["palace"]) for g in groups for n in g["mountains"]]
    yin = set(reference["polarity_source"]["yin"])
    yang = set(reference["polarity_source"]["yang"])
    if (
        len(names) != 24
        or len(set(names)) != 24
        or len(groups) != 8
        or len({g["palace"] for g in groups}) != 8
        or any(len(g["mountains"]) != 3 for g in groups)
        or len(entries) != 24
        or {n for n, _ in entries} != set(names)
        or len(yin) != 12
        or len(yang) != 12
        or yin & yang
        or yin | yang != set(names)
    ):
        raise ValueError(
            "Keep all 24 source mountains and their independent properties"
        )
    if set(reference["categorical_predicate"]["replacement_when"]) != {
        "different_palace",
        "different_polarity_in_same_palace",
    }:
        raise ValueError("Do not replace the cited categorical condition")
    palaces = dict(entries)
    rules = natal_rules()
    actual_mountains = rules["mountains"]
    actual_by_name = {m["name"]: m for m in actual_mountains}
    if len(actual_mountains) != 24 or set(actual_by_name) != set(names):
        raise ValueError("The engine must retain every source mountain")
    half = Fraction(central, 2)
    disagreements = []
    if Fraction(rules["central_half_width_degrees"]) != half:
        disagreements.append(
            {
                "scope": "central_half_width",
                "source_expected_exact": str(half),
                "actual_exact": str(Fraction(rules["central_half_width_degrees"])),
            }
        )
    probes = []
    # Relative coordinates deliberately use the engine's own center. These
    # checks cannot certify absolute compass bearings or physical measurement.
    for index, name in enumerate(names):
        for side in (-1, 1):
            neighbour = names[(index + side) % 24]
            categorical_replacement = palaces[name] != palaces[neighbour] or (
                name in yin
            ) != (neighbour in yin)
            for distance in (4, 5, 7):
                if not Fraction(distance) < Fraction(width, 2):
                    raise ValueError("Probes must remain inside one source mountain")
                expected_mode = (
                    "lower"
                    if distance < half or not categorical_replacement
                    else "replacement"
                )
                angle = (actual_by_name[name]["center_degrees"] + side * distance) % 360
                selected = _selectors(angle, 0)
                actual = [
                    {"mountain": actual_mountains[s[0]]["name"], "mode": s[1]}
                    for s in selected
                ]
                row = {
                    "mountain": name,
                    "neighbour": neighbour,
                    "signed_offset_degrees": side * distance,
                    "expected_mode_under_composition": expected_mode,
                    "actual": actual,
                }
                probes.append(row)
                if actual != [{"mountain": name, "mode": expected_mode}]:
                    disagreements.append({"scope": "relative_probe", **row})
    normalized = [
        normalize_source_quantities(claim)
        for claim in reference["unresolved_thresholds"]
    ]
    return {
        "scope": "Wang geometry plus a separately attributed categorical clause; cross-source composition only",
        "relative_probes": len(probes),
        "probes": probes,
        "disagreements": disagreements,
        "declared_composition_agreement": not disagreements,
        "source_threshold_claims": normalized,
        "unresolved_threshold_claim_count": sum(
            bool(row["missing_normalization_facts"]) for row in normalized
        ),
        "universal_fen_to_degree_conversion_established": False,
        "source_angle_applicability_verified": False,
        "boundary_equality_policy_verified": False,
        "absolute_compass_orientation_verified": False,
        "whole_book_conformity_established": False,
        "independent_human_expert_review_complete": False,
        "real_world_prediction_established": False,
    }
