"""Original printed arithmetic, independent angle algebra and timing provenance."""

import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.astro.day_meridian import (
    SOURCE,
    day_meridian_coordinates,
    target_sun_state,
)
from fatebridge.core.output_midpoints import MidpointAnalysis
from fatebridge.services.astrology import calculate_germany_chart_analysis
from tests.fixtures.surface_payloads import astro_payload

ROOT = Path(__file__).parents[1] / "fixtures"
ORIGINAL = json.loads((ROOT / "uranian-witte1924-day-meridian.json").read_text())
HORIZONS = json.loads((ROOT / "uranian-solar-arc-horizons.json").read_text())
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


def _source_degrees(parts):
    return Fraction(parts[0] * 1800 + parts[1] * 60 + parts[2], 60)


def _independent_circle(degrees):
    z = complex(math.cos(math.radians(degrees)), math.sin(math.radians(degrees)))
    return math.degrees(math.atan2(z.imag, z.real)) % 360


def test_witte1924_original_printed_equation_and_preserved_1923_difference():
    case = ORIGINAL["example"]
    lower = _source_degrees(case["natal_lower_meridian"])
    arc = Fraction(case["solar_arc_degrees_minutes"][0]) + Fraction(
        case["solar_arc_degrees_minutes"][1], 60
    )
    result = day_meridian_coordinates(
        float((lower + 180) % 360),
        float(_source_degrees(case["natal_tropical_sun"])),
        float(arc),
        float(_source_degrees(case["target_tropical_sun"])),
    )
    printed = _source_degrees(case["printed_lower_meridian"])
    assert result["lower_meridian_longitude"] == pytest.approx(
        float(printed), abs=1e-12
    )
    older = ORIGINAL["earlier_source_disagreement"]
    older_upper = _source_degrees(older["printed_upper_meridian"])
    delta_minutes = abs(older_upper - ((printed + 180) % 360)) * 60
    assert (
        delta_minutes
        == older["difference_from_1924_equivalent_upper_arcminutes"]
        == 184
    )
    assert SOURCE["source_sha256"] == ORIGINAL["source_pdf_sha256"]
    assert ORIGINAL["event_claims_adopted"] is False


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_day_meridian_rejects_nonfinite_inputs_in_each_operand(value):
    for index in range(4):
        operands = [200.0, 310.0, 43.0, 1.0]
        operands[index] = value
        with pytest.raises(ValueError, match="finite"):
            day_meridian_coordinates(*operands)


def test_day_meridian_preserves_wrap_side_and_does_not_become_plain_solar_arc():
    tiny = math.nextafter(0.0, -math.inf)
    result = day_meridian_coordinates(0.0, 0.0, 0.0, tiny)
    assert 0 < result["upper_meridian_longitude"] < 360
    assert 0 < result["target_tropical_sun"] < 360
    for mc, sun, arc, target in [(277.25, 306.0, 62.0, 20.0), (-720.0, 720.0, 0, 90)]:
        result = day_meridian_coordinates(mc, sun, arc, target)
        expected = _independent_circle(mc + arc - sun + target)
        assert result["upper_meridian_longitude"] == pytest.approx(expected, abs=2e-12)
        assert (
            result["lower_meridian_longitude"] - result["upper_meridian_longitude"]
        ) % 360 == pytest.approx(180)
        assert (
            result["upper_meridian_longitude"]
            != result["solar_arc_midheaven_longitude"]
        )


@HAS_SWE
@pytest.mark.parametrize("row", HORIZONS["rows"], ids=lambda r: r["utc"])
def test_actual_target_sun_uses_independent_recorded_horizons_positions(row):
    state = target_sun_state(datetime.fromisoformat(row["utc"]))
    delta = abs(
        (state["target_tropical_sun"] - row["apparent_ecliptic_longitude"] + 180) % 360
        - 180
    )
    assert delta * 3600 <= HORIZONS["position_tolerance_arcseconds"]
    assert state["target_julian_day_tt"] is not None
    assert state["target_time_scale_method"]
    assert state["target_sun_ephemeris_model"]


