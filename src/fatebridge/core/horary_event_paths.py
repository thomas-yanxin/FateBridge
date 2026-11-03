"""Lilly event-sequence conditions, distinct from complete house judgement.

P126's principal/principal prior separation and carrier/source prior separation
are two different facts. Reception receipts preserve the actual guest longitude
at each event; the radical chart's sect is held fixed and disclosed.
"""

from __future__ import annotations

from typing import Any, Callable

from fatebridge.core.classical_western import LIGHT_WEIGHT_ORDER
from fatebridge.core.lilly import KINDS, reception


def _condition(
    code: str, passed: bool | None, pages: list[int], detail: str
) -> dict[str, Any]:
    return dict(
        code=code,
        passed=passed,
        source_pages=pages,
        detail=detail,
        status=(
            "unverified"
            if passed is None
            else "satisfied" if passed else "not_satisfied"
        ),
    )


def evaluate_event_paths(
    history: dict[str, Any],
    querent: str,
    quesited: str,
    sect: str | None,
    states: dict[str, dict[str, Any]],
    phase: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unavailable",
        "paths": [],
        "refranation_patterns": [],
        "prohibition_patterns": [],
        "full_original_text_acceptance": False,
        "reception_epoch_policy": "Guest longitude at the named physical event, radical/question-chart sect held fixed; reception at question instant remains separate. Historical source timing interpretation is not independently certified.",
        "source_pages": [110, 111, 125, 126],
        "scope": "Actual roots under the disclosed finite scan. Missing events outside its window, full prohibition variants, houses, accidental strengths and complete judgement remain open.",
    }
    if (
        history.get("status") != "computed"
        or history.get("constant_velocity_projection") is not False
    ):
        result["unavailable_reason"] = history.get(
            "unavailable_reason", "Native event history unavailable"
        )
        return result
    if querent == quesited:
        result["status"] = "same_body_insufficient"
        return result
    result["status"] = "computed_conditions"
    events = history["events"]
    # A tangent, overlap with the question epoch, or a continuous exact interval
    # cannot be ordered by midpoint or alphabetical tie-breaking.
    contacts = [
        e for e in events if e["kind"] == "contact" and e.get("topology") == "crossing"
    ]

    def related(event: dict[str, Any], a: str, b: str | None = None) -> bool:
        return a in event["bodies"] and (b is None or b in event["bodies"])

    def first_for(
        a: str, b: str | None = None, *, past: bool = False
    ) -> tuple[dict[str, Any] | None, bool | None]:
        side = "past" if past else "future"
        rows = [e for e in contacts if e["epoch_relation"] == side and related(e, a, b)]
        if not rows:
            return None, None
        row = rows[-1] if past else rows[0]
        bracket = row["root_bracket_tt"]
        obstacles = [
            e
            for e in events
            if e["kind"] == "contact"
            and e is not row
            and related(e, a, b)
            and e["root_bracket_tt"][0] <= bracket[1]
            and bracket[0] <= e["root_bracket_tt"][1]
        ]
        if (
            any(
                e["epoch_relation"] == "question_boundary" and related(e, a, b)
                for e in events
                if e["kind"] == "contact"
            )
            or obstacles
            or any(
                e["kind"] == "contact"
                and e.get("topology") != "crossing"
                and e["epoch_relation"] == side
                and related(e, a, b)
                and (
                    e["root_bracket_tt"][1] >= bracket[0]
                    if past
                    else e["root_bracket_tt"][0] <= bracket[1]
                )
                for e in events
            )
            or any(a in u["bodies"] for u in history.get("unresolved_intervals", []))
        ):
            return row, None
        return row, True

    def receipt(
        receiver: str,
        guest: str,
        event: dict[str, Any],
        allowed: tuple[str, ...] = KINDS,
    ) -> dict[str, Any]:
        central = reception(
            receiver, guest, event["states"][guest]["longitude"], sect, allowed=allowed
        )
        endpoints = [
            reception(receiver, guest, s["longitude"], sect, allowed=allowed)
            for s in event["state_brackets"][guest]
        ]
        uncertain = any(
            any(
                r[k] != central[k]
                for k in ("receives", "dignities", "unknown_dignities")
            )
            for r in endpoints
        )
        if any(r["receives"] != central["receives"] for r in endpoints):
            central = {**central, "receives": None}
        return {
            "julian_day_tt": event["julian_day_tt"],
            "root_bracket_tt": event["root_bracket_tt"],
            "chart_sect": sect,
            "reception": central,
            "endpoint_receptions": endpoints,
            "boundary_uncertainty": uncertain,
        }

    def add(
        mode: str,
        actors: list[str],
        conditions: list[dict[str, Any]],
        event_receipts: list[dict[str, Any]],
        **facts: Any,
    ) -> None:
        values = [c["passed"] for c in conditions]
        accepted = False if False in values else None if None in values else True
        result["paths"].append(
            {
                "mode": mode,
                "actors": actors,
                "conditions": conditions,
                "sequence_conditions_satisfied": accepted,
                "status": (
                    "sequence_condition_not_met"
                    if accepted is False
                    else (
                        "sequence_conditions_unverified"
                        if accepted is None
                        else "nominal_source_sequence_satisfied"
                    )
                ),
                "event_receptions": event_receipts,
                "full_path_accepted": False,
                **facts,
            }
        )

    prior, prior_order = first_for(querent, quesited, past=True)
    future, future_order = first_for(querent, quesited)
    direct = phase(states[querent], states[quesited])
    transitions = [
        e
        for e in events
        if e["kind"] in {"station", "ingress"}
        and e["epoch_relation"] == "future"
        and any(p in e["bodies"] for p in (querent, quesited))
        and (future is None or e["root_bracket_tt"][0] <= future["root_bracket_tt"][1])
    ]
    intervention = [
        e
        for e in contacts
        if e["epoch_relation"] == "future"
        and len(set(e["bodies"]) & {querent, quesited}) == 1
        and (future is None or e["root_bracket_tt"][0] <= future["root_bracket_tt"][1])
    ]
    velocities = [states[p]["speed"] for p in (querent, quesited)]
    if (
        direct
        and direct["phase"] == "applying"
        and direct["aspect"] == "conjunction"
        and all(v is not None and v > 0 for v in velocities)
        and velocities[0] != velocities[1]
    ):
        applicant, recipient = sorted(
            (querent, quesited), key=lambda p: states[p]["speed"], reverse=True
        )
        for event in transitions:
            if (
                event["kind"] == "station"
                and event["bodies"] == [applicant]
                and event["direction"] < 0
            ):
                # The recipient must still move forward when the applicant
                # reverses (p111). Overlapping closed root brackets, including
                # a station touching the question epoch, cannot establish this
                # by sorting their rounded representative instants.
                recipient_reversal_may_precede = any(
                    e["kind"] == "station"
                    and e["bodies"] == [recipient]
                    and e["epoch_relation"] in {"future", "question_boundary"}
                    and e["root_bracket_tt"][0] <= event["root_bracket_tt"][1]
                    for e in events
                )
                if not recipient_reversal_may_precede and (
                    future is None
                    or event["root_bracket_tt"][1] < future["root_bracket_tt"][0]
                ):
                    result["refranation_patterns"].append(
                        {
                            "applicant": applicant,
                            "recipient": recipient,
                            "station": event,
                            "source_pages": [111],
                            "scope": "Prograde applicant turns retrograde before first principal contact in this window; recipient has no observed reversal before it. Not an assertion about all later contacts.",
                        }
                    )
        if future and future["aspect"] == "conjunction":
            for third in LIGHT_WEIGHT_ORDER:
                speed = states[third]["speed"]
                if (
                    third in {querent, quesited}
                    or speed is None
                    or speed <= states[applicant]["speed"]
                ):
                    continue
                for a in intervention:
                    if not related(a, third, applicant):
                        continue
                    for b in intervention:
                        if (
                            related(b, third, recipient)
                            and a["aspect"] == b["aspect"]
                            and a["root_bracket_tt"][1] < b["root_bracket_tt"][0]
                            and b["root_bracket_tt"][1] < future["root_bracket_tt"][0]
                            and all(
                                e["states"][p]["speed"] > 0
                                for e in (a, b)
                                for p in e["bodies"]
                            )
                            and a["states"][third]["speed"]
                            > a["states"][applicant]["speed"]
                            and b["states"][third]["speed"]
                            > b["states"][recipient]["speed"]
                        ):
                            result["prohibition_patterns"].append(
                                {
                                    "interposer": third,
                                    "applicant": applicant,
                                    "recipient": recipient,
                                    "first_contact": a,
                                    "second_contact": b,
                                    "source_pages": [110, 111],
                                    "scope": "Selected p111 prograde overtaking pattern: same body/ray type reaches applicant then recipient before their conjunction. Other prohibition variants remain unverified.",
                                }
                            )
    add(
        "direct",
        [querent, quesited],
        [
            _condition(
                "nominal_application_at_question",
                None if direct is None else direct["phase"] == "applying",
                [125],
                "Question geometry remains separate from actual future roots",
            ),
            _condition(
                "first_future_principal_contact_in_window",
                future_order,
                [125],
                "No event in a finite window is unknown, not proof that perfection can never occur",
            ),
            _condition(
                "same_aspect_at_nominal_application_and_future_contact",
                (
                    None
                    if direct is None or future is None
                    else direct["aspect"] == future["aspect"]
                ),
                [125],
                "A later different ray is not completion of the current application",
            ),
            _condition(
                "no_selected_refranation_pattern",
                False if result["refranation_patterns"] else None,
                [111, 125],
                "Positive reversal evidence can refute this route; absence does not certify all source variants",
            ),
            _condition(
                "no_selected_prohibition_pattern",
                False if result["prohibition_patterns"] else None,
                [110, 111, 125],
                "Selected p111 pattern only; other intervening events are exposed, not silently classified as prohibition",
            ),
        ],
        (
            [
                receipt(a, b, future)
                for a, b in ((querent, quesited), (quesited, querent))
            ]
            if future
            else []
        ),
        prior_principal_contact=prior,
        future_contact=future,
        transitions=transitions,
        intervening_contacts=intervention,
    )

    for carrier in LIGHT_WEIGHT_ORDER:
        if carrier in {querent, quesited}:
            continue
        latest, latest_order = first_for(carrier, past=True)
        earliest, earliest_order = first_for(carrier)
        for source, target in ((querent, quesited), (quesited, querent)):
            last, last_order = first_for(carrier, source, past=True)
            following, following_order = first_for(carrier, target)
            if last is None or following is None or latest is None or earliest is None:
                continue
            if (
                last["root_bracket_tt"][1] < latest["root_bracket_tt"][0]
                or earliest["root_bracket_tt"][1] < following["root_bracket_tt"][0]
            ):
                continue
            if latest is not last or latest_order is None:
                last_order = None
            if earliest is not following or earliest_order is None:
                following_order = None
            speed = states[carrier]["speed"]
            lighter = LIGHT_WEIGHT_ORDER.index(carrier) > max(
                LIGHT_WEIGHT_ORDER.index(p) for p in (source, target)
            )
            faster = (
                None
                if speed is None or any(v is None for v in velocities)
                else all(abs(speed) > abs(v) for v in velocities)
            )
            received = receipt(
                source, carrier, last, ("rulership", "triplicity", "bound")
            )
            now = phase(states[carrier], states[source])
            add(
                "translation",
                [source, carrier, target],
                [
                    _condition(
                        "principals_previously_separated_by_conjunction_sextile_or_trine",
                        (
                            None
                            if prior is None or prior_order is None
                            else prior["aspect"] in {"conjunction", "sextile", "trine"}
                        ),
                        [125, 126],
                        "This is the principal/principal contact, not the carrier/source contact; finite history and source orb recency remain explicit",
                    ),
                    _condition(
                        "principals_separating_from_prior_ray_at_question",
                        (
                            None
                            if direct is None
                            else (
                                False
                                if direct["phase"] != "separating"
                                else (
                                    None
                                    if prior is None
                                    else direct["aspect"] == prior["aspect"]
                                )
                            )
                        ),
                        [126],
                        "Principal separation is checked independently of the carrier's separating phase; selected p107 orb column and declared equality convention apply; the complete historical recency criterion remains open",
                    ),
                    _condition(
                        "carrier_last_contact_is_source",
                        last_order,
                        [111, 126],
                        "Last actual carrier contact before question, with strict nonoverlapping brackets",
                    ),
                    _condition(
                        "carrier_separating_from_source_at_question",
                        None if now is None else now["phase"] == "separating",
                        [111],
                        "Selected p107 column and instantaneous phase are declared; complete historical translation remains unverified",
                    ),
                    _condition(
                        "lighter_carrier",
                        lighter,
                        [111],
                        "Traditional ponderosity ordering",
                    ),
                    _condition(
                        "faster_carrier_at_question",
                        faster,
                        [111],
                        "Measured absolute longitude speeds, not invented default speeds",
                    ),
                    _condition(
                        "source_receives_carrier_at_prior_contact",
                        received["reception"]["receives"],
                        [126],
                        "Event guest degree, direction source receives carrier, allowed house/triplicity/term; question sect fixed",
                    ),
                    _condition(
                        "carrier_next_contact_is_recipient_before_other_planets",
                        following_order,
                        [126],
                        "Next actual carrier contact among all seven planets, including non-lunar carriers",
                    ),
                ],
                [received, receipt(target, carrier, following)],
                prior_principal_contact=prior,
                prior_carrier_contact=last,
                future_contact=following,
            )
    for collector in LIGHT_WEIGHT_ORDER:
        if collector in {querent, quesited} or LIGHT_WEIGHT_ORDER.index(
            collector
        ) >= min(LIGHT_WEIGHT_ORDER.index(p) for p in (querent, quesited)):
            continue
        a, order_a = first_for(querent, collector)
        b, order_b = first_for(quesited, collector)
        if a is None or b is None:
            continue
        receipts = [receipt(querent, collector, a), receipt(quesited, collector, b)]
        add(
            "collection",
            [querent, quesited, collector],
            [
                _condition(
                    "both_future_collector_contacts_computed",
                    None if None in (order_a, order_b) else True,
                    [111, 126],
                    "Each endpoint's actual first contact with collector is listed, at separate epochs",
                ),
                _condition(
                    "first_endpoint_receives_collector_at_its_contact",
                    receipts[0]["reception"]["receives"],
                    [126],
                    "Direction endpoint receives collector, evaluated at that contact's guest degree",
                ),
                _condition(
                    "second_endpoint_receives_collector_at_its_contact",
                    receipts[1]["reception"]["receives"],
                    [126],
                    "Reception of the first event cannot stand in for the second event",
                ),
                _condition(
                    "endpoints_do_not_behold_each_other_source_criterion",
                    None,
                    [126],
                    "Original behold/orb and house conditions require further source adjudication",
                ),
            ],
            receipts,
            collection_contacts=[a, b],
        )
    return result
