"""Preserve the established gap-forward policy for every reference gap size."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.timezones import parse_timezone_name

ROWS = json.loads(
    (Path(__file__).parent / "data/bazi/dayun-gap-inputs.json").read_text()
)["rows"]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["zone"])
def test_every_registered_gap_magnitude_keeps_forward_resolution(row, monkeypatch):
    gap = row["source_after_offset_seconds"] - row["source_before_offset_seconds"]
    wall = datetime.fromisoformat(row["wall"]).replace(tzinfo=timezone.utc)
    birth_utc = wall - timedelta(seconds=gap + row["source_before_offset_seconds"])
    expected = wall + timedelta(seconds=gap - row["source_after_offset_seconds"])
    birth = birth_utc.astimezone(parse_timezone_name(row["zone"]))
    # Only the nominal age offset is synthetic. Actual offset changes and
    # expected UTC instants use the previously compiled official IANA source.
    details = {
        "elapsed_seconds": gap / 120,
        "start_age_unrounded": gap / 120 / 86400 / 3,
        "year_stem": "甲",
    }
    monkeypatch.setattr(
        TimingAnalysis,
        "calculate_dayun_start_details",
        staticmethod(lambda *args: details),
    )
    current = TimingAnalysis.calculate_dayun_timeline(
        birth, "女", ("丙", "寅"), row["zone"], periods=3
    )
    assert (
        datetime.fromisoformat(current["start_at"]).astimezone(timezone.utc) == expected
    )
    assert current["dst_policy"] == "fold_0_gap_forward"
