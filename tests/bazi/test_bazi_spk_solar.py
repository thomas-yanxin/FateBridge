"""File-backed high-precision Sun identity, failure semantics and consumers."""

import hashlib
import importlib.metadata
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import almanac, ephemeris_runtime, spk_solar
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.utils.errors import EphemerisSourceError
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.support.transports import SPECS, business, inputs, native
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_boundary_decisions_v1"
KERNEL = ROOT / "ephe/solar-de440.bsp"
if not KERNEL.exists():
    KERNEL = Path("/tmp/fatebridge-fengshui-calendar-v10/de440.bsp")
KERNEL_SHA = "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"


@pytest.fixture
def selected_spk(monkeypatch, tmp_path):
    pytest.importorskip("erfa", reason="optional jpl extra not installed")
    pytest.importorskip("jplephem", reason="optional jpl extra not installed")
    if not KERNEL.exists():
        pytest.skip("Declared official external DE440 kernel not present")
    assert hashlib.sha256(KERNEL.read_bytes()).hexdigest() == KERNEL_SHA
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", ephemeris_runtime._configured_path
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "spk")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(KERNEL))
    yield


def test_spk_is_explicit_and_cannot_relabel_a_native_control(selected_spk, monkeypatch):
    first = almanac.get_solar_terms_for_year(2022, "UTC")
    for term in first:
        assert term.resolution_provider == "jpl_spk"
        assert term.ephemeris_model == spk_solar.MODEL_ID
        assert term.ephemeris_retflags == ()
        assert term.solar_model_details["kernel_sha256"] == KERNEL_SHA
        assert term.solar_model_details["time_argument"].startswith("TDB from TT")
        assert term.solar_model_details["accuracy_certified"] is False
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    assert all(
        t.ephemeris_model == "moshier"
        for t in almanac.get_solar_terms_for_year(2022, "UTC")
    )
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    assert all(
        t.ephemeris_model == "fatebridge_de440_solar_v1"
        for t in almanac.get_solar_terms_for_year(2022, "UTC")
    )
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "spk")
    assert almanac.get_solar_terms_for_year(2022, "UTC") is first


def test_all_four_known_analytic_month_minute_counterexamples_are_corrected(
    selected_spk,
):
    probes = json.loads((FIXTURE / "probes.json").read_text())["rows"]
    for identifier in [
        "1922-清明-floor",
        "1964-惊蛰-floor",
        "1975-芒种-floor",
        "2022-小暑-floor",
    ]:
        row = next(r for r in probes if r["id"] == identifier)
        moment = datetime.fromisoformat(row["civil_utc"])
        expected = row["reference_state_under_frozen_policy"]
        assert (
            almanac.get_bazi_month_context(moment, "UTC")["branch"]
            == expected["month_branch"]
        )
        assert (
            BaZiCalendar.get_four_pillars(moment, "UTC")["month"][1]
            == expected["month_branch"]
        )


def test_explicit_missing_invalid_and_out_of_range_kernel_never_falls_back(
    selected_spk, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(tmp_path / "missing.bsp"))
    with pytest.raises(EphemerisSourceError, match="unavailable"):
        almanac.get_solar_terms_for_year(2022, "UTC")
    bad = tmp_path / "invalid.bsp"
    bad.write_bytes(b"not a DAF/SPK")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(bad))
    with pytest.raises(EphemerisSourceError, match="valid type2"):
        almanac.get_solar_terms_for_year(2022, "UTC")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(KERNEL))
    with pytest.raises(EphemerisSourceError, match="cover"):
        almanac.get_solar_terms_for_year(2700, "UTC")


def test_spk_uses_its_own_source_and_does_not_need_a_native_sun_probe(
    selected_spk, monkeypatch
):
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a, **k: None)
    assert all(
        t.resolution_provider == "jpl_spk"
        for t in almanac.get_solar_terms_for_year(2023, "UTC")
    )


def test_a_different_spk_frame_cannot_be_mislabelled_as_bcrs(selected_spk, monkeypatch):
    from jplephem.spk import SPK

    original = SPK.open

    def non_j2000(*args, **kwargs):
        kernel = original(*args, **kwargs)
        for segment in kernel.segments:
            segment.frame = 17
        return kernel

    spk_solar._load.cache_clear()
    monkeypatch.setattr(SPK, "open", non_j2000)
    with pytest.raises(EphemerisSourceError, match="frame 1"):
        spk_solar.source_receipt()


