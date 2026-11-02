"""Aiyar1905 IX.1-7 sign tables with its own English-note reductions.

Source profile arithmetic on supplied signs; chart construction, sidereal origin
and applying sign-count rules to non-D1 vargas remain separately declared.
No Ascendant-target row or Pinda weights are inferred from another author.
"""

from __future__ import annotations

from typing import Any, Mapping

from fatebridge.core.jyotish_aiyar_reductions import RULE as REDUCTION_RULE
from fatebridge.core.jyotish_aiyar_reductions import SOURCE as REDUCTION_SOURCE
from fatebridge.core.jyotish_aiyar_reductions import reduce_row

TARGETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
CONTRIBUTORS = (*TARGETS, "Ascendant")
RULE = "jyotish.ashtakavarga_aiyar1905.v1"
METHOD = "aiyar1905_seven_bav_and_commentary_reductions_v1"
SOURCE = {
    "id": "brihat_jataka_aiyar_1905_seven_bav",
    "title": "Brihat Jataka, N. Chidambaram Aiyar English translation, second edition, 1905",
    "url": "https://archive.org/details/brihatjataka00varaiala",
    "scan_sha256": "ceafc2fe3e385fb834b94fa4f464406da3ba42ab01b3a2ac42a2749abda9f1d9",
    "text_witness_sha256": "bf1afe4510937e04157ba06f2c3a6d849c262ea3fffa1b922662973172bc0152",
    "sections": [
        "IX.1-7, printed97-99/PDF141-143; benefic-dot notation in notes printed100-101"
    ],
    "source_kind": "english_translation_sign_rules",
    "scope": "Seven planetary-target tables with eight contributors. Source-own English-commentary reductions are separately attributed; no Ascendant-target table, Pinda weights, full-book conformity or empirical prediction admission. Varga construction/application are separate choices.",
}
# Literal relative houses1..12, transcribed and frozen before this module.
POSITIVE_HOUSES = {
    "Sun": {
        "Sun": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Venus": (6, 7, 12),
        "Jupiter": (5, 6, 9, 11),
        "Moon": (3, 6, 10, 11),
        "Mercury": (3, 5, 6, 9, 10, 11, 12),
        "Ascendant": (3, 4, 6, 10, 11, 12),
    },
    "Moon": {
        "Ascendant": (3, 6, 10, 11),
        "Mars": (2, 3, 5, 6, 9, 10, 11),
        "Moon": (1, 3, 6, 7, 10, 11),
        "Sun": (3, 6, 7, 8, 10, 11),
        "Saturn": (3, 5, 6, 11),
        "Mercury": (1, 3, 4, 5, 7, 8, 10, 11),
        "Jupiter": (1, 4, 7, 8, 10, 11, 12),
        "Venus": (3, 4, 5, 7, 9, 10, 11),
    },
    "Mars": {
        "Sun": (3, 5, 6, 10, 11),
        "Ascendant": (1, 3, 6, 10, 11),
        "Moon": (3, 6, 11),
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Saturn": (1, 4, 7, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 11),
        "Venus": (6, 8, 11, 12),
        "Jupiter": (6, 10, 11, 12),
    },
    "Mercury": {
        "Venus": (1, 2, 3, 4, 5, 8, 9, 11),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Jupiter": (6, 8, 11, 12),
        "Sun": (5, 6, 9, 11, 12),
        "Mercury": (1, 3, 5, 6, 9, 10, 11, 12),
        "Moon": (2, 4, 6, 8, 10, 11),
        "Ascendant": (1, 2, 4, 6, 8, 10, 11),
    },
    "Jupiter": {
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
        "Sun": (1, 2, 3, 4, 7, 8, 9, 10, 11),
        "Venus": (2, 5, 6, 9, 10, 11),
        "Moon": (2, 5, 7, 9, 11),
        "Saturn": (3, 5, 6, 12),
        "Mercury": (1, 2, 4, 5, 6, 9, 10, 11),
        "Ascendant": (1, 2, 4, 5, 6, 7, 9, 10, 11),
    },
    "Venus": {
        "Ascendant": (1, 2, 3, 4, 5, 8, 9, 11),
        "Moon": (1, 2, 3, 4, 5, 8, 9, 11, 12),
        "Venus": (1, 2, 3, 4, 5, 8, 9, 10, 11),
        "Saturn": (3, 4, 5, 8, 9, 10, 11),
        "Sun": (8, 11, 12),
        "Jupiter": (5, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 9, 11),
        "Mars": (3, 5, 6, 9, 11, 12),
    },
    "Saturn": {
        "Saturn": (3, 5, 6, 11),
        "Mars": (3, 5, 6, 10, 11, 12),
        "Sun": (1, 2, 4, 7, 8, 10, 11),
        "Ascendant": (1, 3, 4, 6, 10, 11),
        "Mercury": (6, 8, 9, 10, 11, 12),
        "Moon": (3, 6, 11),
        "Venus": (6, 11, 12),
        "Jupiter": (5, 6, 11, 12),
    },
}


