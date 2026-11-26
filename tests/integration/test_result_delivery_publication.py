"""Concurrent artifact publication using real processes and file locks."""

from __future__ import annotations

import multiprocessing
import os
from dataclasses import dataclass
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.private_files import locked_private_file


@dataclass(frozen=True, kw_only=True)
class PublicationReport:
    references: list[ServiceResult]
    retained_bytes: list[int]


def publish_results(
    directory: str, barrier: Barrier, output: Queue[PublicationReport]
) -> None:
    delivery.MAX_STORED_BYTES = 8192
    store = delivery.ResultStore(Path(directory))
    barrier.wait(timeout=20)
    references: list[ServiceResult] = []
    retained_bytes: list[int] = []
    for number in range(8):
        references.append(
            store.put({"text": "x" * 1800, "worker": os.getpid(), "n": number})
        )
        with locked_private_file(store.directory / ".lock"):
            retained_bytes.append(
                sum(path.stat().st_size for path in store.directory.iterdir())
            )
    output.put(PublicationReport(references=references, retained_bytes=retained_bytes))


def test_shared_capacity_and_atomic_publication_across_processes(
    tmp_path: Path,
) -> None:
    """Concurrent publishers share retention capacity and leave complete artifacts."""
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    output = context.Queue()
    processes = [
        context.Process(
            target=publish_results, args=(str(tmp_path / "results"), barrier, output)
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
        assert all(size <= 8192 for report in reports for size in report.retained_bytes)
        store = delivery.ResultStore(tmp_path / "results")
        existing = {path.stem for path in store.directory.glob("*.json")}
        removed = [
            ref
            for report in reports
            for ref in report.references
            if ref["result_id"] not in existing
        ]
        assert removed
        with pytest.raises(ParameterError, match="不存在"):
            store.page(removed[0]["result_id"])
        assert not list(store.directory.glob("*.pending"))
        assert all(store.get(result_id)["text"] == "x" * 1800 for result_id in existing)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
            else:
                pass
        output.close()
