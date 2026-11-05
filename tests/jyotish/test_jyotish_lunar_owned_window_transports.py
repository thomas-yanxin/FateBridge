"""Three local public surfaces deliver the repaired Moon and its source basis."""

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.time_scales import datetime_from_tt
from tests.jyotish.test_jyotish_lunar_owned_window import REF, require_window
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.jyotish.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_repaired_same_run_coordinates_and_dasha_on_three_surfaces(
    monkeypatch, capsys, key
):
    from pathlib import Path

    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    row = next(
        r for r in REF["rows"] if r["date_tt"].startswith("9600-01-01T00:00:00.375")
    )
    moment = datetime_from_tt(row["jd_tt"])
    payload = {
        "birth_year": moment.year,
        "birth_month": moment.month,
        "birth_day": moment.day,
        "birth_hour": moment.hour,
        "birth_minute": moment.minute,
        "birth_second": moment.second,
        "birth_microsecond": moment.microsecond,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
        "birth_time_uncertainty_minutes": 0,
        "divisions": [],
        "ephemeris_policy": "require_data_files",
        "name": "工程合成：月球光路窗口",
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 9600
    body = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile",
            "india.charts.D1",
            "india.topic_evidence",
            *(["vimshottari"] if key == "astro_vimshottari" else []),
        ],
    )
    india = body["india"]
    assert india["profile"]["ruleset_id"] == "parashari_lahiri_core_v29"
    profile = india["profile"]
    for frame in ["ecliptic", "equatorial"]:
        require_window(
            profile["native_coordinate_contexts"][f"{frame}_Moon"],
            profile["julian_day_tt"],
        )
    moon = next(p for p in india["charts"]["D1"]["planets"] if p["id"] == "Moon")
    assert (
        moon["longitude"]
        == profile["native_coordinate_contexts"]["ecliptic_Moon"][
            "selected_native_state"
        ][0]
    )
    if key == "astro_vimshottari":
        assert body["vimshottari"]["seed"]["moon_longitude"] == moon["longitude"]
