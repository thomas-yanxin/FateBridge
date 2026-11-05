"""Sequential source switches must not trust another thread's stale path cache."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import local
from types import SimpleNamespace

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from tests.support.transports import AS_OF, SPECS, business, call_cli, native, rest


@pytest.mark.parametrize("storage", ["process_global", "thread_local"])
def test_managed_paths_reconcile_shared_and_per_thread_native_state(
    monkeypatch, storage
):
    state = SimpleNamespace() if storage == "process_global" else local()
    applied = []

    def set_path(path):
        state.path = path
        applied.append(path)

    def read(*args):
        return state.path

    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(runtime, "_THREAD_STATE", local())
    monkeypatch.setattr(
        runtime, "swe", SimpleNamespace(set_ephe_path=set_path, deltat_ex=read)
    )
    monkeypatch.setattr(runtime, "_configured_path", "/configured")
    assert runtime.ephemeris_call("deltat_ex", 2451545, 2) == "/configured"
    with ThreadPoolExecutor(max_workers=1) as worker:
        # Even a TLS library must initialize a new thread on the same path.
        assert (
            worker.submit(runtime.ephemeris_call, "deltat_ex", 2451545, 2).result()
            == "/configured"
        )
        before = len(applied)
        assert (
            worker.submit(runtime.ephemeris_call, "deltat_ex", 2451545, 2).result()
            == "/configured"
        )
        assert len(applied) == before
        with monkeypatch.context() as switch:
            switch.setenv("SE_EPHE_PATH", "/temporary")
            assert (
                worker.submit(runtime.ephemeris_call, "deltat_ex", 2451546, 2).result()
                == "/temporary"
            )
        # The original thread's local signature still says/configured. A
        # process-global native path was changed by the other thread anyway.
        assert runtime.ephemeris_call("deltat_ex", 2451547, 2) == "/configured"

        def preserve_third_party_path():
            with runtime.preserve_ephemeris_path():
                set_path("/third-party")
            return state.path

        with monkeypatch.context() as switch:
            switch.setenv("SE_EPHE_PATH", "/preserved")
            assert worker.submit(preserve_third_party_path).result() == "/preserved"
        assert runtime.ephemeris_call("deltat_ex", 2451547.5, 2) == "/configured"
        runtime.configure_ephemeris_path("/managed")
        assert (
            worker.submit(runtime.ephemeris_call, "deltat_ex", 2451548, 2).result()
            == "/managed"
        )
    before = len(applied)
    assert runtime.ephemeris_call("deltat_ex", 2451549, 2) == "/managed"
    assert runtime.ephemeris_call("deltat_ex", 2451550, 2) == "/managed"
    assert len(applied) <= before + 1


@pytest.fixture
def swiss_files(monkeypatch):
    root = Path(__file__).resolve().parents[2] / "ephe"
    if not all((root / n).is_file() for n in ("sepl_18.se1", "semo_18.se1")):
        pytest.skip("Requires the actual local Swiss Sun/Moon files")
    previous = runtime.configured_ephemeris_path()
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(root))
    runtime.configure_ephemeris_path(str(root))
    try:
        yield root
    finally:
        monkeypatch.undo()
        runtime.configure_ephemeris_path(previous)


def pollute_other_thread(monkeypatch, empty):
    with monkeypatch.context() as switch:
        switch.setenv("SE_EPHE_PATH", str(empty))
        with ThreadPoolExecutor(max_workers=1) as worker:
            value, flags = worker.submit(
                runtime.ephemeris_call,
                "calc",
                2451545.5,
                runtime.swe.SUN,
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
            ).result()
    assert flags == runtime.swe.FLG_MOSEPH | runtime.swe.FLG_SPEED
    return value


@pytest.mark.local_data
def test_actual_native_source_returns_to_swiss_after_other_thread_empty_path(
    swiss_files, monkeypatch, tmp_path
):
    _, first_flags = runtime.ephemeris_call(
        "calc", 2451545, runtime.swe.SUN, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    )
    assert first_flags == runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    pollute_other_thread(monkeypatch, tmp_path)
    _, flags = runtime.ephemeris_call(
        "calc", 2451546, runtime.swe.SUN, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    )
    assert flags == runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    assert Path(runtime.swe.get_current_file_data(0)[0]).parent == swiss_files


@pytest.mark.local_data
def test_real_human_design_adapters_keep_actual_swiss_flags_after_thread_pollution(
    swiss_files, monkeypatch, tmp_path, capsys, rest
):
    spec = SPECS["human_design"]
    payload = dict(
        birth_year=1980,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
    )
    outputs = []
    for surface in ("rest", "mcp", "cli"):
        empty = tmp_path / surface
        empty.mkdir()
        pollute_other_thread(monkeypatch, empty)
        if surface == "rest":
            response = rest.post(
                spec.rest_path,
                json=payload,
                params={"as_of": AS_OF, "response_char_limit": 0},
            )
            assert response.status_code == 200
            body = response.json()
        elif surface == "mcp":
            response = asyncio.run(native(spec, payload))
            assert not response.is_error
            body = response.structured_content
        else:
            code, body = call_cli(
                spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
            )
            assert code == 0
        spec.output_model.model_validate(body)
        for rows in body["activations"].values():
            sun = next(row for row in rows if row["body"] == "Sun")
            assert sun["return_flags"] == runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
            assert sun["ephemeris_model"] == "swieph"
        outputs.append(business(body))
    assert outputs[0] == outputs[1] == outputs[2]
