"""Source and input failures must precede any optional native execution."""

import json
import platform

import pytest

from fatebridge.core import vsop2013_solar as solar
from fatebridge.fetch_vsop2013 import source_profile
from fatebridge.utils.errors import EphemerisSourceError


def test_missing_manifest_is_a_nonretryable_source_failure(monkeypatch):
    monkeypatch.delenv(solar.MANIFEST_ENV, raising=False)
    with pytest.raises(EphemerisSourceError) as caught:
        solar.solar_longitudes_tt([2451545.0])
    result = caught.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"][0]["code"] == "solar_vsop2013_unavailable"


@pytest.mark.parametrize(
    "value",
    [True, "2451545", float("nan"), float("inf"), 10**1000],
    ids=["bool", "string", "nan", "inf", "huge_int"],
)
def test_invalid_epoch_precedes_native_loading(value, monkeypatch):
    monkeypatch.setattr(
        solar, "_selected", lambda: pytest.fail("invalid epoch reached C")
    )
    with pytest.raises(ValueError, match="finite numeric"):
        solar.solar_longitudes_tt([value])


@pytest.mark.parametrize(
    "args",
    [
        (True, 2451545.0, 2451555.0),
        (285.0, 0.0, float("nan")),
        (285.0, 2451555.0, 2451545.0),
        (285.0, 1.0, 1.0),
    ],
)
def test_invalid_bracket_precedes_native_loading(args, monkeypatch):
    monkeypatch.setattr(
        solar, "_selected", lambda: pytest.fail("invalid bracket reached C")
    )
    with pytest.raises(ValueError, match="finite target and increasing"):
        solar.longitude_crossing_tt(*args)


def _manifest():
    profile, digest = source_profile()
    return dict(
        model_id=profile["model_id"],
        version=profile["version"],
        abi_version=1,
        source_profile_sha256=digest,
        calculation_source_sha256=profile["calculation_source_sha256"],
        embedded_series_sha256=profile["embedded_series_sha256"],
        system=platform.system(),
        machine=platform.machine(),
        binary="unread-library.so",
        binary_sha256="0" * 64,
    )


@pytest.mark.parametrize(
    "fault",
    [
        {"abi_version": True},
        {"model_id": "moshier"},
        {"source_profile_sha256": "0" * 64},
        {"embedded_series_sha256": "0" * 64},
        {"binary": "../outside.so"},
        {"binary": "/absolute.so"},
    ],
)
def test_wrong_model_or_path_cannot_load_a_library(fault, tmp_path, monkeypatch):
    data = {**_manifest(), **fault}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    monkeypatch.setenv(solar.MANIFEST_ENV, str(path))
    monkeypatch.setattr(
        solar.ctypes, "CDLL", lambda *a, **k: pytest.fail("invalid source loaded")
    )
    with pytest.raises(EphemerisSourceError) as caught:
        solar._Source(path, solar._signature(path))
    assert caught.value.reason == "solar_vsop2013_invalid"


def test_duplicate_manifest_key_is_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"abi_version":1,"abi_version":1}')
    with pytest.raises(EphemerisSourceError) as caught:
        solar._Source(path, solar._signature(path))
    assert caught.value.reason == "solar_vsop2013_invalid"


def test_binary_hash_is_checked_before_dlopen(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    data = _manifest()
    (tmp_path / data["binary"]).write_bytes(b"not a native image")
    path.write_text(json.dumps(data))
    monkeypatch.setenv(solar.MANIFEST_ENV, str(path))
    monkeypatch.setattr(
        solar.ctypes, "CDLL", lambda *a, **k: pytest.fail("corrupt image loaded")
    )
    with pytest.raises(EphemerisSourceError) as caught:
        solar._Source(path, solar._signature(path))
    assert caught.value.reason == "solar_vsop2013_invalid"


@pytest.mark.parametrize(
    "reason",
    [
        "solar_vsop2013_unavailable",
        "solar_vsop2013_invalid",
        "solar_vsop2013_changed",
        "solar_vsop2013_range",
        "solar_vsop2013_calculation",
    ],
)
def test_new_consistency_errors_keep_the_shared_503_contract(reason):
    error = EphemerisSourceError(reason).as_result()
    assert error["error_code"] == "ephemeris_source_inconsistent"
    assert error["status_code"] == 503 and error["retryable"] is False
