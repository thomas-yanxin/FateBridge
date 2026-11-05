"""Adverse byte-integrity cases; no celestial or predictive acceptance."""

import hashlib
import importlib.util
import json
import stat
import warnings
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "verify_guolao_replay",
    Path(__file__).resolve().parents[2] / "scripts/guolao/verify_guolao_replay.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_bundle(
    tmp_path, *, name="source/原页.txt", body=b"source", record=None, extra=()
):
    path = tmp_path / "evidence.zip"
    expected = record or dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    with warnings.catch_warnings(), zipfile.ZipFile(path, "w") as archive:
        warnings.simplefilter("ignore", UserWarning)
        archive.writestr(name, body)
        for entry, raw in extra:
            archive.writestr(entry, raw)
        archive.writestr(
            "manifest.json",
            json.dumps(dict(schema=MODULE.SCHEMA, files={name: expected})),
        )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_declared_files_verified_without_extraction_or_execution(tmp_path):
    path, digest = make_bundle(tmp_path)
    result = MODULE.verify_bundle(path, expected_sha256=digest)
    assert result["verified_files"] == 1
    assert result["verified_uncompressed_bytes"] == 6
    assert result["extracted_files"] == result["executed_programs"] == 0
    assert result["integrity_only"] and not result["real_world_efficacy_established"]
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("digest", ["", "0" * 64, "A" * 64])
def test_pin_is_required_and_cannot_be_replaced_by_inner_manifest(tmp_path, digest):
    path, _ = make_bundle(tmp_path)
    with pytest.raises(ValueError, match="SHA256"):
        MODULE.verify_bundle(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "record",
    [
        dict(bytes=6, sha256="0" * 64),
        dict(bytes=7, sha256=hashlib.sha256(b"source").hexdigest()),
        dict(bytes=True, sha256=hashlib.sha256(b"source").hexdigest()),
    ],
)
def test_changed_bytes_bad_lengths_and_boolean_counts_are_rejected(tmp_path, record):
    path, digest = make_bundle(tmp_path, record=record)
    with pytest.raises(ValueError):
        MODULE.verify_bundle(path, expected_sha256=digest)


@pytest.mark.parametrize("name", ["../source", "/source", "./source", "a//b", "a\\b"])
def test_noncanonical_archive_paths_are_rejected(tmp_path, name):
    path, digest = make_bundle(tmp_path, name=name)
    with pytest.raises(ValueError, match="path"):
        MODULE.verify_bundle(path, expected_sha256=digest)


@pytest.mark.parametrize("name", ["source/原页.txt", "undeclared.txt"])
def test_duplicate_or_undeclared_archive_entries_are_rejected(tmp_path, name):
    path, digest = make_bundle(tmp_path, extra=[(name, b"unexpected")])
    with pytest.raises(ValueError):
        MODULE.verify_bundle(path, expected_sha256=digest)


def test_symbolic_link_is_rejected_without_following_it(tmp_path):
    entry = zipfile.ZipInfo("linked")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    path, digest = make_bundle(tmp_path, extra=[(entry, b"/private/file")])
    with pytest.raises(ValueError, match="symbolic link"):
        MODULE.verify_bundle(path, expected_sha256=digest)


def test_missing_manifest_is_rejected(tmp_path):
    path = tmp_path / "evidence.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("source", b"text")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="missing"):
        MODULE.verify_bundle(path, expected_sha256=digest)
