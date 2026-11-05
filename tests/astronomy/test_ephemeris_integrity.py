"""Whole-file identity, repair preservation and immutable upstream evidence."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge import fetch_ephe
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from tests.fixtures.ephemeris_manifest import manifest_for_payloads

NAME = "sepl_96.se1"
VALID = b"SW-referenced-planet-data"


def test_windows_style_checkout_preserves_lahiri_source_bytes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    repository = tmp_path / "repository"
    repository.mkdir()
    source = "src/fatebridge/core/astro/continuous_lahiri.py"
    coefficients = "src/fatebridge/data/astronomy/lahiri-frame-v1.json"
    paths = (
        ".gitattributes",
        source,
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
    for name in (coefficients, source, paths[-1]):
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
        b"SW-referenced-planet-datX",
        b"SW-referenced-lunar--data",
    ],
)
def test_prefix_truncation_append_bit_change_and_wrong_body_are_rejected(
    tmp_path, monkeypatch, payload
):
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: payload)
    with pytest.raises(ValueError, match="selected edition"):
        fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog)
    assert list(tmp_path.iterdir()) == []


def test_invalid_cached_file_is_repaired_with_a_recoverable_original(
    tmp_path, monkeypatch
):
    target = tmp_path / NAME
    previous = b"SW-wrong-cached-segment"
    target.write_bytes(previous)
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: VALID)
    assert fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog) == target
    assert target.read_bytes() == VALID
    backups = list((tmp_path / ".fatebridge-ephemeris-backups").rglob("*.se1"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == previous
    assert backups[0].parent.name == hashlib.sha256(previous).hexdigest()
    # Verified reuse must not perform another download or create another backup.
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **kw: pytest.fail("network")
    )
    assert fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog) == target
    assert len(list((tmp_path / ".fatebridge-ephemeris-backups").rglob("*.se1"))) == 1


def test_failed_repair_leaves_existing_data_and_directory_unchanged(
    tmp_path, monkeypatch
):
    target = tmp_path / NAME
    target.write_bytes(b"SW-original")
    catalog = manifest_for_payloads({NAME: VALID})
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: b"SW-truncated")
    with pytest.raises(ValueError):
        fetch_ephe.fetch_one(NAME, tmp_path, manifest=catalog)
    assert target.read_bytes() == b"SW-original"
    assert set(tmp_path.iterdir()) == {target}


def test_failed_final_replacement_keeps_both_original_and_backup(tmp_path, monkeypatch):
    target = tmp_path / NAME
    previous = b"SW-original-to-keep"
    target.write_bytes(previous)
    original_replace = Path.replace

    def interrupted(self, destination):
        if Path(destination) == target:
            raise OSError("simulated final replacement failure")
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", interrupted)
    monkeypatch.setattr(fetch_ephe, "_download", lambda *a, **kw: VALID)
    with pytest.raises(OSError, match="replacement failure"):
        fetch_ephe.fetch_one(
            NAME, tmp_path, manifest=manifest_for_payloads({NAME: VALID})
        )
    assert target.read_bytes() == previous
    backups = list((tmp_path / ".fatebridge-ephemeris-backups").rglob("*.se1"))
    assert len(backups) == 1 and backups[0].read_bytes() == previous
    assert set(tmp_path.iterdir()) == {
        target,
        tmp_path / ".fatebridge-ephemeris-backups",
    }


def test_concurrent_edit_is_preserved_instead_of_replaced(tmp_path, monkeypatch):
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


def test_concurrent_identical_verified_result_can_be_reused(tmp_path, monkeypatch):
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
def test_verify_only_never_repairs_or_downloads(tmp_path, monkeypatch, payload):
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


def test_custom_manifest_retains_custom_data_support(tmp_path, monkeypatch):
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
    tmp_path, monkeypatch, name, verify_only
):
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **kw: pytest.fail("network")
    )
    args = ["--dest", str(tmp_path), "--files", name]
    if verify_only:
        args.append("--verify-only")
    assert fetch_ephe.main(args) == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "invalid", [[], {}, {"schema_version": True}, {"schema_version": 2}]
)
def test_invalid_manifest_has_a_clear_validation_error(tmp_path, invalid):
    file = tmp_path / "invalid.json"
    file.write_text(json.dumps(invalid))
    with pytest.raises(ValueError):
        load_ephemeris_manifest(file)


@pytest.mark.local_data
def test_packaged_catalog_matches_the_frozen_official_tree():
    catalog = load_ephemeris_manifest()
    fixture = Path(__file__).parents[1] / "fixtures/swiss-ephemeris-upstream-tree.json"
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == catalog["source_tree_sha256"]
    rows = json.loads(raw)["tree"]
    official = {
        Path(row["path"]).name: row
        for row in rows
        if row["type"] == "blob"
        and row["path"].startswith("ephe/")
        and row["path"].count("/") == 1
        and row["path"].endswith(".se1")
    }
    assert set(catalog["files"]) == set(official)
    for name, row in official.items():
        assert catalog["files"][name]["bytes"] == row["size"]
        assert catalog["files"][name]["git_blob_sha1"] == row["sha"]
    assert catalog["source_commit"] in catalog["base_url"]
    assert "/master/" not in fetch_ephe.BASE_URL
    # Independently recorded real-file hashes from the preceding acceptance.
    assert (
        catalog["files"]["sepl_96.se1"]["sha256"]
        == "3e3f6dd884552f6a9427b53a2b270ba56a0edceba1363f2e6956cae59ad23b20"
    )
    assert (
        catalog["files"]["semo_96.se1"]["sha256"]
        == "ba5d7a961c2f3763de8965899e8f4d4e60036f3997e83ea75dce2bcc5c37b6f2"
    )


def test_default_catalog_is_not_mutable_by_its_caller():
    catalog = load_ephemeris_manifest()
    catalog["files"].clear()
    assert load_ephemeris_manifest()["files"]
