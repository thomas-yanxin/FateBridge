"""Cycle ephemeris file identity, asteroid contexts and safe consistency errors."""

import os
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import ephemeris_runtime as ephe
from fatebridge.core import human_design_cycle_sources as sources
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.astro import runtime
from fatebridge.core.human_design import chart_at_tt
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design import verify_human_design_reading
from tests.golden.runner import golden_ephemeris

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def private_ephemeris(tmp_path, monkeypatch):
    previous_configured = ephe._configured_path
    directory = tmp_path / "ephe"
    directory.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1", "seas_18.se1"):
        shutil.copy2(ROOT / "ephe" / name, directory / name)
        (directory / name).chmod(0o644)
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    with ephe.preserve_ephemeris_path():
        try:
            yield directory
        finally:
            ephe._configured_path = previous_configured


@pytest.mark.parametrize("tamper", ["file_bytes", "slot_edition", "temporary_path"])
def test_cycle_refuses_changed_source_even_when_every_native_model_flag_stays_swiss(
    private_ephemeris, monkeypatch, tmp_path, tamper
):
    # These controlled eight-day searches test source consistency, not returns.
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 8.0)
    chart = chart_at_tt(2451544.5)
    original = runtime.ephemeris_call
    getter = runtime.swe.get_current_file_data
    native_chiron_calls = 0
    flags = []
    other = tmp_path / "same-data-other-path"
    if tamper == "temporary_path":
        shutil.copytree(private_ephemeris, other)

    def native(operation, *args, **kwargs):
        nonlocal native_chiron_calls
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == 15:
            native_chiron_calls += 1
            flags.append(result[1])
            if tamper == "file_bytes" and native_chiron_calls == 2:
                with (private_ephemeris / "seas_18.se1").open("ab") as handle:
                    handle.write(b"source-change-regression")
            if tamper == "temporary_path":
                if native_chiron_calls == 2:
                    os.environ["SE_EPHE_PATH"] = str(other)
                elif native_chiron_calls == 3:
                    os.environ["SE_EPHE_PATH"] = str(private_ephemeris)
        return result

    def metadata(slot):
        row = getter(slot)
        if tamper == "slot_edition" and slot == 2 and native_chiron_calls >= 2:
            return (*row[:3], row[3] + 1)
        return row

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    monkeypatch.setattr(runtime.swe, "get_current_file_data", metadata)
    try:
        with pytest.raises(EphemerisSourceError) as caught:
            cycles.calculate_cycle_context(
                chart, "2050-01-01T00:00:00Z", require_swiss_files=True
            )
        assert caught.value.reason in {
            "changed_during",
            "edition_changed",
            "physical_configuration_changed",
        }
        assert str(private_ephemeris) not in str(caught.value)
        assert flags and set(flags) == {258}
    finally:
        os.environ["SE_EPHE_PATH"] = str(private_ephemeris)


def test_chiron_keeps_asteroid_file_even_with_analytical_earth_and_stale_planet_slots(
    private_ephemeris, monkeypatch
):
    # Populate physical slots, then explicitly select a directory with only the
    # asteroid file. Native Earth calculations must actually fall to Moshier.
    runtime.ephemeris_call("calc", 2451544.5, 6, 258)
    planets = private_ephemeris / "planet-files"
    planets.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        (private_ephemeris / name).rename(planets / name)
    runtime.swe.close()
    ephe.configure_ephemeris_path(str(private_ephemeris))
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 8.0)
    chart = chart_at_tt(2451544.5)
    result = cycles.calculate_cycle_context(
        chart, "2050-01-01T00:00:00Z", require_swiss_files=False
    )
    source = result["source_evidence"]
    assert {f["slot"] for f in source["files"]} == {2}
    assert {f["filename"] for f in source["files"]} == {"seas_18.se1"}
    assert all(c["native_return_flag_model"] == "moshier" for c in source["contexts"])
    chiron = next(c for c in source["contexts"] if c["body"] == "Chiron")
    assert chiron["status"] == "file_contexts_observed"
    assert len(chiron["file_ids"]) == 1
    assert source["atomic_file_read_proven"] is False


def test_endpoint_hash_detects_byte_change_even_when_stat_signature_is_unchanged(
    private_ephemeris, monkeypatch
):
    runtime.ephemeris_call("calc", 2451544.5, 15, 258)
    source = sources.CycleSourceTrace()
    source.observe("Chiron", "swieph")
    signatures = {p: value[0] for p, value in source._paths.items()}
    monkeypatch.setattr(sources, "_signature", lambda p: signatures[p])
    with (private_ephemeris / "seas_18.se1").open("ab") as handle:
        handle.write(b"endpoint-hash-regression")
    with pytest.raises(EphemerisSourceError) as caught:
        source.finish()
    assert caught.value.reason == "changed_during"


