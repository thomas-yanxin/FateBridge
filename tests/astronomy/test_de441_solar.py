"""Independent original-JPL propagation, including every earlier failed event."""

import gzip
import json
import math
from pathlib import Path

import pytest

from fatebridge.core import almanac, de441_solar
from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
from tests.support.ephemeris_context import empty_ephemeris_path

REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/solar_de441_v1/reference.json.gz"
        ).read_bytes()
    )
)
# Union of the previous revision's 16 native-file and 21 original-DE440
# one-second failures, plus the original1200 supplementary crossing.
PREVIOUS_FAILED_EVENTS = {
    (1200, 0),
    (2240, 13),
    (2240, 14),
    (2246, 18),
    (2260, 6),
    (2274, 12),
    (2274, 13),
    (2275, 14),
    (2280, 22),
    (2287, 12),
    (2287, 13),
    (2287, 14),
    (2292, 3),
    (2292, 5),
    (2292, 6),
    (2292, 7),
    (2292, 8),
    (2292, 9),
    (2292, 23),
    (2294, 2),
    (2294, 19),
    (2294, 20),
    (2298, 11),
    (2298, 12),
    (2298, 13),
}

AVAILABILITY = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1]
            / "data/solar_de441_availability_v1/reference.json.gz"
        ).read_bytes()
    )
)


def test_full_independent_cohort_meets_the_original_angular_gate():
    assert REFERENCE["production_imported"] is False
    assert len(REFERENCE["rows"]) == 14905
    assert REFERENCE["angular_tolerance_arcseconds"] == 0.001
    for row in REFERENCE["rows"]:
        actual = de441_solar.solar_longitude(row["jd_tt"])
        error = math.remainder(actual - row["longitude"], 360) * 3600
        assert abs(error) <= REFERENCE["angular_tolerance_arcseconds"], row


