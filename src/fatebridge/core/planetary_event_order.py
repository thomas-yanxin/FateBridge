"""Adjacent contacts in a finite planetary history, independent of array order.

Closed root brackets, boundary contacts and unresolved intervals retain unknown
order. Representative instants never break a tie between physical roots.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from typing_extensions import NotRequired


class EventBodies(TypedDict):
    bodies: list[str]


class PlanetaryEventRecord(EventBodies):
    kind: str
    julian_day_tt: float
    root_bracket_tt: list[float]
    epoch_relation: str
    states: dict[str, dict[str, float]]
    state_brackets: dict[str, list[dict[str, float]]]
    topology: NotRequired[str]
    ray_degrees: NotRequired[int]
    direction: NotRequired[int]
    aspect: NotRequired[str]
    datetime_utc: NotRequired[str | None]


def event_involves(event: EventBodies, a: str, b: str | None = None) -> bool:
    return a in event["bodies"] and (b is None or b in event["bodies"])


def ordered_contact(
    events: Sequence[PlanetaryEventRecord],
    unresolved_intervals: Sequence[EventBodies],
    a: str,
    b: str | None = None,
    *,
    past: bool = False,
) -> tuple[PlanetaryEventRecord | None, bool | None]:
    """Return the last past or first future crossing and its ordering status.

    Select a candidate by its root bracket, never a representative instant or
    array position. Overlapping candidates keep unknown order; a disclosed
    candidate is not a certified last/next role until its order is established.
    """
    side = "past" if past else "future"
    rows = [
        e
        for e in events
        if e["kind"] == "contact"
        and e.get("topology") == "crossing"
        and e["epoch_relation"] == side
        and event_involves(e, a, b)
    ]
    if not rows:
        return None, None
    row = (max if past else min)(rows, key=lambda e: e["root_bracket_tt"][0])
    bracket = row["root_bracket_tt"]
    obstacles = [
        e
        for e in events
        if e["kind"] == "contact"
        and e is not row
        and event_involves(e, a, b)
        and e["root_bracket_tt"][0] <= bracket[1]
        and bracket[0] <= e["root_bracket_tt"][1]
    ]
    if (
        any(
            e["epoch_relation"] == "question_boundary" and event_involves(e, a, b)
            for e in events
            if e["kind"] == "contact"
        )
        or obstacles
        or any(
            e["kind"] == "contact"
            and e.get("topology") != "crossing"
            and e["epoch_relation"] == side
            and event_involves(e, a, b)
            and (
                e["root_bracket_tt"][1] >= bracket[0]
                if past
                else e["root_bracket_tt"][0] <= bracket[1]
            )
            for e in events
        )
        or any(a in u["bodies"] for u in unresolved_intervals)
    ):
        return row, None
    return row, True
