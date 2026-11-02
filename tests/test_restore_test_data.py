"""Frozen data must survive transport and cannot overwrite unrelated files."""

import hashlib
import io
import tarfile

import pytest

from scripts.restore_test_data import DataManifest, main, restore


def bundle(tmp_path, name="tests/fixtures/reference.json", content=b'{"value": 1}'):
    archive = tmp_path / "fixtures.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(name)
        member.size = len(content)
        member.mode = 0o644
        tar.addfile(member, io.BytesIO(content))
    manifest = DataManifest.model_validate(
        {
            "schema_version": 2,
            "source_revision": "a" * 40,
            "parts": [
                {
                    "name": archive.name,
                    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "size": archive.stat().st_size,
                    "group": "core",
                }
            ],
        }
    )
    return archive, manifest


def test_exact_bytes_restored_and_repeat_restoration_keeps_existing_data(tmp_path):
    _, manifest = bundle(tmp_path)
    root = tmp_path / "checkout"
    assert restore(manifest, root, archive_directory=tmp_path) == 1
    target = root / "tests/fixtures/reference.json"
    assert target.read_bytes() == b'{"value": 1}'
    assert restore(manifest, root, archive_directory=tmp_path) == 0
    target.write_text("existing different reference")
    with pytest.raises(ValueError, match="Existing test data differs"):
        restore(manifest, root, archive_directory=tmp_path)
    assert target.read_text() == "existing different reference"


def test_corrupt_archive_is_rejected_before_any_restoration(tmp_path):
    archive, manifest = bundle(tmp_path)
    archive.write_bytes(archive.read_bytes() + b"corrupt")
    root = tmp_path / "checkout"
    with pytest.raises(ValueError, match="Pinned test-data archive changed"):
        restore(manifest, root, archive_directory=tmp_path)
    assert not root.exists()


@pytest.mark.parametrize(
    "name", ["../outside", "/tmp/outside", "src/fatebridge/__init__.py"]
)
def test_archive_cannot_write_outside_frozen_data_directories(tmp_path, name):
    _, manifest = bundle(tmp_path, name=name)
    with pytest.raises(ValueError, match="Invalid test-data member"):
        restore(manifest, tmp_path / "checkout", archive_directory=tmp_path)


def test_core_jobs_leave_full_research_inputs_for_the_full_matrix(tmp_path):
    _, manifest = bundle(tmp_path)
    manifest.parts[0].group = "validation"
    assert (
        restore(
            manifest, tmp_path / "checkout", core_only=True, archive_directory=tmp_path
        )
        == 0
    )


def test_local_archive_directory_is_required_before_restoration(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["restore_test_data.py"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "--archive-directory" in capsys.readouterr().err
