"""Unresolved civil clocks cannot become an asserted western birth instant."""

import pytest

from fatebridge.core.astro import chart, relationship, runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.predictive import _common
from fatebridge.core.predictive._common import build_predictive_birth_info
from fatebridge.services.astrology import calculate_core_chart_analysis

CASE = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_longitude=15,
    birth_latitude=40,
)


@pytest.mark.parametrize("place", [None, "虚构的未知出生地", "通州区"])
@pytest.mark.parametrize("variant", ["chart", "hellen_chart", "chart13", "germany"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_western_service_rejects_unresolved_zone_before_sky_work(
    monkeypatch, place, variant, solar, zodiacal
):
    def forbidden(*args, **kwargs):
        pytest.fail("An unconfirmed civil timezone must not reach native calculations")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    result = calculate_core_chart_analysis(
        **CASE,
        birth_place=place,
        chart_variant=variant,
        use_true_solar_time=solar,
        zodiacal=zodiacal,
    )
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 400 and not result["retryable"]
    assert "birth_timezone" in result["error"]


@pytest.mark.parametrize("variant", ["chart", "hellen_chart", "chart13"])
def test_direct_chart_cannot_accept_a_marked_fallback_instant(monkeypatch, variant):
    birth = build_astro_birth_info(**CASE)
    assert birth.timezone_source == "default_utc"

    def forbidden(*args, **kwargs):
        pytest.fail("Unknown timezone must be rejected before building the chart")

    monkeypatch.setattr(chart, "_build_core_chart_payload", forbidden)
    with pytest.raises(ValueError, match="birth_timezone"):
        chart.build_core_chart_payload(birth, variant)


@pytest.mark.parametrize("party", ["inner", "outer"])
def test_direct_relative_chart_checks_both_original_clocks(monkeypatch, party):
    unknown = build_astro_birth_info(**CASE)
    known = build_astro_birth_info(**CASE, birth_timezone="UTC")

    def forbidden(*args, **kwargs):
        pytest.fail("Both parties must have a resolved timezone before either chart")

    monkeypatch.setattr(relationship, "_build_relative_base_chart", forbidden)
    with pytest.raises(ValueError, match="birth_timezone"):
        relationship.build_relative_payload(
            unknown if party == "inner" else known,
            unknown if party == "outer" else known,
        )


def test_predictive_birth_factory_requires_a_resolved_civil_timezone():
    with pytest.raises(ValueError, match="birth_timezone"):
        build_predictive_birth_info(**CASE)


def test_predictive_natal_subject_also_rejects_a_marked_fallback(monkeypatch):
    birth = build_astro_birth_info(**CASE)

    def forbidden(*args, **kwargs):
        pytest.fail("A fallback instant must not become a predictive natal subject")

    monkeypatch.setattr(_common, "build_subject", forbidden)
    with pytest.raises(ValueError, match="birth_timezone"):
        _common.build_natal_subject(birth)


@pytest.mark.parametrize("variant", ["germany", "chart13"])
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_explicit_solar_clock_keeps_its_distinct_non_civil_source(variant, basis):
    result = calculate_core_chart_analysis(
        **CASE, chart_variant=variant, birth_clock_basis=basis
    )
    assert "error" not in result, result
    core = result["base_chart"] if variant == "germany" else result
    assert core["person_info"]["timezone_source"] == "solar_clock_conversion"
