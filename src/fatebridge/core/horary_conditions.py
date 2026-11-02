"""Evaluate named Lilly conditions without inventing missing event histories.

All current direct, translation and collection candidates in this evaluator
are enumerated: the first proxy must not hide alternative carriers/collectors.
Named necessary house-dwelling conditions are reported separately; complete
house-dwelling and lunar co-significator judgements remain open.
Nominal routes use question-epoch reception; event_paths separately evaluates
physical sequences and event-epoch receptions. Full p.125-126 judgement remains
open, including the interpretation of reception epochs and house conditions.
"""

from __future__ import annotations

from typing import Any, Callable

from fatebridge.core.classical_western import LIGHT_WEIGHT_ORDER
from fatebridge.core.horary_event_paths import evaluate_event_paths
from fatebridge.core.lilly import KINDS, RULESET, dignity_at, pair_reception, reception
from fatebridge.core.lilly_houses import dwelling_clause

Phase = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]


def _condition(
    code: str, passed: bool | None, pages: list[int], detail: str
) -> dict[str, Any]:
    return {
        "code": code,
        "passed": passed,
        "status": (
            "unverified"
            if passed is None
            else "satisfied" if passed else "not_satisfied"
        ),
        "source_pages": pages,
        "detail": detail,
    }


def _has_dignity(placement: dict[str, Any]) -> bool | None:
    return (
        False
        if placement["peregrine"] is True
        else True if placement["dignities"] else None
    )


