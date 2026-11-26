"""Check hash-bound TZif indexing and the loaded-clock fallback."""

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
from fatebridge.utils.tzif_transitions import read_tzif_transitions

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "tests/data/bazi/tzif"
REFERENCE = json.loads((STUDY / "reference-first.json").read_text())


def serial(rows):
    return [
        [at.isoformat(), int(a.total_seconds()), int(b.total_seconds())]
        for at, a, b in rows
    ]


@pytest.mark.parametrize(
    "zone,wall,reason",
    [
        ("Africa/Monrovia", datetime(1972, 1, 7, 0, 44), "跳时区间"),
        ("Pacific/Kwajalein", datetime(1969, 9, 30, 1, 30), "重复区间"),
    ],
)
def test_standard_offset_changes_have_a_civil_clock_diagnostic(
    zone: str, wall, reason: str
) -> None:
    local = wall.replace(tzinfo=timezones.parse_timezone_name(zone))
    assert local.dst() == local.replace(fold=1).dst() == timedelta(0)
    with pytest.raises(ValueError, match=f"时区偏移变动造成的{reason}"):
        timezones.validate_local_clock(local)


def test_full597_explicit_tables_equal_frozen_stdlib_reference() -> None:
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
        index = read_tzif_transitions(data)
        assert index is not None
        assert index.seconds == tuple(record["transition_seconds"])


@pytest.mark.parametrize(
    "record", REFERENCE["exhaustive_days"], ids=lambda r: r["zone"]
)
def test_day_and_nine_day_events_equal_complete_original_scans(record) -> None:
    zone = timezones.parse_timezone_name(record["zone"])
    day = date.fromisoformat(record["day"])
    assert serial(_clock_changes_near_day(zone, day)) == record["near_changes"]
    assert (
        serial(_forward_changes_on_utc_day(zone, day))
        == record["daily_forward_changes"]
    )


def test_index_is_complete_for_every_registered_explicit_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The reference describes these frozen bytes, not a later installed IANA revision.
    monkeypatch.setattr(
        timezones,
        "_timezone_bytes",
        lambda key: (STUDY / "all-declared-tzif" / key).read_bytes(),
    )
    timezones._parse_timezone_name_cached.cache_clear()
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    checked = 0
    try:
        for key, record in REFERENCE["tables"].items():
            assert (
                hashlib.sha256(timezones._timezone_bytes(key)).hexdigest()
                == record["tzif_sha256"]
            )
            values = record["transition_seconds"]
            if not values:
                continue
            else:
                pass
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
    finally:
        timezones._parse_timezone_name_cached.cache_clear()


def test_index_scope_checks_endpoints_tail_rules_and_loaded_object_identity() -> None:
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
    assert timezones.timezone_transition_candidates(zone, future_low, future_high) == (
        datetime(2100, 3, 14, 7, tzinfo=timezone.utc),
    )
    assert timezones.timezone_transition_candidates(timezone.utc, low, high) is None
    assert (
        timezones.timezone_transition_candidates(
            timezones.parse_timezone_name("Etc/GMT"), low, high
        )
        == ()
    )
    recife = timezones.parse_timezone_name("America/Recife")
    last = datetime(2002, 2, 17, 2, tzinfo=timezone.utc)
    upper = last + timedelta(seconds=2)
    assert timezones.timezone_transition_candidates(
        recife, last - timedelta(microseconds=1), upper
    ) == (last,)
    assert timezones.timezone_transition_candidates(recife, last, upper) == ()


def test_footer_window_and_foreign_object_call_the_original_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_transition_index_uses_the_same_loaded_rules_without_a_second_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zone = timezones.parse_timezone_name("America/New_York")
    low, high = clock_scan_bounds(date(2020, 3, 8))
    expected = timezones.timezone_transition_candidates(zone, low, high)

    def fail_on_read(key):
        raise AssertionError("Loaded timezone rules must not reread TZif bytes")

    monkeypatch.setattr(timezones, "_timezone_bytes", fail_on_read)
    assert expected
    assert timezones.timezone_transition_candidates(zone, low, high) == expected
