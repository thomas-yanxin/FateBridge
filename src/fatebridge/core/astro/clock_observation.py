"""Optional observations of completed clock conversions, without extra calls.

Observers belong to the current calculation context. Supplied observations are
replay witnesses, not authenticated native executions or measured Earth rotation.
"""

from contextvars import ContextVar
from typing import Any, Callable

observer: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "clock_conversion_observer", default=None
)


def observe_clock(kind: str, **values: Any) -> None:
    callback = observer.get()
    if callback is not None:
        callback({"kind": kind, **values})
