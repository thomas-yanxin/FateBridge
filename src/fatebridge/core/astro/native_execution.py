"""Run a whole registered operation in a fresh, private native-library process.

Swiss auxiliary tables and user Delta-T are mutable native state; closing the
library or starting a thread does not reliably reset them. A new exec process
owns all clock, geometry, event and grid calls for one outer operation. This is
state isolation, not independent astronomical validation or an atomic file read.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from typing import Any, Protocol

from pydantic import JsonValue

from fatebridge.core.astro.native_wire import (
    RESULT_ENCODING,
    NativeExecutionError,
    decode,
    decode_result,
    encode,
    encode_result,
)
from fatebridge.core.compressed_ephemeris import endpoint_context_evidence
from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.core.execution_context import (
    clock_snapshot,
    merge_clock_reads,
)
from fatebridge.utils.errors import EphemerisSourceError, JyotishCalculationError

__all__ = [
    "RESULT_ENCODING",
    "AuxiliaryInputs",
    "NativeExecutionError",
    "calculate",
    "context_evidence",
    "context_for_entry",
    "decode",
    "decode_result",
    "encode",
    "encode_result",
    "in_native_worker",
    "message_bytes",
]

_WORKER_ACTIVE = False
_ENTRIES = {
    "fatebridge.core.human_design.human_design_cycle_input.validate_cycle_reference",
    "fatebridge.services.human_design.calculate_human_design",
    "fatebridge.core.jyotish.jyotish.positions",
    "fatebridge.core.jyotish.jyotish.build_india",
    "fatebridge.services.jyotish.calculate_vimshottari",
    "fatebridge.services.astrology.calculate_core_chart_analysis",
}
_MAX_MESSAGE = 64 * 1024 * 1024
_TIMEOUT = 1800.0
_AUXILIARY_EVIDENCE: dict[str, Any] | None = None


class NativeSampleObserver(Protocol):
    def __call__(
        self, offset_seconds: float, sample: dict[str, JsonValue], /
    ) -> None: ...


class AuxiliaryInputs:
    """Endpoint fingerprints, including absent files that could shadow a source.

    The ordered candidates follow the same path parser as source diagnostics.
    Each identity describes a possible native input at the endpoint.
    """

    def __init__(self, search_path: str | None) -> None:
        selected = search_path or "."
        depths = {
            name: len(ephemeris_search_directories(selected, filename=name))
            for name in ("swe_deltat.txt", "sedeltat.txt", "seleapsec.txt")
        }
        # Keep the receipt's three slots per root. An unreachable filename
        # is absent by the native path-buffer rule, even if it exists on disk.
        self.paths = [
            directory.absolute() / name if index < depth else None
            for index, directory in enumerate(ephemeris_search_directories(selected))
            for name, depth in depths.items()
        ]
        self.initial = self.snapshot()

    def snapshot(self) -> list[Any]:
        rows: list[list[int | str | None]] = []
        for index, path in enumerate(self.paths):
            if path is None:
                rows.append([index, None, None])
                continue
            try:
                digest = hashlib.sha256()
                with path.open("rb") as source:
                    size = 0
                    for chunk in iter(lambda: source.read(65536), b""):
                        size += len(chunk)
                        digest.update(chunk)
                rows.append([index, size, digest.hexdigest()])
            except (FileNotFoundError, NotADirectoryError):
                rows.append([index, None, None])
            except OSError as error:
                raise EphemerisSourceError("auxiliary_unavailable") from error
        return rows

    def check(self) -> None:
        if self.snapshot() != self.initial:
            raise EphemerisSourceError("auxiliary_changed_during")

    def evidence(self) -> dict[str, Any]:
        return {
            "mechanism": "fresh_exec_process",
            "lifetime": "one_outer_india_operation",
            "auxiliary_candidates_checked": len(self.paths),
            "auxiliary_files_present": [
                {
                    "search_index": index // 3,
                    "filename": path.name,
                    "bytes": size,
                    "sha256": digest,
                }
                for path, (index, size, digest) in zip(self.paths, self.initial)
                if path is not None and digest is not None
            ],
            "scope": "Clock inversion, physical coordinates, houses, solar events and all grid samples share this private native context. Auxiliary search candidates are fingerprinted at calculation endpoints; identities do not prove atomic reads, table validity or astronomical accuracy.",
        }


def context_for_entry(entry: str) -> dict[str, str]:
    if (
        entry
        == "fatebridge.core.human_design.human_design_cycle_input.validate_cycle_reference"
    ):
        return {
            "lifetime": "one_human_design_cycle_request_validation",
            "scope": "Request-only birth/reference TT ordering in a fresh native process. The calculation revalidates in its separate whole-operation context. Auxiliary candidate identities do not prove atomic reads, table validity or physical accuracy.",
        }
    if entry == "fatebridge.services.human_design.calculate_human_design":
        from fatebridge.core.human_design.human_design_context import (
            CONTEXT_LIFETIME,
            CONTEXT_SCOPE,
        )

        return {"lifetime": CONTEXT_LIFETIME, "scope": CONTEXT_SCOPE}
    return {}


def context_evidence() -> dict[str, Any]:
    return {
        **(_AUXILIARY_EVIDENCE or {"mechanism": "local_engine_context"}),
        "compressed_file_endpoint_policy": endpoint_context_evidence(),
    }


def in_native_worker() -> bool:
    return _WORKER_ACTIVE


def message_bytes(message: dict[str, Any]) -> bytes:
    # Typed trees can exceed the byte budget solely through separator spaces.
    # Compact JSON preserves every value and the unchanged64MiB wire bound.
    payload = (
        json.dumps(
            message, ensure_ascii=True, allow_nan=False, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    if len(payload) > _MAX_MESSAGE:
        raise NativeExecutionError("Native calculation message exceeds limit")
    return payload


def _receive(process: subprocess.Popen[bytes], deadline: float) -> dict[str, Any]:
    stdout = process.stdout
    assert stdout is not None
    # note (native IPC): Windows selectors cannot monitor anonymous pipes, so a bounded reader shares the child's deadline.
    received: queue.Queue[bytes | Exception] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            received.put(stdout.readline(_MAX_MESSAGE + 1))
        except Exception as error:
            received.put(error)

    reader = Thread(target=read, name="fatebridge-native-response", daemon=True)
    reader.start()
    try:
        payload = received.get(timeout=max(0, deadline - time.monotonic()))
    except queue.Empty as error:
        raise TimeoutError(
            "Private native calculation exceeded its deadline"
        ) from error
    reader.join()
    if isinstance(payload, Exception):
        raise NativeExecutionError(
            "Private native calculation exited without a result"
        ) from payload
    elif not payload:
        raise NativeExecutionError("Private native calculation exited without a result")
    if len(payload) > _MAX_MESSAGE:
        raise NativeExecutionError("Native calculation message exceeds limit")
    try:
        message = json.loads(payload)
    except ValueError as error:
        raise NativeExecutionError("Invalid native calculation response") from error
    if not isinstance(message, dict):
        raise NativeExecutionError("Invalid native calculation response")
    return message


def calculate(
    entry: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """Parent dispatch. Caller holds the managed source-session lock."""
    from fatebridge.core.astro.iers_ut1 import active_ut1
    from fatebridge.core.astro.source_session import current_source_session
    from fatebridge.core.ephemeris_runtime import effective_ephemeris_search_path
    from fatebridge.core.physical_source_observation import (
        current_policy,
        merge_worker_policy,
        policy_mode,
    )

    if entry not in _ENTRIES:
        raise NativeExecutionError("Unsupported private calculation entry")
    session = current_source_session()
    if session is None:
        raise NativeExecutionError("Private calculation requires a source session")
    options = dict(kwargs)
    auxiliary_path = effective_ephemeris_search_path()
    auxiliary = AuxiliaryInputs(auxiliary_path)
    observer: NativeSampleObserver | None = options.pop("_sample_observer", None)
    request = {
        "entry": entry,
        "args": encode(args),
        "kwargs": encode(options),
        "path": session.path,
        "jpl": session.jpl,
        "clock": clock_snapshot(),
        "ut1_source": "iers_c04" if active_ut1.get() is not None else "swiss_delta_t",
        "observer": observer is not None,
        "auxiliary_path": auxiliary_path,
        "auxiliary_fingerprints": auxiliary.initial,
    }
    if current_policy() is not None:
        request["physical_ephemeris_policy"] = policy_mode()
    payload = message_bytes(request)
    worker = Path(__file__).with_name("_native_worker.py")
    deadline = time.monotonic() + _TIMEOUT
    with subprocess.Popen(
        [sys.executable, "-I", "-u", str(worker)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=os.getcwd(),
    ) as process:
        assert process.stdin is not None
        try:
            process.stdin.write(payload)
            process.stdin.flush()
            while True:
                response = _receive(process, deadline)
                session.check()
                if response.get("kind") == "ready":
                    continue
                if response.get("kind") == "sample":
                    if observer is None:
                        raise NativeExecutionError("Unexpected native sample callback")
                    observer(*decode(response["args"]))
                    session.check()
                    process.stdin.write(message_bytes({"kind": "continue"}))
                    process.stdin.flush()
                    continue
                if response.get("kind") != "result":
                    raise NativeExecutionError(
                        "Invalid native calculation response kind"
                    )
                auxiliary.check()
                merge_clock_reads(response.get("clock_reads", []))
                if "error" in response:
                    error = response["error"]
                    if error["type"] == "source":
                        policy = current_policy()
                        if policy is not None:
                            policy.failure = policy.failure or error["reason"]
                        raise EphemerisSourceError(error["reason"])
                    if error["type"] == "jyotish":
                        if error.get("reason") not in JyotishCalculationError.MESSAGES:
                            raise NativeExecutionError(
                                "Invalid Jyotish integrity reason"
                            )
                        raise JyotishCalculationError(error["reason"])
                    if error["type"] == "value":
                        raise ValueError(error["message"])
                    if error["type"] == "import":
                        raise ModuleNotFoundError(
                            "Private native calculation dependency unavailable"
                        )
                    raise NativeExecutionError("Private native calculation failed")
                merge_worker_policy(response.get("physical_ephemeris_policy"))
                result = decode_result(response["value"])
                process.stdin.close()
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
                if process.returncode:
                    raise NativeExecutionError(
                        "Private native calculation did not finish cleanly"
                    )
                return result
        finally:
            # Also runs on callback exceptions and cancellation. Reap exactly
            # this owned child; never leave private input in a long-lived pool.
            if process.poll() is None:
                process.kill()
            process.wait()
