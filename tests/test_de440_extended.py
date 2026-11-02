"""Original-source identity, range policy and derived cache dependency regressions."""

import gzip
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import almanac, de440_solar, solar_model_policy
from fatebridge.utils.errors import EphemerisSourceError

BASE = Path(__file__).parent / "fixtures/de440_extended_v42"
DATA = Path(de440_solar.__file__).parents[1] / "data/astronomy"
NEW = "fatebridge_de440_solar_extended_v1"
OLD = "fatebridge_de440_solar_v1"
REFERENCE = json.loads((BASE / "reference-points.json").read_text())


@pytest.fixture(autouse=True)
def controlled_source(monkeypatch, tmp_path):
    original = de440_solar._profile
    original.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    for name in ["FATEBRIDGE_JPL_FILE", "FATEBRIDGE_SOLAR_SPK_FILE"]:
        monkeypatch.delenv(name, raising=False)
    yield
    original.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()


def refuse_profile(monkeypatch, wanted):
    original = de440_solar._profile

    def load(profile_id=de440_solar.MODEL_ID):
        if profile_id == wanted:
            raise EphemerisSourceError("solar_de440_invalid")
        return original(profile_id)

    monkeypatch.setattr(de440_solar, "_profile", load)


def test_original_profiles_retain_their_exact_frozen_bytes():
    manifest = json.loads((BASE / "freeze.json").read_text())
    for filename, expected in manifest["old_profile_sha256"].items():
        assert hashlib.sha256((DATA / filename).read_bytes()).hexdigest() == expected


def test_new_receipt_preserves_source_identity_and_qualification_scope():
    receipt = de440_solar.source_receipt(NEW)
    assert receipt["model_id"] == NEW
    assert receipt["software_solar_term_years"] == [1684, 2304]
    assert receipt["public_auto_and_de440_input_years"] == [1700, 2300]
    assert receipt["source_kernel_sha256"] == (
        "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
    )
    assert receipt["reference_event_table_used"] is False
    assert receipt["accuracy_certified"] is False
    assert receipt["native_moshier_relabelled"] is False
    assert set(receipt["segment_coverage_tdb_jd"]) == {"0->3", "3->399", "0->10"}
    receipt["software_solar_term_years"][0] = 1
    assert de440_solar.source_receipt(NEW)["software_solar_term_years"] == [1684, 2304]


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("year", [1700, 1799, 1800, 2200, 2201, 2300])
def test_public_years_match_independent_reference_and_named_profile(
    mode, year, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    expected_model = OLD if 1800 <= year <= 2200 else NEW
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for row in [r for r in REFERENCE["rows"] if r["year"] == year]:
        term = terms[row["index"]]
        almanac.require_calculated_solar_term(term)
        assert term.ephemeris_model == expected_model
        assert term.solar_model_details["model_id"] == expected_model
        assert (
            term.solar_model_details["numerical_epoch_representation"]
            == "explicit_two_part_tt"
        )
        assert (
            abs(
                (term.solar_model_details["selected_crossing_jd_tt"] - row["jd_tt"])
                * 86400
            )
            <= 1
        )


@pytest.mark.parametrize("year", [1699, 2301])
def test_unselected_extension_does_not_become_a_native_year_dependency(
    year, monkeypatch
):
    refuse_profile(monkeypatch, NEW)
    assert {
        t.ephemeris_model for t in almanac.get_solar_terms_for_year(year, "UTC")
    } == {"moshier"}
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(year, "UTC")


@pytest.mark.parametrize("year", [1800, 2000, 2200])
def test_established_profile_and_its_guard_years_do_not_load_extension(
    year, monkeypatch
):
    refuse_profile(monkeypatch, NEW)
    almanac.get_solar_term_environment_key(year=year)
    previous, following = almanac.get_adjacent_solar_terms(
        datetime.fromisoformat(f"{year}-01-01T12:00:00+00:00"), "UTC"
    )
    assert previous.ephemeris_model == following.ephemeris_model == OLD


@pytest.mark.parametrize("year", [1700, 2300])
def test_extended_input_context_does_not_load_unused_old_data(year, monkeypatch):
    refuse_profile(monkeypatch, OLD)
    almanac.get_solar_term_environment_key(year=year)
    previous, following = almanac.get_adjacent_solar_terms(
        datetime.fromisoformat(f"{year}-01-01T12:00:00+00:00"), "UTC"
    )
    assert previous.ephemeris_model == following.ephemeris_model == NEW
    receipt = solar_model_policy.solar_model_environment_receipt(
        observed_de440_models=[NEW]
    )
    assert receipt["model_id"] == NEW


@pytest.mark.parametrize("year", [1799, 2201])
@pytest.mark.parametrize("missing", [OLD, NEW])
def test_derived_mixed_year_cache_requires_both_consumed_profiles(
    year, missing, monkeypatch
):
    refuse_profile(monkeypatch, missing)
    with pytest.raises(EphemerisSourceError):
        almanac.get_solar_term_environment_key(year=year)


def test_mixed_profile_receipt_does_not_invent_one_global_model():
    receipt = solar_model_policy.solar_model_environment_receipt(
        observed_de440_models=[OLD, NEW]
    )
    assert receipt["source_resolution"] == "observed_multiple_packaged_profiles"
    assert "model_id" not in receipt
    assert {r["model_id"] for r in receipt["sources"]} == {OLD, NEW}


@pytest.mark.parametrize("models", [[], ["moshier"], ["forged_de440_model"]])
def test_receipt_rejects_unobserved_or_unrecognized_profile_claims(models):
    with pytest.raises(ValueError):
        solar_model_policy.solar_model_environment_receipt(observed_de440_models=models)


def test_explicit_models_and_strict_jpl_do_not_silently_use_new_profile(monkeypatch):
    refuse_profile(monkeypatch, NEW)
    for mode in ["analytic", "aa1996"]:
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
        with pytest.raises(ValueError, match="1800..2200"):
            if mode == "aa1996":
                solar_model_policy.solar_model_cache_key(year=1700)
            else:
                solar_model_policy.analytic_selected(1700, "moshier")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "required-native.eph")
    assert solar_model_policy.solar_model_cache_key(year=1700) == (
        "auto",
        "native_strict_jpl",
    )


