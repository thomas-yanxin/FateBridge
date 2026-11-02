"""Optional native model failures cannot become another physical source."""

import json

import pytest

from fatebridge.core import aa1996_solar, almanac, solar_model_policy
from fatebridge.fetch_aa1996 import build, source_profile
from fatebridge.utils.errors import EphemerisSourceError


def test_missing_model_is_structured_failure_before_native_fallback(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.delenv(aa1996_solar.MANIFEST_ENV, raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(
        almanac,
        "_solar_term_utc_via_swe",
        lambda *a, **k: pytest.fail("native fallback"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        almanac.get_solar_terms_for_year(2026, "UTC")
    result = caught.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"][0]["code"] == "solar_aa1996_unavailable"


def test_text_receipt_does_not_resolve_unused_aa1996_library(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("unused library")
    )
    assert solar_model_policy.solar_model_environment_receipt(resolve_source=False) == {
        "mode": "aa1996",
        "source_resolution": "not_observed_in_business_output",
        "scope": "Configuration only; no independent solar source was resolved for this receipt. Actual consumed models are reported separately in provenance.",
    }


def test_strict_jpl_conflict_precedes_aa1996_loading(monkeypatch):
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("conflicting model loaded")
    )
    with pytest.raises(ValueError, match="AA1996.*conflicts"):
        solar_term_cache_context(almanac.swe, year=2026)


@pytest.mark.parametrize("year", [1799, 2201])
def test_aa1996_input_years_do_not_expand_silently(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("out-of-policy model loaded")
    )
    with pytest.raises(ValueError, match="1800..2200"):
        solar_model_policy.solar_model_cache_key(year=year)


@pytest.mark.parametrize(
    "value", [True, "2451545", float("nan"), float("inf"), 10**1000]
)
def test_invalid_epoch_never_reaches_native_code(value, monkeypatch):
    monkeypatch.setattr(
        aa1996_solar, "_selected", lambda: pytest.fail("invalid input reached C")
    )
    with pytest.raises(ValueError, match="finite numeric"):
        aa1996_solar.solar_longitudes_tt([value])


@pytest.mark.parametrize(
    "fault",
    [
        {"abi_version": True},
        {"model_id": "moshier"},
        {"source_profile_sha256": "0" * 64},
    ],
)
def test_incorrect_model_claims_are_rejected_before_loading(
    fault, monkeypatch, tmp_path
):
    profile, digest = source_profile()
    import platform

    manifest = dict(
        model_id=profile["model_id"],
        version=profile["version"],
        abi_version=1,
        source_profile_sha256=digest,
        calculation_source_sha256=profile["calculation_source_sha256"],
        system=platform.system(),
        machine=platform.machine(),
        **{},
    )
    manifest.update(fault)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        aa1996_solar.ctypes,
        "CDLL",
        lambda *a, **k: pytest.fail("incorrect model loaded"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"


def test_duplicate_manifest_field_is_not_last_value_wins(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        '{"model_id":"moshier","model_id":"fatebridge_moshier_aa1996_solar_v1"}'
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"


def test_build_rejects_unpinned_bytes_and_keeps_failure_directory(
    tmp_path, monkeypatch
):
    import fatebridge.fetch_aa1996 as builder

    monkeypatch.setattr(builder.platform, "system", lambda: "Darwin")
    bad = tmp_path / "incorrect-source.tar.gz"
    bad.write_bytes(b"not the pinned source")
    destination = tmp_path / "attempt"
    monkeypatch.setattr(
        builder.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("unexpected download"),
    )
    with pytest.raises(ValueError, match="pinned source bytes"):
        build(destination, swiss_archive=bad, aa56_archive=bad, compiler="not-used")
    assert destination.is_dir() and not (destination / "manifest.json").exists()
