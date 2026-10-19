"""Indexed artifact delivery, bounded disk usage and process coordination."""

import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path
from typing import Any

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.utils.errors import ParameterError


def _reconstruct(store, result_id, path=None):
    offset = 0
    parts = []
    while True:
        page = store.page(result_id, offset, path)
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    text = "".join(parts)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == page["sha256"]
    return json.loads(text)


def test_indexed_utf8_pages_and_nested_fields_preserve_exact_canonical_document(
    tmp_path,
):
    store = delivery.ResultStore(tmp_path / "results")
    original = {
        "earlier": {"大量文字": '祖孙故事👩🏽‍💻\\"\n' * 300},
        "中文": [{"text": "🌳上海\t\n" * 1200}, None, True, 1.5],
        "run_metadata": {"run_id": "fixed", "tool_name": "probe"},
    }
    ref = store.put(original)
    assert json.loads(Path(ref["file_path"]).read_text())["payload"] == original
    assert _reconstruct(store, ref["result_id"]) == original
    for path, value in [
        ("中文.0.text", original["中文"][0]["text"]),
        ("中文.1", None),
        ("中文.2", True),
        ("中文.3", 1.5),
        ("earlier", original["earlier"]),
    ]:
        assert _reconstruct(store, ref["result_id"], path) == value
        text = delivery._json(value)
        for offset in [0, 1, min(2047, len(text)), len(text)]:
            assert (
                store.page(ref["result_id"], offset, path)["text"]
                == text[offset : offset + delivery.PAGE_CHARS]
            )
    text = delivery._json(original)
    for offset in [1, 2047, 2048, 2049, len(text)]:
        assert (
            store.page(ref["result_id"], offset)["text"]
            == text[offset : offset + delivery.PAGE_CHARS]
        )
    for artifact in store.directory.iterdir():
        assert artifact.stat().st_mode & 0o777 == 0o600


def test_repeated_pages_and_scope_do_not_load_serialize_or_hash_the_result(
    tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path / "results")
    original = {
        "blob": "中文🌳" * 10000,
        "run_metadata": {"tool_name": "probe", "run_id": "same-run"},
    }
    ref = store.put(original)
    store.page(ref["result_id"], path="blob")  # first field index builds once

    def unexpected(*args, **kwargs):
        raise AssertionError("A page cannot repeat whole-result work")

    monkeypatch.setattr(store, "_record", unexpected)
    monkeypatch.setattr(delivery, "_json", unexpected)
    original_hash = delivery.hashlib.sha256

    def only_small_path_hash(data):
        assert len(data) <= 1000, "A page cannot hash the entire result"
        return original_hash(data)

    monkeypatch.setattr(delivery.hashlib, "sha256", only_small_path_hash)
    assert (
        store.manifest(ref["result_id"], allowed_tools={"probe"})["run_metadata"][
            "run_id"
        ]
        == "same-run"
    )
    # Scope checks and indexed field reads use immutable manifest facts.
    for path in [None, "blob"]:
        offset = 0
        while True:
            page = store.page(ref["result_id"], offset, path, allowed_tools={"probe"})
            assert page["sha256"]
            offset = page["next_offset"]
            if offset is None:
                break
    with pytest.raises(ValueError, match="未在当前 MCP 配置中公开"):
        store.page(ref["result_id"], allowed_tools={"hidden"})


class _CountingReader:
    def __init__(self, handle, counts):
        self.handle = handle
        self.counts = counts

    def __getattr__(self, name):
        return getattr(self.handle, name)

    def __enter__(self):
        self.handle.__enter__()
        return self

    def __exit__(self, *args):
        return self.handle.__exit__(*args)

    def read(self, *args):
        value = self.handle.read(*args)
        self.counts[0] += len(
            value.encode("utf-8") if isinstance(value, str) else value
        )
        return value


def test_full_export_reads_linear_bytes_instead_of_whole_document_per_page(
    tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path / "results")
    refs = [store.put({"blob": "中文abc" * size}) for size in [10000, 40000]]
    counts = [0]
    fdopen = os.fdopen
    monkeypatch.setattr(
        delivery.os,
        "fdopen",
        lambda *a, **kw: _CountingReader(fdopen(*a, **kw), counts),
    )
    work = []
    for ref in refs:
        counts[0] = 0
        offset = 0
        while True:
            page = store.page(ref["result_id"], offset)
            offset = page["next_offset"]
            if offset is None:
                break
        work.append(counts[0])
        # Include manifest JSON and index reads; payload bytes are read once.
        assert counts[0] < ref["total_bytes"] * 2
    assert work[1] < work[0] * 4.2


