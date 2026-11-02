"""Run a whole registered operation in a fresh, private native-library process.

Swiss auxiliary tables and user Delta-T are mutable native state; closing the
library or starting a thread does not reliably reset them. A new exec process
owns all clock, geometry, event and grid calls for one outer operation. This is
state isolation, not independent astronomical validation or an atomic file read.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import re
import subprocess
import sys
import time
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from fatebridge.core.execution_context import (
    clock_snapshot,
    merge_clock_reads,
)
from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset
from fatebridge.utils.errors import EphemerisSourceError, JyotishCalculationError

_WORKER_ACTIVE = False
_ENTRIES = {
    "fatebridge.core.human_design_cycle_input.validate_cycle_reference",
    "fatebridge.services.human_design.calculate_human_design",
    "fatebridge.core.jyotish.positions",
    "fatebridge.core.jyotish.build_india",
    "fatebridge.services.jyotish.calculate_vimshottari",
    "fatebridge.services.astrology.calculate_core_chart_analysis",
}
_MAX_MESSAGE = 64 * 1024 * 1024
_TIMEOUT = 1800.0
_AUXILIARY_EVIDENCE: dict[str, Any] | None = None


class AuxiliaryInputs:
    """Endpoint fingerprints, including absent files that could shadow a source.

    Swiss 2.10.03 swi_fopen uses at most 20 path components; Unix accepts both
    colon and semicolon, Windows semicolon. These are candidate identities,
    not proof that a particular native call read a candidate file.
    """

    def __init__(self, search_path: str | None) -> None:
        directories = re.split(";" if os.name == "nt" else "[;:]", search_path or ".")[
            :20
        ]
        self.paths = [
            Path(directory or ".").absolute() / name
            for directory in directories
            for name in ("swe_deltat.txt", "sedeltat.txt", "seleapsec.txt")
        ]
        self.initial = self.snapshot()

    def snapshot(self) -> list[Any]:
        rows = []
        for index, path in enumerate(self.paths):
            try:
                digest = hashlib.sha256()
                with path.open("rb") as source:
                    size = 0
                    for chunk in iter(lambda: source.read(65536), b""):
                        size += len(chunk)
                        digest.update(chunk)
                rows.append([index, size, digest.hexdigest()])
            except FileNotFoundError:
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
                    "filename": self.paths[index].name,
                    "bytes": size,
                    "sha256": digest,
                }
                for index, size, digest in self.initial
                if digest is not None
            ],
            "scope": "Clock inversion, physical coordinates, houses, solar events and all grid samples share this private native context. Auxiliary search candidates are fingerprinted at calculation endpoints; identities do not prove atomic reads, table validity or astronomical accuracy.",
        }


def context_for_entry(entry: str) -> dict[str, str]:
    if entry == "fatebridge.core.human_design_cycle_input.validate_cycle_reference":
        return {
            "lifetime": "one_human_design_cycle_request_validation",
            "scope": "Request-only birth/reference TT ordering in a fresh native process. The calculation revalidates in its separate whole-operation context. Auxiliary candidate identities do not prove atomic reads, table validity or physical accuracy.",
        }
    if entry == "fatebridge.services.human_design.calculate_human_design":
        from fatebridge.core.human_design_context import CONTEXT_LIFETIME, CONTEXT_SCOPE

        return {"lifetime": CONTEXT_LIFETIME, "scope": CONTEXT_SCOPE}
    return {}


def context_evidence() -> dict[str, Any]:
    from fatebridge.core.compressed_ephemeris import endpoint_context_evidence

    return {
        **(_AUXILIARY_EVIDENCE or {"mechanism": "local_engine_context"}),
        "compressed_file_endpoint_policy": endpoint_context_evidence(),
    }


class NativeExecutionError(RuntimeError):
    """Bounded, non-input-bearing failure of the private calculation process."""


def in_native_worker() -> bool:
    return _WORKER_ACTIVE


JSON_TREE_ENCODING = "json_tree_v1"


def _json_tree(value: Any) -> bool:
    """Exact finite JSON types only; do not erase tuples or typed objects."""
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_json_tree(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _json_tree(item) for key, item in value.items())
    return False


def encode_result(value: Any, encoding: str | None = None) -> Any:
    """Negotiate a lossless JSON-tree result, keeping legacy typed fallback."""
    if encoding not in (None, JSON_TREE_ENCODING):
        raise NativeExecutionError("Unsupported native result encoding")
    if encoding == JSON_TREE_ENCODING and _json_tree(value):
        return [JSON_TREE_ENCODING, value]
    return encode(value)


def decode_result(value: Any, encoding: str | None = None) -> Any:
    if encoding not in (None, JSON_TREE_ENCODING):
        raise NativeExecutionError("Unsupported native result encoding")
    if (
        isinstance(value, list)
        and value
        and value[0] == JSON_TREE_ENCODING
        and encoding != JSON_TREE_ENCODING
    ):
        raise NativeExecutionError("Unnegotiated native JSON-tree result")
    return decode(value)


def encode(value: Any) -> Any:
    """Typed JSON only; maps cannot impersonate protocol type envelopes."""
    from fatebridge.core.astro.birth import AstroBirthInfo

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Native calculation values must be finite")
        return value
    if isinstance(value, datetime):
        zone = getattr(value.tzinfo, "key", None) or getattr(value.tzinfo, "zone", None)
        return ["datetime", value.isoformat(), zone, value.fold]
    if isinstance(value, AstroBirthInfo):
        return [
            "birth",
            encode({f.name: getattr(value, f.name) for f in fields(value)}),
        ]
    if isinstance(value, dict):
        return ["map", [[encode(k), encode(v)] for k, v in value.items()]]
    if isinstance(value, (tuple, list)):
        return [
            "tuple" if isinstance(value, tuple) else "list",
            [encode(v) for v in value],
        ]
    raise TypeError("Unsupported native calculation argument type")


def decode(value: Any) -> Any:
    if not isinstance(value, list):
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        raise NativeExecutionError("Invalid native calculation value")
    if not value:
        raise NativeExecutionError("Invalid native calculation envelope")
    tag = value[0]
    if tag == JSON_TREE_ENCODING and len(value) == 2:
        if not _json_tree(value[1]):
            raise NativeExecutionError("Invalid native JSON tree")
        return value[1]
    if tag == "datetime" and len(value) == 4:
        moment = datetime_fromisoformat_preserving_offset(value[1])
        if value[2] is not None:
            from fatebridge.utils.timezones import parse_timezone_name

            # Use the package's pinned TZif, as birth normalization does. The
            # host ZoneInfo database can contain different historical rules.
            named = moment.replace(tzinfo=parse_timezone_name(value[2]), fold=value[3])
            if named.utcoffset() != moment.utcoffset():
                raise NativeExecutionError("Native datetime zone offset changed")
            moment = named
        return moment.replace(fold=value[3])
    if tag == "birth" and len(value) == 2:
        from fatebridge.core.astro.birth import AstroBirthInfo

        return AstroBirthInfo(**decode(value[1]))
    if tag == "map" and len(value) == 2:
        return {decode(k): decode(v) for k, v in value[1]}
    if tag in {"list", "tuple"} and len(value) == 2:
        items = [decode(v) for v in value[1]]
        return tuple(items) if tag == "tuple" else items
    raise NativeExecutionError("Invalid native calculation envelope")


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


def _receive(process: subprocess.Popen[bytes], deadline: float) -> Any:
    assert process.stdout is not None
    # Windows selectors cannot monitor anonymous pipes. One bounded reader is
    # active at a time; a timeout kills/reaps the child in calculate's finally,
    # closing the pipe and ending this reader as well.
    received: queue.Queue[bytes | Exception] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            assert process.stdout is not None
            received.put(process.stdout.readline(_MAX_MESSAGE + 1))
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
    if isinstance(payload, Exception) or not payload:
        raise NativeExecutionError("Private native calculation exited without a result")
    if len(payload) > _MAX_MESSAGE:
        raise NativeExecutionError("Native calculation message exceeds limit")
    try:
        message = json.loads(payload)
    except (ValueError, UnicodeError) as error:
        raise NativeExecutionError("Invalid native calculation response") from error
    if not isinstance(message, dict):
        raise NativeExecutionError("Invalid native calculation response")
    return message


def calculate(
    entry: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    result_encoding: str | None = None,
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
    if result_encoding not in (None, JSON_TREE_ENCODING):
        raise NativeExecutionError("Unsupported native result encoding")
    session = current_source_session()
    if session is None:
        raise NativeExecutionError("Private calculation requires a source session")
    options = dict(kwargs)
    auxiliary_path = effective_ephemeris_search_path()
    auxiliary = AuxiliaryInputs(auxiliary_path)
    observer: Callable[..., Any] | None = options.pop("_sample_observer", None)
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
    if result_encoding is not None:
        request["result_encoding"] = result_encoding
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
                auxiliary.check()
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
                        raise ImportError(
                            "Private native calculation dependency unavailable"
                        )
                    raise NativeExecutionError("Private native calculation failed")
                merge_worker_policy(response.get("physical_ephemeris_policy"))
                result = decode_result(response["value"], result_encoding)
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
