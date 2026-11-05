"""Real file coverage and controlled source changes, never birth-event evidence."""

import copy
import hashlib
import os
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_sources import SourceComparison
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture(autouse=True)
def restore_runtime(monkeypatch):
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def data18(tmp_path):
    root = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR", Path(__file__).resolve().parents[2] / "ephe"
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"):
        path = root / name
        assert (
            path.is_file()
        ), "Acquire pinned Swiss test files separately: python -m fatebridge.fetch_ephe --years 1800 2500"
        verify_ephemeris_bytes(name, path.read_bytes(), manifest)
    target = tmp_path / "private-ephe"
    target.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(root / name, target / name)
        (target / name).chmod(0o644)
    e.configure_ephemeris_path(str(target))
    return root, target


def birth(moment=None):
    if moment is None:
        from datetime import datetime, timezone

        moment = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        preserve_instant=True,
    )


def edge_birth():
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    return birth(datetime_from_tt(e.swe.get_current_file_data(0)[2]))


def test_real_backend_transition_cannot_be_reported_as_birth_time_only_stability(
    data18,
):
    _, directory = data18
    subject = edge_birth()
    before = positions(subject, subject.utc_datetime - timedelta(seconds=60))
    after = positions(subject, subject.utc_datetime + timedelta(seconds=60))
    assert before["ephemeris_by_body"]["Sun"] == "swieph"
    assert after["ephemeris_by_body"]["Sun"] == "moshier"
    with pytest.raises(EphemerisSourceError) as caught:
        build_india(subject, divisions=[], birth_time_uncertainty_minutes=1)
    assert caught.value.reason == "model_changed"
    assert str(directory) not in str(caught.value)