def test_missing_introspection_is_reported_as_unidentified_not_certified(monkeypatch):
    monkeypatch.setattr(runtime, "swe", SimpleNamespace())
    source = sources.CycleSourceTrace()
    source.observe("Chiron", "moshier")
    result = source.finish()
    assert result["status"] == "identity_incomplete"
    assert result["has_unidentified_sources"] is True
    assert result["files"] == []
    assert result["contexts"][0]["status"] == "identity_unavailable"
    assert result["accuracy_certified"] is False


@pytest.fixture(scope="module", params=[False, True], ids=["swiss", "empty"])
def source_run(request):
    spec = next(s for s in CATALOG if s.key == "human_design")
    data = dict(
        birth_year=1980,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        cycle_reference_datetime="2029-07-01T00:00:00Z",
    )
    if request.param:
        with golden_ephemeris():
            return execute_tool(spec, spec.request_model(**data))
    return execute_tool(spec, spec.request_model(**data))


def test_full_source_context_indices_replay_all_evaluations_without_private_paths(
    source_run,
):
    assert (
        verify_human_design_reading(source_run)["status"]
        == "verified_fixed_template_reading"
    )
    source = source_run["cycle_context"]["source_evidence"]
    assert source["endpoint_file_hashes_checked"] is True
    assert str(ROOT) not in str(source)
    for body in source_run["cycle_context"]["bodies"]:
        assert len(body["evaluation_source_context_indices"]) == len(
            body["evaluation_witnesses"]
        )


@pytest.mark.parametrize(
    "tamper",
    [
        "wrong_body_context",
        "missing_index",
        "bool_index",
        "invented_file",
        "has_unidentified",
        "hash_checked",
        "atomic_cert",
        "accuracy_cert",
        "wrong_manifest",
        "unused_context",
    ],
)
def test_rehashing_cannot_certify_or_detach_source_contexts(source_run, tamper):
    run = deepcopy(source_run)
    context = run["cycle_context"]
    source = context["source_evidence"]
    if tamper == "wrong_body_context":
        context["bodies"][0]["evaluation_source_context_indices"][0] = 1
    elif tamper == "missing_index":
        context["bodies"][0]["evaluation_source_context_indices"].pop()
    elif tamper == "bool_index":
        context["bodies"][0]["evaluation_source_context_indices"][0] = False
    elif tamper == "invented_file":
        source["contexts"][0]["file_ids"].append("se1:2:" + "0" * 64)
    elif tamper == "has_unidentified":
        source["has_unidentified_sources"] = True
    elif tamper == "hash_checked":
        source["endpoint_file_hashes_checked"] = False
    elif tamper == "atomic_cert":
        source["atomic_file_read_proven"] = True
    elif tamper == "accuracy_cert":
        source["accuracy_certified"] = True
    elif tamper == "wrong_manifest":
        if source["files"]:
            source["files"][0]["matches_packaged_manifest"] = not source["files"][0][
                "matches_packaged_manifest"
            ]
        else:
            source["contexts"][0]["status"] = "file_contexts_observed"
    else:
        source["contexts"].append(deepcopy(source["contexts"][0]))
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(run)["status"] == "rejected"


@pytest.mark.parametrize("birth_tt", [2378496.5, 2378496.50016])
def test_first_1800_cycles_bind_a_coherent_native_natal_epoch_before_long_searches(
    birth_tt,
):
    chart = chart_at_tt(birth_tt, require_swiss_files=True)
    result = cycles.calculate_cycle_context(
        chart, "1866-01-01T00:00:00Z", require_swiss_files=True
    )
    assert result["status"] == "computed_finite_search"
    for body in result["bodies"]:
        if body["body"] != "Chiron":
            natal = next(
                a
                for a in chart["activations"]["personality"]
                if a["body"] == body["body"]
            )
            assert body["natal_longitude"] == natal["longitude"]


def test_original_natal_observations_are_reused_after_time_conversion_resets_caches(
    monkeypatch,
):
    captured = sources.CycleBirthSources()
    chart = chart_at_tt(
        2378496.5, require_swiss_files=True, source_observer=captured.observe
    )
    cycles.reference_epoch("1866-01-01T00:00:00Z")
    original = runtime.ephemeris_call
    repeated = []

    def native(operation, *args, **kwargs):
        if operation == "calc" and args[0] == 2378496.5 and args[1] in (6, 7):
            repeated.append(args[1])
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    result = cycles.calculate_cycle_context(
        chart, "1866-01-01T00:00:00Z", require_swiss_files=True, birth_sources=captured
    )
    assert result["status"] == "computed_finite_search"
    assert repeated == []
    for body in result["bodies"][:2]:
        original_activation = next(
            a for a in chart["activations"]["personality"] if a["body"] == body["body"]
        )
        assert body["natal_longitude"] == original_activation["longitude"]
