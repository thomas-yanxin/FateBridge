"""Raman76-77 war arithmetic on declared, branch-matched strength inputs.

The fixed Bimba coefficients are textual constants, not measured apparent
diameters. This component does not certify a complete single-author Shadbala.
"""

from __future__ import annotations

import math
from fractions import Fraction
from itertools import combinations
from typing import Any

from fatebridge.core.jyotish_balas import PLANETS, directed_angle

STARS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
BIMBA = {
    "Mars": "9.4",
    "Mercury": "6.6",
    "Jupiter": "190.4",
    "Venus": "16.6",
    "Saturn": "158.0",
}
THROUGH_HORA = (
    "nathonnatha_bala",
    "paksha_bala",
    "tribhaga_bala",
    "abda_bala",
    "masa_bala",
    "dina_bala",
    "hora_bala",
)
SOURCE = {
    "id": "raman_war_76_77_727c8063",
    "title": "B.V.Raman, Graha and Bhava Balas, sections76-77, printed60-61",
    "url": "https://astrojyotish.info/pdf/graha-bhava-balas.pdf",
    "sha256": "727c8063f64816a0c1c7f6bc577c249629854e980bf860bf4cfd8de16ec9bab2",
    "sections": ["76-77 printed60-61/PDF65-66, page images verified"],
    "edition": "Foreword to thirteenth edition1992; exact reprint unverified",
    "scope": "War criterion, lower-longitude victor, fixed Bimba constants and through-Hora arithmetic only; other sections and mixed upstream strengths not thereby certified",
}


def finite(value: Any) -> Fraction | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("War strength inputs must be finite numbers or missing")
    return Fraction(value)


