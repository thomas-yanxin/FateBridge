"""Offline (no-swisseph) charts must honor the configured house system.

Regression for the bug where the approximate fallback silently degraded the
``equal_mc`` house system (10th cusp = MC, swisseph code ``D``) into plain
``equal`` houses anchored on the ascendant. That mislabeled the system *and*
shifted every planet by a house whenever the ascendant and ``MC + 90°`` fall in
different signs.

The birth below is entirely synthetic — chosen only because its ascendant and
``MC + 90°`` land in different signs, which is exactly the configuration that
exposes the bug.
"""

from __future__ import annotations

import pytest

import fatebridge.core.astro.runtime as astrology_core
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.astro.profiles import _resolve_offline_house_system
from fatebridge.services.astrology import calculate_core_chart_analysis

# Synthetic birth: ascendant and MC+90 fall in different signs, so equal_mc and
# equal-from-ascendant genuinely diverge here.
_SYNTH = dict(
    name="测试样例",
    birth_year=1990,
    birth_month=6,
    birth_day=1,
    birth_hour=1,
    birth_minute=0,
    birth_timezone="Asia/Shanghai",
    birth_longitude=116.4,
    birth_latitude=39.9,
    chart_variant="chart",
)


def _birth_info():
    payload = {k: v for k, v in _SYNTH.items() if k != "chart_variant"}
    return build_astro_birth_info(**payload)


def test_build_houses_equal_mc_anchors_on_midheaven():
    """equal_mc's 1st cusp sits 90° after the MC, not at the ascendant."""
    ascendant = 252.05
    midheaven = 176.48
    houses = _build_houses(ascendant, "equal_mc", midheaven=midheaven)
    for index, house in enumerate(houses):
        expected = normalize_angle(midheaven + 90.0 + index * 30.0)
        assert house["cusp_longitude"] == pytest.approx(expected, abs=1e-4)


def test_offline_equal_mc_is_mc_anchored_not_ascendant(monkeypatch):
    """With swisseph disabled, equal_mc cusps anchor on the MC, not the ASC."""
    monkeypatch.setattr(astrology_core, "swe", None)
    # chart13 still defaults to equal_mc, so it drives the lenient offline
    # equal_mc fallback this regression guards. (The natal `chart` default is now
    # Placidus, which fails loud offline — covered by the test below. Explicit
    # hsys=8 offline also fails loud, so it can't reach the MC+90 fallback.)
    chart = calculate_core_chart_analysis(**{**_SYNTH, "chart_variant": "chart13"})

    profile = chart["chart_profile"]
    assert profile["house_system"] == "equal_mc"
    assert profile["engine_backend"] == "fatebridge_approximate_orbital_model"

    ascendant = chart["angles"]["ascendant"]["longitude"]
    midheaven = chart["angles"]["midheaven"]["longitude"]
    first_cusp = chart["houses"][0]["cusp_longitude"]

    # The anchor is MC+90, and (for this birth) that is NOT the ascendant — the
    # exact distinction the bug erased.
    assert first_cusp == pytest.approx(normalize_angle(midheaven + 90.0), abs=1e-4)
    assert first_cusp != pytest.approx(normalize_angle(ascendant), abs=1e-2)


def test_offline_equal_mc_matches_swisseph(monkeypatch):
    """Offline equal_mc placements must equal the swisseph ('D') placements."""
    if astrology_core.swe is None:
        pytest.skip("swisseph not installed")
    # chart13 still defaults to equal_mc (the natal `chart` default is now
    # Placidus), so it exercises the offline equal_mc fallback against swisseph.
    synth13 = {**_SYNTH, "chart_variant": "chart13"}
    online = {
        p["id"]: p["house"] for p in calculate_core_chart_analysis(**synth13)["planets"]
    }

    monkeypatch.setattr(astrology_core, "swe", None)
    offline = {
        p["id"]: p["house"] for p in calculate_core_chart_analysis(**synth13)["planets"]
    }

    assert offline == online


def test_offline_quadrant_request_fails_loud(monkeypatch):
    """Offline Placidus can't be computed — fail loudly rather than fake it.

    swisseph is a hard dependency; a missing one is a broken install, not a
    supported precision tier. Erroring is more honest than silently handing
    back an equal-house approximation under the Placidus name (which an LLM
    consumer could easily fail to notice).
    """
    monkeypatch.setattr(astrology_core, "swe", None)
    # hsys=3 is Placidus (a quadrant system that genuinely needs swisseph).
    with pytest.raises(ValueError, match="swisseph"):
        build_core_chart_payload(_birth_info(), chart_variant="chart", hsys=3)


def test_online_quadrant_request_is_untouched():
    """With swisseph present, Placidus stays Placidus."""
    if astrology_core.swe is None:
        pytest.skip("swisseph not installed")
    chart = calculate_core_chart_analysis(**_SYNTH, hsys=3)
    profile = chart["chart_profile"]
    assert profile["house_system"] == "placidus"
    assert profile["house_system_source"] == "explicit"


@pytest.mark.parametrize(
    "value,expected_key",
    [
        (0, "whole_sign"),
        ("0", "whole_sign"),
        ("W", "whole_sign"),
        ("whole_sign", "whole_sign"),
        ("P", "placidus"),
        ("p", "placidus"),
        ("Placidus", "placidus"),
        ("placidus", "placidus"),
        ("K", "koch"),
        ("Koch", "koch"),
        ("R", "regiomontanus"),
        ("Regiomontanus", "regiomontanus"),
    ],
)
def test_astro_house_system_accepts_string_and_integer(value, expected_key) -> None:
    info = _resolve_offline_house_system(value, context_label="test")
    assert info["key"] == expected_key


@pytest.mark.parametrize("bad", ["", None, "nonsense", 99, "equal"])
def test_astro_house_system_rejects_unknown(bad) -> None:
    with pytest.raises(ValueError):
        _resolve_offline_house_system(bad, context_label="test")
