"""Rao12.7 arithmetic with a declared seven-graha occupancy reading."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fatebridge.core import jyotish_aiyar_reductions as aiyar

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
RULE = "jyotish.pinda_rao2000_seven_occupants.v1"
METHOD = "rao2000_classical_seven_occupants_equal_unresolved_v1"
TRINES = ((0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11))
PAIRS = ((0, 7), (1, 6), (2, 5), (8, 11), (9, 10))
RASI_WEIGHTS = (7, 10, 8, 4, 10, 6, 7, 8, 9, 5, 11, 12)
GRAHA_WEIGHTS = (5, 5, 8, 5, 10, 7, 5)
BAV_TOTALS = dict(zip((*PLANETS, "Ascendant"), (48, 49, 39, 54, 56, 52, 39, 49)))
SOURCE = {
    "id": "pvr_2000_pinda_1cafa828",
    "title": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (2000; 2010 update)",
    "url": "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
    "sha256": "1cafa828f34764ed5e85816882df2e8f0bc014c5c57ccdb27169416e117fd4db",
    "sections": ["3.1; 12.7.1-12.7.3; Tables28-29; printed157-160/PDF169-172"],
    "scope": "Trinal reduction, all five coowned pairs and Pinda under an explicitly selected seven-classical-graha occupancy reading. Single-occupied equal nonzero counts have no supplied rule and stay unknown. Not unique whole-book acceptance or event forecasting.",
}


def _counts(values: Sequence[int]) -> list[int]:
    result = list(values)
    if len(result) != 12 or any(type(v) is not int or not 0 <= v <= 8 for v in result):
        raise ValueError("Pinda requires twelve integer BAV counts0..8")
    return result


def _signs(signs: Mapping[str, int]) -> dict[str, int]:
    if set(signs) != set(PLANETS) or any(
        type(v) is not int or not 0 <= v < 12 for v in signs.values()
    ):
        raise ValueError(
            "Pinda occupancy requires exactly seven classical planetary signs0..11"
        )
    return dict(signs)


def coowned(
    values: Sequence[int], signs: Mapping[str, int]
) -> tuple[list[int | None], list[dict[str, Any]]]:
    """Reduce every coowned pair; leave the unspecified empty cell unknown."""
    original = _counts(values)
    occupied = set(_signs(signs).values())
    result: list[int | None] = list(original)
    steps = []
    for pair in PAIRS:
        a, b = pair
        before = [original[a], original[b]]
        flags = [a in occupied, b in occupied]
        after: list[int | None] = list(before)
        if 0 in before:
            rule = "12.7.2.1"
        elif all(flags):
            rule = "12.7.2.2"
        elif not any(flags):
            rule = "12.7.2.4a" if before[0] == before[1] else "12.7.2.4b"
            after = [0, 0] if before[0] == before[1] else [min(before)] * 2
        else:
            empty = 1 if flags[0] else 0
            full = 1 - empty
            if before[empty] == before[full]:
                rule = "12.7.2.single_occupied_equal_nonzero_unspecified"
                after[empty] = None
            elif before[empty] < before[full]:
                rule = "12.7.2.3a"
                after[empty] = 0
            else:
                rule = "12.7.2.3b"
                after[empty] = before[full]
        result[a], result[b] = after
        steps.append(
            {
                "sign_indices": list(pair),
                "before": before,
                "occupied_by_classical_grahas": flags,
                "after": after,
                "source_rule": rule,
            }
        )
    return result, steps


def reduce_row(values: Sequence[int], signs: Mapping[str, int]) -> dict[str, Any]:
    """Keep integer terms, traceable reductions and explicit source missingness."""
    raw = _counts(values)
    positions = _signs(signs)
    trinal = list(raw)
    trinal_steps = []
    for group in TRINES:
        before = [raw[i] for i in group]
        subtract = min(before)
        after = [v - subtract for v in before]
        for sign, value in zip(group, after):
            trinal[sign] = value
        trinal_steps.append(
            {
                "sign_indices": list(group),
                "before": before,
                "subtract": subtract,
                "after": after,
            }
        )
    sodhita, steps = coowned(trinal, positions)
    ambiguities = [
        {
            "sign_indices": step["sign_indices"],
            "reason": "one_occupied_equal_nonzero_unspecified",
            "affected_empty_signs": [
                sign
                for sign, value in zip(step["sign_indices"], step["after"])
                if value is None
            ],
        }
        for step in steps
        if None in step["after"]
    ]
    rasi_terms = [None if v is None else v * w for v, w in zip(sodhita, RASI_WEIGHTS)]
    graha_terms: list[dict[str, Any]] = []
    for p, w in zip(PLANETS, GRAHA_WEIGHTS):
        count = sodhita[positions[p]]
        graha_terms.append(
            {
                "planet": p,
                "sign_index": positions[p],
                "count": count,
                "multiplier": w,
                "product": None if count is None else count * w,
            }
        )
    rasi = (
        None
        if any(v is None for v in rasi_terms)
        else sum(v for v in rasi_terms if v is not None)
    )
    products = [row["product"] for row in graha_terms]
    graha = None if any(v is None for v in products) else sum(products)
    return {
        "status": (
            "partial_source_rule" if ambiguities else "computed_declared_occupancy"
        ),
        "trikona": trinal,
        "sodhita": sodhita,
        "trikona_steps": trinal_steps,
        "coowned_steps": steps,
        "source_ambiguities": ambiguities,
        "rasi_multipliers": list(RASI_WEIGHTS),
        "rasi_terms": rasi_terms,
        "graha_terms": graha_terms,
        "rasi_pinda": rasi,
        "graha_pinda": graha,
        "sodhya_pinda": None if rasi is None or graha is None else rasi + graha,
    }


def analyze(
    bhinna: Mapping[str, Sequence[int]], signs: Mapping[str, int]
) -> dict[str, Any]:
    positions = _signs(signs)
    if set(bhinna) not in (set(PLANETS), {*PLANETS, "Ascendant"}):
        raise ValueError("Pinda targets must be the seven classical planetary BAVs")
    totals = {p: sum(_counts(values)) for p, values in bhinna.items()}
    if any(total != BAV_TOTALS[p] for p, total in totals.items()):
        raise ValueError("Pinda requires the unreduced Rao BAV totals for each target")
    targets = {p: reduce_row(bhinna[p], positions) for p in PLANETS}
    return {
        "status": (
            "partial_source_rule"
            if any(t["source_ambiguities"] for t in targets.values())
            else "computed_declared_occupancy"
        ),
        "method_id": METHOD,
        "source_id": SOURCE["id"],
        "source_section": "3.1 and12.7.1-12.7.3; Tables28-29",
        "rule_ids": [RULE],
        "occupancy_planets": list(PLANETS),
        "input_sign_indices": positions,
        "input_bhinna_totals": totals,
        "targets": targets,
        "source_profile_comparison": {
            "aiyar1905_commentary": {
                "method_id": aiyar.METHOD,
                "source_id": aiyar.SOURCE["id"],
                "source_section": aiyar.SOURCE["section"],
                "rule_ids": [aiyar.RULE],
                "input_sign_indices": positions,
                "targets": {
                    p: aiyar.reduce_row(bhinna[p], sorted(set(positions.values())))
                    for p in PLANETS
                },
                "rao_default_replaced": False,
                "input_scope": "Same sibling unreduced bhinna rows and this analysis input_sign_indices; only the reduction reading differs. Does not certify the original BAV or varga against Aiyar.",
                "interpretation_scope": "English commentary integer reduction counts and their sum only. Aiyar two-original-zero rule and single-occupied equality rule stay together. No Rao null is overwritten; no Pinda weights, probability or empirical event conclusion supplied.",
            }
        },
        "unreduced_tables_preserved": True,
        "assumptions": [
            "Occupancy uses the seven classical grahas, selected from the3.1 distinction between seven grahas and two shadow grahas;12.7 does not explicitly resolve alternative occupancy conventions.",
            "Ascendant contributes to the input BAV but is neither a planetary target nor a graha occupant or graha-weighted product.",
            "No numeric rule is supplied for a single occupied pair with equal nonzero values; the empty sign and affected sums remain null.",
        ],
        "interpretation_scope": "Declared-source integer arithmetic only; partial values are not zero. No transit timing, probability, physical strength or empirical prediction admission.",
    }
