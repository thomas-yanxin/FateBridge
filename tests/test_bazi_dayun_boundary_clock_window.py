"""Analysis context must not hide known boundary-envelope witnesses."""

import gzip
import hashlib
import io
import json
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from dateutil.relativedelta import relativedelta

from fatebridge.core.output_timing import DayunBirthEventAnalysis
from fatebridge.services.dayun_boundary_clock_events import (
    forward_gaps_for_wall_image,
    projected_wall_image,
)

STUDY = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/bazi-dayun-boundary-clock-window-v1"
)


def frozen(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(path.read_bytes()))


def short_clock(delta, hour=1):
    # Two changes inside one hour, equal offsets at both scan endpoints.
    # Explicit TZif data makes coarse endpoint sampling fail observably.
    first = int(datetime(2020, 1, 1, hour, tzinfo=timezone.utc).timestamp())
    header = b"TZif\0" + b"\0" * 15 + struct.pack(">6l", 0, 0, 0, 2, 2, 8)
    data = header + struct.pack(">2l", first, first + 1800) + bytes((1, 0))
    data += struct.pack(">lBB", 0, 0, 0) + struct.pack(">lBB", delta, 1, 4)
    return ZoneInfo.from_file(io.BytesIO(data + b"STD\0DST\0"), key="same-clock-key")


def test_scan_preserves_multiple_changes_and_loaded_object_identity():
    hour, half = short_clock(3600), short_clock(1800)
    low, high = datetime(2020, 1, 1, 1, 15), datetime(2020, 1, 1, 2, 15)
    gaps, start, end = forward_gaps_for_wall_image(hour, low, high)
    other, _, _ = forward_gaps_for_wall_image(half, low, high)
    assert hour.utcoffset(start) == hour.utcoffset(end) == timedelta(0)
    assert len(gaps) == len(other) == 1
    assert gaps[0].upper_wall == datetime(2020, 1, 1, 2)
    assert other[0].upper_wall == datetime(2020, 1, 1, 1, 30)
    assert forward_gaps_for_wall_image(hour, low, high)[0] is gaps


def test_scan_filters_gap_ends_outside_the_image_and_handles_fixed_offsets():
    low, high = datetime(2020, 1, 1, 2, 1), datetime(2020, 1, 1, 2, 15)
    assert forward_gaps_for_wall_image(short_clock(3600), low, high)[0] == ()
    assert (
        forward_gaps_for_wall_image(timezone(timedelta(hours=14)), low, high)[0] == ()
    )
    with pytest.raises(OverflowError):
        forward_gaps_for_wall_image(short_clock(3600), datetime.min, datetime.min)
    with pytest.raises(ValueError):
        forward_gaps_for_wall_image(short_clock(3600), high, low)


def test_day_cache_preserves_a_transition_exactly_at_utc_midnight():
    low, high = datetime(2020, 1, 1, 0, 45), datetime(2020, 1, 1, 1, 15)
    gaps, _, _ = forward_gaps_for_wall_image(short_clock(3600, hour=0), low, high)
    assert len(gaps) == 1
    assert gaps[0].instant_utc == datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_projected_image_keeps_both_sides_of_backward_leap_clipping():
    low = datetime(2000, 2, 28, 23, 59, 59, 900000)
    high = datetime(2000, 2, 29, 0, 0, 0, 100000)
    a, b = projected_wall_image(low, high, 10)
    assert a == datetime(2010, 2, 28)
    assert b == datetime(2010, 2, 28, 23, 59, 59, 999999)
    assert a < min(low + relativedelta(years=10), high + relativedelta(years=10))
    assert b > max(low + relativedelta(years=10), high + relativedelta(years=10))


def test_projected_image_contains_dense_calendar_probes_over_full_cycle():
    for year in range(1900, 2300):
        low = datetime(year, 2, 28, 23, 59)
        high = datetime(year, 3, 1, 0, 1)
        probes = [low, high, datetime(year, 3, 1) - timedelta(microseconds=1)]
        for index in range(13):
            a, b = projected_wall_image(low, high, index * 10)
            assert all(
                a <= point + relativedelta(years=index * 10) <= b for point in probes
            )


def test_registered_reference_and_original_failures_are_preserved():
    reference = frozen("reference-first.json.gz")
    replay = frozen("reference-formatted-replay.json.gz")
    reference.pop("collector_sha256")
    replay.pop("collector_sha256")
    assert reference == replay
    assert reference["control_count"] == 34 and reference["context_count"] == 102
    assert len(reference["all_original_unknowns"]) == 782
    baseline = frozen("baseline-second.json.gz")
    assert baseline["counts"]["same_root_safe_envelope_failure_contexts"] == 48
    assert baseline["counts"]["controls_with_numeric_failure"] == 0
    assert baseline["counts"]["controls_with_context_dependent_envelopes"] == 24


def test_complete_candidate_retains_all_same_root_witnesses_and_schema():
    baseline = frozen("baseline-second.json.gz")
    candidate = frozen("candidate-first.json.gz")
    assert candidate["counts"]["contexts"] == 102
    assert candidate["counts"]["same_root_safe_envelope_failure_contexts"] == 0
    assert candidate["counts"]["controls_with_numeric_failure"] == 0
    assert candidate["counts"]["missing_safe_witness_state_contexts"] == 0
    assert (
        candidate["original_unknowns_retained"]
        == baseline["original_unknowns_retained"]
    )
    for old, new in zip(baseline["records"], candidate["records"]):
        assert old["id"] == new["id"]
        assert old["observations"] == new["observations"]
        for before, after in zip(old["contexts"], new["contexts"]):
            result = after["actual_range"]
            DayunBirthEventAnalysis.model_validate(result["dayun_event_analysis"])
            assert result["sample_count"] == before["actual_range"]["sample_count"] == 3
            assert (
                result["dayun_event_analysis"]["boundary_clock_scan"]["boundary_count"]
                == 13
            )
            assert (
                result["dayun_event_analysis"]["continuous_completeness_certified"]
                is False
            )
            original = before["actual_range"]["dayun_boundary_ranges"]
            updated = result["dayun_boundary_ranges"]
            for a, b in zip(original, updated):
                for field in ("start", "end"):
                    assert datetime.fromisoformat(
                        b[f"earliest_{field}_at"]
                    ) <= datetime.fromisoformat(a[f"earliest_{field}_at"])
                    assert datetime.fromisoformat(
                        b[f"latest_{field}_at"]
                    ) >= datetime.fromisoformat(a[f"latest_{field}_at"])


def test_daily_cache_candidate_reproduces_every_first_candidate_record():
    original = frozen("candidate-first.json.gz")
    cached = frozen("candidate-day-cache-second.json.gz")
    assert cached["records"] == original["records"]
    assert cached["counts"] == original["counts"]
    assert (
        cached["original_unknowns_retained"] == original["original_unknowns_retained"]
    )
