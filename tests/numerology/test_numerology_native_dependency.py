"""Selected solar sources are required; configuration-only receipts do not load them."""

import pytest

from fatebridge.core import almanac, analytic_solar, solar_model_policy
from fatebridge.core import solar_term_runtime as runtime
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def native_empty_source(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    analytic_solar.profile.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()
    yield
    analytic_solar.profile.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()


def poison_analytic_profile(monkeypatch, tmp_path, fault):
    package = tmp_path / "analytic-package"
    package.mkdir()
    if fault == "malformed":
        path = package / "data/astronomy/analytic-solar-v1.json"
        path.parent.mkdir(parents=True)
        path.write_text("[")
    analytic_solar.profile.cache_clear()
    monkeypatch.setattr(analytic_solar, "files", lambda _: package)


@pytest.mark.parametrize("fault", ["missing", "malformed"])
@pytest.mark.parametrize("year", [1799, 2026, 2201])
def test_selected_complete_moshier_year_grid_requires_its_frame_source(
    year, fault, monkeypatch, tmp_path
):
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    assert all(
        term.ephemeris_model == "fatebridge_complete_moshier_solar_v1"
        and term.ephemeris_retflags == ()
        and term.solar_model_details["native_moshier_relabelled"] is False
        and term.solar_model_details["accuracy_certified"] is False
        for term in terms
    )
    poison_analytic_profile(monkeypatch, tmp_path, fault)
    almanac.get_solar_terms_for_year.cache_clear()
    with pytest.raises(EphemerisSourceError) as failure:
        almanac.get_solar_terms_for_year(year, "UTC")
    assert failure.value.reason == "solar_analytic_invalid"


@pytest.mark.parametrize("fault", ["missing", "malformed"])
def test_native_configuration_receipt_does_not_resolve_unused_coefficients(
    fault, monkeypatch, tmp_path
):
    poison_analytic_profile(monkeypatch, tmp_path, fault)
    for resolve in [False, True]:
        receipt = solar_model_policy.solar_model_environment_receipt(
            resolve_source=resolve
        )
        assert receipt["mode"] == "native"
        assert receipt["source_resolution"] == "configuration_only"
        assert receipt["analytic_source_resolved"] is False
        assert "model_id" not in receipt and "loaded_coefficient_sha256" not in receipt
    assert analytic_solar.profile.cache_info().misses == 0


@pytest.mark.parametrize("mode", ["analytic", "de440"])
@pytest.mark.parametrize("fault", ["missing", "malformed"])
def test_actually_selected_analytic_or_frame_profile_is_still_required(
    mode, fault, monkeypatch, tmp_path
):
    poison_analytic_profile(monkeypatch, tmp_path, fault)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    with pytest.raises((OSError, ValueError, EphemerisSourceError)):
        almanac.get_solar_terms_for_year(2026, "UTC")
    assert analytic_solar.profile.cache_info().misses > 0


def test_native_key_keeps_native_files_clock_and_jpl_context_dependencies(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        runtime, "effective_ephemeris_search_path", lambda: str(tmp_path)
    )
    monkeypatch.setattr(runtime, "configured_jpl_file", lambda: None)
    clock = ["first-loaded-clock"]
    monkeypatch.setattr(runtime, "loaded_clock_profile_key", lambda: clock[0])
    native = almanac.swe
    before = runtime.solar_term_cache_context(native, year=2026)
    (tmp_path / "sepl_18.se1").write_bytes(b"file identity fixture, not ephemeris data")
    added = runtime.solar_term_cache_context(native, year=2026)
    assert added != before
    clock[0] = "second-loaded-clock"
    changed = runtime.solar_term_cache_context(native, year=2026)
    assert changed != added
    monkeypatch.setattr(runtime, "configured_jpl_file", lambda: "de440.eph")
    assert runtime.solar_term_cache_context(native, year=2026) != changed


def test_native_configuration_cannot_certify_an_incompatible_observed_de440():
    with pytest.raises(ValueError, match="Observed"):
        solar_model_policy.solar_model_environment_receipt(
            observed_de440_models=["fatebridge_de440_solar_v1"]
        )


@pytest.mark.parametrize("tool", ["knowledge_read"])
@pytest.mark.parametrize("fault", ["missing", "malformed"])
def test_unused_source_fault_does_not_block_actual_three_adapters(
    tool, fault, monkeypatch, rest, tmp_path, capsys
):
    poison_analytic_profile(monkeypatch, tmp_path, fault)
    payload = dict(domain="heluo", key="乾為天:1")
    response, code, cli, mcp = run_three(
        SPECS[tool], payload, ["title"], rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in [response.json(), cli, mcp.structured_content]:
        policy = result["run_metadata"]["runtime"]["solar_term_policy"]
        assert (
            policy["mode"] == "native" and policy["analytic_source_resolved"] is False
        )
        assert "model_id" not in policy and "loaded_coefficient_sha256" not in policy
    assert analytic_solar.profile.cache_info().misses == 0


@pytest.mark.parametrize("tool", ["heluo", "canping"])
@pytest.mark.parametrize("fault", ["missing", "malformed"])
def test_selected_frame_fault_blocks_actual_calendar_transports(
    tool, fault, monkeypatch, rest, tmp_path, capsys
):
    poison_analytic_profile(monkeypatch, tmp_path, fault)
    payload = dict(
        date="2000-05-15",
        time="09:00",
        zone="UTC",
        gender="男",
        use_true_solar_time=False,
    )
    response, code, cli, mcp = run_three(
        SPECS[tool], payload, ["analysis_type"], rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "solar_analytic_invalid"}
        ]
