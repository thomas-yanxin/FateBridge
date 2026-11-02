"""A single failed body must not replace the native sky of all other bodies."""

from itertools import product

import pytest

from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.geometry import combine_longitudes
from fatebridge.core.astro.reference import PLANET_SEQUENCE
from fatebridge.core.local_techniques.otherbu import build_otherbu_result

FACES = {"planet": "Jupiter", "sign": "Aries", "house": 0}
SKY = {"date": "2024-03-20", "time": "06:30", "zone": "UTC", "lat": 51.5, "lon": 0}
APPROXIMATE = "fatebridge_approximate_orbital_model"


@pytest.mark.parametrize(
    "failed_planet,zodiacal", list(product(PLANET_SEQUENCE, [0, 1]))
)
def test_single_failure_preserves_every_other_native_longitude(
    monkeypatch, failed_planet, zodiacal
):
    complete = build_otherbu_result(**FACES, **SKY, zodiacal=zodiacal, hsys=0)
    original = ephemeris._swisseph_planet_state
    called = []

    def selective(planet, *args, **kwargs):
        called.append(planet)
        return None if planet == failed_planet else original(planet, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", selective)
    partial = build_otherbu_result(**FACES, **SKY, zodiacal=zodiacal, hsys=0)
    assert called == list(PLANET_SEQUENCE)
    expected = {p["id"]: p for p in complete["chart"]["chart"]["objects"]}
    actual = {p["id"]: p for p in partial["chart"]["chart"]["objects"]}
    for name in PLANET_SEQUENCE:
        if name != failed_planet:
            assert actual[name] == expected[name]
    if failed_planet not in {"Sun", "Moon"}:
        assert actual["Pars Fortuna"] == expected["Pars Fortuna"]
    if failed_planet != "North Node":
        assert actual["South Node"] == expected["South Node"]
    profile = partial["chart"]["params"]["chart_profile"]
    assert profile["engine_precision"] == "mixed_precision_runtime_model"
    assert profile["engine_backend"] == "swisseph_api_with_approximate_orbits"
    # A failed analytical node changes computation quality, but does not mix
    # the physical planets' vector ephemerides. Keep both claims testable.
    expected_model = (
        complete["chart"]["params"]["chart_profile"]["ephemeris_model"]
        if failed_planet == "North Node"
        else "mixed"
    )
    assert profile["ephemeris_model"] == expected_model
    assert profile["orbital_fallback"]["approximate_planets"] == [failed_planet]
    models = profile["planetary_models"]
    assert models[failed_planet] == APPROXIMATE
    assert all(models[name] != APPROXIMATE for name in models if name != failed_planet)
    assert profile["orbital_fallback"]["note_zh"] in partial["snapshot_text"]
    if zodiacal:
        methods = profile["sidereal_planetary_methods"]
        assert methods[failed_planet] == "ayanamsha_offset_approximation"
        assert all(
            methods[name] == "swisseph_calc_sidereal_lahiri"
            for name in methods
            if name != failed_planet
        )
        assert profile["sidereal_position_method"] == (
            "mixed_native_lahiri_and_ayanamsha_offset_approximation"
        )
    for key in [
        "symbolic_details",
        "interpretation",
        "diceChart",
        "rulesets",
        "rule_trace",
    ]:
        assert partial[key] == complete[key]


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_fallback_sidereal_coordinates_have_the_declared_offset_method(
    monkeypatch, zodiacal
):
    original = ephemeris._swisseph_planet_state
    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda name, *a, **kw: None if name == "Pluto" else original(name, *a, **kw),
    )
    tropical = build_otherbu_result(**FACES, **SKY, zodiacal=0, hsys=0)
    current = build_otherbu_result(**FACES, **SKY, zodiacal=zodiacal, hsys=0)
    a = next(p for p in tropical["chart"]["chart"]["objects"] if p["id"] == "Pluto")
    b = next(p for p in current["chart"]["chart"]["objects"] if p["id"] == "Pluto")
    offset = current["chart"]["params"]["chart_profile"]["ayanamsha"] if zodiacal else 0
    assert b["lon"] == combine_longitudes(a["lon"], -offset)


def test_all_failures_return_explicit_per_body_approximation_without_claiming_native(
    monkeypatch,
):
    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", lambda *a, **kw: None)
    result = build_otherbu_result(**FACES, **SKY, hsys=0)
    profile = result["chart"]["params"]["chart_profile"]
    assert profile["engine_precision"] == "approximate_orbital_model"
    assert profile["engine_backend"] == APPROXIMATE
    assert profile["ephemeris_model"] == "none"
    assert set(profile["planetary_models"].values()) == {APPROXIMATE}
    assert profile["orbital_fallback"]["approximate_planets"] == list(PLANET_SEQUENCE)
    assert len(result["chart"]["chart"]["objects"]) == 13


def test_no_runtime_uses_the_same_declared_approximation(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = build_otherbu_result(**FACES, **SKY, hsys=0)
    profile = result["chart"]["params"]["chart_profile"]
    assert set(profile["planetary_models"].values()) == {APPROXIMATE}
    assert (
        profile["orbital_fallback"]["time_argument"]
        == "UT1_day_number_ignoring_TT_difference"
    )


def test_fully_native_sky_has_no_orbital_fallback_claim():
    result = build_otherbu_result(**FACES, **SKY, hsys=0)
    assert "orbital_fallback" not in result["chart"]["params"]["chart_profile"]
