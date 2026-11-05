"""Clock-source regression, managed interleaving and provenance checks."""

import copy
import threading
from collections import Counter
from datetime import datetime

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import birth_clock
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.physical_sources import _file_digest
from fatebridge.core.astro.solar_sources import SunSourceCohort
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.core.jyotish import build_india
from fatebridge.services import astrology, jyotish
from fatebridge.utils.errors import EphemerisSourceError
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401


def subject(basis):
    return build_astro_birth_info(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_microsecond=123456,
        birth_clock_basis=basis,
        birth_longitude=10,
        birth_latitude=0,
        preserve_instant=True,
    )


@pytest.mark.parametrize("radius", [None, 0, 1])
def test_existing_LAT_birth_cannot_silently_change_its_clock_source(
    data18, tmp_path, radius
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    birth = subject("local_apparent_solar")
    assert birth.clock_conversion["solar_ephemeris_models_observed"] == ["moshier"]
    e.configure_ephemeris_path(str(full))
    with pytest.raises(EphemerisSourceError) as caught:
        build_india(birth, divisions=[], birth_time_uncertainty_minutes=radius)
    assert caught.value.reason == "birth_clock_source_mismatch"


@pytest.mark.parametrize("radius", [None, 0, 1])
@pytest.mark.parametrize("model", ["empty", "full"])
def test_unchanged_LAT_source_remains_valid(data18, tmp_path, radius, model):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty if model == "empty" else full))
    birth = subject("local_apparent_solar")
    actual = build_india(birth, divisions=[], birth_time_uncertainty_minutes=radius)
    assert actual["status"] == "complete"


@pytest.mark.parametrize("radius", [None, 0, 1])
def test_LMT_is_not_incorrectly_assigned_a_solar_position_dependency(
    data18, tmp_path, radius
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    birth = subject("local_mean_solar")
    e.configure_ephemeris_path(str(full))
    assert (
        build_india(birth, divisions=[], birth_time_uncertainty_minutes=radius)[
            "status"
        ]
        == "complete"
    )


def arguments():
    return dict(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_microsecond=123456,
        birth_clock_basis="local_apparent_solar",
        birth_longitude=10,
        birth_latitude=0,
        divisions=[],
        birth_time_uncertainty_minutes=1,
    )


def invoke(service):
    if service == "periods":
        return jyotish.calculate_vimshottari(**arguments(), analysis_year=2026)
    return astrology.calculate_core_chart_analysis(
        **arguments(), chart_variant="india_chart"
    )


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("service", ["natal", "periods"])
def test_writer_cannot_interleave_between_clock_resolution_and_native_build(
    data18, tmp_path, monkeypatch, service
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    module, name = (
        (jyotish, "build_astro_birth_info")
        if service == "periods"
        else (astrology, "_build_birth_info")
    )
    original = getattr(module, name)
    started, finished = threading.Event(), threading.Event()
    threads = []

    def construct(*args, **kwargs):
        birth = original(*args, **kwargs)
        assert current_source_session() is not None

        def writer():
            started.set()
            e.configure_ephemeris_path(str(full))
            finished.set()

        thread = threading.Thread(target=writer)
        threads.append(thread)
        thread.start()
        assert started.wait(2)
        assert not finished.wait(0.03)
        return birth

    monkeypatch.setattr(module, name, construct)
    try:
        result = invoke(service)
    finally:
        for thread in threads:
            thread.join(3)
    assert finished.is_set() and not any(t.is_alive() for t in threads)
    assert "error" not in result, result
    profile = result["india"]["profile"]
    assert profile["ephemeris_by_body"]["Sun"] == "moshier"
    assert (
        profile["clock_context"]["source_comparison"]["physical_instant_shifted"]
        is False
    )
    assert (
        profile["clock_context"]["source_comparison"]["status"]
        == "compatible_observed_sun_contexts"
    )
    assert e.configured_ephemeris_path() == str(full)
    assert current_source_session() is None


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("service", ["natal", "periods"])
def test_same_thread_configuration_mutation_returns_source_error(
    data18, tmp_path, monkeypatch, service
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    module, name = (
        (jyotish, "build_astro_birth_info")
        if service == "periods"
        else (astrology, "_build_birth_info")
    )
    original = getattr(module, name)

    def changed(*args, **kwargs):
        birth = original(*args, **kwargs)
        e.configure_ephemeris_path(str(full))
        return birth

    monkeypatch.setattr(module, name, changed)
    result = invoke(service)
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "physical_configuration_changed"}
    ]
    assert current_source_session() is None


@pytest.mark.native_engine_fault
def test_native_file_failure_after_clock_is_diagnosed_by_outer_endpoint_hash(
    data18, monkeypatch
):
    _, full = data18
    original = jyotish.build_astro_birth_info

    def changed(*args, **kwargs):
        birth = original(*args, **kwargs)
        with (full / "sepl_18.se1").open("ab") as file:
            file.write(b"changed after clock conversion")
        return birth

    monkeypatch.setattr(jyotish, "build_astro_birth_info", changed)
    result = invoke("periods")
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "changed_during"}
    ]
    assert str(full) not in str(result)
    assert current_source_session() is None


