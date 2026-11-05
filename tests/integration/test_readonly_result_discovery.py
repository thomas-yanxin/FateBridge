"""Private-directory discovery and immutable-read failure boundaries."""

import copy
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.cli import run
from fatebridge.utils.errors import ParameterError
from tests.integration.test_readonly_result_verification import (
    PAYLOADS,
    REFERENCE,
    block_writes,
    forbidden,
)


@pytest.fixture
def default_store(tmp_path, monkeypatch):
    root = tmp_path / "temporary-root"
    root.mkdir()
    monkeypatch.setenv("TMPDIR", str(root))
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", None)
    store = delivery.ResultStore()
    payload = copy.deepcopy(PAYLOADS[REFERENCE["cases"][0]["id"]])
    ref = store.put(payload)
    return store, payload, ref


def verify(store, payload, ref):
    return store.verified_page(
        ref["result_id"], ref["sha256"], payload["run_metadata"]["run_id"]
    )


def test_default_reader_finds_original_without_temp_probe_or_existing_lock(
    default_store, monkeypatch
):
    store, payload, ref = default_store
    (store.directory / ".lock").unlink()
    monkeypatch.setattr(tempfile, "tempdir", None)
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        page = verify(delivery.ResultStore(), payload, ref)
    assert page["verification"]["payload_sha256"] == ref["sha256"]
    assert not (store.directory / ".lock").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symbolic-root alias")
def test_aliases_of_same_private_directory_are_not_ambiguous(
    default_store, tmp_path, monkeypatch
):
    store, payload, ref = default_store
    alias = tmp_path / "alias-root"
    alias.symlink_to(store.directory.parent, target_is_directory=True)
    monkeypatch.setenv("TEMP", str(alias))
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        assert (
            verify(delivery.ResultStore(), payload, ref)["verification"]["run_id"]
            == payload["run_metadata"]["run_id"]
        )


def test_duplicate_id_is_rejected_without_selecting_by_digest_and_explicit_cli_works(
    default_store, tmp_path, monkeypatch, capsys
):
    store, payload, ref = default_store
    other = tmp_path / "other-root"
    other.mkdir()
    copied = other / store.directory.name
    shutil.copytree(store.directory, copied)
    monkeypatch.setenv("TEMP", str(other))
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        with pytest.raises(ParameterError, match="多个目录"):
            verify(delivery.ResultStore(), payload, ref)
        assert (
            run(
                [
                    "result-read",
                    ref["result_id"],
                    "--sha256",
                    ref["sha256"],
                    "--run-id",
                    payload["run_metadata"]["run_id"],
                    "--directory",
                    str(store.directory),
                    "--path",
                    "input_normalized",
                ]
            )
            == 0
        )
    assert '"calculation_repeated":false' in capsys.readouterr().out


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes and symlinks")
@pytest.mark.parametrize(
    "fault",
    [
        "directory_mode",
        "payload_mode",
        "metadata_mode",
        "directory_link",
        "payload_link",
        "metadata_link",
    ],
)
def test_nonprivate_or_linked_artifacts_never_gain_readonly_verification(
    fault, default_store, monkeypatch
):
    store, payload, ref = default_store
    directory = store.directory
    target = directory if fault.startswith("directory") else Path(ref["file_path"])
    if fault.startswith("metadata"):
        target = target.with_suffix(".meta")
    if fault.endswith("mode"):
        target.chmod(0o755 if fault.startswith("directory") else 0o644)
    else:
        outside = target.with_name(target.name + "-outside")
        target.rename(outside)
        target.symlink_to(outside, target_is_directory=fault.startswith("directory"))
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        with pytest.raises(ParameterError):
            verify(store, payload, ref)


def test_pruning_between_metadata_and_payload_read_does_not_certify_a_missing_result(
    default_store, monkeypatch
):
    store, payload, ref = default_store
    original = store._record

    def concurrent_prune(result_id, **kwargs):
        Path(ref["file_path"]).unlink()
        return original(result_id, **kwargs)

    monkeypatch.setattr(store, "_record", concurrent_prune)
    monkeypatch.setattr(store, "_remove", forbidden)
    with pytest.raises(ParameterError):
        verify(store, payload, ref)


@pytest.mark.parametrize("result_id", ["../private", "a" * 47, "g" * 48])
def test_default_reader_rejects_invalid_id_before_discovery(result_id, monkeypatch):
    monkeypatch.setattr(delivery, "result_directory_candidates", forbidden)
    with pytest.raises(ParameterError, match="无效结果引用"):
        delivery.ResultStore().verified_page(result_id, "0" * 64, "original-run")
