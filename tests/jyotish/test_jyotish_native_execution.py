"""Production process boundary and the frozen correct-calculation contract.

All contamination cases must compute exactly as the current clean config.
Rejection is not counted as repair. These are synthetic state-isolation cases,
not independent astronomical or event-prediction samples.
"""

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import native_execution as execution
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.execution_context import call_clock
from fatebridge.core.jyotish import build_india, positions
from fatebridge.services.jyotish import calculate_vimshottari
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401

MODES = [
    "empty",
    "file",
    "alias",
    "stale",
    "manual",
    "stale_small",
    "manual_small",
    "stale_under_lock",
    "transient_geometry",
    "transient_events",
]


def invoke(mode, directory):
    completed = subprocess.run(
        [
            sys.executable,
            str(
                (Path(__file__).parents[2] / "tests/support/jyotish_native_subject.py")
            ),
            mode,
            str(directory),
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("mode", MODES)
def test_valid_input_calculates_like_fresh_current_configuration(tmp_path, mode):
    actual = invoke(mode, tmp_path / "actual")
    expected = invoke(
        "file" if mode in {"file", "alias"} else "empty", tmp_path / "reference"
    )
    assert actual.get("status") == expected["status"] == "complete", actual
    assert actual == expected


def birth():
    return build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        preserve_instant=True,
    )


@pytest.mark.parametrize(
    "zone,year",
    [("America/New_York", 1890), ("Asia/Shanghai", 1500), ("Europe/Paris", 2050)],
)
def test_codec_preserves_pinned_zone_microseconds_and_birth_dto(zone, year):
    moment = datetime(year, 2, 1, 12, 34, 56, 123456, tzinfo=parse_timezone_name(zone))
    original = replace(
        birth(),
        local_datetime=moment,
        recorded_datetime=moment,
        utc_datetime=moment.astimezone(timezone.utc),
        timezone=zone,
    )
    restored = execution.decode(execution.encode(original))
    assert restored == original
    assert restored.local_datetime.tzinfo.key == zone
    assert (
        restored.local_datetime.replace(month=8).utcoffset()
        == moment.replace(month=8).utcoffset()
    )
    mapping = {1: ("datetime", [original]), "map": {"birth": "not a protocol tag"}}
    assert execution.decode(execution.encode(mapping)) == mapping


def test_unrepresentable_inputs_are_rejected_without_arbitrary_deserialization():
    for value in [float("nan"), float("inf"), object(), lambda: None]:
        with pytest.raises((TypeError, ValueError)):
            execution.encode(value)
    with pytest.raises(execution.NativeExecutionError):
        execution.decode(["arbitrary_module", "os.system"])


def test_isolation_does_not_reset_the_callers_native_delta_t(tmp_path):
    e.configure_ephemeris_path(str(tmp_path))
    e.swe.set_delta_t_userdef(400 / 86400)
    try:
        actual = positions(birth())
        assert actual["ascendant"] == pytest.approx(347.5222842087043, abs=1e-10)
        assert e.swe.deltat_ex(2451545.0, e.swe.FLG_SWIEPH) * 86400 == 400
    finally:
        e.swe.set_delta_t_userdef(e.swe.DELTAT_AUTOMATIC)


def test_service_keeps_frozen_clock_and_returns_timezone_reads(tmp_path):
    e.configure_ephemeris_path(str(tmp_path))
    with call_clock("2026-10-22T23:45:00Z") as clock:
        result = calculate_vimshottari(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_longitude=0,
            birth_latitude=0,
            birth_timezone="+05:30",
            divisions=[],
        )
    assert "error" not in result, result
    assert result["analysis_context"]["analysis_datetime"].startswith(
        "2026-10-23T00:00"
    )
    assert clock.reads == ["+05:30"]
    context = result["india"]["profile"]["native_execution_context"]
    assert context["mechanism"] == "fresh_exec_process"
    assert context["lifetime"] == "one_outer_india_operation"


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
@pytest.mark.parametrize("initially_present", [True, False])
def test_auxiliary_creation_or_mutation_during_actual_child_grid_is_rejected(
    tmp_path, filename, initially_present
):
    e.configure_ephemeris_path(str(tmp_path))
    path = tmp_path / filename
    if initially_present:
        path.write_text("# Synthetic empty auxiliary control\n")
    seen = []

    def observe(offset, raw):
        seen.append(offset)
        path.write_text("# Changed during actual child calculation\n")

    with pytest.raises(EphemerisSourceError) as caught:
        build_india(
            birth(),
            divisions=[],
            birth_time_uncertainty_minutes=1,
            _sample_observer=observe,
        )
    assert seen and caught.value.reason == "auxiliary_changed_during"


def test_callback_error_reaps_child_and_next_valid_operation_succeeds(
    tmp_path, monkeypatch
):
    e.configure_ephemeris_path(str(tmp_path))
    calls = []
    children = []
    original = execution.subprocess.Popen

    def started(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(execution.subprocess, "Popen", started)

    def stop(offset, raw):
        calls.append(offset)
        raise RuntimeError("synthetic observer abort")

    with pytest.raises(RuntimeError, match="synthetic observer abort"):
        build_india(
            birth(),
            divisions=[],
            birth_time_uncertainty_minutes=1,
            _sample_observer=stop,
        )
    assert calls
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdout.closed and children[0].stdin.closed
    assert positions(birth())["ascendant"] == pytest.approx(
        347.5222842087043, abs=1e-10
    )


def test_deadline_reaps_child(tmp_path, monkeypatch):
    e.configure_ephemeris_path(str(tmp_path))
    children = []
    original = execution.subprocess.Popen

    def started(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(execution.subprocess, "Popen", started)
    monkeypatch.setattr(execution, "_TIMEOUT", 0.001)
    with pytest.raises(TimeoutError):
        positions(birth())
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdout.closed and children[0].stdin.closed


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-state inspection")
def test_forcibly_killed_owner_does_not_leave_a_computing_child(tmp_path):
    ready = tmp_path / "private-child-ready.json"
    child = None

    def running(pid):
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True
        )
        return result.returncode == 0 and not result.stdout.strip().startswith("Z")

    helper = subprocess.Popen(
        [
            sys.executable,
            str(
                (Path(__file__).parents[2] / "tests/support/jyotish_orphan_subject.py")
            ),
            str(ready),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 180
        while (
            not ready.exists() and helper.poll() is None and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert ready.exists(), "Owner never reached actual child calculation"
        record = json.loads(ready.read_text())
        assert record["owner"] == helper.pid
        child = record["child"]
        assert running(child)
        helper.kill()
        helper.wait(timeout=10)
        deadline = time.monotonic() + 10
        while running(child) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not running(child), "Child continued after owner was SIGKILLed"
    finally:
        if helper.poll() is None:
            helper.kill()
        helper.wait()
        if child is not None and running(child):
            os.kill(child, signal.SIGKILL)
