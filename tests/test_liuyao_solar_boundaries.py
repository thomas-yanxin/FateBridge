"""Independent minute references and non-independent clock round-trip regression."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.local_techniques.sixyao import build_sixyao_result

BASE = Path(__file__).parent / "fixtures/liuyao_solar_v16"
REFERENCE = json.loads((BASE / "reference.json").read_text())
ERRATA = json.loads((BASE / "input-errata.json").read_text())
_row = REFERENCE["records"][ERRATA["record_index"]]
assert _row[ERRATA["field"]] == ERRATA["old_value"]
_row[ERRATA["field"]] = ERRATA["new_value"]


def test_published_source_frozen_before_repair():
    freeze = json.loads((BASE / "freeze.json").read_text())
    for name, digest in freeze["files_sha256"].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert REFERENCE["rounding_mode_verified"] is False
    assert len(REFERENCE["records"]) == 24


@pytest.mark.parametrize("record", REFERENCE["records"], ids=lambda r: r["name"])
def test_calculated_term_against_independent_naoj_printed_minute(record):
    actual = next(t for t in get_solar_terms_for_year(2026) if t.name == record["name"])
    published = datetime.fromisoformat(record["published_at"])
    assert abs((actual.moment - published).total_seconds()) <= 60


@pytest.mark.parametrize("zone", ["Asia/Shanghai", "Asia/Tokyo", "America/New_York"])
@pytest.mark.parametrize("record", REFERENCE["records"], ids=lambda r: r["name"])
def test_public_months_on_both_sides_of_published_minute_band(record, zone):
    published = datetime.fromisoformat(record["published_at"])
    for sign, expected in [(-1, "before_month_branch"), (1, "after_month_branch")]:
        moment = (published + sign * timedelta(seconds=61)).astimezone(ZoneInfo(zone))
        result = build_sixyao_result(
            date=moment.date().isoformat(),
            time=moment.time().isoformat(),
            zone=zone,
            gua_code="111111",
        )
        assert result["nongli"]["monthGanZi"][1] == record[expected]
        assert (
            result["liuyao_evidence"]["calendar_conventions"]["month_branch"]
            == record[expected]
        )


def test_fractional_cast_clocks_round_trip_across_the_consumed_boundary():
    # The root is deliberately runtime-derived: this is output fidelity, not
    # independent evidence that the computed root is physically accurate.
    term = next(t for t in get_solar_terms_for_year(2026) if t.name == "立春")
    months = []
    for moment in [term.moment - timedelta(microseconds=1), term.moment]:
        result = build_sixyao_result(
            date=moment.date().isoformat(),
            time=moment.time().isoformat(),
            zone="Asia/Shanghai",
            gua_code="111111",
        )
        expected = moment.replace(tzinfo=None)
        calendar = result["calendar_context"]
        for text in [
            calendar["solar_datetime"],
            calendar["lunar_calendar"]["solar_datetime"],
            calendar["lunar_calendar"]["birth"],
            result["nongli"]["birth"],
        ]:
            assert datetime.fromisoformat(text) == expected
        assert (
            datetime.fromisoformat(
                result["liuyao_evidence"]["calendar_conventions"]["cast_at"]
            )
            == moment
        )
        assert moment.isoformat(sep=" ").split("+")[0] in result["snapshot_text"]
        months.append(result["nongli"]["monthGanZi"][1])
    assert months == ["丑", "寅"]
