"""Real fallback paths, independent TT roots, and civil-clock policy fidelity."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.cli import run
from fatebridge.core import almanac
from fatebridge.core.astro.time_scales import leap_table
from fatebridge.core.fengshui.calendar import lichun_resolution
from fatebridge.services.fengshui import calculate_annual_stars
from fatebridge.services.run_metadata import attach_run_metadata
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.fengshui_calendar import audit_lichun_reference
from tests.fixtures.fengshui import payload
from tests.support.fengshui_transports import mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client

FOLDER = Path(__file__).parents[1] / "data/fengshui_lichun_tt"
REFERENCE = json.loads((FOLDER / "reference.json").read_text())


def test_all_421_independent_tt_crossings_retain_the_original_values_and_gate():
    manifest = json.loads((FOLDER / "hashes.json").read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
    assert len(REFERENCE["rows"]) == 421
    assert sum(1800 <= row["year"] <= 2200 for row in REFERENCE["rows"]) == 401
    assert REFERENCE["protocol"]["coverage_derivation"]["first_period_start"] == 1784
    assert REFERENCE["protocol"]["coverage_derivation"]["last_period_end"] == 2204
    assert REFERENCE["protocol"]["numeric_implementation_tolerance_seconds"] == 1.0
    audit = audit_lichun_reference(REFERENCE)
    assert audit["rows"] == audit["matched"] == 421
    assert audit["all_scoped_tt_checks_passed"]
    assert audit["reality_prediction"] == "not_tested"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "reordered",
        "nonfinite",
        "boolean_tt",
        "boolean_bracket",
        "looser_gate",
    ],
)
def test_missing_or_corrupt_references_and_relaxed_gate_cannot_manufacture_acceptance(
    fault,
):
    changed = deepcopy(REFERENCE)
    if fault == "missing":
        changed["rows"].pop()
    elif fault == "duplicate":
        changed["rows"][1] = changed["rows"][0]
    elif fault == "reordered":
        changed["rows"].reverse()
    elif fault == "nonfinite":
        changed["rows"][0]["jd_tt"] = float("nan")
    elif fault == "boolean_tt":
        changed["rows"][0]["jd_tt"] = True
    elif fault == "boolean_bracket":
        changed["rows"][0]["bracket_width_seconds"] = False
    else:
        changed["protocol"]["numeric_implementation_tolerance_seconds"] = 5
    with pytest.raises(ValueError):
        audit_lichun_reference(changed)


def test_one_changed_reference_row_is_reported_as_a_failed_comparison():
    changed = deepcopy(REFERENCE)
    changed["rows"][0]["jd_tt"] += 60 / 86400
    audit = audit_lichun_reference(changed)
    assert audit["rows"] == 421 and audit["matched"] == 420
    assert audit["failed_count"] == 1 and not audit["all_scoped_tt_checks_passed"]
    assert not audit["comparisons"][0]["within_tolerance"]


@pytest.fixture(params=["missing_dependency", "solver_failure"])
def unavailable_native(monkeypatch, request):
    # These faults target Swiss, not the independent packaged DE440 model.
    # Keep the default model's numerical audit above unmodified.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    if request.param == "missing_dependency":
        monkeypatch.setattr(almanac, "swe", None)
    else:
        monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *args: None)
    almanac.get_solar_terms_for_year.cache_clear()
    yield
    almanac.get_solar_terms_for_year.cache_clear()


def test_real_fallback_never_passes_independent_numeric_acceptance(unavailable_native):
    audit = audit_lichun_reference(REFERENCE)
    assert audit["rows"] == audit["failed_count"] == 421
    assert audit["matched"] == 0 and not audit["all_scoped_tt_checks_passed"]
    assert audit["maximum_absolute_difference_seconds"] is None
    assert all(row["difference_seconds"] is None for row in audit["comparisons"])


@pytest.mark.parametrize("name", ["annual_stars", "minggua", "xuankong_natal"])
def test_unavailable_native_crossing_is_rejected_on_every_public_surface(
    unavailable_native, monkeypatch, tmp_path, capsys, name
):
    inputs = (
        {"effective_year": 2026}
        if name == "annual_stars"
        else {"birth_date": "2000-07-01", "gender_convention": "male"}
    )
    if name == "xuankong_natal":
        inputs = payload(name)
        inputs["period"] = {
            "basis": "construction_completion",
            "effective_event_year": 2004,
            "evidence": "synthetic unavailable-provider test",
        }
    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    path = tmp_path / "request.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and protocol.is_error and code == 1
    for body in (http.json(), protocol.structured_content, cli):
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert body["issues"][0]["code"] == "solar_native_unavailable"
        assert "layers" not in body


@pytest.mark.parametrize(
    "provider",
    ["linear_fallback", "linear_1900_fallback", "new_approximation_provider"],
)
def test_receipt_uses_resolution_semantics_instead_of_provider_spelling(provider):
    record = {
        "moment": "2026-02-04T00:00:00+00:00",
        "provider": provider,
        "approximate": True,
        "precision_scope": "explicit_resolution_record",
    }
    assert (
        attach_run_metadata(
            {"boundary_resolution": record}, tool_name="fengshui_annual_stars"
        )["run_metadata"]["engine_is_approximate"]
        is True
    )


@pytest.mark.parametrize(
    "year,historical,future",
    [
        (1800, True, False),
        (1965, False, False),
        (2026, False, False),
        (2028, False, True),
        (2204, False, True),
    ],
)
def test_actual_tt_and_civil_time_policies_are_exposed(year, historical, future):
    resolution = lichun_resolution(year, "UTC")
    assert not resolution["approximate"]
    basis = resolution["time_basis"]
    assert basis["root_time_scale"] == "TT"
    assert basis["historical_ut1_convention"] is historical
    assert basis["future_leap_seconds_assumed_unchanged"] is future
    assert basis["leap_table_expires_at"] == leap_table()["expires_at"]


@pytest.mark.parametrize(
    "year,wording", [(1900, "UT1/ΔT约定"), (2028, "按冻结闰秒表不变假设")]
)
def test_snapshot_preserves_historical_or_conditional_civil_clock_meaning(
    year, wording
):
    result = calculate_annual_stars(effective_year=year)
    assert result["status"] == "complete"
    assert wording in result["snapshot_text"]


def test_confirmed_year_does_not_invent_a_solver_or_clock_assumption():
    from fatebridge.services.fengshui import calculate_minggua

    result = calculate_minggua(effective_birth_year=1900, gender_convention="male")
    time = result["layers"]["minggua"]["time_context"]
    assert time["interval_scope"] == "not_needed_for_confirmed_effective_birth_year"
    assert "time_basis" not in time
    assert "UT1/ΔT约定" not in result["snapshot_text"]
