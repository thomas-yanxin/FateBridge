"""Shared Astrodice transport and horizon fixtures."""

import math
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import fatebridge.api as api
from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import analytic_earth_attitude, earth_attitude
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.services.tool_catalog import CATALOG

SPEC = next(spec for spec in CATALOG if spec.name == "interpret_astrology_dice")


@pytest.fixture
def rest(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


SKY = {"date": "2024-06-21", "time": "12:00", "timezone": "UTC"}


def singular_sky_inputs(
    *,
    native: bool,
    hemisphere: int = 1,
    latitude_offset: float = 0,
    date_text: str = SKY["date"],
) -> dict[str, str | float]:
    birth, _, _ = _build_birth_info(
        date_text=date_text,
        time_text=SKY["time"],
        timezone_name="UTC",
        lat=0,
        lon=0,
    )
    times = birth.time_scales
    if native:
        native_attitude = earth_attitude(runtime.swe, times.ut1, julian_day_tt=times.tt)
        obliquity_degrees = native_attitude.reduction.house_obliquity
        sidereal_degrees = native_attitude.house_sidereal_degrees
    else:
        analytic_attitude = analytic_earth_attitude(
            times.ut1, fallback_julian_day_tt(times.ut1, times.tt)
        )
        obliquity_degrees = analytic_attitude.true_obliquity
        sidereal_degrees = analytic_attitude.equator.greenwich_sidereal_degrees
    target = 270 if hemisphere == 1 else 90
    return {
        **SKY,
        "date": date_text,
        "latitude": hemisphere * (90 - obliquity_degrees) + latitude_offset,
        "longitude": math.remainder(target - sidereal_degrees, 360),
    }
