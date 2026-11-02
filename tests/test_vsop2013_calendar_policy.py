"""Optional named-source routing, structural identity and unchanged boundary gates."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import almanac, solar_model_policy, vsop2013_solar
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture(autouse=True)
def selected(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "vsop2013")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def test_missing_selected_source_never_uses_native_fallback(monkeypatch):
    monkeypatch.delenv(vsop2013_solar.MANIFEST_ENV, raising=False)
    monkeypatch.setattr(
        almanac,
        "_solar_term_utc_via_swe",
        lambda *a, **k: pytest.fail("native fallback"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        almanac.get_solar_terms_for_year(2026, "UTC")
    result = caught.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert caught.value.reason == "solar_vsop2013_unavailable"


@pytest.mark.parametrize("year", [1699, 2301])
def test_public_year_grid_stays_within_full_input_scope(year, monkeypatch):
    monkeypatch.setattr(
        vsop2013_solar, "cache_key", lambda: pytest.fail("out of scope source loaded")
    )
    with pytest.raises(ValueError, match="1700..2300"):
        solar_model_policy.solar_model_cache_key(year=year)


def test_strict_jpl_conflict_is_checked_before_optional_loading(monkeypatch):
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setattr(
        vsop2013_solar, "cache_key", lambda: pytest.fail("conflicting source loaded")
    )
    with pytest.raises(ValueError, match="VSOP2013.*conflicts"):
        solar_term_cache_context(almanac.swe, year=2026)


def test_unobserved_configuration_receipt_never_loads_optional_source(monkeypatch):
    monkeypatch.setattr(
        vsop2013_solar, "cache_key", lambda: pytest.fail("unused source loaded")
    )
    receipt = solar_model_policy.solar_model_environment_receipt(resolve_source=False)
    assert receipt["mode"] == "vsop2013"
    assert receipt["source_resolution"] == "not_observed_in_business_output"
    assert "model_id" not in receipt


@pytest.mark.parametrize("year", [1700, 1800, 2000, 2200, 2300])
def test_adjacent_context_uses_selected_full_input_scope_without_loading(
    year, monkeypatch
):
    monkeypatch.setattr(
        vsop2013_solar, "cache_key", lambda: pytest.fail("context range loaded source")
    )
    assert solar_model_policy.solar_context_input_years(year) == (1700, 2300)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "wrong_model",
        "native_flags",
        "binary_sha256",
        "source_profile_sha256",
        "calculation_source_sha256",
        "build_manifest_sha256",
    ],
)
def test_calculated_predicate_requires_distinct_model_and_source_fields(fault):
    fields = [
        "binary_sha256",
        "source_profile_sha256",
        "calculation_source_sha256",
        "build_manifest_sha256",
    ]
    details = dict(model_id=vsop2013_solar.MODEL_ID, **{k: "a" * 64 for k in fields})
    if fault in fields:
        details.pop(fault)
    if fault == "wrong_model":
        details["model_id"] = "moshier"
    term = almanac.SolarTerm(
        name="立春",
        moment=datetime(2026, 2, 4, tzinfo=timezone.utc),
        date_key="20260204",
        day_ganzhi="己酉",
        resolution_provider="vsop2013",
        ephemeris_model=vsop2013_solar.MODEL_ID,
        ephemeris_retflags=(260,) if fault == "native_flags" else (),
        solar_model_details=details,
    )
    assert almanac.is_calculated_solar_term(term) is (fault == "none")


def test_boundary_guard_remains_five_seconds_and_names_actual_model():
    from fatebridge.core.fengshui.calendar import (
        boundary_model_policy,
        boundary_uncertainty_reason,
    )
    from fatebridge.core.fengshui.snapshot import _calendar_cautions

    moment = datetime(2026, 2, 4, tzinfo=timezone.utc)
    resolution = dict(
        moment=moment.isoformat(),
        approximate=False,
        ephemeris_model=vsop2013_solar.MODEL_ID,
    )
    policy = boundary_model_policy(resolution)
    assert policy["operational_guard_seconds"] == 5.0
    assert (
        policy["uncertainty_reason"]
        == "vsop2013_solar_model_guard_not_accuracy_certification"
    )
    for offset in [-5, 0, 5]:
        assert (
            boundary_uncertainty_reason(moment + timedelta(seconds=offset), resolution)
            == policy["uncertainty_reason"]
        )
    assert (
        boundary_uncertainty_reason(moment + timedelta(seconds=5.001), resolution)
        is None
    )
    assert boundary_model_policy({**resolution, "approximate": True}) is None
    lines = _calendar_cautions({"boundary": resolution})
    assert any("VSOP2013" in line for line in lines)
    assert not any("AA1996" in line or "Moshier；" in line for line in lines)


@pytest.mark.parametrize("origin", [1699, 2301])
def test_derived_projection_cannot_invent_an_in_range_origin(origin, monkeypatch):
    from fatebridge.core import canping_solar

    monkeypatch.setattr(
        vsop2013_solar,
        "cache_key",
        lambda: pytest.fail("unqualified origin loaded source"),
    )
    with pytest.raises(ValueError, match="1700..2300"):
        canping_solar.projection_boundary(
            origin,
            "UTC",
            origin_civil_year=origin,
            origin_bazi_year=origin,
            horizon=120,
        )
