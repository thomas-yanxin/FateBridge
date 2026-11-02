"""Native catalogue snapshots and fingerprints must describe the same inputs."""

import hashlib
import json
import os
import shutil
from contextlib import nullcontext
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime, guolao, suzhan_astronomy
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info

pytestmark = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture
def catalogue(tmp_path, monkeypatch):
    previous = ephemeris_runtime.configured_ephemeris_path()
    target = tmp_path / "catalogue"
    target.mkdir()
    for name in ("sefstars.txt", "sources.json"):
        shutil.copyfile(guolao.DATA / name, target / name)
    monkeypatch.setattr(guolao, "DATA", target)
    # The old wrapper imported a separate DATA alias. This must not determine
    # the fingerprint once the shared native reader supplies its own receipt.
    monkeypatch.setattr(suzhan_astronomy, "DATA", target, raising=False)
    monkeypatch.setattr(ephemeris_runtime, "_configured_path", str(tmp_path / "no-se1"))
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    try:
        yield target
    finally:
        monkeypatch.undo()
        runtime.swe.close()
        ephemeris_runtime.configure_ephemeris_path(previous or "")


def birth():
    return build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )


@pytest.mark.parametrize("replacement_suffix", [b"\n", b"not valid JSON"])
def test_metadata_fingerprint_is_from_the_bytes_read_before_calculation(
    catalogue, monkeypatch, replacement_suffix
):
    metadata = catalogue / "sources.json"
    original_bytes = metadata.read_bytes()
    expected = hashlib.sha256(original_bytes).hexdigest()
    original_positions = suzhan_astronomy.positions

    def replace_metadata_after_calculation(*args, **kwargs):
        raw = original_positions(*args, **kwargs)
        metadata.write_bytes(original_bytes + replacement_suffix)
        return raw

    monkeypatch.setattr(
        suzhan_astronomy, "positions", replace_metadata_after_calculation
    )
    result = suzhan_astronomy.build_equatorial_mansions(birth())
    assert result["catalogue_sources_sha256"] == expected
    assert (
        result["catalogue_sources_sha256"]
        != hashlib.sha256(metadata.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("restore_during_lookup", [False, True])
def test_native_lookup_cannot_switch_catalogue_after_its_hash_was_validated(
    catalogue, monkeypatch, restore_during_lookup
):
    original_bytes = (catalogue / "sefstars.txt").read_bytes()
    expected = suzhan_astronomy.build_equatorial_mansions(birth())
    replacement = original_bytes.replace(
        b"FBJ00,FBJ00,ICRS,13.0,25.0,",
        b"FBJ00,FBJ00,ICRS,13.0,26.0,",
        1,
    )
    assert replacement != original_bytes
    original_call = runtime.ephemeris_call
    replaced = False
    native_calls = 0

    def replace_catalogue_before_native_read(name, *args, **kwargs):
        nonlocal replaced, native_calls
        if name == "fixstar2":
            native_calls += 1
            if native_calls == 1:
                (catalogue / "sefstars.txt").write_bytes(replacement)
                replaced = True
            elif native_calls == 2 and restore_during_lookup:
                (catalogue / "sefstars.txt").write_bytes(original_bytes)
        return original_call(name, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", replace_catalogue_before_native_read)
    result = suzhan_astronomy.build_equatorial_mansions(birth())
    assert replaced
    assert result["boundaries"] == expected["boundaries"]
    assert result["catalogue_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert result["catalogue_sha256"] != hashlib.sha256(replacement).hexdigest()
    if restore_during_lookup:
        # A -> B -> A defeats before/after file-hash guards; the native reader
        # must still have used the captured A for the entire original call.
        assert (catalogue / "sefstars.txt").read_bytes() == original_bytes
        assert suzhan_astronomy.build_equatorial_mansions(birth()) == expected
    else:
        # The next call must reject a newly changed, now unbound bundle.
        with pytest.raises(ValueError, match="指纹不一致"):
            suzhan_astronomy.build_equatorial_mansions(birth())


@pytest.mark.parametrize("fail_inside", [False, True])
def test_captured_path_retains_auxiliary_search_order_and_cleans_up(
    catalogue, tmp_path, fail_inside
):
    from fatebridge.core.fixed_star_paths import fixed_star_search_path

    operator = tmp_path / "operator"
    operator.mkdir()
    captured_bytes = (catalogue / "sefstars.txt").read_bytes()
    cwd = Path.cwd()
    environment = os.environ.get("SE_EPHE_PATH")
    captured_path = None
    error_context = (
        pytest.raises(RuntimeError, match="synthetic") if fail_inside else nullcontext()
    )
    with error_context:
        with fixed_star_search_path(
            catalogue, str(operator), catalogue_bytes=captured_bytes
        ) as search:
            directories = [Path(p).resolve() for p in search.split(os.pathsep)]
            assert directories[1:] == [catalogue.resolve(), operator.resolve()]
            assert len(os.fsencode(search)) <= 242
            captured_path = directories[0]
            assert captured_path != catalogue.resolve()
            (catalogue / "sefstars.txt").write_bytes(b"changed after capture")
            assert (captured_path / "sefstars.txt").read_bytes() == captured_bytes
            if fail_inside:
                raise RuntimeError("synthetic native failure")
    assert captured_path is not None and not captured_path.exists()
    assert Path.cwd() == cwd
    assert os.environ.get("SE_EPHE_PATH") == environment


def test_next_consistently_updated_bundle_gets_new_receipts_without_stale_cache(
    catalogue,
):
    original = suzhan_astronomy.build_equatorial_mansions(birth())
    changed = (catalogue / "sefstars.txt").read_bytes() + b"\n# synthetic version B\n"
    (catalogue / "sefstars.txt").write_bytes(changed)
    metadata = json.loads((catalogue / "sources.json").read_bytes())
    metadata["catalogue_sha256"] = hashlib.sha256(changed).hexdigest()
    source_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode()
    (catalogue / "sources.json").write_bytes(source_bytes)
    result = suzhan_astronomy.build_equatorial_mansions(birth())
    assert result["boundaries"] == original["boundaries"]
    assert result["catalogue_sha256"] == hashlib.sha256(changed).hexdigest()
    assert (
        result["catalogue_sources_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    )
    assert result["catalogue_sha256"] != original["catalogue_sha256"]
    assert result["catalogue_sources_sha256"] != original["catalogue_sources_sha256"]
