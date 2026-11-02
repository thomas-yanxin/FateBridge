"""Aiyar1905 Chapter IX English commentary, printed101-104.

This is a distinct reduction profile, not a repair of Rao's source omissions.
It transforms supplied integer benefic-dot rows; it does not construct a BAV,
assign Pinda weights, interpret events or authenticate planetary occupancy.
"""

from __future__ import annotations

from typing import Any, Sequence

METHOD = "aiyar1905_commentary_classical_occupancy_reductions_v1"
RULE = "jyotish.aiyar1905_commentary_reductions.v1"
SOURCE = {
    "id": "brihat_jataka_aiyar_1905_ashtakavarga_notes",
    "title": "Brihat Jataka, N. Chidambaram Aiyar English translation, second edition, 1905",
    "url": "https://archive.org/details/brihatjataka00varaiala",
    "scan_sha256": "ceafc2fe3e385fb834b94fa4f464406da3ba42ab01b3a2ac42a2749abda9f1d9",
    "text_witness_sha256": "bf1afe4510937e04157ba06f2c3a6d849c262ea3fffa1b922662973172bc0152",
    "source_kind": "english_translation_commentary",
    "section": "Chapter IX extended N.B. notes; printed101-104, PDF145-148",
    "scope": "Selected English commentary arithmetic, not attribution to a numbered Sanskrit verse or whole-text acceptance. Occupancy is a declared classical-graha reading. No Pinda weighting or empirical event prediction.",
}
TRINES = ((0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11))
PAIRS = ((0, 7), (1, 6), (2, 5), (8, 11), (9, 10))


def _counts(values: Sequence[int]) -> list[int]:
    row = list(values)
    if len(row) != 12 or any(type(x) is not int or not 0 <= x <= 8 for x in row):
        raise ValueError("Aiyar reduction requires twelve integer dot counts0..8")
    return row


def _occupancy(signs: Sequence[int]) -> set[int]:
    positions = list(signs)
    if (
        any(type(x) is not int or not 0 <= x < 12 for x in positions)
        or len(set(positions)) != len(positions)
        or len(positions) > 7
    ):
        raise ValueError(
            "Occupancy requires distinct integer sign indices0..11, at most7"
        )
    return set(positions)


def trinal(values: Sequence[int]) -> tuple[list[int], list[dict[str, Any]]]:
    """Decide each group from its original row, once, as the worked example does."""
    original = _counts(values)
    result = original.copy()
    steps = []
    for group in TRINES:
        before = [original[i] for i in group]
        positive = sum(v > 0 for v in before)
        if len(set(before)) == 1:
            rule, after = "IX.NB.I.4", [0, 0, 0]
        elif positive == 1:
            rule, after = "IX.NB.I.3", [0, 0, 0]
        elif positive == 2:
            rule, after = "IX.NB.I.2", before.copy()
        else:
            rule = "IX.NB.I.1"
            after = [v - min(before) for v in before]
        for i, v in zip(group, after):
            result[i] = v
        steps.append(
            {
                "sign_indices": list(group),
                "before": before,
                "after": after,
                "source_rule": rule,
            }
        )
    return result, steps


def coowned(
    values: Sequence[int], occupied_signs: Sequence[int]
) -> tuple[list[int], list[dict[str, Any]]]:
    """Apply the five pairs, with zero exceptions and an explicit equality rule."""
    original = _counts(values)
    occupied = _occupancy(occupied_signs)
    result = original.copy()
    steps = []
    for pair in PAIRS:
        before = [original[i] for i in pair]
        flags = [i in occupied for i in pair]
        after = before.copy()
        if min(before) == 0:
            rule = "IX.NB.II.4"
        elif all(flags):
            rule = "IX.NB.II.1"
        elif not any(flags):
            if before[0] == before[1]:
                rule, after = "IX.NB.II.3a", [0, 0]
            else:
                rule, after = "IX.NB.II.3b", [min(before)] * 2
        else:
            full = 0 if flags[0] else 1
            empty = 1 - full
            if before[full] < before[empty]:
                rule, after[empty] = "IX.NB.II.2.1", before[full]
            elif before[full] > before[empty]:
                rule, after[empty] = "IX.NB.II.2.2", 0
            else:
                rule, after[empty] = "IX.NB.II.2.3", 0
        for i, v in zip(pair, after):
            result[i] = v
        steps.append(
            {
                "sign_indices": list(pair),
                "before": before,
                "occupied": flags,
                "after": after,
                "source_rule": rule,
            }
        )
    return result, steps


def reduce_row(values: Sequence[int], occupied_signs: Sequence[int]) -> dict[str, Any]:
    """Selected-source arithmetic with no Pinda or event admission."""
    original = _counts(values)
    positions = sorted(_occupancy(occupied_signs))
    first, trinal_steps = trinal(original)
    second, coowned_steps = coowned(first, positions)
    return {
        "method_id": METHOD,
        "source_id": SOURCE["id"],
        "status": "computed_declared_occupancy",
        "occupied_sign_indices": positions,
        "trikona": first,
        "sodhita": second,
        "reduced_sum": sum(second),
        "trikona_steps": trinal_steps,
        "coowned_steps": coowned_steps,
        "scope": "Transformation of the supplied dot row under the selected English commentary and occupancy. No claim that the input BAV itself conforms to this source. Reduced sum is not a Pinda, physical strength, probability or event forecast.",
    }