def consensus(scenarios: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    result = {}
    for p in PLANETS:
        values = {row[p] for row in scenarios.values()}
        result[p] = next(iter(values)) if len(values) == 1 else None
    return result


def war_bala(
    longitudes: dict[str, float],
    components: dict[str, Any],
    paksha: dict[str, dict[str, Any]],
    sthana: dict[str, Any] | None,
    dig: dict[str, Any] | None,
) -> dict[str, Any]:
    """Pair contributions use the same Paksha branch as the final Kala sum.

    Multiple neighbours, equal longitudes and the longitude-origin cut keep
    their aggregate missing. Independent disjoint pairs may still be computed.
    """
    normalized = {p: Fraction(longitudes[p]) % 360 for p in STARS}
    candidates: list[dict[str, Any]] = []
    neighbours: dict[str, set[str]] = {p: set() for p in STARS}
    for a, b in combinations(STARS, 2):
        angle = directed_angle(longitudes[a], longitudes[b])
        distance = min(angle, 360 - angle)
        if distance < 1:
            candidates.append(
                {"planets": [a, b], "separation_degrees": float(distance)}
            )
            neighbours[a].add(b)
            neighbours[b].add(a)
    pairs: list[dict[str, Any]] = []
    for candidate in candidates:
        a, b = candidate["planets"]
        state = "declared_lower_longitude_winner"
        winner: str | None = a if normalized[a] < normalized[b] else b
        if normalized[a] == normalized[b]:
            state, winner = "equal_longitude_unadjudicated", None
        elif abs(normalized[a] - normalized[b]) > 180:
            state, winner = "longitude_origin_crossing_unadjudicated", None
        elif len(neighbours[a]) > 1 or len(neighbours[b]) > 1:
            state, winner = "simultaneous_multi_planet_war_unadjudicated", None
        pairs.append({**candidate, "status": state, "winner": winner})
    # A chain of three or more must not acquire a spurious isolated endpoint
    # result merely because only one edge touches that endpoint.
    blocked = set()
    for p in STARS:
        group, pending = set(), [p]
        while pending:
            q = pending.pop()
            if q in group:
                continue
            group.add(q)
            pending.extend(neighbours[q] - group)
        if len(group) > 2:
            blocked.update(group)
    for pair in pairs:
        if any(p in blocked for p in pair["planets"]):
            pair.update(
                status="simultaneous_multi_planet_war_unadjudicated", winner=None
            )
    scenarios: dict[str, dict[str, Any]] = {}
    evidence: dict[str, Any] = {}
    for name, lunar in paksha.items():
        values: dict[str, float | None] = dict.fromkeys(PLANETS, 0.0)
        basis = {}
        exact_totals: dict[str, Fraction | None] = {}
        for p in STARS:
            inputs = {
                "sthana_bala": sthana["summary"][p]["total_virupa"] if sthana else None,
                "dig_bala": dig["summary"][p] if dig else None,
                **{
                    key: (
                        lunar[p]
                        if key == "paksha_bala"
                        else components[key]["summary"][p]
                    )
                    for key in THROUGH_HORA
                },
            }
            numbers = [finite(v) for v in inputs.values()]
            total = (
                None
                if None in numbers
                else sum((v for v in numbers if v is not None), Fraction(0))
            )
            exact_totals[p] = total
            if total is not None and not math.isfinite(float(total)):
                raise ValueError("Prewar strength exceeds finite numerical range")
            basis[p] = {
                "inputs": inputs,
                "missing_inputs": [k for k, v in inputs.items() if v is None],
                "total_virupa": float(total) if total is not None else None,
            }
        pair_results = []
        for pair in pairs:
            a, b = pair["planets"]
            winner = pair["winner"]
            left, right = exact_totals[a], exact_totals[b]
            denominator = abs(Fraction(BIMBA[a]) - Fraction(BIMBA[b]))
            amount = None
            state = pair["status"]
            if (
                left is not None
                and right is not None
                and state != "simultaneous_multi_planet_war_unadjudicated"
            ):
                # The magnitude does not depend on the unresolved winner.
                # Multiple simultaneous wars still lack a registered pair rule.
                amount = float(abs(left - right) / denominator)
                if not math.isfinite(amount):
                    raise ValueError("War amount exceeds finite numerical range")
            if winner is not None and amount is not None:
                loser = b if winner == a else a
                values[winner], values[loser] = amount, -amount
            else:
                if winner is not None:
                    state = "prewar_inputs_missing"
                values[a] = values[b] = None
            pair_results.append(
                {
                    **pair,
                    "status": state,
                    "fixed_disc_difference_arcseconds": float(denominator),
                    "amount_virupa": amount,
                }
            )
        scenarios[name] = values
        evidence[name] = {"prewar_basis": basis, "pairs": pair_results}
    summary = consensus(scenarios)
    return {
        "source_id": SOURCE["id"],
        "source_section": "76-77 printed60-61/PDF65-66; full section takes precedence over abbreviated summary107",
        "method": "raman_76_77_on_declared_upstream_balas",
        "unit": "signed virupa",
        "summary": summary,
        "scenarios": scenarios,
        "candidates": candidates,
        "pairs": pairs,
        "evidence": evidence,
        "status": (
            "no_candidate_under_less_than_one_degree_rule"
            if not candidates
            else (
                "partial_unadjudicated_pairs"
                if any(any(row[p] is None for p in STARS) for row in scenarios.values())
                else "conditional_amounts_from_declared_inputs"
            )
        ),
        "unresolved_planets": [
            p for p in STARS if any(row[p] is None for row in scenarios.values())
        ],
        "conditional_planets": [
            p
            for p in STARS
            if summary[p] is None
            and all(row[p] is not None for row in scenarios.values())
        ],
        "fixed_bimba_arcseconds": {p: float(v) for p, v in BIMBA.items()},
        "upstream_profile": {
            "sthana": sthana.get("profile") if sthana else None,
            "dig_source_id": dig.get("source_id") if dig else None,
            "temporal_scope": "existing declared Natha, Paksha, Tribhaga and calendar lord readings; same nature branch throughout",
            "scope": "War formula is Raman, inputs retain their own source profiles; not a complete Raman or Santhanam Shadbala reconstruction",
        },
        "rule_ids": ["jyotish.yuddha_raman_76_77.v1"],
        "source_disagreements": [
            "Santhanam27.20 adds/subtracts the difference of Shadbalas without this fixed-disc divisor; not silently substituted.",
            "Raman76 explicitly stops input Kala at Hora; abbreviated summary107 does not specify that cutoff. Ayana, Cheshta, Drik and Naisargika are excluded from this calculation.",
        ],
        "interpretation_scope": "Traditional component under declared mixed upstream readings. Signed values are not victory in life, event probabilities, complete Shadbala or empirical prediction evidence. No arbitrary60 cap or invented zero for unresolved participants.",
    }
