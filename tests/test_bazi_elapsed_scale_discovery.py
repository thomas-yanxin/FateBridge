"""Do not conflate a known clock-scale difference with adopted calendar policy."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (ROOT / "tests/data/bazi/elapsed-scale-reference.json").read_text()
)


def test_all_frozen_positive_steps_and_both_sided_controls_are_retained():
    rows = REFERENCE["rows"]
    assert len(rows) == len({r["id"] for r in rows}) == 108
    counts = Counter(r["transition_utc"] for r in rows)
    assert len(counts) == 27 and set(counts.values()) == {4}
    assert Counter(r["kind"] for r in rows) == dict.fromkeys(
        ("cross_forward", "cross_reverse", "before", "after"), 27
    )
    assert REFERENCE["no_application_or_native_imports"] is True


def test_known_atomic_elapsed_intervals_are_derived_from_endpoint_offsets():
    for row in REFERENCE["rows"]:
        nominal = (
            datetime.fromisoformat(row["end_utc"])
            - datetime.fromisoformat(row["start_utc"])
        ).total_seconds()
        atomic = nominal + row["end_tai_minus_utc"] - row["start_tai_minus_utc"]
        assert row["nominal_utc_label_seconds"] == nominal
        assert row["uniform_atomic_elapsed_seconds"] == atomic
        assert (
            atomic
            == {"cross_forward": 3, "cross_reverse": -3, "before": 1, "after": 1}[
                row["kind"]
            ]
        )


def test_current_elapsed_helper_uses_nominal_labels_without_claiming_atomic_duration():
    from fatebridge.core.almanac import elapsed_days_between

    for row in REFERENCE["rows"]:
        start, end = (
            datetime.fromisoformat(row["start_utc"]),
            datetime.fromisoformat(row["end_utc"]),
        )
        assert (
            elapsed_days_between(start, end) * 86400 == row["nominal_utc_label_seconds"]
        )
