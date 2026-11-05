"""Endpoint selection must retain the exact request and reject bad sources."""

from types import SimpleNamespace

import pytest

from fatebridge.core import compressed_ephemeris as c
from fatebridge.core import ephemeris_runtime
from fatebridge.utils.errors import EphemerisSourceError


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
            native.selected = mode != "stuck"
            if mode == "fallback":
                return corrected[0], 260
        if native.selected:
            if mode == "flags":
                return corrected[0], 2
            return corrected
        return first

    return native, invoke, calls, first, corrected, (100.0 if endpoint else 50.0)


@pytest.mark.parametrize(
    "operation,keywords",
    [("calc", False), ("calc", True), ("calc_ut", False), ("calc_ut", True)],
)
def test_original_operation_and_epoch_are_recalculated(
    monkeypatch, operation, keywords
):
    native, invoke, calls, first, selected, epoch = fixture(monkeypatch)
    epoch -= operation == "calc_ut"
    args = () if keywords else (epoch, 4, 258)
    kwargs = (
        {"tjdet" if operation == "calc" else "tjdut": epoch, "planet": 4, "flags": 258}
        if keywords
        else {}
    )
    with c.audit_compressed_endpoints():
        result = c._post_call_endpoint_guard(native, operation, args, kwargs, invoke)
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
def test_ordinary_native_states_are_returned_without_reset(monkeypatch, body):
    native, invoke, calls, first, _, epoch = fixture(monkeypatch, endpoint=False)
    native.SUN = 0
    rebuilt = []

    def external_rebuild(module, operation, args, kwargs, at, flags, initial, call):
        assert (module, operation, args, kwargs, at, flags, call) == (
            native,
            "calc",
            (epoch, body, 258),
            {},
            epoch,
            258,
            invoke,
        )
        assert initial is first
        rebuilt.append(body)
        return initial

    # This unit isolates endpoint dispatch; the source reconstruction has its
    # own native-state and fault-injection tests, rather than this tiny stub.
    monkeypatch.setattr(c, "_external_solar_rebuild", external_rebuild)
    assert (
        c.compressed_endpoint_call(native, "calc", (epoch, body, 258), {}, invoke)
        is first
    )
    assert len(calls) == 1
    assert rebuilt == ([native.SUN] if body == native.SUN else [])


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
def test_endpoint_cannot_hide_a_failed_context(monkeypatch, mode, reason):
    native, invoke, _, _, _, epoch = fixture(monkeypatch, mode=mode)
    with pytest.raises(EphemerisSourceError) as error:
        c.compressed_endpoint_call(native, "calc", (epoch, 4, 258), {}, invoke)
    assert error.value.reason == reason
    assert "/private" not in str(error.value)


def test_unknown_native_version_is_not_certified(monkeypatch):
    native, invoke, _, _, _, epoch = fixture(monkeypatch)
    native.version = "future_version"
    with pytest.raises(EphemerisSourceError) as error:
        c.compressed_endpoint_call(native, "calc", (epoch, 4, 258), {}, invoke)
    assert error.value.reason == "compressed_endpoint_unverified"


@pytest.mark.parametrize("body", [-1, 10, 11, 40, 10001])
def test_analytical_factors_ignore_stale_physical_slots(monkeypatch, body):
    native, invoke, calls, first, _, epoch = fixture(monkeypatch)
    assert (
        c.compressed_endpoint_call(native, "calc", (epoch, body, 258), {}, invoke)
        is first
    )
    assert len(calls) == 1


def test_real_binding_ordinary_state_remains_exact():
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
    monkeypatch,
):
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
def test_retarded_sequence_retains_all_source_and_epoch_guards(monkeypatch, fault):
    native, invoke, calls, _, _, _ = fixture(monkeypatch, endpoint=False)
    windows = (("/private/file.se1", 0.0, 200.0, 441),) * 2
    monkeypatch.setattr(c, "_windows", lambda unused: windows)
    sample = -1.0 if fault == "outside" else 49.0
    with c.audit_compressed_endpoints():
        if fault != "no_reception":
            c._LAST_COORDINATE.set(
                {
                    "private_native_cache_reset": True,
                    "physical_jd_tt": 50.0,
                    "selected_windows": c._public_windows(windows),
                }
            )

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

        if fault is None:
            run()
            assert len(calls) == 1
            assert c.endpoint_context_evidence()["native_cache_resets_so_far"] == 0
        else:
            with pytest.raises(EphemerisSourceError) as error:
                run()
            assert error.value.reason == "dependency_source_window_incoherent"
        assert c._DEPENDENCY_CONTEXT.get() is None
