"""Internal period endpoints preserve explicit source and public-year policies."""

import json
import platform

import pytest

from fatebridge.core import aa1996_solar, almanac, solar_term_runtime
from fatebridge.core.fengshui.historical_solar import historical_solar_resolution
from fatebridge.fetch_aa1996 import source_profile
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize("year", [1783, 1800, 2000, 2200, 2205])
def test_unused_internal_profile_never_loads_aa1996(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("unused AA1996 source")
    )
    assert historical_solar_resolution(year, "立春", "UTC") is None


def test_historical_aa1996_strict_jpl_conflict_precedes_source_loading(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de441.eph")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("conflicting source loaded")
    )
    with pytest.raises(ValueError, match="AA1996.*conflicts"):
        historical_solar_resolution(1784, "立春", "UTC")


def test_mode_change_during_historical_aa1996_root_is_a_source_failure(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    context = ("frozen-clock", ("aa1996", aa1996_solar.MODEL_ID, ("frozen-source",)))
    monkeypatch.setattr(
        solar_term_runtime, "solar_term_cache_context", lambda *a, **k: context
    )

    def changed(*args, **kwargs):
        assert kwargs["aa1996"] is True and kwargs["expected_aa1996_key"] == (
            "frozen-source",
        )
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        return datetime(1784, 2, 4, tzinfo=timezone.utc), {
            "solar_model_details": {"qualified_solar_term_years": [1784, 2204]}
        }

    monkeypatch.setattr(almanac, "_solar_term_utc_via_analytic", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        historical_solar_resolution(1784, "立春", "UTC")
    assert caught.value.reason == "solar_configuration_changed"


def test_older_build_does_not_silently_acquire_the_extended_working_span(
    tmp_path, monkeypatch
):
    profile, digest = source_profile()
    manifest = dict(
        model_id=profile["model_id"],
        version="1.0.0",
        abi_version=1,
        source_profile_sha256=digest,
        calculation_source_sha256=profile["calculation_source_sha256"],
        system=platform.system(),
        machine=platform.machine(),
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        aa1996_solar.ctypes, "CDLL", lambda *a, **k: pytest.fail("older build loaded")
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"
