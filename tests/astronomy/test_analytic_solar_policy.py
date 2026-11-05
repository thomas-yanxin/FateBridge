"""The better Sun model is explicit; native controls and strict failures survive."""

from dataclasses import replace
from datetime import datetime

import pytest

from fatebridge.core import almanac
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.de440_solar import MODEL_ID as DE440_MODEL_ID
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_MODEL
from fatebridge.core.moshier_solar import PROVIDER as COMPLETE_MOSHIER_PROVIDER
from fatebridge.core.solar_model_policy import analytic_selected, solar_model_policy
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def empty_ephemeris(monkeypatch, tmp_path):
    original = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        yield
    finally:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
        configure_ephemeris_path(original if original is not None else "")
        almanac.get_solar_terms_for_year.cache_clear()


def test_default_empty_directory_uses_named_model_and_native_control_remains(
    empty_ephemeris, monkeypatch
):
    enhanced = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(enhanced) == 24
    for term in enhanced:
        assert term.resolution_provider == "jpl_de440"
        assert term.ephemeris_model == DE440_MODEL_ID
        assert term.ephemeris_retflags == ()
        assert term.solar_model_details["native_choice_probe_model"] is None
        assert term.solar_model_details["native_choice_probe_retflags"] == []
        assert term.solar_model_details["accuracy_certified"] is False
        assert almanac.is_calculated_solar_term(term)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    native = almanac.get_solar_terms_for_year(2026, "UTC")
    assert all(
        t.resolution_provider == COMPLETE_MOSHIER_PROVIDER
        and t.ephemeris_model == COMPLETE_MOSHIER_MODEL
        for t in native
    )
    assert native is not enhanced
    assert any(a.moment != b.moment for a, b in zip(enhanced, native))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    assert almanac.get_solar_terms_for_year(2026, "UTC") is enhanced


@pytest.mark.parametrize("native_model", ["swieph", "jpl"])
def test_auto_keeps_actual_data_backed_sun(native_model, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    assert analytic_selected(2026, native_model) is False


def test_unknown_modes_and_forged_analytic_provenance_are_rejected(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "unknown")
    with pytest.raises(ValueError, match="must be"):
        solar_model_policy()
    term = almanac.SolarTerm(
        "立春", datetime(2026, 2, 4), "20260204", "", "fatebridge_analytic", MODEL_ID
    )
    with pytest.raises(RuntimeError, match="具名"):
        almanac.require_calculated_solar_term(term)
    assert (
        almanac.is_calculated_solar_term(
            replace(term, solar_model_details={"model_id": "moshier"})
        )
        is False
    )


def test_native_solver_failure_cannot_be_silently_promoted_to_success(
    empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a, **kw: None)
    with pytest.raises(EphemerisSourceError, match="no linear approximation"):
        almanac.get_solar_terms_for_year(2026, "UTC")


def test_receipt_policy_is_live_even_when_deployment_fingerprints_are_cached(
    monkeypatch,
):
    from fatebridge.core.solar_model_policy import solar_model_environment_receipt

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    first = solar_model_environment_receipt()
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    second = solar_model_environment_receipt()
    assert first["mode"] == "auto" and second["mode"] == "native"
    assert len(first["frame_coefficient_sha256"]) == 64
    assert second["source_selection"] == "native_swiss_or_complete_moshier"
    assert second["source_resolution"] == "configuration_only"
    assert second["analytic_source_resolved"] is False
    assert "model_id" not in second and "loaded_coefficient_sha256" not in second


def test_returned_metadata_cannot_mutate_the_shared_year_cache(empty_ephemeris):
    terms = almanac.get_solar_terms_for_year(2026, "UTC")
    first = terms[0].as_dict()
    first["solar_model_details"]["model_id"] = "changed_after_delivery"
    first["solar_model_details"]["root_bracket_tt"][0] = -1
    first["solar_model_details"]["native_choice_probe_retflags"].append(-1)
    repeated = almanac.get_solar_terms_for_year(2026, "UTC")[0].as_dict()
    assert repeated["solar_model_details"]["model_id"] == DE440_MODEL_ID
    assert repeated["solar_model_details"]["root_bracket_tt"][0] > 0
    assert repeated["solar_model_details"]["native_choice_probe_retflags"] == []


def test_explicit_analytic_control_preserves_the_original_source(
    empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    terms = almanac.get_solar_terms_for_year(2026, "UTC")
    for term in terms:
        assert term.resolution_provider == "fatebridge_analytic"
        assert term.ephemeris_model == MODEL_ID
        assert (
            term.solar_model_details["native_choice_probe_model"]
            == COMPLETE_MOSHIER_MODEL
        )
        assert term.solar_model_details["native_choice_probe_retflags"] == []


@pytest.mark.parametrize("year", [1799, 2201])
def test_analytic_range_does_not_silently_expand(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    assert analytic_selected(year, "moshier") is False
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    with pytest.raises(ValueError, match="1800..2200"):
        analytic_selected(year, "moshier")


def test_strict_jpl_conflict_is_checked_even_after_auto_year_is_cached(
    empty_ephemeris, monkeypatch
):
    almanac.get_solar_terms_for_year(2026, "UTC")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    with pytest.raises(ValueError, match="conflicts with strict JPL"):
        almanac.get_solar_terms_for_year(2026, "UTC")
