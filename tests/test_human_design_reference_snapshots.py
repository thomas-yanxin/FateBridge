"""Every served source identity belongs to the exact reviewed bytes read."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import human_design_references as refs
from fatebridge.core.astro import native_execution, runtime
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source(tmp_path, monkeypatch):
    original = refs._read
    data = {name: original(name) for name in refs.REFERENCE_NAMES}
    refs.clear_reference_cache()

    def read(name):
        value = data[name]
        if isinstance(value, Exception):
            raise EphemerisSourceError("human_design_reference_unavailable") from value
        return value

    monkeypatch.setattr(refs, "_read", read)
    yield data
    refs.clear_reference_cache()


def test_all_reviewed_catalogues_remain_exact_and_every_runtime_reader_is_bound():
    assert len(refs.REFERENCE_NAMES) == len(refs.REFERENCE_SHA256) == 12
    for name, digest in refs.REFERENCE_SHA256.items():
        raw = (ROOT / "src/fatebridge/data/human_design" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        with refs.coherent_human_design_references():
            assert refs.reference_bytes(name) == raw
            assert refs.reference_sha256(name) == digest
            assert refs.reference_data(name) == json.loads(raw)


@pytest.mark.parametrize("name", refs.REFERENCE_NAMES)
@pytest.mark.parametrize(
    "mutation", ["different_bytes", "unavailable", "memory_mutation", "cache_clear"]
)
def test_all_catalogues_reject_mid_operation_mutation(source, name, mutation):
    with pytest.raises(EphemerisSourceError) as caught:
        with refs.coherent_human_design_references():
            raw = refs.reference_bytes(name)
            record = refs.reference_data(name)
            if mutation == "memory_mutation":
                record["unexpected_mutation"] = True
            else:
                source[name] = (
                    FileNotFoundError("private/source/path")
                    if mutation == "unavailable"
                    else raw + b"\n"
                )
                if mutation == "cache_clear":
                    refs.clear_reference_cache()
            # Even a cache clear cannot swap a second revision into this view.
            assert refs.reference_bytes(name) == raw
            assert refs.reference_sha256(name) == hashlib.sha256(raw).hexdigest()
    assert caught.value.reason == (
        "human_design_reference_unavailable"
        if mutation == "unavailable"
        else "human_design_reference_changed"
    )


@pytest.mark.parametrize("name", refs.REFERENCE_NAMES)
def test_valid_but_unreviewed_file_cannot_supply_a_new_cold_source(source, name):
    source[name] += b"\n"
    with pytest.raises(EphemerisSourceError) as caught:
        with refs.coherent_human_design_references():
            refs.reference_data(name)
    assert caught.value.reason == "human_design_reference_identity_mismatch"


@pytest.mark.parametrize(
    "raw",
    [
        b"invalid",
        b"[]",
        b'{"duplicate":1,"duplicate":2}',
        b'{"number":NaN}',
        b'{"number":Infinity}',
    ],
)
def test_corrupt_or_ambiguous_json_is_not_accepted_as_source(source, raw):
    name = refs.REFERENCE_NAMES[0]
    source[name] = raw
    with pytest.raises(EphemerisSourceError) as caught:
        with refs.coherent_human_design_references():
            refs.reference_data(name)
    assert caught.value.reason == "human_design_reference_invalid"


def test_old_loaded_data_cannot_take_a_later_file_hash(source):
    name = "profile-2026-reference.json"
    raw = source[name]
    doc = refs.reference_data(name)
    source[name] += b"\n"
    assert refs.reference_data(name) is doc
    assert refs.reference_sha256(name) == hashlib.sha256(raw).hexdigest()
    with pytest.raises(EphemerisSourceError):
        with refs.coherent_human_design_references():
            refs.reference_data(name)


def test_unused_optional_catalogue_is_not_required_and_nested_view_is_pinned(source):
    source["cycles-2026-reference.json"] = FileNotFoundError("unused")
    with refs.coherent_human_design_references():
        first = refs.reference_data("profile-2026-reference.json")
        with refs.coherent_human_design_references():
            assert refs.reference_data("profile-2026-reference.json") is first


def test_original_mixed_profile_receipt_is_preserved_and_rejected_without_recalculation(
    monkeypatch,
):
    path = (
        ROOT
        / "tests/fixtures/human_design_reference_snapshot_v1/before-profile-run.json.gz"
    )
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "6104a4e5e2a471496982b45d64a7c0c84cfff764c4cd50d19039d3d247f1d021"
    )
    with gzip.open(path, "rt") as handle:
        value = json.load(handle)
    assert value["profile"] == "6/2"
    assert (
        value["profile_evidence"]["source_catalog_sha256"]
        == "10c864e3d89abb009b516012cc2059045f794e729662704169dc04d1f462c39d"
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Stored reading verification recalculated its chart")

    monkeypatch.setattr(native_execution, "calculate", forbidden)
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    checked = verify_human_design_reading(value)
    assert checked["status"] == "rejected", checked