@HAS_SWE
@pytest.mark.parametrize("uncertainty", [None, 0, 5])
def test_day_meridian_replays_every_confirmed_birth_sample_without_inventing_precision(
    uncertainty,
):
    result = calculate_germany_chart_analysis(
        **astro_payload(),
        analysis_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        birth_time_uncertainty_minutes=uncertainty,
    )["midpoint_analysis"]
    solar = result["solar_arc_analysis"]
    day = solar["daily_meridian"]
    profile = day["profile"]
    assert day["real_world_efficacy"] == "not_tested"
    assert day["original_text_conformance"] == "not_assessed"
    comparison = day["source_comparison"]
    assert comparison["status"] == "printed_arithmetic_difference_explained"
    assert comparison["computed_for_current_chart"] is False
    assert comparison["difference_is_universal_correction"] is False
    assert comparison["original_variants_fully_reconciled"] is False
    assert comparison["original_progression_time_key_accepted"] is False
    assert profile["meridians_are_observations"] is False
    expected = _independent_circle(
        profile["natal_upper_meridian_longitude"]
        + profile["solar_arc_degrees"]
        - profile["natal_tropical_sun"]
        + profile["target_tropical_sun"]
    )
    assert profile["upper_meridian_longitude"] == pytest.approx(expected, abs=2e-12)
    sensitivity = day["birth_time_sensitivity"]
    assert sensitivity["uncertainty_minutes"] == uncertainty
    assert sensitivity["continuous_interval_proven"] is False
    assert sensitivity["sample_frequency_is_probability"] is False
    if uncertainty is None:
        assert sensitivity["status"] == "not_assessed"
        assert "samples" not in sensitivity
    else:
        assert sensitivity["sample_count"] == (1 if uncertainty == 0 else 21)
        assert sensitivity["clock_policy"] == result["time_sensitivity"]["clock_policy"]
        assert (
            sensitivity["recorded_interval_start_utc"]
            == result["time_sensitivity"]["recorded_interval_start_utc"]
        )
        for sample in sensitivity["samples"]:
            expected = _independent_circle(
                sample["natal_upper_meridian_longitude"]
                + sample["solar_arc_degrees"]
                - sample["natal_tropical_sun"]
                + profile["target_tropical_sun"]
            )
            assert sample["upper_meridian_longitude"] == pytest.approx(
                expected, abs=2e-12
            )
        if uncertainty == 0:
            assert (
                sensitivity["factor_spans"]["upper_meridian_longitude"][
                    "maximum_offset_from_nominal_degrees"
                ]
                == 0
            )
    invalid = {
        "solar_arc_analysis": {
            "daily_meridian": {"profile": {"upper_meridian_longitude": "not-a-number"}}
        }
    }
    with pytest.raises(ValidationError):
        MidpointAnalysis.model_validate(invalid)


@HAS_SWE
def test_sidereal_display_and_birth_instant_keep_the_method_and_layers_distinct():
    args = {
        **astro_payload(),
        "analysis_datetime": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    tropical = calculate_germany_chart_analysis(**args, zodiacal=0)["midpoint_analysis"]
    sidereal = calculate_germany_chart_analysis(**args, zodiacal=1)["midpoint_analysis"]
    t = tropical["solar_arc_analysis"]["daily_meridian"]["profile"]
    s = sidereal["solar_arc_analysis"]["daily_meridian"]["profile"]
    assert t["target_tropical_sun"] == s["target_tropical_sun"]
    assert t["solar_arc_degrees"] == s["solar_arc_degrees"]
    natal_shift = (
        t["natal_upper_meridian_longitude"] - s["natal_upper_meridian_longitude"]
    ) % 360
    assert (
        t["upper_meridian_longitude"] - s["upper_meridian_longitude"]
    ) % 360 == pytest.approx(natal_shift, abs=2e-12)
    nominal = calculate_germany_chart_analysis(**astro_payload())["midpoint_analysis"]
    assert "solar_arc_analysis" not in nominal


def test_target_sun_rejects_unknown_offset_and_missing_ephemeris(monkeypatch):
    with pytest.raises(ValueError, match="timezone"):
        target_sun_state(datetime(2000, 1, 1))
    monkeypatch.setattr(runtime, "swe", None)
    with pytest.raises(ValueError, match="Swiss"):
        target_sun_state(datetime(2000, 1, 1, tzinfo=timezone.utc))


@HAS_SWE
def test_day_meridian_at_the_effective_birth_instant_returns_natal_angles():
    layer = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime(2000, 1, 1, 4, 30, tzinfo=timezone.utc),
    )["midpoint_analysis"]
    day = layer["solar_arc_analysis"]["daily_meridian"]["profile"]
    assert day["solar_arc_degrees"] == 0
    assert day["transit_sun_displacement_degrees"] == 0
    assert day["upper_meridian_longitude"] == day["natal_upper_meridian_longitude"]
    assert day["lower_meridian_longitude"] == day["natal_lower_meridian_longitude"]
