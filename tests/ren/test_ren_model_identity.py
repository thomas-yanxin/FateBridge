"""Named solar providers need their actual frame and source receipts."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.services.metaphysics import _build_analysis_seed
from fatebridge.utils.errors import EphemerisSourceError
from tests.ren.test_ren_transports import PAYLOAD
from tests.support.transports import SPECS, native, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_model_identity_v1"
FREEZE_SHA = "62d60748aef9269330494d850fc90bb993e2558d0b3552482205c21c81e86534"
SEED_PAYLOAD = {
    k: v for k, v in PAYLOAD.items() if k not in {"is_diurnal", "guiren_profile"}
}


def protocol():
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == FREEZE_SHA
    )
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert set(p.name for p in CORPUS.iterdir()) == {"freeze.json", "protocol.json"}
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in frozen["files"].items()
    )
    return json.loads((CORPUS / "protocol.json").read_text())


@pytest.fixture
def packaged(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    almanac.get_solar_terms_for_year.cache_clear()
    BaZiCalendar._get_four_pillars_cached.cache_clear()
    try:
        yield
    finally:
        almanac.get_solar_terms_for_year.cache_clear()
        BaZiCalendar._get_four_pillars_cached.cache_clear()


def corrupt_dependencies(monkeypatch, field, value):
    original = ren_calendar.get_adjacent_solar_terms

    def corrupt(*args, **kwargs):
        return tuple(
            replace(t, solar_model_details={**t.solar_model_details, field: value})
            for t in original(*args, **kwargs)
        )

    monkeypatch.setattr(ren_calendar, "get_adjacent_solar_terms", corrupt)


@pytest.mark.parametrize("fault", protocol()["faults"], ids=lambda f: f["field"])
def test_de440_frame_source_and_claim_faults_are_rejected(fault, packaged, monkeypatch):
    seed = _build_analysis_seed(**SEED_PAYLOAD)
    corrupt_dependencies(monkeypatch, fault["field"], fault["value"])
    with pytest.raises(EphemerisSourceError) as rejected:
        ren_calendar.require_ren_calendar(seed)
    assert rejected.value.reason == "solar_de440_invalid"


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_corrupt_frame_never_publishes_a_board(
    key, project, packaged, monkeypatch, surface_calls
):
    corrupt_dependencies(monkeypatch, "position_frame", "heliocentric J2000")
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    params, options, flags = {}, {}, []
    if project:
        params = {"fields": "analysis_type", "strict_fields": "true"}
        options = {"fields": ["analysis_type"], "strict_fields": True}
        flags = ["--fields", "analysis_type", "--strict-fields", "true"]
    http, mcp, code, cli = surface_calls(
        spec, payload, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 503 and mcp.is_error and code != 0
    for body in (http.json(), mcp.structured_content, cli):
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert "jinkou" not in body and "liureng" not in body


def test_unused_swiss_solver_failure_does_not_break_actual_de440(packaged, monkeypatch):
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a, **kw: None)
    policy = ren_calendar.require_ren_calendar(_build_analysis_seed(**SEED_PAYLOAD))
    assert {t["provider"] for t in policy["solar_term_dependencies"]} == {"jpl_de440"}
    assert (
        policy["solar_longitude_definition"]["horizons_frame_equivalence_certified"]
        is False
    )


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_missing_model_receipt_remains_a_nonretryable_dependency_failure(
    key, packaged, monkeypatch, surface_calls
):
    corrupt_dependencies(monkeypatch, "coefficient_sha256", None)
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    http, mcp, code, cli = surface_calls(spec, payload, cli_first=False)
    assert http.status_code == 503 and mcp.is_error and code != 0
    for body in (http.json(), mcp.structured_content, cli):
        assert body["error_code"] == "dependency_missing"
        assert body["retryable"] is False
        assert "jinkou" not in body and "liureng" not in body


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_selected_packaged_solver_failure_cannot_publish_linear_boundary(
    key, packaged, monkeypatch, surface_calls
):
    monkeypatch.setattr(
        almanac, "_solar_term_utc_via_analytic", lambda *a, **kw: (None, {})
    )
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    http, mcp, code, cli = surface_calls(spec, payload, cli_first=False)
    assert http.status_code == 503 and mcp.is_error and code != 0
    for body in (http.json(), mcp.structured_content, cli):
        assert body["error_code"] == "dependency_missing"
        assert "jinkou" not in body and "liureng" not in body


@pytest.mark.parametrize(
    "model,flags", [("swieph", (4,)), ("moshier", (2,)), ("jpl", (2,))]
)
def test_native_model_must_agree_with_its_own_return_flags(model, flags, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    term = almanac.get_solar_terms_for_year(2026, "UTC")[0]
    with pytest.raises(RuntimeError, match="模型回执"):
        ren_calendar.require_ren_solar_term(
            replace(term, ephemeris_model=model, ephemeris_retflags=flags)
        )
