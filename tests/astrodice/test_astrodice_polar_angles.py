"""Eastern intersection from independent horizon constraints and native method.

The altitude constraint follows USNO faq/alt_az. The Swiss houses_armc oracle
uses the same supplied sidereal angle and mean obliquity, isolating branch
selection from the fallback's deliberately approximate sidereal-time model.
Neither test certifies the fallback's accuracy at all epochs.
"""

import math
from itertools import product

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import geographic_pole_angle_definition
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _angles, _gmst, _sign_name
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result

JD = 2460483.0
EPS = 23.439291 - 0.0130042 * ((JD - 2451545.0) / 36525.0)
LATITUDES = [-89.9999, -80, -66.6, -40, 0, 40, 66.6, 80, 89.9999]
FACES = {"planet": "Jupiter", "sign": "Aries", "house": 0}
SKY = {"date": "2024-06-21", "time": "12:00", "zone": "UTC", "lon": 0}


def geographic_longitude(armc):
    return (armc - _gmst(JD) + 180) % 360 - 180


@pytest.mark.parametrize("latitude,armc", list(product(LATITUDES, range(0, 360, 5))))
def test_approximate_ascendant_satisfies_horizon_and_eastern_hemisphere(latitude, armc):
    result = _angles(JD, geographic_longitude(armc), latitude)
    lam, eps, phi, theta = map(math.radians, [result["ascendant"], EPS, latitude, armc])
    # Independently convert the returned longitude to equatorial RA/Dec, then
    # apply USNO's altitude equation and the local eastern component.
    ra = math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam))
    dec = math.asin(math.sin(lam) * math.sin(eps))
    hour_angle = theta - ra
    sin_altitude = math.cos(hour_angle) * math.cos(dec) * math.cos(phi) + math.sin(
        dec
    ) * math.sin(phi)
    eastern_component = -math.cos(dec) * math.sin(hour_angle)
    assert abs(sin_altitude) < 2e-14
    assert eastern_component > 0
    assert 0 <= result["ascendant"] < 360


def test_approximate_branch_matches_native_method_with_identical_angle_inputs():
    swe = pytest.importorskip("swisseph")
    for latitude, armc in product(LATITUDES, range(0, 360, 5)):
        actual = _angles(JD, geographic_longitude(armc), latitude)
        expected = swe.houses_armc(armc, latitude, EPS, b"E")[1]
        for key, truth in zip(["ascendant", "midheaven"], expected[:2]):
            distance = abs((actual[key] - truth + 180) % 360 - 180)
            assert distance < 2e-9, (latitude, armc, key, distance)


@pytest.mark.parametrize("latitude,armc", [(80, 270), (-80, 90)])
def test_known_offline_counterexamples_use_eastern_intersection(latitude, armc):
    result = _angles(JD, geographic_longitude(armc), latitude)
    expected = 0 if latitude > 0 else 180
    assert abs((result["ascendant"] - expected + 180) % 360 - 180) < 1e-10


def test_branch_flip_does_not_round_a_pre_zero_intersection_into_aries():
    # The unflipped computed candidate is 179.99999999999997 degrees. An
    # intermediate +180 rounds it to 360; exact reduction of those supplied
    # floats retains the preceding representable side. No accuracy claim is
    # made about an actual input meridian at this precision.
    armc = math.nextafter(270.0, math.inf)
    result = _angles(JD, geographic_longitude(armc), 80)
    assert result["ascendant"] == math.nextafter(360.0, 0.0)
    assert _sign_name(result["ascendant"]) == "Pisces"


def test_offline_high_latitude_context_recomputes_houses_and_fortune(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = build_otherbu_result(
        **FACES,
        **{**SKY, "lon": geographic_longitude(270)},
        lat=80,
        hsys=0,
        fortune_method="ptolemy_iii10",
    )
    sky = result["chart"]["chart"]
    ascendant = sky["angles"]["ascendant"]
    assert ascendant == pytest.approx(0, abs=1e-10)
    assert sky["houses"][0]["lon"] == 0
    points = {p["id"]: p for p in sky["objects"]}
    assert points["Sun"]["house"] == "House4"  # Old western branch: House10.
    expected_fortune = (ascendant + points["Moon"]["lon"] - points["Sun"]["lon"]) % 360
    assert points["Pars Fortuna"]["lon"] == pytest.approx(expected_fortune, abs=1e-12)
    assert "angle_definition" not in result["chart"]["params"]["chart_profile"]


@pytest.mark.parametrize("latitude", [-90, 90])
@pytest.mark.parametrize("native", [True, False])
def test_exact_pole_keeps_computable_sky_and_declares_meridian_convention(
    monkeypatch, latitude, native
):
    if not native:
        monkeypatch.setattr(runtime, "swe", None)
    result = build_otherbu_result(**FACES, **SKY, lat=latitude, hsys=0)
    sky = result["chart"]
    profile = sky["params"]["chart_profile"]
    definition = profile["angle_definition"]
    assert definition["status"] == "geographic_pole_meridian_convention"
    assert definition["fixed_direction_diurnal_rising_defined"] is False
    assert definition["reference_meridian"] == "supplied_geographic_longitude"
    assert "ascendant_dependent_lots" in definition["dependent_quantities"]
    assert definition["note_zh"] in result["snapshot_text"]
    assert len(sky["chart"]["objects"]) == 13
    assert len(sky["chart"]["houses"]) == 12
    assert all(math.isfinite(p["lon"]) for p in sky["chart"]["objects"])
    assert profile["angle_method"] == ("swisseph" if native else "approximate_angles")
    plain = build_otherbu_result(**FACES)
    for key in [
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ]:
        assert result[key] == plain[key]


@pytest.mark.parametrize("latitude", [-90, 90])
def test_shared_core_summary_keeps_the_same_pole_qualification(latitude):
    birth, _, _ = _build_birth_info(
        date_text=SKY["date"],
        time_text=SKY["time"],
        timezone_name="UTC",
        lat=latitude,
        lon=0,
    )
    result = build_core_chart_payload(birth, "chart", hsys=0)
    assert result["chart_profile"]["angle_definition"]["note_zh"] in result["summary"]


@pytest.mark.parametrize("latitude", [-89.999999999, -80, 0, 80, 89.999999999])
def test_nearby_latitudes_are_not_reclassified_as_exact_poles(latitude):
    assert geographic_pole_angle_definition(latitude) is None


def test_pole_definition_cannot_be_mutated_for_later_calls():
    first = geographic_pole_angle_definition(90)
    first["source_urls"].clear()
    assert len(geographic_pole_angle_definition(90)["source_urls"]) == 2