def test_unindexed_record_is_rejected_without_rewriting_the_saved_result(tmp_path):
    store = delivery.ResultStore(tmp_path / "results")
    directory = store._directory()
    result_id = "a" * 48
    expires_at = time.time() + 600
    payload = {"run_metadata": {"run_id": "legacy"}, "text": "旧结果🌳" * 1000}
    primary = directory / f"{result_id}.json"
    primary.write_text(
        json.dumps({"expires_at": expires_at, "payload": payload}, indent=2)
    )
    primary.chmod(0o600)
    original = primary.read_bytes()
    for read in (store.manifest, store.page):
        with pytest.raises(ParameterError, match="不存在或已损坏"):
            read(result_id)
        assert primary.read_bytes() == original
        assert not (directory / f"{result_id}.meta").exists()


def _process_writer(directory: str, barrier: Any, output: Any) -> None:
    delivery.MAX_STORED_BYTES = 8192
    store = delivery.ResultStore(Path(directory))
    barrier.wait(timeout=20)
    try:
        refs = []
        snapshots = []
        for number in range(8):
            refs.append(
                store.put({"text": "x" * 1800, "worker": os.getpid(), "n": number})
            )
            with store._locked():
                snapshots.append(
                    sum(path.stat().st_size for path in store.directory.iterdir())
                )
        output.put({"refs": refs, "usage": snapshots})
    except Exception as exc:
        output.put({"error": repr(exc)})


def test_cross_process_capacity_reservation_commit_and_pruning_are_atomic(tmp_path):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    output = context.Queue()
    processes = [
        context.Process(
            target=_process_writer, args=(str(tmp_path / "results"), barrier, output)
        )
        for _ in range(4)
    ]
    try:
        for process in processes:
            process.start()
        reports = [output.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert all("error" not in report for report in reports), reports
        assert all(usage <= 8192 for report in reports for usage in report["usage"])
        store = delivery.ResultStore(tmp_path / "results")
        existing = {path.stem for path in store.directory.glob("*.json")}
        removed = [
            ref
            for report in reports
            for ref in report["refs"]
            if ref["result_id"] not in existing
        ]
        assert removed  # real capacity pressure reclaimed complete artifact groups
        with pytest.raises(ParameterError, match="不存在"):
            store.page(removed[0]["result_id"])
        assert all(
            not path.name.endswith(".pending") for path in store.directory.iterdir()
        )
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        output.close()


def test_expiry_reclaims_record_indexes_and_field_sidecars(tmp_path, monkeypatch):
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "中文" * 5000})
    store.page(ref["result_id"], path="text")
    assert len(list(store.directory.glob(ref["result_id"] + ".*"))) == 5
    monkeypatch.setattr(delivery.time, "time", lambda: ref["expires_at"] + 1)
    with pytest.raises(ParameterError, match="过期"):
        store.page(ref["result_id"])
    assert not list(store.directory.glob(ref["result_id"] + ".*"))


def test_crashed_writer_pending_and_orphan_indexes_are_reclaimed(tmp_path):
    store = delivery.ResultStore(tmp_path / "results")
    directory = store._directory()
    result_id = "f" * 48
    for suffix in ["json.pending", "meta", "idx"]:
        (directory / f"{result_id}.{suffix}").write_bytes(b"old crashed write")
    store.put({"text": "healthy"})
    assert not list(directory.glob(result_id + ".*"))


@pytest.mark.parametrize("suffix", ["json", "meta", "idx"])
def test_artifact_symlinks_are_never_followed(tmp_path, suffix):
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "private"})
    path = store.directory / f"{ref['result_id']}.{suffix}"
    original = path.read_bytes()
    outside = tmp_path / "outside"
    outside.write_bytes(original)
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ParameterError):
        store.page(ref["result_id"])
    assert outside.read_bytes() == original


def test_oversize_attempt_does_not_evict_an_existing_deliverable(tmp_path, monkeypatch):
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "keep this run"})
    monkeypatch.setattr(delivery, "MAX_STORED_BYTES", 4096)
    with pytest.raises(ParameterError, match="容量"):
        store.put({"text": "x" * 5000})
    assert _reconstruct(store, ref["result_id"]) == {"text": "keep this run"}


@pytest.mark.parametrize("suffix", ["meta", "idx"])
def test_corrupt_metadata_or_page_indexes_fail_explicitly(tmp_path, suffix):
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "private" * 1000})
    target = store.directory / f"{ref['result_id']}.{suffix}"
    if suffix == "meta":
        metadata = json.loads(target.read_text())
        metadata["body_offset"] = -1
        target.write_text(json.dumps(metadata))
    else:
        target.write_bytes(
            delivery._INDEX_ENTRY.pack(0) + delivery._INDEX_ENTRY.pack(10**9)
        )
    with pytest.raises(ParameterError, match="损坏"):
        store.page(ref["result_id"])
