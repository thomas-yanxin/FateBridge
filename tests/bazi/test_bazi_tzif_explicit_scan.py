"""Index only hash-bound explicit TZif periods; preserve full-scan fallback."""

import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.services.dayun_boundary_clock_events import (
    _forward_changes_on_utc_day,
)
from fatebridge.utils import timezones
from fatebridge.utils.clock_events import _clock_changes_near_day, clock_scan_bounds
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.tzif_transitions import explicit_transition_seconds

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "tests/data/bazi/tzif"
REFERENCE = json.loads((STUDY / "reference-first.json").read_text())


def serial(rows):
    return [
        [at.isoformat(), int(a.total_seconds()), int(b.total_seconds())]
        for at, a, b in rows
    ]


def test_full597_explicit_tables_equal_frozen_stdlib_reference():
    path = STUDY / "reference-first.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == (STUDY / "reference-first.sha256").read_text().strip()
    )
    assert len(REFERENCE["tables"]) == 597
    assert REFERENCE["no_fatebridge_imports"] is True
    for key, record in REFERENCE["tables"].items():
        data = (STUDY / "all-declared-tzif" / key).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["tzif_sha256"]
        assert explicit_transition_seconds(data) == tuple(record["transition_seconds"])


@pytest.mark.parametrize(
    "record", REFERENCE["exhaustive_days"], ids=lambda r: r["zone"]
)
def test_day_and_nine_day_events_equal_complete_original_scans(record):
    zone = timezones.parse_timezone_name(record["zone"])
    day = date.fromisoformat(record["day"])
    assert serial(_clock_changes_near_day(zone, day)) == record["near_changes"]
    assert (
        serial(_forward_changes_on_utc_day(zone, day))
        == record["daily_forward_changes"]
    )


def test_index_is_complete_for_every_registered_explicit_transition():
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    checked = 0
    for key, record in REFERENCE["tables"].items():
        values = record["transition_seconds"]
        if not values:
            continue
        zone = timezones.parse_timezone_name(key)
        # No intermediate cache parsing: even near cache capacity the exact
        # loaded object is kept. Each candidate is checked on both sides.
        for value in values:
            try:
                at = epoch + timedelta(seconds=value)
                before = at - timedelta(microseconds=1)
            except OverflowError:
                continue
            candidates = timezones.timezone_transition_candidates(zone, before, at)
            assert candidates == (at,), (key, value)
            assert before.astimezone(zone).utcoffset() is not None
            assert at.astimezone(zone).utcoffset() is not None
            checked += 1
    assert checked > 30000


def test_bounds_and_loaded_object_identity_never_infer_footer_or_foreign_data():
    key = "America/New_York"
    zone = timezones.parse_timezone_name(key)
    low, high = clock_scan_bounds(date(2020, 3, 8))
    values = timezones.timezone_transition_candidates(zone, low, high)
    assert values == (datetime(2020, 3, 8, 7, tzinfo=timezone.utc),)
    assert timezones.timezone_transition_candidates(zone, values[0], high) == ()
    assert timezones.timezone_transition_candidates(zone, low, values[0]) == values
    foreign = ZoneInfo.from_file(
        io.BytesIO((STUDY / "all-declared-tzif" / key).read_bytes()), key=key
    )
    assert timezones.timezone_transition_candidates(foreign, low, high) is None
    future_low, future_high = clock_scan_bounds(date(2100, 3, 14))
    assert (
        timezones.timezone_transition_candidates(zone, future_low, future_high) is None
    )
    assert timezones.timezone_transition_candidates(timezone.utc, low, high) is None
    assert (
        timezones.timezone_transition_candidates(
            timezones.parse_timezone_name("Etc/GMT"), low, high
        )
        is None
    )


def test_footer_window_and_foreign_object_call_the_original_scanner(monkeypatch):
    # Force exactly the production fallback branch, with a counting tzinfo
    # facade. This detects accidental coarser endpoint sampling.
    from datetime import tzinfo

    class Counted(tzinfo):
        calls = 0

        def utcoffset(self, moment):
            self.calls += 1
            return timedelta(0)

        def dst(self, moment):
            return timedelta(0)

    zone = Counted()
    day = date(2020, 1, 1)
    _forward_changes_on_utc_day.cache_clear()
    assert _forward_changes_on_utc_day(zone, day) == ()
    assert zone.calls >= 86401


def test_current_rules_drift_still_fails_before_index_use(monkeypatch):
    zone = timezones.parse_timezone_name("America/New_York")
    low, high = clock_scan_bounds(date(2020, 3, 8))
    original = timezones._timezone_bytes
    monkeypatch.setattr(
        timezones, "_timezone_bytes", lambda key: original(key) + b"changed"
    )
    with pytest.raises(EphemerisSourceError) as error:
        timezones.timezone_transition_candidates(zone, low, high)
    assert error.value.reason == "timezone_rules_changed"