def test_receipt_identifies_loaded_modules_when_installed_metadata_disappears(
    selected_spk, monkeypatch
):
    before = spk_solar.source_receipt()

    def missing(*args, **kwargs):
        raise importlib.metadata.PackageNotFoundError("simulated installer change")

    monkeypatch.setattr(importlib.metadata.Distribution, "from_name", missing)
    assert spk_solar.source_receipt()["dependencies"] == before["dependencies"]


@pytest.mark.parametrize("key", ["bazi_birth", "liuri_analysis"])
def test_missing_selected_spk_is_a_structured_error_on_three_protocols(
    key, selected_spk, monkeypatch, tmp_path, surface_calls
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(tmp_path / "missing.bsp"))
    spec = SPECS[key]
    payload = inputs(spec)
    http, mcp, code, cli = surface_calls(spec, payload, cli_first=False)
    assert http.status_code == 503 and mcp.is_error and code != 0
    for value in [http.json(), cli]:
        assert value["retryable"] is False
        assert "solar_spk_unavailable" in str(value["issues"])
        assert "bazi_birth" not in value and "liuri_info" not in value


def test_source_change_and_path_alias_are_observed_without_manual_cache_clear(
    selected_spk, monkeypatch, tmp_path
):
    copy = tmp_path / "de440-copy.bsp"
    shutil.copy2(KERNEL, copy)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(copy))
    before = spk_solar.cache_key()
    alias = tmp_path / "alias.bsp"
    alias.symlink_to(copy)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(alias))
    assert spk_solar.cache_key() == before
    # An unused DAF comment byte changes identity, not the orbital vectors.
    with copy.open("r+b") as handle:
        handle.seek(1024)
        byte = handle.read(1)
        handle.seek(1024)
        handle.write(bytes([byte[0] ^ 1]))
    assert spk_solar.cache_key() != before
    with pytest.raises(EphemerisSourceError, match="changed"):
        spk_solar._load(Path(before[0]), before[1]).check_unchanged()


def test_transient_source_aba_cannot_cache_another_kernel_under_the_original_key(
    selected_spk, monkeypatch, tmp_path
):
    second = tmp_path / "second.bsp"
    shutil.copy2(KERNEL, second)
    with second.open("r+b") as handle:
        handle.seek(1024)
        value = handle.read(1)[0]
        handle.seek(1024)
        handle.write(bytes([value ^ 1]))
    original = spk_solar.longitude_crossing_tt
    calls = 0

    def select_other_only_during_one_root(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls != 1:
            return original(*args, **kwargs)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(second))
        try:
            return original(*args, **kwargs)
        finally:
            monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(KERNEL))

    monkeypatch.setattr(
        spk_solar, "longitude_crossing_tt", select_other_only_during_one_root
    )
    almanac.get_solar_terms_for_year.cache_clear()
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        almanac.get_solar_terms_for_year(2031, "UTC")
    monkeypatch.setattr(spk_solar, "longitude_crossing_tt", original)
    recovered = almanac.get_solar_terms_for_year(2031, "UTC")
    assert {t.solar_model_details["kernel_sha256"] for t in recovered} == {KERNEL_SHA}


@pytest.mark.parametrize("topic", TOPICS)
def test_all_ten_bazi_calendar_views_return_actual_spk_on_three_protocols(
    topic, selected_spk, surface_calls
):
    spec = SPECS["bazi_" + topic]
    payload = {**inputs(spec), "use_true_solar_time": False}
    key = "bazi_birth" if topic == "birth" else topic + "_analysis"
    fields = [key + ".calendar_context"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http, mcp, code, cli = surface_calls(
        spec, payload, projection=opts, cli_first=False
    )
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    for result in [http.json(), mcp.structured_content, cli]:
        term = result[key]["calendar_context"]["current_solar_term"]
        assert term["resolution_provider"] == "jpl_spk"
        assert term["solar_model_details"]["kernel_sha256"] == KERNEL_SHA
        assert (
            spk_solar.MODEL_ID
            in result["run_metadata"]["provenance"]["ephemeris_model"]
        )


@pytest.mark.parametrize(
    "key",
    [
        "liuyue_analysis",
        "liuri_analysis",
        "liushi_analysis",
        "sixyao",
        "liureng_gods",
        "jinkou",
    ],
)
def test_shared_timing_and_divination_consumers_preserve_spk_identity(
    key, selected_spk, surface_calls
):
    spec = SPECS[key]
    payload = inputs(spec)
    # All inputs here are existing fictional test fixtures, not user birth data.
    opts = dict(include_snapshot_text=False, response_char_limit=0)
    http, mcp, code, cli = surface_calls(
        spec, payload, projection=opts, cli_first=False
    )
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    assert (
        spk_solar.MODEL_ID
        in http.json()["run_metadata"]["provenance"]["ephemeris_model"]
    )
