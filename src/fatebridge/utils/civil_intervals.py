"""UTC preimages of local clock intervals, including gaps and repeated clocks.

The caller's existing wall-clock membership rule is preserved. In particular,
choosing the earliest start and latest end would incorrectly fill holes when a
rollback crosses a day boundary. Only public PEP495/zoneinfo operations are used;
no TZif oracle, private timezone API or transition sampling enters production.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

METHOD_ID = "local_wall_interval_preimage_v1"
UTC = timezone.utc
MICROSECOND = timedelta(microseconds=1)


def _boundary_points(wall: datetime, zone: tzinfo) -> set[datetime]:
    points = {wall.replace(tzinfo=zone, fold=fold).astimezone(UTC) for fold in (0, 1)}
    if len(points) == 1:
        return points
    low, high = sorted(points)
    old = low.astimezone(zone).utcoffset()
    if old == high.astimezone(zone).utcoffset():
        raise ValueError("Local fold mappings do not bracket an offset transition")
    # In both a gap and a fold the two mappings bracket the actual transition.
    # UTC arithmetic keeps repeated local clocks distinct, down to datetime's
    # microsecond resolution; a root tolerance is not a physical clock accuracy.
    while high - low > MICROSECOND:
        middle = low + (high - low) // 2
        if middle.astimezone(zone).utcoffset() == old:
            low = middle
        else:
            high = middle
    points.add(high)
    return points


def local_interval_preimages(
    start: datetime, end: datetime, zone: tzinfo
) -> list[tuple[datetime, datetime]]:
    """Return all UTC components whose local clock is in [start, end).

    Inputs are naive local bounds and a named ZoneInfo or fixed offset. The
    bounds themselves need not exist. Returned endpoints are real UTC instants;
    their local spelling can jump over a missing bound or repeat with a fold.
    """
    if start.tzinfo is not None or end.tzinfo is not None or end <= start:
        raise ValueError("Local interval requires ordered naive clock bounds")
    if not isinstance(zone, (ZoneInfo, timezone)):
        raise ValueError("Local intervals require ZoneInfo or a fixed UTC offset")
    points = sorted(_boundary_points(start, zone) | _boundary_points(end, zone))
    result: list[tuple[datetime, datetime]] = []
    for low, high in zip(points, points[1:]):
        middle = low + (high - low) // 2
        clock = middle.astimezone(zone).replace(tzinfo=None)
        if not start <= clock < end:
            continue
        if result and result[-1][1] == low:
            result[-1] = result[-1][0], high
        else:
            result.append((low, high))
    return result
