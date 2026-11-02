"""Offline historical planetary references independent of the natal clock.

The TT epoch and tolerances were fixed before the earlier network attempt.
NASA data test planetary longitudes, not a reconstructed Witte birth time.
"""

import csv
import hashlib
import io
import json
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.midpoints import _native_factors
from fatebridge.core.astro.time_scales import datetime_from_tt
from tests.ephemeris_case_runtime import native_ephemeris_files

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/uranian-historical-horizons.json").read_text()
)


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["body"])
def test_native_historical_longitude_matches_predeclared_nasa_tt_reference(
    case, native_ephemeris_files
):
    raw = case["raw_http_json"].encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == case["raw_http_json_sha256"]
    response = json.loads(raw)
    assert "error" not in response
    text = response["result"]
    assert "GEOCENTRIC" in text and "{source: DE441}" in text
    params = case["request_parameters"]
    assert params["COMMAND"] == f"'{case['body_id']}'"
    assert re.search(
        rf"Target body name:\s+{re.escape(case['body'])}\s+\({case['body_id']}\)",
        text,
    )
    assert params["TIME_TYPE"] == "'TT'"
    assert params["CENTER"] == "'500@399'"
    assert params["QUANTITIES"] == "'31'"
    rows = list(csv.reader(io.StringIO(text.split("$$SOE\n")[1].split("$$EOE")[0])))
    assert len(rows) == 1
    reference_epoch = datetime.strptime(rows[0][0].strip(), "%Y-%b-%d %H:%M:%S.%f")
    assert reference_epoch == datetime.fromisoformat(case["epoch_tt"])
    assert float(rows[0][3]) == case["apparent_ecliptic_longitude"]
    assert float(rows[0][4]) == case["apparent_ecliptic_latitude"]

    # Independent calendar ordinal: this number labels TT, never civil UTC.
    jd_tt = (
        reference_epoch.toordinal()
        + 1721424.5
        + (
            reference_epoch - reference_epoch.replace(hour=0, minute=0, second=0)
        ).total_seconds()
        / 86400
    )
    civil = datetime_from_tt(jd_tt)
    birth = build_astro_birth_info(
        birth_year=civil.year,
        birth_month=civil.month,
        birth_day=civil.day,
        birth_hour=civil.hour,
        birth_minute=civil.minute,
        birth_second=civil.second,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    # The independently fixed TT epoch may have a fractional civil second.
    # Retain it in the internal calculation; no fractional birth record is
    # claimed, and no clock is shifted to fit a printed natal coordinate.
    birth = replace(
        birth,
        utc_datetime=civil.astimezone(timezone.utc),
        local_datetime=civil,
        recorded_datetime=civil,
    )
    native = _native_factors(birth, False, include_hypothetical=False)
    assert abs(native["julian_day_tt"] - jd_tt) * 86400 <= 0.0002
    actual = next(f for f in native["factors"] if f["id"] == case["body"])
    assert actual["model"] == "swieph"
    error = (
        abs(
            (actual["longitude"] - case["apparent_ecliptic_longitude"] + 180) % 360
            - 180
        )
        * 3600
    )
    assert error <= case["tolerance_arcseconds"]
