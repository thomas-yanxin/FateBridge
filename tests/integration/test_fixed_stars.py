"""Current traditional stellar labels and actual native chart integration."""

from __future__ import annotations

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.classical_western import (
    FIXED_STARS,
)
from fatebridge.services.astrology import calculate_core_chart_analysis

_NATAL = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.4667,
    birth_latitude=32.5417,
    name="左右",
    birth_place="海安",
)


# ── pure: catalogue + precession ──────────────────────────────────────────────


def test_catalogue_is_well_formed():
    assert len(FIXED_STARS) == 20
    for star, data in FIXED_STARS.items():
        assert data["nature"]  # at least one Ptolemaic nature (traditional attr)
        assert data["cn"]  # traditional Chinese name
        # The engine returns positions; the assistant provides interpretation.
        assert "gloss" not in data


# ── pure: conjunction detection ───────────────────────────────────────────────


# ── integration: real chart ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def natal_stars():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    return build_core_chart_payload(info, "hellen_chart")["fixed_stars"]


def test_natal_chart_surfaces_antares_on_mercury(natal_stars):
    # Real sky: Antares sits ~0.1° from this chart's Mercury.
    antares = [h for h in natal_stars if h["star"] == "Antares"]
    assert antares, "expected Antares conjunct a chart point"
    assert antares[0]["point"] == "Mercury"
    assert antares[0]["orb"] < 0.2


def test_snapshot_renders_fixed_stars_section():
    payload = calculate_core_chart_analysis(
        chart_variant="hellen_chart", use_true_solar_time=True, **_NATAL
    )
    text = payload["snapshot_text"]
    assert "[恒星]" in text
    assert "心宿二" in text  # Antares' Chinese name


# ── calibration: vendored table vs authoritative swisseph (local only) ────────
