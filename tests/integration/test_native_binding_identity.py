"""Read-only identity caching cannot turn an unsupported motion model into an applied one."""

from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import longitude_motion, runtime
from fatebridge.core.astro.native_identity import binding_distribution_version


def test_identity_lookup_reuses_only_the_same_binary_version_and_resolver(tmp_path):
    binary = tmp_path / "native.so"
    binary.write_bytes(b"original")
    native = SimpleNamespace(__file__=str(binary), version="2.10.03")
    calls = []

    def resolve(name):
        calls.append(name)
        return "2.10.3.2"

    assert [binding_distribution_version(native, resolve) for _ in range(100)] == [
        "2.10.3.2"
    ] * 100
    assert calls == ["pyswisseph"]
    native.version = "unverified"
    assert (
        binding_distribution_version(native, resolve) == "2.10.3.2" and len(calls) == 2
    )
    binary.write_bytes(b"a different binary image")
    assert (
        binding_distribution_version(native, resolve) == "2.10.3.2" and len(calls) == 3
    )

    def replacement(name):
        return "unsupported-binding"

    assert binding_distribution_version(native, replacement) == "unsupported-binding"


@pytest.mark.parametrize("file_present", [False, True])
def test_unknown_binary_identity_keeps_uncached_resolution(file_present, tmp_path):
    native = SimpleNamespace(version="2.10.03")
    if file_present:
        native.__file__ = str(tmp_path / "missing.so")
    calls = []

    def resolve(name):
        calls.append(name)
        return str(len(calls))

    assert binding_distribution_version(native, resolve) == "1"
    assert binding_distribution_version(native, resolve) == "2"


def test_missing_package_never_acquires_a_verified_version(tmp_path):
    binary = tmp_path / "native.so"
    binary.write_bytes(b"one")
    native = SimpleNamespace(__file__=str(binary), version="2.10.03")

    def missing(name):
        raise PackageNotFoundError(name)

    assert binding_distribution_version(native, missing) == "unavailable"


@pytest.mark.parametrize("problem", ["binding", "native"])
def test_warmed_identity_cache_does_not_bypass_unknown_version_guard(
    problem, monkeypatch
):
    swe = runtime.swe
    assert swe is not None
    monkeypatch.setattr(longitude_motion, "version", lambda name: "2.10.3.2")
    # Also warm the same-epoch correction, then invalidate its version identity.
    context = {}
    assert longitude_motion.nutation_obliquity_rate(2451545.0, context) is not None
    assert context["tropical_rotation"]["status"] == "applied"
    if problem == "binding":
        monkeypatch.setattr(longitude_motion, "version", lambda name: "unverified")
    else:
        monkeypatch.setattr(swe, "version", "unverified")

    def must_not_apply(*args, **kwargs):
        raise AssertionError("unknown version performed a correction")

    monkeypatch.setattr(runtime, "ephemeris_call", must_not_apply)
    assert longitude_motion.nutation_obliquity_rate(2451545.0, context) is None
    assert context["tropical_rotation"]["status"] == "not_applied"
    assert context["tropical_rotation"]["reason"] == "unverified_native_version"