def _both(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def _moon_next_target(
    target: str, motion: dict[str, Any] | None
) -> tuple[bool | None, dict[str, Any] | None, str]:
    if (
        not motion
        or motion.get("constant_velocity_projection") is not False
        or motion.get("status") not in {"computed", "boundary_ambiguous"}
    ):
        return (
            None,
            None,
            "Native lunar event search unavailable; a linear projection is not historical event evidence",
        )
    contacts = motion.get("contacts", [])
    if not contacts:
        return (
            None,
            None,
            "No certain contact in the lunar before-ingress window; no assertion about events outside this window",
        )
    first = contacts[0]
    bracket = first["root_bracket_tt"]
    if any(row["root_bracket_tt"][0] <= bracket[1] for row in contacts[1:]):
        return (
            None,
            first,
            "Overlapping first-event brackets cannot establish a strict order",
        )
    if any(
        row["root_bracket_tt"][0] <= bracket[1]
        for row in motion.get("ambiguous_boundary_contacts", [])
    ):
        return (
            None,
            first,
            "An ambiguous boundary event may overlap or precede the selected contact",
        )
    return (
        first["other"] == target,
        first,
        "First certain native longitude contact before lunar ingress, under the declared scan model; not a complete prohibition or historical separation test",
    )


def evaluate_lilly_conditions(
    states: dict[str, dict[str, Any]],
    querent: str,
    quesited: str,
    sect: str | None,
    phase: Phase,
    *,
    lunar_motion: dict[str, Any] | None,
    zodiac_type: str | None,
    event_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    principal = pair_reception(
        querent,
        states[querent]["longitude"],
        quesited,
        states[quesited]["longitude"],
        sect,
    )
    routes = []

    def add(
        mode: str,
        actors: list[str],
        conditions: list[dict[str, Any]],
        receipts: list[dict[str, Any]],
        **extra: Any,
    ) -> None:
        # Absence at the question epoch is not silently promoted to a verdict
        # about an uncomputed past or future dignity epoch.
        conditions.append(
            _condition(
                "required_event_epoch_reception_and_sequence",
                None,
                [110, 111, 125, 126],
                "Actual finite event roots and event-epoch receptions are listed separately in event_paths; the source timing interpretation and complete sequence criteria remain unverified here",
            )
        )
        conditions.append(
            _condition(
                "source_house_and_accidental_conditions",
                None,
                [125, 126, 127],
                "Full source-specific house, strength and judgement conditions remain unverified",
            )
        )
        routes.append(
            {
                "mode": mode,
                "actors": actors,
                "condition_epoch": "question_instant",
                "status": (
                    "nominal_condition_not_met"
                    if any(c["passed"] is False for c in conditions)
                    else "remaining_conditions_unverified"
                ),
                "conditions": conditions,
                "receptions": receipts,
                "full_path_accepted": False,
                **extra,
            }
        )

    if querent != quesited:
        direct = phase(states[querent], states[quesited])
        if direct and direct["phase"] == "applying":
            conditions = [
                _condition(
                    "instantaneous_principal_application",
                    True,
                    [125],
                    "Current longitude derivative, not proof of future perfection",
                )
            ]
            if direct["aspect"] in {"sextile", "trine", "square"}:
                own = [
                    dignity_at(p, states[p]["longitude"], sect)
                    for p in (querent, quesited)
                ]
                conditions.append(
                    _condition(
                        "both_principals_have_positive_dignity_now",
                        _both([_has_dignity(r) for r in own]),
                        [125],
                        "Positive essential dignity at question instant; debility is a separate condition",
                    )
                )
            if direct["aspect"] == "opposition":
                mutual_house = "rulership" in principal["mutual_same_kind"]
                conditions.append(
                    _condition(
                        "mutual_reception_by_domicile_now",
                        mutual_house,
                        [125],
                        "The p125 opposition case specifically calls for reciprocal houses, not one directional reception or arbitrary dignity",
                    )
                )
            add(
                "direct",
                [querent, quesited],
                conditions,
                principal["directions"],
                aspect=direct,
            )

        for third in LIGHT_WEIGHT_ORDER:
            if third in {querent, quesited}:
                continue
            current = states[third]
            to_a, to_b = phase(current, states[querent]), phase(
                current, states[quesited]
            )
            if not to_a or not to_b:
                continue
            weights = [LIGHT_WEIGHT_ORDER.index(p) for p in (querent, quesited)]
            third_weight = LIGHT_WEIGHT_ORDER.index(third)
            velocities = [states[p]["speed"] for p in (querent, quesited)]
            speed = current["speed"]
            if speed is None or any(v is None for v in velocities):
                continue
            separating = to_a["phase"] == "separating" and to_b["phase"] == "applying"
            reversed_separation = (
                to_b["phase"] == "separating" and to_a["phase"] == "applying"
            )
            if (
                third_weight > max(weights)
                and all(abs(speed) > abs(v) for v in velocities)
                and (separating or reversed_separation)
            ):
                source, target = (
                    (querent, quesited) if separating else (quesited, querent)
                )
                received = reception(
                    source,
                    third,
                    current["longitude"],
                    sect,
                    allowed=("rulership", "triplicity", "bound"),
                )
                conditions = [
                    _condition(
                        "source_receives_carrier_now_by_house_triplicity_or_term",
                        received["receives"],
                        [126],
                        "Direction is source receives carrier. Exaltation/face alone are not one of the three listed translation dignities",
                    ),
                    _condition(
                        "lighter_and_faster_carrier_now",
                        True,
                        [111],
                        "Traditional ponderosity and measured absolute speed are both checked",
                    ),
                    _condition(
                        "prior_principal_separation_history",
                        None,
                        [126],
                        "P126 first requires the two principals to have separated from each other by conjunction/sextile/trine; carrier/source separation is a distinct condition",
                    ),
                ]
                event = None
                if third == "Moon":
                    first, event, detail = _moon_next_target(target, lunar_motion)
                    conditions.append(
                        _condition(
                            "lunar_next_contact_is_recipient_in_search_window",
                            first,
                            [126],
                            detail,
                        )
                    )
                else:
                    conditions.append(
                        _condition(
                            "carrier_reaches_recipient_before_other_planets",
                            None,
                            [126],
                            "See event_paths for the actual non-lunar carrier sequence; this question-epoch record alone does not establish it",
                        )
                    )
                add(
                    "translation",
                    [source, third, target],
                    conditions,
                    [received],
                    source_planet=source,
                    target_planet=target,
                    carrier=third,
                    next_lunar_contact=event,
                )
            if (
                third_weight < min(weights)
                and all(abs(speed) < abs(v) for v in velocities)
                and all(row["phase"] == "applying" for row in (to_a, to_b))
            ):
                collection_receipts = [
                    reception(
                        endpoint, third, current["longitude"], sect, allowed=KINDS
                    )
                    for endpoint in (querent, quesited)
                ]
                conditions = [
                    _condition(
                        "both_endpoints_receive_collector_now",
                        _both([r["receives"] for r in collection_receipts]),
                        [126],
                        "Both endpoints receive the heavier collector at the collector's longitude, not the reverse direction",
                    ),
                    _condition(
                        "heavier_and_slower_collector_now",
                        True,
                        [111, 126],
                        "Traditional ponderosity and measured absolute speed are both checked",
                    ),
                    _condition(
                        "endpoints_do_not_behold_each_other",
                        None,
                        [126],
                        "The full historical behold/orb criterion is unverified; absence from the current product radius does not prove it",
                    ),
                ]
                add(
                    "collection",
                    [querent, quesited, third],
                    conditions,
                    collection_receipts,
                    collector=third,
                )
    mutual = principal["mutual"]
    reading = (
        "依第112页互纳规则，当前双向接纳提供成事支持；这是该条传统规则的条件性解读，不是全书判断或现实结果认证。"
        if mutual is True
        else (
            "当前未形成第112页所定义的双向接纳；这不排除其他原典路径。"
            if mutual is False
            else "当前资料不能核定第112页的双向接纳；同一星体不能构成双向关系，未知昼夜也不套默认值。"
        )
    )
    event_paths = evaluate_event_paths(
        event_history or {}, querent, quesited, sect, states, phase
    )
    return {
        "rule_id": RULESET,
        "chart_sect": sect,
        "coordinate_scope": (
            "tropical_selected_edition"
            if zodiac_type in {"Tropic", "Tropical"}
            else (
                "sidereal_extension_not_original_edition_acceptance"
                if zodiac_type == "Sidereal"
                else "unknown_or_unsupported_zodiac"
            )
        ),
        "principal_reception": principal,
        "p112_mutual_reception": {
            "premise_satisfied": mutual,
            "source_pages": [112],
            "conditional_reading_zh": reading,
            "full_judgement_accepted": False,
        },
        "routes": routes,
        "event_paths": event_paths,
        "p126_127_dwelling": dwelling_clause(
            states, querent, quesited, event_history or {}, event_paths, phase
        ),
        "same_body_not_bilateral": querent == quesited,
        "full_original_text_acceptance": False,
        "scope": "Selected pp104-105 and112 table/reception facts at question epoch; p125-126 conditions evaluated individually. Unknown event histories are not satisfied gates or a yes/no judgement",
    }
