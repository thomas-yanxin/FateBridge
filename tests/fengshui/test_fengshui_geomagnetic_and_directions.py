"""Geomagnetic (WMM2025 & IGRF-14) and directional/KongWang oracle tests."""

from __future__ import annotations

import math
import time

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.directions import (
    MOUNTAINS_24,
    bearing_context,
    classify_facing_band,
    sitting_from_facing,
    sitting_support,
)
from fatebridge.core.fengshui.geomagnetic import geomagnetic_reference
from fatebridge.core.fengshui.models import DirectionsRequest, GeomagneticReference
from fatebridge.services.fengshui import calculate_directions


@pytest.mark.parametrize(
    "lat,lon,h,year,exp_d,exp_i,exp_h",
    [
        (40.5, -105.5, -1.0, 2027.0, 7.815, 66.354, 20594.3),
        (-72.0, 127.0, 10.0, 2025.0, -147.651, -83.093, 7674.5),
        (25.0, 17.0, 464.0, 2030.0, 2.779, 33.538, 26424.0),
    ],
)
def test_wmm2025_noaa_official_checkpoints(
    lat: float,
    lon: float,
    h: float,
    year: float,
    exp_d: float,
    exp_i: float,
    exp_h: float,
) -> None:
    res = geomagnetic_reference(
        GeomagneticReference(
            model_id="wmm2025_v1",
            latitude=lat,
            longitude=lon,
            height_km_wgs84=h,
            decimal_year=year,
            evidence="NOAA WMM2025_TEST_VALUES.txt",
        )
    )
    field = res["field"]
    assert res["selected_model_id"] == "wmm2025_v1"
    assert abs(field["declination_degrees_east"] - exp_d) < 0.005
    assert abs(field["inclination_degrees_down"] - exp_i) < 0.005
    assert abs(field["horizontal_intensity_nt"] - exp_h) < 1.0


def test_igrf14_historical_and_auto_dispatch() -> None:
    # §6 #8(b): Shanghai 2008.5 -> D ≈ -5.3°
    sh = geomagnetic_reference(
        GeomagneticReference(
            latitude=31.2304,
            longitude=121.4737,
            height_km_wgs84=0.01,
            decimal_year=2008.5,
            evidence="Shanghai Period 8 house oracle",
        ),
        bearing_degrees=180.0,
        north_reference="magnetic",
    )
    assert sh["selected_model_id"] == "igrf14_v1"
    assert -5.6 < sh["field"]["declination_degrees_east"] < -5.0
    assert sh["conversion"]["status"] == "model_candidate"
    assert sh["conversion"]["candidate"]["north_reference"] == "true"

    # Boundary epochs 1900.0 and 2030.0 work cleanly via IGRF-14
    for yr in (1900.0, 1984.5, 2030.0):
        res = geomagnetic_reference(
            GeomagneticReference(
                model_id="igrf14_v1",
                latitude=39.9042,
                longitude=116.4074,
                height_km_wgs84=0.05,
                decimal_year=yr,
                evidence="IGRF-14 epoch boundary",
            )
        )
        assert res["selected_model_id"] == "igrf14_v1"
        assert math.isfinite(res["field"]["declination_degrees_east"])

    # Explicit wmm2025_v1 rejects pre-2025 epochs
    with pytest.raises(ValidationError):
        GeomagneticReference(
            model_id="wmm2025_v1",
            latitude=31.23,
            longitude=121.47,
            height_km_wgs84=0.01,
            decimal_year=2008.5,
            evidence="Out of WMM2025 range",
        )


def test_geomagnetic_pole_and_blackout_guard_and_speed() -> None:
    pole = geomagnetic_reference(
        GeomagneticReference(
            latitude=90.0,
            longitude=0.0,
            height_km_wgs84=0.0,
            decimal_year=2026.0,
            evidence="North geographic pole",
        ),
        bearing_degrees=180.0,
        north_reference="magnetic",
    )
    assert pole["heading_context"]["geographic_pole"] is True
    assert pole["conversion"]["status"] == "unavailable"
    assert pole["conversion"]["unavailable_reason"] == "geographic_pole"

    ref = GeomagneticReference(
        latitude=40.5,
        longitude=-105.5,
        height_km_wgs84=-1.0,
        decimal_year=2027.0,
        evidence="speed check",
    )
    geomagnetic_reference(ref)
    t0 = time.perf_counter()
    for _ in range(100):
        geomagnetic_reference(ref)
    per_call_ms = (time.perf_counter() - t0) * 1000 / 100
    assert per_call_ms < 1.0


@pytest.mark.parametrize(
    "degrees,expected_subband,expected_kongwang,expected_adj",
    [
        (180.0, "zhengxiang", None, None),
        (181.5, "zhengxiang", None, None),
        (182.0, "jianxiang_lower", None, "丁"),
        (264.0, "jianxiang_replacement", None, "庚"),
        (22.5, "jianxiang_replacement", "da_kongwang", "癸"),
        (67.5, "jianxiang_replacement", "da_kongwang", "寅"),
        (37.5, "jianxiang_replacement", "yinyang_chacuo", "丑"),
        (82.5, "jianxiang_replacement", "yinyang_chacuo", "甲"),
        (172.5, "jianxiang_replacement", "yinyang_chacuo", "丙"),
        (262.5, "jianxiang_replacement", "yinyang_chacuo", "庚"),
        (7.5, "jianxiang_replacement", "xiao_kongwang", "子"),
    ],
)
def test_kongwang_and_subband_classifier(
    degrees: float,
    expected_subband: str,
    expected_kongwang: str | None,
    expected_adj: str | None,
) -> None:
    band = classify_facing_band(degrees)
    assert band["facing_subband"] == expected_subband
    assert band["kongwang"] == expected_kongwang
    assert band["adjacent_mountain"] == expected_adj


def test_directions_service_and_interval_support() -> None:
    assert len(MOUNTAINS_24) == 24
    ctx = bearing_context(360.0, "magnetic")
    assert ctx["direction"] == "N" and ctx["mountain"] == "子"
    sit = sitting_from_facing(0.0, "magnetic")
    assert sit["direction"] == "S" and sit["mountain"] == "午"
    sup = sitting_support(22.5, 1.0, "magnetic")
    assert {row["sitting_trigram"] for row in sup} == {"离", "坤"}

    res = calculate_directions(
        DirectionsRequest(bearing_degrees=22.5, north_reference="magnetic")
    )
    assert res["status"] == "complete"
    assert res["layers"]["directions"]["bearing"]["kongwang"] == "da_kongwang"
