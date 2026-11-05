"""Calendar audits hold configured native/time inputs as well as package files."""

import os
from types import SimpleNamespace

import pytest


@pytest.fixture
def environment(monkeypatch, tmp_path):
    from fatebridge.core import (
        ephemeris_runtime,
        solar_model_policy,
        solar_term_runtime,
    )

    state = {"path": str(tmp_path), "mode": "auto", "coefficient": "a", "clock": "b"}
    monkeypatch.setattr(
        ephemeris_runtime, "effective_ephemeris_search_path", lambda: state["path"]
    )
    monkeypatch.setattr(
        solar_model_policy,
        "solar_model_environment_receipt",
        lambda: {
            "mode": state["mode"],
            "model_id": "synthetic-policy",
            "loaded_coefficient_sha256": state["coefficient"],
        },
    )
    monkeypatch.setattr(
        solar_term_runtime, "loaded_clock_profile_key", lambda: state["clock"]
    )
    return tmp_path, state


@pytest.mark.parametrize("name", ["swe_deltat.txt", "sedeltat.txt"])
def test_deltat_inventory_changes_for_same_size_same_mtime_bytes(environment, name):
    from fatebridge.services.replay_metadata import ephemeris_inventory

    directory, _ = environment
    p = directory / name
    p.write_text("2026 100.0\n")
    stamp = p.stat()
    before = ephemeris_inventory()
    assert "0/" + name in before["files"]
    p.write_text("2026 101.0\n")
    os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert ephemeris_inventory()["sha256"] != before["sha256"]
    assert str(directory) not in str(before)


@pytest.mark.parametrize("separator", [";", ";;"])
def test_inventory_covers_native_semicolon_search_paths(
    tmp_path, monkeypatch, separator
):
    from fatebridge.services.replay_metadata import _ephemeris_inventory

    a, b = tmp_path / "first", tmp_path / "second"
    a.mkdir()
    b.mkdir()
    (a / "sepl_18.se1").write_bytes(b"synthetic-first-file")
    (b / "sedeltat.txt").write_text("2026 100.0\n")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "seasnam.txt").write_text("not in the selected search roots")
    inventory = _ephemeris_inventory(str(a) + separator + str(b))
    assert set(inventory["files"]) == {"0/sepl_18.se1", "1/sedeltat.txt"}


@pytest.mark.parametrize("name", ["swe_deltat.txt", "sedeltat.txt"])
@pytest.mark.parametrize("operation", ["add", "modify", "remove"])
def test_both_deltat_names_invalidate_the_solar_year_cache_identity(
    monkeypatch, tmp_path, name, operation
):
    from fatebridge.core import solar_model_policy, solar_term_runtime

    p = tmp_path / name
    if operation != "add":
        p.write_text("2026 100.0\n")
    monkeypatch.setattr(
        solar_term_runtime, "effective_ephemeris_search_path", lambda: str(tmp_path)
    )
    monkeypatch.setattr(solar_term_runtime, "configured_jpl_file", lambda: None)
    monkeypatch.setattr(solar_term_runtime, "loaded_clock_profile_key", lambda: "clock")
    monkeypatch.setattr(
        solar_model_policy,
        "solar_model_cache_key",
        lambda: ("auto", "synthetic", "coeff"),
    )
    native = SimpleNamespace(version="synthetic")
    before = solar_term_runtime.solar_term_cache_context(native)
    if operation == "add":
        p.write_text("2026 100.0\n")
    elif operation == "remove":
        p.unlink()
    else:
        stamp = p.stat()
        p.write_text("2026 101.0\n")
        os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert solar_term_runtime.solar_term_cache_context(native) != before


def guard_api():
    from fatebridge.validation.meihua_runtime_guard import (
        capture_calendar_runtime,
        verify_calendar_runtime,
    )

    return capture_calendar_runtime, verify_calendar_runtime


@pytest.mark.parametrize("name", ["swe_deltat.txt", "sedeltat.txt"])
@pytest.mark.parametrize("operation", ["add", "modify", "remove"])
def test_calendar_runtime_guard_rejects_unbundled_deltat_changes(
    environment, name, operation
):
    directory, _ = environment
    p = directory / name
    if operation != "add":
        p.write_text("2026 100.0\n")
    capture, verify = guard_api()
    receipt = capture()
    if operation == "add":
        p.write_text("2026 100.0\n")
    elif operation == "remove":
        p.unlink()
    else:
        stamp = p.stat()
        p.write_text("2026 101.0\n")
        os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(ValueError, match="runtime inputs changed during audit"):
        verify(receipt)


@pytest.mark.parametrize(
    "field,value", [("mode", "analytic"), ("coefficient", "c"), ("clock", "c")]
)
def test_configuration_and_loaded_clock_inputs_cannot_change(environment, field, value):
    _, state = environment
    capture, verify = guard_api()
    receipt = capture()
    state[field] = value
    with pytest.raises(ValueError, match="runtime inputs changed during audit"):
        verify(receipt)


def test_equal_bytes_at_another_search_path_do_not_hide_a_context_switch(
    environment, tmp_path
):
    directory, state = environment
    (directory / "swe_deltat.txt").write_text("2026 100.0\n")
    other = directory / "other"
    other.mkdir()
    (other / "swe_deltat.txt").write_bytes((directory / "swe_deltat.txt").read_bytes())
    capture, verify = guard_api()
    receipt = capture()
    state["path"] = str(other)
    with pytest.raises(ValueError, match="runtime inputs changed during audit"):
        verify(receipt)
    assert str(directory) not in str(receipt)


def test_stable_inventory_is_a_configured_input_guard_not_a_native_read_set(
    environment,
):
    capture, verify = guard_api()
    receipt = capture()
    verify(receipt)
    assert receipt["guard_id"] == "meihua_calendar_runtime_guard_v1"
    assert receipt["actual_native_read_set_attested"] is False
    assert receipt["physical_accuracy_established"] is False


@pytest.mark.parametrize("change", ["filename", "bytes"])
def test_selected_native_jpl_inputs_are_guarded(environment, monkeypatch, change):
    from fatebridge.core import jpl_ephemeris

    directory, _ = environment
    chosen = {"name": "synthetic.eph"}
    p = directory / chosen["name"]
    p.write_bytes(b"synthetic-byte-1")
    monkeypatch.setattr(jpl_ephemeris, "configured_jpl_file", lambda: chosen["name"])
    capture, verify = guard_api()
    receipt = capture()
    if change == "filename":
        chosen["name"] = "other.eph"
    else:
        stamp = p.stat()
        p.write_bytes(b"synthetic-byte-2")
        os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(ValueError, match="runtime inputs changed during audit"):
        verify(receipt)


@pytest.mark.parametrize("name", ["baseline", "supported", "tam1900", "hko2100"])
def test_all_calendar_audits_capture_runtime_before_reference_reads(
    name, monkeypatch, tmp_path
):
    from fatebridge.validation import meihua, meihua_calendar

    module = meihua if name == "baseline" else meihua_calendar

    def rejected():
        raise ValueError("controlled_runtime_guard_failure")

    monkeypatch.setattr(module, "capture_calendar_runtime", rejected, raising=False)
    with pytest.raises(ValueError, match="controlled_runtime_guard_failure"):
        if name == "baseline":
            module.audit_meihua(tmp_path)
        elif name == "supported":
            module.audit_supported_calendar(tmp_path, tmp_path)
        elif name == "tam1900":
            module.audit_tam_1900(tmp_path)
        else:
            module.audit_hko_2100_supplement(tmp_path)