def calculate(signs: Mapping[str, int]) -> dict[str, Any]:
    if set(signs) != set(CONTRIBUTORS) or any(
        type(v) is not int or not 0 <= v < 12 for v in signs.values()
    ):
        raise ValueError(
            "Aiyar tables require exactly seven planets and Ascendant, integer signs0..11"
        )
    positions = dict(signs)
    # Inverse membership from each absolute sign; independent reference instead
    # shifts the literal positive-house list forward into initially empty rows.
    pav = {
        p: {
            d: [
                int((sign - positions[d]) % 12 + 1 in POSITIVE_HOUSES[p][d])
                for sign in range(12)
            ]
            for d in CONTRIBUTORS
        }
        for p in TARGETS
    }
    bav = {
        p: [sum(pav[p][d][sign] for d in CONTRIBUTORS) for sign in range(12)]
        for p in TARGETS
    }
    sav = [sum(bav[p][sign] for p in TARGETS) for sign in range(12)]
    physical = {p: positions[p] for p in TARGETS}
    return {
        "status": "computed_declared_source",
        "method_id": METHOD,
        "source_id": SOURCE["id"],
        "source_section": "IX.1-7; printed97-99/PDF141-143",
        "rule_ids": [RULE, REDUCTION_RULE],
        "input_sign_indices": positions,
        "contributor_order": list(CONTRIBUTORS),
        "target_order": list(TARGETS),
        "samudaya_targets": list(TARGETS),
        "prastara": pav,
        "bhinna": bav,
        "samudaya": sav,
        "bhinna_totals": {p: sum(bav[p]) for p in TARGETS},
        "samudaya_total": sum(sav),
        "notation": {
            "one": "benefic dot in this English edition",
            "zero": "malefic line in this English edition",
        },
        "reductions_applied": False,
        "reduction_analysis": {
            "method_id": "aiyar1905_commentary_classical_occupancy_reductions_v1",
            "source_id": REDUCTION_SOURCE["id"],
            "source_section": REDUCTION_SOURCE["section"],
            "rule_ids": [REDUCTION_RULE],
            "input_sign_indices": physical,
            "targets": {
                p: reduce_row(bav[p], sorted(set(physical.values()))) for p in TARGETS
            },
            "rao_default_replaced": False,
            "input_scope": "This Aiyar profile's own unreduced bhinna, built from IX.1-7. Not the parent Rao BAV. Seven physical grahas define the declared occupancy.",
            "interpretation_scope": "Selected-source integer reductions and their sum only. No Ascendant-target BAV, Pinda weighting, probability or empirical event prediction.",
        },
        "interpretation_scope": "Counts from this English sign-rule source on the supplied same chart signs. Chart construction and applying these rules to non-D1 vargas are separate declared comparison choices; not prescriptions verified from this author. No event guarantee or probability.",
    }
