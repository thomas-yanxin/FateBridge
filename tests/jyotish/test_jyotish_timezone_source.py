"""An unresolved civil birth label is not a declared UTC instant."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.core import jyotish
from fatebridge.core.astro import chart, runtime
from fatebridge.core.astro.birth import (
    build_astro_birth_info,
    require_resolved_birth_timezone,
)
from fatebridge.core.jyotish_clock import clock_context, require_recorded_instant
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.jyotish import calculate_vimshottari

PROTOCOL = json.loads(
    (Path(__file__).parents[1] / "fixtures/jyotish-timezone-input-v1.json").read_text()
)
BASE = PROTOCOL["unknown_cases"][0]["payload"]


def birth_arguments(payload):
    return {k: v for k, v in payload.items() if k not in {"divisions"}}


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", PROTOCOL["tool_keys"])
@pytest.mark.parametrize("solar", [False, True])
def test_unknown_service_clocks_stop_before_every_native_sky_call(
    monkeypatch, key, solar
):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("An unconfirmed clock must not reach native sky calculations")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    for case in PROTOCOL["unknown_cases"]:
        payload = {**case["payload"], "use_true_solar_time": solar}
        if key == "astro_vimshottari":
            # Even a direct SDK caller cannot disable this service precondition
            # or use a known analysis clock to manufacture a birth timezone.
            result = calculate_vimshottari(
                **payload,
                analysis_year=2001,
                analysis_timezone="UTC",
                require_resolved_timezone=False,
            )
        else:
            result = calculate_core_chart_analysis(
                **payload, chart_variant="india_chart"
            )
        assert result["error_code"] == "validation_error", result
        assert result["status_code"] == 400 and not result["retryable"]
        assert "birth_timezone" in result["error"]
        assert "india" not in result and "vimshottari" not in result
    assert not calls


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("consumer", ["positions", "build_india", "core", "clock"])
@pytest.mark.parametrize("source", PROTOCOL["direct_sdk_sources_to_reject"])
def test_prebuilt_unconfirmed_birth_objects_cannot_bypass_natal_guards(
    monkeypatch, consumer, source
):
    # Keep the shared constructor's distinguishable legacy carrier for other
    # consumers. The Indian natal boundary owns its stricter requirement.
    birth = build_astro_birth_info(**birth_arguments(BASE), preserve_instant=True)
    assert birth.timezone == "UTC" and birth.timezone_source == "default_utc"
    birth = replace(birth, timezone_source=source)

    def forbidden(*args, **kwargs):
        pytest.fail("Unknown SDK clock provenance must be rejected before sky work")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    with pytest.raises(ValueError, match="birth_timezone"):
        if consumer == "positions":
            jyotish.positions(birth)
        elif consumer == "build_india":
            jyotish.build_india(birth, divisions=[])
        elif consumer == "core":
            chart.build_core_chart_payload(birth, "india_chart")
        else:
            clock_context(birth)


@pytest.mark.parametrize("case", PROTOCOL["valid_controls"], ids=lambda c: c["id"])
def test_declared_clock_sources_preserve_the_pre_edit_independent_utc_vectors(case):
    birth = build_astro_birth_info(
        **birth_arguments(case["payload"]),
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    require_recorded_instant(birth)
    if case["expected_utc"] is not None:
        assert birth.utc_datetime.isoformat() == case["expected_utc"]
    if case["id"] == "resolved_place":
        assert birth.timezone_source == "birth_place"
    elif case["id"] in {"local_mean_solar", "local_apparent_solar"}:
        assert birth.timezone_source == "solar_clock_conversion"
        assert birth.clock_conversion["input_clock_basis"] == case["id"]
    else:
        assert birth.timezone_source == "birth_timezone"


@pytest.mark.parametrize(
    "source", ["birth_timezone", "birth_place", "solar_clock_conversion"]
)
def test_only_declared_known_source_kinds_are_accepted(source):
    require_resolved_birth_timezone(source)


def test_legacy_generic_constructor_keeps_explicit_unknown_provenance():
    birth = build_astro_birth_info(**birth_arguments(BASE), preserve_instant=True)
    assert birth.timezone_source == "default_utc"
    with pytest.raises(ValueError, match="坐标不能代替民用时区"):
        require_recorded_instant(birth)
