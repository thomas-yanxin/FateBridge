"""Endpoint selection must retain the exact request and reject bad sources."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core import compressed_ephemeris as c
from fatebridge.core import ephemeris_runtime
from fatebridge.core.ephemeris_installation import has_project_ephemeris_files
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files as native_ephemeris_files,
)


def _ensure_local_ephe(monkeypatch: pytest.MonkeyPatch) -> None:
    current = ephemeris_runtime.configured_ephemeris_path()
    if current and has_project_ephemeris_files(Path(current)):
        return
    fallback = ephemeris_runtime.default_ephe_dir()
    if not fallback:
        pytest.skip("Local Swiss Ephemeris .se1 files unavailable")
    monkeypatch.setenv("SE_EPHE_PATH", fallback)
    ephemeris_runtime.configure_ephemeris_path(fallback)


@pytest.mark.local_data
@pytest.mark.parametrize("restore_newer_moon", [False, True])
def test_actual_overlapping_moon_profiles_remain_explicit_without_external_reset(
    native_ephemeris_files, monkeypatch: pytest.MonkeyPatch, restore_newer_moon: bool
) -> None:
    _ensure_local_ephe(monkeypatch)
    native = ephemeris_runtime.swe
    birth = 2378496.5
    flags = (
        native.FLG_SWIEPH
        | native.FLG_SPEED
        | native.FLG_TRUEPOS
        | native.FLG_XYZ
        | native.FLG_EQUATORIAL
        | native.FLG_J2000
        | native.FLG_ICRS
    )
    baseline = ephemeris_runtime.ephemeris_call("calc", birth, native.SUN, 258)
    ephemeris_runtime.ephemeris_call("calc", birth - 365.0, native.MOON, flags)
    older_end = native.get_current_file_data(1)[2]
    if restore_newer_moon:
        ephemeris_runtime.ephemeris_call("calc", older_end + 1, native.MOON, flags)

    def unexpected_reset(*args):
        raise AssertionError("External solar call reset native configuration")

    with monkeypatch.context() as patch:
        patch.setattr(native, "set_ephe_path", unexpected_reset)
        first = ephemeris_runtime.ephemeris_call("calc", birth, native.SUN, 258)
        second = ephemeris_runtime.ephemeris_call("calc", birth, native.SUN, 258)
    assert first == second
    assert first[1] == baseline[1] == 258
    assert abs(first[0][0] - baseline[0][0]) < 1e-9


@pytest.mark.local_data
def test_owned_solar_source_restores_its_profile_after_off_epoch_history(
    native_ephemeris_files, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ensure_local_ephe(monkeypatch)
    native = ephemeris_runtime.swe
    birth = 2378496.5
    with c.audit_compressed_endpoints():
        first = ephemeris_runtime.ephemeris_call("calc", birth, native.SUN, 258)
        original = deepcopy(c.coordinate_context_evidence())
        ephemeris_runtime.ephemeris_call("calc", birth - 90, native.MOON, 258)
        second = ephemeris_runtime.ephemeris_call("calc", birth, native.SUN, 258)
        restored = deepcopy(c.coordinate_context_evidence())
    assert first == second
    assert original["selected_windows"] == restored["selected_windows"]
    assert (
        original["solar_light_path"]["states"] == restored["solar_light_path"]["states"]
    )
    assert original["physical_jd_tt"] == restored["physical_jd_tt"] == birth
    assert original["private_native_cache_reset"] is True
    assert restored["private_native_cache_reset"] is True


def fixture(monkeypatch, *, endpoint=True, mode="good"):
    monkeypatch.setattr(c, "binding_distribution_version", lambda *args: "2.10.3.2")
    old = ("/private/data/old.se1", 0.0, 100.0, 441)
    new = ("/private/data/new.se1", 90.0, 200.0, 441)
    native = SimpleNamespace(
        FLG_SWIEPH=2,
        FLG_MOSEPH=4,
        FLG_JPLEPH=1,
        FLG_SPEED=256,
        version="2.10.03",
        selected=False,
    )
    calls = []

    def window(slot):
        if mode == "edition" and native.selected:
            return (*new[:3], 431)
        else:
            pass
        return new if native.selected else old

    native.get_current_file_data = window
    native.deltat_ex = lambda *args: 1.0
    first = (tuple(float(i) for i in range(6)), 258)
    corrected = (tuple(float(i) + 0.125 for i in range(6)), 258)

    def invoke(module, operation, args, kwargs):
        calls.append((operation, args, kwargs))
        epoch = args[0] if args else kwargs.get("tjdet", kwargs.get("tjdut"))
        if epoch > 100:
            if mode == "unavailable":
                raise RuntimeError("private path must not escape")
            else:
                pass
            native.selected = mode != "stuck"
            if mode == "fallback":
                return corrected[0], 260
            else:
                pass
        else:
            pass
        if native.selected:
            if mode == "flags":
                return corrected[0], 2
            else:
                pass
            return corrected
        else:
            pass
        return first

    return native, invoke, calls, first, corrected, (100.0 if endpoint else 50.0)


@pytest.mark.parametrize(
    "operation,keywords",
    [("calc", False), ("calc", True), ("calc_ut", False), ("calc_ut", True)],
)
def test_original_operation_and_epoch_are_recalculated(
    monkeypatch: pytest.MonkeyPatch, operation: str, keywords: bool
) -> None:
    native, invoke, calls, first, selected, epoch = fixture(monkeypatch)
    epoch -= operation == "calc_ut"
    args = () if keywords else (epoch, 4, 258)
    kwargs = (
        {"tjdet" if operation == "calc" else "tjdut": epoch, "planet": 4, "flags": 258}
        if keywords
        else {}
    )
    with c.audit_compressed_endpoints():
        result, _ = c._post_call_endpoint_guard(native, operation, args, kwargs, invoke)
        receipt = c.endpoint_context_evidence()
    assert result is selected
    assert calls[0] == calls[-1] == (operation, args, kwargs)
    assert calls[1][0] == "calc" and calls[1][1][0] > 100
    assert receipt["calls_corrected_so_far"] == 1
    record = receipt["records"][0]
    assert record["physical_jd_tt"] == 100
    assert record["original_native_state"] == list(first[0])
    assert record["native_state_changed"]
    assert record["physical_instant_shifted"] is False
    assert "/private" not in str(receipt)
    assert c.endpoint_context_evidence()["calls_corrected_so_far"] is None


@pytest.mark.parametrize("body", [0, 1, 4, 14])
def test_ordinary_native_states_are_returned_without_reset(
    monkeypatch: pytest.MonkeyPatch, body: int
) -> None:
    native, invoke, calls, first, _, epoch = fixture(monkeypatch, endpoint=False)
    native.SUN = 0
    assert (
        c.compressed_endpoint_call(native, "calc", (epoch, body, 258), {}, invoke)
        is first
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("fallback", "model_changed"),
        ("edition", "edition_changed"),
        ("flags", "coordinate_contract_changed"),
        ("unavailable", "compressed_endpoint_unresolved"),
        ("stuck", "compressed_endpoint_unresolved"),
    ],
)
def test_endpoint_cannot_hide_a_failed_context(
    monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    native, invoke, _, _, _, epoch = fixture(monkeypatch, mode=mode)
    with pytest.raises(EphemerisSourceError) as error:
        c.compressed_endpoint_call(native, "calc", (epoch, 4, 258), {}, invoke)
    assert error.value.reason == reason
    assert "/private" not in str(error.value)


def test_unknown_native_version_is_not_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, invoke, _, _, _, epoch = fixture(monkeypatch)
    native.version = "future_version"
    with pytest.raises(EphemerisSourceError) as error:
        c.compressed_endpoint_call(native, "calc", (epoch, 4, 258), {}, invoke)
    assert error.value.reason == "compressed_endpoint_unverified"


@pytest.mark.parametrize("body", [-1, 10, 11, 40, 10001])
def test_analytical_factors_ignore_stale_physical_slots(
    monkeypatch: pytest.MonkeyPatch, body
) -> None:
    native, invoke, calls, first, _, epoch = fixture(monkeypatch)
    assert (
        c.compressed_endpoint_call(native, "calc", (epoch, body, 258), {}, invoke)
        is first
    )
    assert len(calls) == 1


def test_real_binding_ordinary_state_remains_exact() -> None:
    from fatebridge.core import ephemeris_runtime as e

    with e.preserve_ephemeris_path():
        raw = e.swe.calc(2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH | e.swe.FLG_SPEED)
        assert (
            e.ephemeris_call(
                "calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
            )
            == raw
        )


def test_private_preselection_precedes_requested_target_without_inventing_a_before_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, invoke, calls, first, _, epoch = fixture(monkeypatch, endpoint=False)
    resets = []
    native.set_ephe_path = resets.append
    native.SUN, native.MOON, native.FLG_TRUEPOS = 0, 1, 16
    native.EARTH = 14
    for name, value in {
        "FLG_BARYCTR": 16384,
        "FLG_HELCTR": 8,
        "FLG_TOPOCTR": 32768,
        "FLG_XYZ": 4096,
        "FLG_EQUATORIAL": 2048,
        "FLG_J2000": 32,
        "FLG_ICRS": 131072,
        "FLG_SIDEREAL": 65536,
        "FLG_RADIANS": 8192,
        "FLG_NONUT": 64,
        "FLG_NOABERR": 1024,
        "FLG_NOGDEFL": 512,
    }.items():
        setattr(native, name, value)
    original_invoke = invoke

    def invoke(module, operation, args, kwargs):
        value = original_invoke(module, operation, args, kwargs)
        if args[2] & native.FLG_XYZ:
            state = (0.0,) * 6 if args[1] == native.EARTH else value[0]
            return (
                state,
                args[2] | native.FLG_NONUT | native.FLG_NOABERR | native.FLG_NOGDEFL,
            )
        else:
            pass
        return value

    with c.audit_compressed_endpoints():
        result = c.compressed_endpoint_call(native, "calc", (epoch, 4, 258), {}, invoke)
        policy = c.endpoint_context_evidence()
        context = c.coordinate_context_evidence()
    assert result is first
    assert len(resets) == 1
    requested = ("calc", (epoch, 4, 258), {})
    assert calls[0] == ("calc", (epoch, 0, 18), {})
    assert calls[-1] == requested
    assert calls.count(requested) == 1
    assert all(call[1][2] & native.FLG_TRUEPOS for call in calls[1:-1])
    assert context["planet_light_path"]["status"] == "already_covered"
    assert policy["native_cache_resets_so_far"] == 1
    assert context["selected_native_state"] == list(first[0])
    assert context["original_native_state"] is None
    assert context["native_state_changed"] is None
    assert context["physical_instant_shifted"] is False
    assert c.coordinate_context_evidence() is None


@pytest.mark.parametrize(
    "fault", [None, "no_reception", "outside", "different_epoch", "file_changed"]
)
def test_retarded_sequence_retains_all_source_and_epoch_guards(
    monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    native, invoke, calls, _, _, _ = fixture(monkeypatch, endpoint=False)
    windows = (("/private/file.se1", 0.0, 200.0, 441),) * 2
    monkeypatch.setattr(c, "_windows", lambda unused: windows)
    sample = -1.0 if fault == "outside" else 49.0
    with c.audit_compressed_endpoints():
        if fault != "no_reception":
            c._CONTEXT.set(
                c._CompressedEndpointState(
                    audit=c._CONTEXT.get().audit,
                    last_coordinate={
                        "private_native_cache_reset": True,
                        "physical_jd_tt": 50.0,
                        "selected_windows": c._public_windows(windows),
                    },
                )
            )
        else:
            pass

        def run():
            with c.preserve_native_dependency_context(
                50.0, sample, "swieph", native=ephemeris_runtime.swe
            ):
                c.compressed_endpoint_call(
                    native,
                    "calc",
                    (48.0 if fault == "different_epoch" else sample, 4, 258),
                    {},
                    invoke,
                )
                if fault == "file_changed":
                    monkeypatch.setattr(
                        c,
                        "_windows",
                        lambda unused: (("/different/file.se1", 0.0, 200.0, 441),) * 2,
                    )
                else:
                    pass

        if fault is None:
            run()
            assert len(calls) == 1
            assert c.endpoint_context_evidence()["native_cache_resets_so_far"] == 0
        else:
            with pytest.raises(EphemerisSourceError) as error:
                run()
            assert error.value.reason == "dependency_source_window_incoherent"
        assert c._CONTEXT.get().dependency_context is None


@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("endpoint", [False, True])
def test_guard_retains_full_slots_and_the_final_requested_observation(
    monkeypatch: pytest.MonkeyPatch, operation: str, endpoint: bool
) -> None:
    native, original_invoke, calls, first, corrected, epoch = fixture(
        monkeypatch, endpoint=endpoint
    )
    native.SUN = 0
    native.FLG_BARYCTR = 16384
    initial_windows = (
        ("/private/planets-old.se1", 0.0, 100.0, 441),
        ("/private/moon-old.se1", -10.0, 110.0, 441),
    )
    final_windows = (
        ("/private/planets-new.se1", 90.0, 200.0, 441),
        ("/private/moon-new.se1", 80.0, 210.0, 441),
    )
    native.get_current_file_data = lambda slot: (
        final_windows if native.selected else initial_windows
    )[slot]
    flags = 258 | native.FLG_BARYCTR
    original = first[0], flags
    selected = corrected[0], flags

    def invoke(module, name, args, kwargs):
        value = original_invoke(module, name, args, kwargs)
        return original if value is first else selected

    args = (epoch - (operation == "calc_ut"), native.SUN, flags)
    result, observed = c._post_call_endpoint_guard(native, operation, args, {}, invoke)
    expected = final_windows if endpoint else initial_windows
    assert result is (selected if endpoint else original)
    assert observed == expected
    assert len(observed) == 2
    assert c._physical_windows(native, native.SUN, flags, observed) == (expected[0],)
    assert calls[0] == calls[-1] == (operation, args, {})
    if endpoint:
        assert observed != initial_windows
        assert calls[1][0] == "calc" and calls[1][1][0] > 100.0
    else:
        assert len(calls) == 1
