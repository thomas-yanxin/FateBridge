"""Offline origin uses the complete named source and the orbital TT clock."""

import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import geometry, runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.continuous_lahiri import apparent_lahiri_origin
from fatebridge.core.astro.time_scales import fallback_julian_day_tt

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-lahiri-origin-reference-v1.json"
    ).read_text()
)


@pytest.mark.parametrize("case", REFERENCE["rows"])
def test_complete_origin_matches_explicit_native_lahiri(case, monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    origin, rate = apparent_lahiri_origin(case["jd_tt"])
    assert (
        abs(math.remainder(origin - case["native_apparent_origin_degrees"], 360))
        <= REFERENCE["offset_gate_degrees"]
    )
    assert (
        abs(rate - case["native_five_point_rate_deg_TT_day"])
        <= REFERENCE["rate_gate_degrees_per_TT_day"]
    )
    assert geometry._ayanamsha(-1e6, julian_day_tt=case["jd_tt"]) == origin


@pytest.mark.parametrize("date", [(1, 1, 1), (2000, 1, 1), (9999, 12, 31)])
def test_offline_origin_and_motion_use_the_same_orbital_TT(date, monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    birth = build_astro_birth_info(
        birth_year=date[0],
        birth_month=date[1],
        birth_day=date[2],
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    payload = build_core_chart_payload(birth, "chart", hsys=0, zodiacal=1)
    provenance = payload["chart_profile"]["orbital_fallback"]
    epoch = provenance["julian_day_tt"]
    origin, rate = apparent_lahiri_origin(epoch)
    assert payload["chart_profile"]["ayanamsha_includes_nutation"] is True
    assert payload["chart_profile"]["ayanamsha"] == pytest.approx(origin, abs=1e-8)
    assert provenance["longitude_motion_origin_rate_degrees_per_day"] == pytest.approx(
        rate, abs=1e-12
    )
    assert fallback_julian_day_tt(0, epoch) == epoch