def test_previous_failed_events_use_actual_calendar_roots_with_unchanged_gate(
    monkeypatch,
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    assert REFERENCE["TT_tolerance_seconds"] == 1.0
    rows = {
        (r["year"], r["index"]): r
        for r in REFERENCE["rows"]
        if (r["year"], r["index"]) in PREVIOUS_FAILED_EVENTS
    }
    assert set(rows) == PREVIOUS_FAILED_EVENTS
    with empty_ephemeris_path():
        for (year, index), row in rows.items():
            term = almanac.get_solar_terms_for_year(year, "UTC")[index]
            assert term.resolution_provider == de441_solar.PROVIDER
            assert term.ephemeris_model == de441_solar.MODEL_ID
            assert term.ephemeris_retflags == ()
            assert almanac.is_calculated_solar_term(term)
            details = term.solar_model_details
            actual = details["selected_crossing_jd_tt"]
            assert (
                abs((actual - row["jd_tt"]) * 86400)
                <= REFERENCE["TT_tolerance_seconds"]
            ), row
            low, high = details["root_bracket_tt"]
            assert math.nextafter(low, math.inf) == high == actual
            assert (
                math.remainder(de441_solar.solar_longitude(low) - row["longitude"], 360)
                < 0
            )
            assert (
                math.remainder(
                    de441_solar.solar_longitude(high) - row["longitude"], 360
                )
                >= 0
            )


def test_named_source_receipt_distinguishes_the_loaded_product_from_original_JPL():
    details = de441_solar.model_details()
    assert details["model_id"] == "fatebridge_de441_solar_v1"
    assert details["source_model_id"] == "bounded_de441_planetary_source_v3"
    assert details["original_JPL_file_loaded_at_runtime"] is False
    assert details["native_moshier_relabelled"] is False
    assert details["reference_values_used_at_runtime"] is False
    assert details["accuracy_certified"] is False
    assert (
        details["frame_model"]
        == "vondrak_scalar_obliquity_full_simon77_iau2006_bias_v1"
    )
    assert all(
        len(details[k]) == 64
        for k in (
            "coefficient_sha256",
            "frame_coefficient_sha256",
            "nutation_coefficient_sha256",
            "tdb_coefficient_sha256",
        )
    )


def test_remote_and_endpoint_roots_against_independent_original_records(monkeypatch):
    from fatebridge.core.metaphysics.ren_term_longitude import validate_term_longitude

    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    assert AVAILABILITY["production_imported"] is False
    assert AVAILABILITY["TT_tolerance_seconds"] == 1.0
    assert AVAILABILITY["angular_tolerance_arcseconds"] == 0.001
    assert len(AVAILABILITY["rows"]) == 220
    with empty_ephemeris_path():
        for row in AVAILABILITY["rows"]:
            year, index = row["year"], row["index"]
            if year in (0, 10000):
                context = 1 if year == 0 else 9999
                term = almanac._solar_terms_for_context_year(
                    year, "UTC", context, term_index=index
                )[0]
            else:
                term = almanac.get_solar_terms_for_year(year, "UTC")[index]
            assert term.ephemeris_model == de441_solar.MODEL_ID
            assert term.resolution_provider == de441_solar.PROVIDER
            assert term.ephemeris_retflags == ()
            assert term.ephemeris_library_version is None
            assert almanac.is_calculated_solar_term(term)
            validate_term_longitude(
                name=term.name,
                provider=term.resolution_provider,
                model=term.ephemeris_model,
                flags=term.ephemeris_retflags,
                library_version=term.ephemeris_library_version,
                details=term.solar_model_details,
                complete=True,
            )
            details = term.solar_model_details
            assert abs(details["selected_crossing_jd_tt"] - row["jd_tt"]) * 86400 <= 1
            assert (
                abs(
                    math.remainder(
                        de441_solar.solar_longitude(row["jd_tt"]) - row["longitude"],
                        360,
                    )
                )
                * 3600
                <= 0.001
            )


@pytest.mark.parametrize("year", [2000, 6000, 9999])
def test_bundled_source_and_atomic_clock_work_without_optional_native_library(
    monkeypatch, year
):
    from fatebridge.core import ephemeris_runtime
    from fatebridge.core.astro import runtime

    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    with empty_ephemeris_path():
        expected = almanac.get_solar_terms_for_year(year, "UTC")
        with monkeypatch.context() as absent:
            for owner in (almanac, ephemeris_runtime, runtime):
                absent.setattr(owner, "swe", None)
            actual = almanac.get_solar_terms_for_year(year, "UTC")
            assert [
                t.solar_model_details["selected_crossing_jd_tt"] for t in actual
            ] == [t.solar_model_details["selected_crossing_jd_tt"] for t in expected]
            assert all(t.ephemeris_library_version is None for t in actual)
            for term in actual:
                require_ren_solar_term(term)


def test_missing_historical_clock_is_not_filled_with_an_approximate_tt(monkeypatch):
    from fatebridge.core import ephemeris_runtime
    from fatebridge.core.astro import runtime
    from fatebridge.core.solar_term_clock import SolarTermClockError

    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    with empty_ephemeris_path():
        with monkeypatch.context() as absent:
            for owner in (almanac, ephemeris_runtime, runtime):
                absent.setattr(owner, "swe", None)
            with pytest.raises(SolarTermClockError) as failure:
                almanac.get_solar_terms_for_year(1, "UTC")
            assert failure.value.reason == "solar_root_clock_unavailable"


@pytest.mark.parametrize("policy", ["swiss", "native_jpl", "corrupt_native_file"])
def test_source_failures_do_not_resolve_the_unselected_bundle(
    monkeypatch, tmp_path, policy
):
    from fatebridge.utils.errors import EphemerisSourceError

    def unused(*args):
        raise AssertionError("A strict or corrupt source cannot become DE441")

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if policy == "swiss":
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "swiss")
    elif policy == "native_jpl":
        from fatebridge.core.solar_model_policy import (
            solar_model_cache_key,
            solar_model_environment_receipt,
        )

        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing-de441.eph")
        # The cache must not load an unused source in strict JPL mode either.
        monkeypatch.setattr(de441_solar, "model_details", unused)
        assert solar_model_cache_key(year=6000) == ("native", "native_strict_jpl")
        receipt = solar_model_environment_receipt()
        assert receipt["mode"] == "native"
        assert receipt["source_selection"] == "strict_native_jpl"
    else:
        (tmp_path / "sepl_60.se1").write_bytes(b"broken ephemeris header\n")
    monkeypatch.setattr(de441_solar, "solar_longitude", unused)
    with pytest.raises(EphemerisSourceError) as failure:
        almanac.get_solar_terms_for_year(2000 if policy == "swiss" else 6000, "UTC")
    assert (
        failure.value.reason
        == {
            "swiss": "solar_swiss_files_required",
            "native_jpl": "jpl_file_unavailable",
            "corrupt_native_file": "solar_native_unavailable",
        }[policy]
    )


@pytest.mark.parametrize("epoch", [math.nan, math.inf, -math.inf])
def test_nonfinite_reception_is_rejected_at_the_solar_boundary(epoch):
    with pytest.raises(ValueError, match="finite"):
        de441_solar.solar_longitude(epoch)
