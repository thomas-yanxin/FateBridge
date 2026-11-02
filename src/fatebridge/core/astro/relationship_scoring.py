"""Versioned, replayable modern relationship heuristics (not a text rule)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Tuple

from fatebridge.core.astro.reference import (
    _TRADITIONAL_PLANET_IDS,
    ASPECTS,
    HARMONIOUS_ASPECTS,
)

RULE_ID = "fatebridge_relationship_heuristic_v2"
ASPECT_LIMIT = 24


def relationship_scoring_policy() -> Dict[str, Any]:
    return {
        "rule_id": RULE_ID,
        "population": "seven_traditional_planets",
        "overlap_formula": "sum(min(count_A,count_B))/max(total_A,total_B,1)*100",
        "aspect_selection": "smallest 24 unrounded orbs, including all exact ties at the cutoff",
        "aspect_baseline": 50,
        "harmonious_aspects": sorted(HARMONIOUS_ASPECTS),
        "per_aspect_delta": 4,
        "overall_formula": "rounded arithmetic mean of rounded element, rounded modality and clamped aspect scores",
        "rounding": "nearest integer, ties to even; overlap components rounded before overall mean",
        "is_probability": False,
        "original_text_rule": False,
        "empirically_calibrated": False,
    }


def _overlap(
    inner: List[Dict[str, Any]], outer: List[Dict[str, Any]], dimension: str
) -> Dict[str, Any]:
    left = Counter(
        item[dimension] for item in inner if item["id"] in _TRADITIONAL_PLANET_IDS
    )
    right = Counter(
        item[dimension] for item in outer if item["id"] in _TRADITIONAL_PLANET_IDS
    )
    overlap = sum(min(left[key], right[key]) for key in left)
    denominator = max(sum(left.values()), sum(right.values()), 1)
    raw = 100 * overlap / denominator
    return {
        "inner_counts": dict(sorted(left.items())),
        "outer_counts": dict(sorted(right.items())),
        "overlap_count": overlap,
        "denominator": denominator,
        "unrounded_score": raw,
        "score": int(round(raw)),
    }


def compatibility_with_evidence(
    inner: List[Dict[str, Any]],
    outer: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """Keep raw-orb ties; IDs affect display order only, never membership.

    The nominal cap and arithmetic are product conventions, not calibrated
    relationship predictions. Preserve v1's component rounding and clamping;
    v2 changes only which contacts survive a tie at the cap.
    """
    element = _overlap(inner, outer, "element")
    modality = _overlap(inner, outer, "modality")
    known_aspects = {name for name, _ in ASPECTS}
    for row in aspects:
        if (
            row["inner"] not in _TRADITIONAL_PLANET_IDS
            or row["outer"] not in _TRADITIONAL_PLANET_IDS
            or row["aspect"] not in known_aspects
            or not math.isfinite(row["orb"])
            or row["orb"] < 0
        ):
            raise ValueError(
                "Relationship scoring requires finite seven-planet contacts"
            )
    ordered = sorted(
        enumerate(aspects),
        key=lambda pair: (
            pair[1]["orb"],
            pair[1]["inner"],
            pair[1]["outer"],
            pair[1]["aspect"],
        ),
    )
    cutoff = ordered[min(ASPECT_LIMIT, len(ordered)) - 1][1]["orb"] if ordered else None
    selected = [
        {
            **row,
            "synastry_aspect_index": index,
            "delta": 4 if row["aspect"] in HARMONIOUS_ASPECTS else -4,
        }
        for index, row in ordered
        if row["orb"] <= cutoff
    ]
    positive = sum(row["delta"] > 0 for row in selected)
    negative = len(selected) - positive
    raw_harmony = 50 + 4 * (positive - negative)
    harmony = max(0, min(100, raw_harmony))
    numerator = element["score"] + modality["score"] + harmony
    scores = {
        "element_harmony_score": element["score"],
        "modality_balance_score": modality["score"],
        "synastry_aspect_score": harmony,
        "overall_score": int(round(numerator / 3)),
    }
    return scores, {
        "rule_id": RULE_ID,
        "source_paths": [
            "inner_chart.planets",
            "outer_chart.planets",
            "synastry_aspects",
        ],
        "element_overlap": element,
        "modality_overlap": modality,
        "aspect_selection": {
            "candidate_count": len(ordered),
            "nominal_limit": ASPECT_LIMIT,
            "cutoff_orb": cutoff,
            "boundary_tie_count": sum(row["orb"] == cutoff for _, row in ordered),
            "selected_count": len(selected),
            "excluded_count": len(ordered) - len(selected),
            "selected_contacts": selected,
            "baseline": 50,
            "positive_count": positive,
            "negative_count": negative,
            "unclamped_score": raw_harmony,
            "clamped": harmony != raw_harmony,
            "score": harmony,
        },
        "overall": {
            "numerator": numerator,
            "denominator": 3,
            "unrounded_score": numerator / 3,
            "score": scores["overall_score"],
        },
    }
