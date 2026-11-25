"""Check forward displacement and local type membership for the reference rows."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import parse_timezone_name
from tests.support.synthetic_dayun import synthetic_dayun_start

ROWS = json.loads(
    (Path(__file__).parents[1] / "data/bazi/dayun-gap-inputs.json").read_text()
)["rows"]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["zone"])
def test_every_registered_gap_magnitude_keeps_forward_resolution(
    row, monkeypatch: pytest.MonkeyPatch
) -> None:
    gap = row["source_after_offset_seconds"] - row["source_before_offset_seconds"]
    wall = datetime.fromisoformat(row["wall"]).replace(tzinfo=timezone.utc)
    birth_utc = wall - timedelta(seconds=gap + row["source_before_offset_seconds"])
    expected = wall + timedelta(seconds=gap - row["source_after_offset_seconds"])
    birth = birth_utc.astimezone(parse_timezone_name(row["zone"]))
    # Only the nominal age offset is synthetic. Actual offset changes and
    # expected UTC instants use the previously compiled official IANA source.
    monkeypatch.setattr(
        TimingAnalysis,
        "resolve_dayun_start",
        staticmethod(
            lambda birth, gender, zone: synthetic_dayun_start(
                birth, zone, gap / 120, forward=False
            )
        ),
    )
    args = (birth, "女", ("丙", "寅"), row["zone"])
    # IANA 2026f marks the old type as -00 in these four fixed rows.
    # The numeric offset difference is not a defined civil-clock gap.
    if row["zone"] in {
        "Antarctica/Mawson",
        "Antarctica/Davis",
        "Antarctica/Casey",
        "Antarctica/Macquarie",
    }:
        with pytest.raises(ParameterError) as error:
            TimingAnalysis.calculate_dayun_timeline(*args, periods=0)
        assert error.value.issues == [
            {"path": "request", "code": "unresolved_timezone_offset"}
        ]
        return
    else:
        pass
    current = TimingAnalysis.calculate_dayun_timeline(*args, periods=3)
    assert (
        datetime.fromisoformat(current["start_at"]).astimezone(timezone.utc) == expected
    )
    assert current["dst_policy"] == "fold_0_gap_forward"
