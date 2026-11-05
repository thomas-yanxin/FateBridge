"""Regression: default "current moment" must not drift with the server's clock.

Bare ``datetime.now()`` reads the *server* timezone, so a UTC-deployed host
resolves the wrong calendar date for callers who omit an explicit
year/month/day — most visibly the 流年 year near the New Year / 立春 boundary.
``current_local_datetime`` anchors the default to a fixed civil timezone
(Asia/Shanghai) so the resolution is deterministic wherever the process runs.
"""

from datetime import datetime, timezone

import pytest
from dateutil import tz as dateutil_tz

import fatebridge.core.almanac as almanac
from fatebridge.core.almanac import DEFAULT_TIMEZONE, current_local_datetime


@pytest.fixture(
    params=[
        "2026-12-31T23:59:58+00:00",
        "2026-03-08T06:59:59+00:00",
        "2026-03-08T07:00:00+00:00",
    ]
)
def frozen_now(monkeypatch, request):
    instant = datetime.fromisoformat(request.param)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # Model a UTC server even when the developer's machine uses Shanghai.
            if tz is None:
                return instant.replace(tzinfo=None)
            return instant.astimezone(tz)

    monkeypatch.setattr(almanac, "datetime", FrozenDatetime)
    return instant


def test_returns_naive_datetime() -> None:
    """Downstream code decomposes this into naive year/month/day; keep it naive
    so it never mixes with the aware datetimes elsewhere (TypeError)."""
    assert current_local_datetime().tzinfo is None


def test_anchored_to_default_timezone_not_server_clock(frozen_now) -> None:
    """The wall-clock must equal UTC-now projected into Asia/Shanghai, proving
    it is anchored to the civil timezone rather than the process's local TZ.

    Against the old ``datetime.now()`` this assertion fails on any non-Shanghai
    server; against the helper it holds regardless of where the test runs.
    """
    shanghai = dateutil_tz.gettz(DEFAULT_TIMEZONE)
    reference = frozen_now.astimezone(shanghai).replace(tzinfo=None)
    got = current_local_datetime()
    assert got == reference


@pytest.mark.parametrize("timezone_name", ["UTC", "America/New_York"])
def test_honours_explicit_timezone(frozen_now, timezone_name) -> None:
    """An explicit timezone overrides the default so callers that already carry
    an analysis timezone (e.g. the subject's birth timezone) stay consistent."""
    got = current_local_datetime(timezone_name)
    zone = timezone.utc if timezone_name == "UTC" else dateutil_tz.gettz(timezone_name)
    reference = frozen_now.astimezone(zone).replace(tzinfo=None)
    assert got == reference
