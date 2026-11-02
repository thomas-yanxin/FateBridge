"""Canonical source selection keeps native Sun roots independent of warmup."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe
from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
from fatebridge.core.native_solar_source import POLICY_ID, prime_swiss_solar_context

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_native_context_v1"
PIN = "9d98cff244870e19c0fae041485effd6ab12d40d0747ebbbe40470d008f257c4"


def reference():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    f = json.loads((CORPUS / "freeze.json").read_text())
    assert set(p.name for p in CORPUS.iterdir()) == {
        "freeze.json",
        "reference.json",
        "protocol.json",
    }
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in f["files"].items()
    )
    return json.loads((CORPUS / "reference.json").read_text())


@pytest.fixture
def native_files(monkeypatch):
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    assert swe is not None


@pytest.mark.parametrize("case", reference()["rows"], ids=lambda x: x["term"])
@pytest.mark.parametrize("warmup", [-30, 30])
def test_solver_matches_pre_fix_independent_canonical_c_reference(
    case, warmup, native_files
):
    almanac.get_solar_terms_for_year.cache_clear()
    point = case["expected_jd_tt"]
    ephemeris_call("calc", point + warmup, swe.SUN, swe.FLG_SWIEPH)
    term = next(
        t
        for t in almanac.get_solar_terms_for_year(1800, "UTC")
        if t.name == case["term"]
    )
    d = term.solar_model_details
    assert d["selected_crossing_jd_tt"] == case["expected_jd_tt"]
    assert d["root_bracket_tt"] == case["expected_bracket_tt"]
    assert d["native_source_context"]["policy_id"] == POLICY_ID
    for actual, expected in zip(
        d["native_source_context"]["file_windows"], case["file_windows"]
    ):
        assert {k: actual[k] for k in expected} == expected
        assert len(actual["sha256"]) == 64
    require_ren_solar_term(term)


@pytest.mark.parametrize("case", reference()["rows"], ids=lambda x: x["term"])
def test_source_reobservation_after_1799_warmup_selects_current_epoch_files(
    case, native_files
):
    epoch = case["expected_jd_tt"]
    ephemeris_call("calc", epoch - 30, swe.SUN, swe.FLG_SWIEPH)
    value, context = prime_swiss_solar_context(epoch, native=swe, invoke=ephemeris_call)
    assert value[1] == swe.FLG_SWIEPH
    assert [r["filename"] for r in context["file_windows"]] == [
        "sepl_18.se1",
        "semo_18.se1",
    ]
    assert context["physical_target_epoch_shifted"] is False
    assert context["preflight_state_returned_as_target"] is False


def test_analytic_native_probe_keeps_its_new_actual_file_context(
    native_files, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    terms = almanac.get_solar_terms_for_year(1800, "UTC")
    expected = {r["term"]: r for r in reference()["rows"]}
    for term in terms[:2]:
        d = term.solar_model_details
        assert d["native_choice_probe_jd_tt"] == expected[term.name]["expected_jd_tt"]
        assert d["native_choice_probe_source_context"]["policy_id"] == POLICY_ID
        require_ren_solar_term(term)


@pytest.mark.parametrize("mode", ["de440", "spk"])
def test_independent_modes_keep_absent_native_probe_absent(
    mode, native_files, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    if mode == "spk":
        pytest.importorskip("erfa")
        pytest.importorskip("jplephem")
        monkeypatch.setenv(
            "FATEBRIDGE_SOLAR_SPK_FILE", str(ROOT / "ephe/solar-de440.bsp")
        )

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "An independent solver must not acquire an unrequested native probe"
        )

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", forbidden)
    almanac.get_solar_terms_for_year.cache_clear()
    for term in almanac.get_solar_terms_for_year(1800, "UTC")[:2]:
        d = term.solar_model_details
        assert d["native_choice_probe_jd_tt"] is None
        assert "native_choice_probe_source_context" not in d
        require_ren_solar_term(term)


def test_same_epoch_preflight_preserves_operator_clock_and_tidal_settings(native_files):
    # The public getter cannot distinguish automatic from explicit tidal
    # settings. Isolate this mutation rather than guessing how to restore it.
    code = """
from fatebridge.core.ephemeris_runtime import swe, ephemeris_call
from fatebridge.core.native_solar_source import prime_swiss_solar_context
ephemeris_call('calc', 2378500.5, swe.SUN, swe.FLG_SWIEPH)
swe.set_tid_acc(-25.7)
swe.set_delta_t_userdef(42.0 / 86400)
before = (swe.get_tid_acc(), swe.deltat(2378500.5))
prime_swiss_solar_context(2378500.5, native=swe, invoke=ephemeris_call)
assert (swe.get_tid_acc(), swe.deltat(2378500.5)) == before
"""
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