def test_adjacent_same_edition_segments_restore_the_entire_five_point_grid(data18):
    root, directory = data18
    subject = edge_birth()
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(root / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    result = build_india(subject, divisions=[], birth_time_uncertainty_minutes=1)
    sensitivity = result["birth_time_sensitivity"]
    assert sensitivity["sample_count"] == 5
    assert sensitivity["sampled_ephemeris_fallback_bodies"] == []
    sources = sensitivity["source_comparison"]
    assert [r["offset_seconds"] for r in sources["sample_source_indices"]] == [
        -60,
        -30,
        0,
        30,
        60,
    ]
    assert {
        p["model"]
        for s in sources["physical_ephemeris_sources"]
        for p in s["by_factor"].values()
    } == {"swieph"}
    assert {
        f["de_number"]
        for s in sources["physical_ephemeris_sources"]
        for f in s["files"]
    } == {441}


def test_actual_source_identities_are_frame_specific_and_exclude_analytical_nodes(
    data18,
):
    _, directory = data18
    result = build_india(birth(), divisions=[])
    source = result["profile"]["physical_ephemeris_source"]
    assert len(source["by_factor"]) == 14
    assert all("Rahu" not in key and "Ketu" not in key for key in source["by_factor"])
    for file in source["files"]:
        assert (
            file["sha256"]
            == hashlib.sha256((directory / file["filename"]).read_bytes()).hexdigest()
        )
        assert file["matches_packaged_manifest"]
    assert not source["atomic_file_read_proven"] and not source["accuracy_certified"]


def test_all_moshier_grid_is_still_comparable(tmp_path):
    e.configure_ephemeris_path(str(tmp_path))
    result = build_india(birth(), divisions=[], birth_time_uncertainty_minutes=1)
    sources = result["birth_time_sensitivity"]["source_comparison"]
    assert len(sources["sample_source_indices"]) == 5
    assert all(not s["files"] for s in sources["physical_ephemeris_sources"])
    assert {
        p["model"]
        for s in sources["physical_ephemeris_sources"]
        for p in s["by_factor"].values()
    } == {"moshier"}


def test_a_single_frame_body_source_is_readable_with_strict_projection(data18):
    from fatebridge.application.projection import project_fields

    result = {"india": build_india(birth(), divisions=[])}
    path = "india.profile.physical_ephemeris_source.by_factor.ecliptic_Sun.model"
    projected = project_fields(result, [path], strict_fields=True)
    assert projected["india"]["profile"]["physical_ephemeris_source"]["by_factor"][
        "ecliptic_Sun"
    ] == {"model": "swieph"}


@pytest.mark.native_engine_fault
def test_file_hashing_is_shared_across_the_calculation_not_repeated_per_sample(
    data18, monkeypatch
):
    from fatebridge.core.astro import physical_sources

    calls = []
    original = physical_sources._file_digest

    def counted(path):
        calls.append(path.name)
        return original(path)

    monkeypatch.setattr(physical_sources, "_file_digest", counted)
    build_india(birth(), divisions=[], birth_time_uncertainty_minutes=1)
    assert sorted(calls) == ["semo_18.se1", "semo_18.se1", "sepl_18.se1", "sepl_18.se1"]


def test_changed_configuration_cannot_be_hidden_in_a_later_sample(data18, tmp_path):
    _, _ = data18
    changed = False

    def observer(offset, raw):
        nonlocal changed
        if not changed:
            e.configure_ephemeris_path(str(tmp_path / "different-source"))
            changed = True

    with pytest.raises(EphemerisSourceError) as caught:
        build_india(
            birth(),
            divisions=[],
            birth_time_uncertainty_minutes=1,
            _sample_observer=observer,
        )
    assert caught.value.reason == "physical_configuration_changed"


def test_same_file_mutation_is_rejected_at_calculation_endpoints(data18):
    _, directory = data18
    changed = False

    def observer(offset, raw):
        nonlocal changed
        if not changed:
            path = directory / "sepl_18.se1"
            path.write_bytes(path.read_bytes() + b"private-test-change")
            changed = True

    with pytest.raises(EphemerisSourceError) as caught:
        build_india(
            birth(),
            divisions=[],
            birth_time_uncertainty_minutes=1,
            _sample_observer=observer,
        )
    assert caught.value.reason == "changed_during"


def test_per_frame_model_swaps_are_rejected_even_when_aggregate_set_is_unchanged(
    data18,
):
    raw = positions(birth())
    raw["physical_ephemeris_source"]["by_factor"]["equatorial_Sun"].update(
        model="moshier", file_ids=[]
    )
    other = copy.deepcopy(raw)
    original = positions(birth())["physical_ephemeris_source"]["by_factor"]
    other["physical_ephemeris_source"]["by_factor"]["equatorial_Sun"] = original[
        "equatorial_Sun"
    ]
    other["physical_ephemeris_source"]["by_factor"]["equatorial_Moon"].update(
        model="moshier", file_ids=[]
    )
    assert {
        r["model"] for r in raw["physical_ephemeris_source"]["by_factor"].values()
    } == {r["model"] for r in other["physical_ephemeris_source"]["by_factor"].values()}
    comparison = SourceComparison()
    comparison.add(raw)
    with pytest.raises(EphemerisSourceError) as caught:
        comparison.add(other)
    assert caught.value.reason == "model_changed"


@pytest.mark.native_engine_fault
def test_native_failure_without_changed_sources_retains_its_original_error(
    monkeypatch, tmp_path
):
    e.configure_ephemeris_path(str(tmp_path))

    def fail(*args, **kwargs):
        raise RuntimeError("controlled-native-failure")

    monkeypatch.setattr(e.swe, "calc", fail)
    with pytest.raises(RuntimeError, match="controlled-native-failure"):
        positions(birth())


@pytest.mark.parametrize("worker_response_delay", [0, 6], ids=["ready", "slow_start"])
def test_other_thread_configuration_cannot_interleave_the_grid(
    data18, tmp_path, monkeypatch, worker_response_delay
):
    from threading import Event, Thread
    from time import sleep

    from fatebridge.core.astro import native_execution

    attempted, done = Event(), Event()
    errors = []
    later_path = str(tmp_path / "later-configuration")
    original_receive = native_execution._receive
    first_response = True

    def receive(process, deadline):
        nonlocal first_response
        if first_response:
            first_response = False
            sleep(worker_response_delay)
        return original_receive(process, deadline)

    monkeypatch.setattr(native_execution, "_receive", receive)

    def writer():
        try:
            attempted.set()
            e.configure_ephemeris_path(later_path)
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    thread = Thread(target=writer, daemon=True)

    def observer(offset, raw):
        # Start contention once a sample exists. A pre-sample writer timeout
        # measures private-worker startup, not whether the source lock holds.
        if thread.ident is None:
            thread.start()
            assert attempted.wait(5)
        assert not done.wait(0.02)
        assert e.configured_ephemeris_path() == str(data18[1])

    try:
        result = build_india(
            birth(),
            divisions=[],
            birth_time_uncertainty_minutes=1,
            _sample_observer=observer,
        )
    finally:
        if thread.ident is not None:
            thread.join(5)
    assert done.is_set() and not errors
    assert not first_response
    assert not thread.is_alive()
    assert e.configured_ephemeris_path() == later_path
    assert result["birth_time_sensitivity"]["sample_count"] == 5


def test_optional_motion_window_gap_keeps_its_missing_status_instead_of_false_source_error(
    data18,
):
    from datetime import datetime, timezone

    subject = birth(datetime(1900, 1, 1, tzinfo=timezone.utc))
    result = build_india(
        subject,
        divisions=[],
        birth_time_uncertainty_minutes=2,
        cheshta_model="simon1994_j2000",
    )
    assert len(result["birth_time_sensitivity"]["cheshta_model_statuses_on_grid"]) == 2
    assert result["birth_time_sensitivity"]["source_comparison"][
        "optional_motion_models"
    ]