@pytest.mark.native_engine_fault
def test_clock_iteration_grid_and_replay_share_one_endpoint_verified_file_trace(
    data18, monkeypatch
):
    import fatebridge.core.astro.physical_sources as physical

    calls = []

    def counted(path):
        calls.append(path.name)
        return _file_digest(path)

    monkeypatch.setattr(physical, "_file_digest", counted)
    replay_calls = []
    original = birth_clock.resolve_solar_birth_clock

    def resolved(*args, **kwargs):
        replay_calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(birth_clock, "resolve_solar_birth_clock", resolved)
    result = invoke("periods")
    assert "error" not in result, result
    assert Counter(calls) == {"sepl_18.se1": 2, "semo_18.se1": 2}
    # One original, one nominal replay and two interval endpoints, not a
    # complete clock inversion for every native sample.
    assert len(replay_calls) == 4
    grid = result["india"]["birth_time_sensitivity"]
    assert (
        len(grid["source_comparison"]["sample_source_indices"]) == grid["sample_count"]
    )
    assert (
        result["vimshottari"]["birth_time_sensitivity"]["evaluated_sample_count"]
        == grid["sample_count"]
    )


def test_every_actual_LAT_sun_call_including_roundtrip_has_source_evidence(data18):
    birth = subject("local_apparent_solar")
    receipt = birth.clock_conversion
    sources = receipt["solar_source_comparison"]
    rows = sources["observations"]
    assert len(rows) == receipt["solar_model_call_count"]
    assert [r["phase"] for r in rows].count("final") == 1
    assert [r["phase"] for r in rows].count("roundtrip") == 1
    assert any(r["phase"] == "inversion" for r in rows)
    for row in rows:
        source = sources["physical_ephemeris_sources"][row["source_index"]]
        assert set(source["by_factor"]) == {"equatorial_Sun"}
        assert source["by_factor"]["equatorial_Sun"]["model"] == "swieph"
        assert source["atomic_file_read_proven"] is False
        assert source["accuracy_certified"] is False
        assert all("sha256" in f and f["de_number"] == 441 for f in source["files"])


def test_legacy_identity_is_not_fabricated_and_old_library_is_not_silently_certified(
    data18,
):
    birth = subject("local_apparent_solar")
    birth.clock_conversion.pop("solar_source_comparison")
    result = build_india(birth, divisions=[])
    checked = result["profile"]["clock_context"]["source_comparison"]
    assert checked["status"] == "original_sun_identity_incomplete"
    assert checked["original_sun_identity_recorded"] is False
    birth.clock_conversion["swisseph_version"] = "different-declared-library"
    with pytest.raises(EphemerisSourceError) as error:
        build_india(birth, divisions=[])
    assert error.value.reason == "birth_clock_source_mismatch"


def test_source_switch_smaller_than_numeric_tolerance_is_still_not_the_same_source(
    data18, tmp_path
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    birth = build_astro_birth_info(
        birth_year=2024,
        birth_month=3,
        birth_day=10,
        birth_hour=2,
        birth_minute=30,
        birth_clock_basis="local_apparent_solar",
        birth_longitude=10,
        birth_latitude=0,
        preserve_instant=True,
    )
    e.configure_ephemeris_path(str(full))
    current, _ = birth_clock.resolve_solar_birth_clock(
        datetime(2024, 3, 10, 2, 30), 10, "local_apparent_solar"
    )
    assert abs((current - birth.utc_datetime).total_seconds()) <= 0.0002
    with pytest.raises(EphemerisSourceError) as error:
        build_india(birth, divisions=[])
    assert error.value.reason == "birth_clock_source_mismatch"


@pytest.mark.parametrize("predicate", ["edition", "hash"])
def test_sun_context_comparison_handles_new_auxiliary_slots_without_rewriting_earlier_reads(
    data18, predicate
):
    original = subject("local_apparent_solar").clock_conversion[
        "solar_source_comparison"
    ]["physical_ephemeris_sources"][0]
    assert len({f["slot"] for f in original["files"]}) == 2
    early = copy.deepcopy(original)
    early["files"] = [f for f in early["files"] if f["slot"] == 0]
    early["by_factor"]["equatorial_Sun"]["file_ids"] = [f["id"] for f in early["files"]]
    cohort = SunSourceCohort()
    cohort.add(early)
    cohort.add(original)
    assert len(cohort.sources[0]["files"]) == 1
    changed = copy.deepcopy(original)
    target = next(f for f in changed["files"] if f["slot"] == 0)
    target["de_number" if predicate == "edition" else "sha256"] = (
        440 if predicate == "edition" else "different-content"
    )
    with pytest.raises(EphemerisSourceError) as error:
        cohort.add(changed)
    assert error.value.reason == (
        "edition_changed" if predicate == "edition" else "changed_across"
    )


def test_non_indian_route_does_not_enter_the_indian_source_session(monkeypatch):
    observed = []

    def stopped(*args, **kwargs):
        observed.append(current_source_session())
        raise ValueError("stop before unrelated chart computation")

    monkeypatch.setattr(astrology, "_build_birth_info", stopped)
    result = astrology.calculate_core_chart_analysis(
        **{
            k: v
            for k, v in arguments().items()
            if k not in {"birth_clock_basis", "birth_microsecond", "birth_second"}
        },
        chart_variant="chart",
    )
    assert "error" in result
    assert observed == [None]
