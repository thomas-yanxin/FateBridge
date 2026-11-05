"""Explicit file-backed crossings retain the original one-second TT gate."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac, solar_model_policy
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_ren_calendar_guard import references

EPHE = Path(__file__).resolve().parents[1] / "ephe"


@pytest.fixture
def swiss_environment(monkeypatch, tmp_path):
    original = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "swiss")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    try:
        yield
    finally:
        monkeypatch.undo()
        configure_ephemeris_path(original)
        almanac.get_solar_terms_for_year.cache_clear()


def test_swiss_does_not_load_unrelated_coefficients(swiss_environment, monkeypatch):
    def unused():
        raise AssertionError("Swiss mode must not resolve analytic coefficients")

    monkeypatch.setattr(solar_model_policy, "profile", unused)
    assert solar_model_policy.solar_model_cache_key(year=1800) == (
        "swiss",
        "native_swiss_runtime",
    )
    receipt = solar_model_policy.solar_model_environment_receipt()
    assert receipt["mode"] == "swiss"
    assert receipt["analytical_fallback_allowed"] is False
    assert receipt["source_resolution"] == "configuration_only"


@pytest.mark.parametrize("fault", ["missing_files", "missing_library", "no_root"])
def test_swiss_rejects_approximation_instead_of_publishing_a_year(
    swiss_environment, monkeypatch, fault
):
    if fault == "missing_library":
        monkeypatch.setattr(almanac, "swe", None)
    elif fault == "no_root":
        monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a: None)
    with pytest.raises(EphemerisSourceError) as failure:
        almanac.get_solar_terms_for_year(2000, "UTC")
    assert failure.value.reason == "solar_swiss_files_required"
    assert failure.value.as_result()["retryable"] is False


@pytest.mark.parametrize("year", [1799, 2201])
def test_swiss_public_year_guard_is_not_the_internal_neighbor_allowance(
    swiss_environment, year
):
    with pytest.raises(ValueError, match="1800..2200"):
        almanac.get_solar_terms_for_year(year, "UTC")


def test_swiss_conflicts_with_strict_jpl(swiss_environment, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    with pytest.raises(ValueError, match="Swiss.*conflicts with strict JPL"):
        almanac.get_solar_terms_for_year(2000, "UTC")


@pytest.mark.local_data
def test_same96_references_with_original_native_failures_retained(
    swiss_environment, monkeypatch, tmp_path
):
    manifest = load_ephemeris_manifest()
    for name in ("sepl_12.se1", "semo_12.se1", "sepl_18.se1", "semo_18.se1"):
        verify_ephemeris_bytes(name, (EPHE / name).read_bytes(), manifest)
    expected = {(r["year"], r["index"]): r for r in references()}
    observed = {}
    for mode, directory in (("swiss", EPHE), ("native", tmp_path), ("auto", tmp_path)):
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
        monkeypatch.setenv("SE_EPHE_PATH", str(directory))
        rows = {}
        for origin in (1800, 2200):
            for term in almanac._term_window(
                datetime(origin, 6, 1, tzinfo=timezone.utc), "UTC"
            ):
                key = term.moment.year, almanac.SOLAR_TERM_NAMES.index(term.name)
                if key not in expected:
                    continue
                details = term.solar_model_details
                error = (
                    abs(details["selected_crossing_jd_tt"] - expected[key]["jd_tt"])
                    * 86400
                )
                rows[key] = error
                assert (
                    term.ephemeris_model
                    == {
                        "swiss": "swieph",
                        "native": "fatebridge_complete_moshier_solar_v1",
                        "auto": "fatebridge_de440_solar_v1",
                    }[mode]
                )
                if mode == "swiss":
                    assert {
                        r["slot"]
                        for r in details["native_source_context"]["file_windows"]
                    } == {0, 1}
        assert set(rows) == set(expected) and len(rows) == 96
        observed[mode] = rows
    assert max(observed["swiss"].values()) <= 1.0
    assert max(observed["auto"].values()) <= 1.0
    assert max(observed["native"].values()) <= 1.0
    # The twelve historical Moshier failures are retained separately.
    from scripts.audit_solar_model_reference import audit

    stock_failures = audit()["retained_stock_moshier_failed_ids"]
    assert {tuple(key) for key in stock_failures} == {
        (1799, 3),
        (1799, 4),
        (1799, 5),
        (1799, 6),
        (1799, 7),
        (1799, 11),
        (1799, 18),
        (1799, 23),
        (1800, 5),
        (1800, 21),
        (2200, 7),
        (2201, 8),
    }


@pytest.mark.local_data
def test_canping_swiss_guard_years_and_incomplete_horizon_are_explicit(
    swiss_environment, monkeypatch
):
    from fatebridge.core.canping_solar import projection_boundary
    from fatebridge.core.output_canping_solar import CanpingSolarBoundary

    monkeypatch.setenv("SE_EPHE_PATH", str(EPHE))
    lookup = {(r["year"], r["index"]): r for r in references()}
    for year, origin in ((1799, 1800), (2201, 2200)):
        row = projection_boundary(
            year,
            "UTC",
            origin_civil_year=origin,
            origin_bazi_year=origin - 1,
            horizon=120,
        )
        assert row["record"]["ephemeris_model"] == "swieph"
        CanpingSolarBoundary.model_validate(row)
        assert (
            abs(
                row["record"]["solar_model_details"]["selected_crossing_jd_tt"]
                - lookup[year, 2]["jd_tt"]
            )
            * 86400
            <= 1.0
        )
    with pytest.raises(EphemerisSourceError) as failure:
        projection_boundary(
            2202,
            "UTC",
            origin_civil_year=2200,
            origin_bazi_year=2199,
            horizon=120,
        )
    assert failure.value.reason == "solar_swiss_range"


@pytest.mark.local_data
def test_canping_swiss_preserves_full_schedule_or_fails_without_substitution(
    swiss_environment, monkeypatch
):
    from fatebridge.core.local_techniques.canping import build_canping_result
    from fatebridge.core.output_chinese import CanpingSeries

    monkeypatch.setenv("SE_EPHE_PATH", str(EPHE))
    args = dict(time="09:00", zone="UTC", gender="男", use_true_solar_time=False)
    result = build_canping_result(date="1800-01-01", **args)
    series = result["liunian_series"]
    CanpingSeries.model_validate(series)
    assert len(series["rows"]) == 120 and len(series["year_boundaries"]) == 121
    assert series["year_boundaries"][0]["year"] == 1799
    assert {row["record"]["ephemeris_model"] for row in series["year_boundaries"]} == {
        "swieph"
    }
    with pytest.raises(EphemerisSourceError) as failure:
        build_canping_result(date="2200-05-15", **args)
    assert failure.value.reason == "solar_swiss_range"


@pytest.mark.parametrize("available", [False, True])
@pytest.mark.local_data
def test_swiss_success_and_data_failure_agree_on_three_transports(
    swiss_environment, monkeypatch, available, rest, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(EPHE if available else tmp_path))
    spec = SPECS["liureng_gods"]
    payload = dict(
        analysis_year=1800,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="UTC",
        use_true_solar_time=False,
    )
    fields = ["liureng.calendar_policy", "run_metadata.runtime.solar_term_policy"]
    options = dict(
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
        include_snapshot_text=False,
    )
    response = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
            "--include-snapshot-text",
            "false",
        ],
    )
    outputs = [response.json(), protocol.structured_content, cli]
    if not available:
        assert response.status_code == 503 and protocol.is_error and code == 1
        for output in outputs:
            assert output["error_code"] == "ephemeris_source_inconsistent"
            assert output["issues"][0]["code"] == "solar_swiss_files_required"
        return
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        policy = output["run_metadata"]["runtime"]["solar_term_policy"]
        assert (
            policy["mode"] == "swiss" and policy["analytical_fallback_allowed"] is False
        )
