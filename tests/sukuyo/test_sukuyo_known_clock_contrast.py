"""Known clock is a point; an unknown local date retains every support branch."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence

FIXTURE = Path(__file__).parents[1] / "data/sukuyo-known-vs-unknown-before-c-v78.json"
RAW = FIXTURE.read_bytes()
REF = json.loads(RAW)


def test_known_point_and_unknown_date_match_the_independent_reference():
    assert (
        hashlib.sha256(RAW).hexdigest()
        == "5edf34f4916d3fe266aec449ded5a65cd10bfd7dd4e9ed080441c38629ede865"
    )
    assert REF["no_production_or_timezone_parser_imported"]
    known = calendar_mansion(REF["input_date"], REF["known_clock"]["time"], REF["zone"])
    unknown = calendar_mansion(REF["input_date"], zone=REF["zone"])
    assert known["calendar_date"] == REF["known_clock"]["reference_date"]
    assert known["input_datetime"] is not None and known["birth_time_known"]
    assert known["natal_su27"] == "柳" and known["calendar_day_part"] is None
    assert "calendar_candidates" not in known and "date_support" not in known
    observed = unknown["date_support"]["utc_support_intervals"]
    assert len(observed) == len(REF["unknown_clock"]["intervals"]) == 2
    for row, expected in zip(observed, REF["unknown_clock"]["intervals"], strict=True):
        assert row["calendar_date"] == expected["reference_date"]
        assert row["start_utc_inclusive"] == expected["start_utc_inclusive"]
        assert row["end_utc_exclusive"] == expected["end_utc_exclusive"]
        assert int(row["end_utc_epoch_microseconds"]) - int(
            row["start_utc_epoch_microseconds"]
        ) == int(expected["duration_microseconds"])
    assert unknown["input_datetime"] is None and not unknown["birth_time_known"]
    assert unknown["status"] == "partial" and unknown["natal_su27"] is None
    known_text = day_evidence(known)["reading_text"]
    unknown_text = day_evidence(unknown)["reading_text"]
    assert (
        "单一瞬间" in known_text
        and "未知钟时" in known_text
        and "完整UTC原像" in known_text
    )
    assert "2024-03-19" in unknown_text and "2024-03-20" in unknown_text
    assert "单一瞬间" not in unknown_text
    assert known["calendar_day_part"] == unknown["calendar_day_part"] is None


@pytest.mark.parametrize("clock", ["00:00:00", "12:00:00", "23:59:59"])
def test_known_clock_reading_preserves_actual_mode_at_every_selected_time(clock):
    result = calendar_mansion(REF["input_date"], clock, REF["zone"])
    moment = datetime.fromisoformat(REF["input_date"] + "T" + clock).replace(
        tzinfo=timezone(
            timedelta(microseconds=int(REF["exact_declared_offset_microseconds"]))
        )
    )
    expected = moment.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    assert result["calendar_date"] == expected
    assert "calendar_candidates" not in result
    assert result["calendar_day_part"] is None
    text = day_evidence(result)["reading_text"]
    assert "单一瞬间" in text and "未知钟时" in text
