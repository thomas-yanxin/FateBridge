"""Every served source identity belongs to the exact reviewed bytes read."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.human_design import human_design_references as refs
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path, monkeypatch):
    original = refs._read
    data = {name: original(name) for name in refs.REFERENCE_NAMES}
    refs.clear_reference_cache()

    def read(name):
        value = data[name]
        if isinstance(value, Exception):
            raise EphemerisSourceError("human_design_reference_unavailable") from value
        else:
            pass
        return value

    monkeypatch.setattr(refs, "_read", read)
    yield data
    refs.clear_reference_cache()


def test_all_reviewed_catalogues_remain_exact_and_every_runtime_reader_is_bound() -> (
    None
):
    assert len(refs.REFERENCE_NAMES) == len(refs.REFERENCE_SHA256) == 12
    for name, digest in refs.REFERENCE_SHA256.items():
        raw = (ROOT / "src/fatebridge/data/human_design" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        with refs.coherent_human_design_references():
            assert refs.reference_bytes(name) == raw
            assert refs.reference_sha256(name) == digest
            assert refs.reference_data(name) == json.loads(raw)


@pytest.mark.parametrize("name", refs.REFERENCE_NAMES)
@pytest.mark.parametrize("mutation", ["different_bytes", "unavailable", "cache_clear"])
def test_all_catalogues_pin_loaded_bytes_until_cold_reload(
    source, name, mutation: str
) -> None:
    with refs.coherent_human_design_references():
        raw = refs.reference_bytes(name)
        source[name] = (
            FileNotFoundError("private/source/path")
            if mutation == "unavailable"
            else raw + b"\n"
        )
        if mutation == "cache_clear":
            refs.clear_reference_cache()
        else:
            pass
        assert refs.reference_bytes(name) == raw
        assert refs.reference_sha256(name) == hashlib.sha256(raw).hexdigest()
    refs.clear_reference_cache()
    with pytest.raises(EphemerisSourceError) as caught:
        refs.reference_data(name)
    assert caught.value.reason == (
        "human_design_reference_unavailable"
        if mutation == "unavailable"
        else "human_design_reference_identity_mismatch"
    )


@pytest.mark.parametrize("name", refs.REFERENCE_NAMES)
def test_valid_but_unreviewed_file_cannot_supply_a_new_cold_source(
    source, name
) -> None:
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
def test_corrupt_or_ambiguous_json_is_not_accepted_as_source(
    source, raw: bytes
) -> None:
    name = refs.REFERENCE_NAMES[0]
    source[name] = raw
    with pytest.raises(EphemerisSourceError) as caught:
        with refs.coherent_human_design_references():
            refs.reference_data(name)
    assert caught.value.reason == "human_design_reference_invalid"


def test_old_loaded_data_cannot_take_a_later_file_hash(source) -> None:
    name = "profile-2026-reference.json"
    raw = source[name]
    doc = refs.reference_data(name)
    source[name] += b"\n"
    assert refs.reference_data(name) is doc
    assert refs.reference_sha256(name) == hashlib.sha256(raw).hexdigest()
    refs.clear_reference_cache()
    with pytest.raises(EphemerisSourceError):
        with refs.coherent_human_design_references():
            refs.reference_data(name)


def test_unused_optional_catalogue_is_not_required_and_nested_view_is_pinned(
    source,
) -> None:
    source["cycles-2026-reference.json"] = FileNotFoundError("unused")
    with refs.coherent_human_design_references():
        first = refs.reference_data("profile-2026-reference.json")
        with refs.coherent_human_design_references():
            assert refs.reference_data("profile-2026-reference.json") is first
