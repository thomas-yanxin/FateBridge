"""Whole-file identity, repair preservation and immutable upstream evidence."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge import fetch_ephe
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
)
from tests.support.ephemeris_context import manifest_for_payloads

NAME = "sepl_96.se1"
VALID = b"SW-referenced-planet-data"


def test_windows_style_checkout_preserves_lahiri_source_bytes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    repository = tmp_path / "repository"
    repository.mkdir()
    source = "src/fatebridge/core/astro/continuous_lahiri.py"
    shared_source = "src/fatebridge/core/astro/reference_frames.py"
    coefficients = "src/fatebridge/data/astronomy/lahiri-frame-v1.json"
    paths = (
        ".gitattributes",
        source,
        shared_source,
        coefficients,
        "src/fatebridge/data/sukuyo_dayan_reference_LICENSE.txt",
    )
    for name in paths:
        target = repository / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "core.autocrlf", "true"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "add", "--", *paths],
        check=True,
        capture_output=True,
    )
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "checkout-index",
            "--all",
            "--prefix=" + str(checkout) + "/",
        ],
        check=True,
        capture_output=True,
    )
    for name in (coefficients, source, shared_source, paths[-1]):
        assert (checkout / name).read_bytes() == (root / name).read_bytes(), name
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; runpy.run_path(sys.argv[1])",
            str(checkout / source),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "payload",
    [
        b"SW",
        VALID[:-1],
        VALID + b"0",
        b"XX" + VALID[2:],
    ],
)
def test_prefix_truncation_append_and_invalid_header_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload
) -> None:
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: payload)
    with pytest.raises(ValueError):
        fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog)
    assert list(tmp_path.iterdir()) == []


def test_invalid_cached_file_is_repaired_and_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / NAME
    previous = b"SW-wrong-cached-segment"
    target.write_bytes(previous)
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: VALID)
    assert fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog) == target
    assert target.read_bytes() == VALID
    assert set(tmp_path.iterdir()) == {target}
    # Verified reuse must not perform another download.
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **kw: pytest.fail("network")
    )
    assert fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog) == target
    assert set(tmp_path.iterdir()) == {target}


def test_failed_repair_leaves_existing_data_and_directory_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / NAME
    target.write_bytes(b"SW-original")
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: b"SW-truncated")
    with pytest.raises(ValueError):
        fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog)
    assert target.read_bytes() == b"SW-original"
    assert set(tmp_path.iterdir()) == {target}


def test_failed_final_replacement_keeps_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / NAME
    previous = b"SW-original-to-keep"
    target.write_bytes(previous)
    original_replace = Path.replace

    def interrupted(self, destination):
        if Path(destination) == target:
            raise OSError("simulated final replacement failure")
        else:
            pass
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", interrupted)
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: VALID)
    with pytest.raises(OSError, match="replacement failure"):
        fetch_ephe.fetch_one(
            NAME, tmp_path, manifest=manifest_for_payloads({NAME: VALID})
        )
    assert target.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {target}


def test_concurrent_edit_is_preserved_instead_of_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / NAME
    target.write_bytes(b"SW-before")

    def download(*a, **kw):
        target.write_bytes(b"SW-concurrent-edit")
        return VALID

    monkeypatch.setattr(fetch_ephe, "_download", download)
    with pytest.raises(ValueError, match="changed during download"):
        fetch_ephe.fetch_one(
            NAME, tmp_path, manifest=manifest_for_payloads({NAME: VALID})
        )
    assert target.read_bytes() == b"SW-concurrent-edit"
    assert set(tmp_path.iterdir()) == {target}


def test_concurrent_identical_verified_result_can_be_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / NAME

    def download(*a, **kw):
        target.write_bytes(VALID)
        return VALID

    monkeypatch.setattr(fetch_ephe, "_download", download)
    assert (
        fetch_ephe.fetch_one(
            NAME, tmp_path, manifest=manifest_for_payloads({NAME: VALID})
        )
        == target
    )
    assert target.read_bytes() == VALID
    assert set(tmp_path.iterdir()) == {target}


@pytest.mark.parametrize("payload", [VALID, b"SW-invalid"])
def test_verify_only_never_repairs_or_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload
) -> None:
    target = tmp_path / NAME
    target.write_bytes(payload)
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(
        fetch_ephe, "load_ephemeris_manifest", lambda path=None: catalog
    )
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **kw: pytest.fail("network")
    )
    result = fetch_ephe.main(
        ["--dest", str(tmp_path), "--files", NAME, "--verify-only"]
    )
    assert result == (0 if payload == VALID else 1)
    assert target.read_bytes() == payload
    assert set(tmp_path.iterdir()) == {target}


def test_custom_manifest_retains_custom_data_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = manifest_for_payloads({"custom.se1": VALID})
    file = tmp_path / "custom-manifest.json"
    file.write_text(json.dumps(custom))
    requested = []
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda url: requested.append(url) or VALID
    )
    assert (
        fetch_ephe.main(
            ["--manifest", str(file), "--dest", str(tmp_path), "--files", "custom.se1"]
        )
        == 0
    )
    assert requested == [custom["base_url"] + "/custom.se1"]
    assert (tmp_path / "custom.se1").read_bytes() == VALID


@pytest.mark.parametrize("name", ["../bad.se1", "/bad.se1", "x\\bad.se1", "x.se1?bad"])
@pytest.mark.parametrize("verify_only", [False, True])
def test_invalid_names_never_read_or_write_outside_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, verify_only: bool
) -> None:
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **kw: pytest.fail("network")
    )
    args = ["--dest", str(tmp_path), "--files", name]
    if verify_only:
        args.append("--verify-only")
    else:
        pass
    assert fetch_ephe.main(args) == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "invalid", [[], {}, {"schema_version": True}, {"schema_version": 2}]
)
def test_invalid_manifest_has_a_clear_validation_error(tmp_path: Path, invalid) -> None:
    file = tmp_path / "invalid.json"
    file.write_text(json.dumps(invalid))
    with pytest.raises(ValueError):
        load_ephemeris_manifest(file)


def test_default_catalog_is_not_mutable_by_its_caller() -> None:
    catalog = load_ephemeris_manifest()
    catalog["files"].clear()
    assert load_ephemeris_manifest()["files"]
