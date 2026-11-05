"""Freeze the current execution clock to one timezone-aware instant."""

from contextlib import contextmanager
from datetime import datetime, timezone, tzinfo
from typing import Iterator
from unittest.mock import patch

FROZEN_NOW = datetime(2026, 1, 1, 4, tzinfo=timezone.utc)


@contextmanager
def freeze_clock(frozen: datetime = FROZEN_NOW) -> Iterator[None]:
    if frozen.tzinfo is None:
        raise ValueError("The test clock requires a timezone-aware instant")

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return (
                frozen.astimezone(tz) if tz is not None else frozen.replace(tzinfo=None)
            )

    with patch("fatebridge.core.execution_context.datetime", FrozenDatetime):
        yield