@pytest.mark.parametrize("fault", ["missing", "crc", "frame", "scope", "rehash"])
def test_invalid_selected_extension_fails_closed(fault, tmp_path, monkeypatch):
    folder = tmp_path / "package/data/astronomy"
    folder.mkdir(parents=True)
    for name in [
        "de440-solar-extended-v1.json",
        "de440-solar-extended-v1.bin.gz",
        "geocentric-tdb-v1.json",
    ]:
        shutil.copyfile(DATA / name, folder / name)
    metadata = folder / "de440-solar-extended-v1.json"
    binary = folder / "de440-solar-extended-v1.bin.gz"
    manifest = json.loads(metadata.read_text())
    if fault == "missing":
        binary.unlink()
    elif fault == "crc":
        raw = bytearray(binary.read_bytes())
        raw[-1] ^= 1
        binary.write_bytes(raw)
    elif fault == "frame":
        manifest["segments"][0]["frame"] = 2
    elif fault == "scope":
        manifest["software_solar_term_years"] = [1, 9999]
    else:
        data = bytearray(gzip.decompress(binary.read_bytes()))
        data[40] ^= 1
        packed = gzip.compress(data, mtime=0)
        binary.write_bytes(packed)
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        manifest["uncompressed_sha256"] = hashlib.sha256(data).hexdigest()
        for segment in manifest["segments"]:
            begin = segment["offset_bytes"]
            segment["sha256"] = hashlib.sha256(
                data[begin : begin + segment["bytes"]]
            ).hexdigest()
    metadata.write_text(json.dumps(manifest))
    monkeypatch.setattr(de440_solar, "files", lambda *_: tmp_path / "package")
    with pytest.raises(EphemerisSourceError) as error:
        almanac.get_solar_terms_for_year(1700, "UTC")
    assert error.value.reason == "solar_de440_invalid"


def test_adjacent_context_keeps_its_selected_profile_separate_from_standalone_year():
    ordinary = almanac.get_solar_terms_for_year(1799, "UTC")
    guarded = almanac._solar_terms_for_context_year(1799, "UTC", 1800)
    assert ordinary[0].ephemeris_model == NEW
    assert guarded[0].ephemeris_model == OLD
    assert guarded[0].solar_model_details["adjacent_boundary_context_year"] == 1800
    assert guarded[0].solar_model_details["solar_model_input_years"] == [1800, 2200]
