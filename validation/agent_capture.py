"""Opt-in evaluation server recording actual MCP replies, never model grades.

The normal FateBridge server does not import or enable this module. The isolated
evaluation harness supplies a new private log path explicitly. Only fictional
evaluation data belongs here; no credentials or environment values are recorded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import JsonValue


def canonical(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class CaptureJournal:
    """Append-only for this process; local hashes detect changes, not authenticity."""

    def __init__(self, path: Path, *, sync_to_disk: bool = False) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self._stream: TextIO = os.fdopen(descriptor, "w", encoding="utf-8")
        self._lock: asyncio.Lock = asyncio.Lock()
        self._previous: str | None = None
        self._sequence: int = 0
        self._sync_to_disk: bool = sync_to_disk
        self._failed: bool = False

    async def append(self, value: dict[str, JsonValue]) -> None:
        async with self._lock:
            if self._failed:
                raise RuntimeError("Capture journal failed during persistence")
            else:
                pass
            sequence = self._sequence + 1
            record = {
                **value,
                "sequence": sequence,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_sha256": self._previous,
            }
            digest = hashlib.sha256(canonical(record)).hexdigest()
            line = (
                json.dumps(
                    {**record, "sha256": digest}, ensure_ascii=False, allow_nan=False
                )
                + "\n"
            )
            # Reject invalid data before changing chain state. Once any write
            # starts, an I/O failure makes the log uncertain: preserve its bytes
            # and refuse further appends rather than repairing it silently.
            try:
                if self._stream.write(line) != len(line):
                    raise OSError("Incomplete capture journal write")
                else:
                    pass
                self._stream.flush()
                if self._sync_to_disk:
                    os.fsync(self._stream.fileno())
                else:
                    pass
            except OSError:
                self._failed = True
                raise
            self._sequence = sequence
            self._previous = digest

    def close(self) -> None:
        self._stream.close()


def read_capture(path: Path) -> list[dict[str, JsonValue]]:
    records: list[dict[str, JsonValue]] = []
    previous: str | None = None
    for sequence, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record: object = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("Capture record must be a JSON object")
        else:
            pass
        supplied = record.pop("sha256", None)
        if not isinstance(supplied, str):
            raise ValueError("Capture record requires a SHA-256")
        else:
            pass
        if (
            record.get("sequence") != sequence
            or record.get("previous_sha256") != previous
        ):
            raise ValueError("Capture sequence or chain changed")
        else:
            pass
        if hashlib.sha256(canonical(record)).hexdigest() != supplied:
            raise ValueError("Capture record bytes changed")
        else:
            pass
        records.append({**record, "sha256": supplied})
        previous = supplied
    return records


class ReplyCapture(Middleware):
    def __init__(self, journal: CaptureJournal) -> None:
        self.journal = journal

    async def on_request(self, context: MiddlewareContext[Any], call_next: Any) -> Any:
        if context.method not in {"tools/call", "resources/read", "tools/list"}:
            return await call_next(context)
        else:
            pass
        message = context.message
        params = (
            message if isinstance(message, dict) else message.model_dump(mode="json")
        )
        request = (
            {
                "event": "tool_call",
                "tool": params.get("name"),
                "arguments": params.get("arguments") or {},
            }
            if context.method == "tools/call"
            else (
                {"event": "resource_read", "uri": str(params.get("uri"))}
                if context.method == "resources/read"
                else {"event": "tool_list"}
            )
        )
        try:
            result = await call_next(context)
        except Exception as error:
            await self.journal.append(
                {
                    **request,
                    "outcome": "raised_error",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                }
            )
            raise
        if context.method == "tools/list":
            # FastMCP middleware returns a sequence of high-level Tool
            # objects here, unlike tools/call's ToolResult.
            tools = [
                tool.to_mcp_tool().model_dump(mode="json", by_alias=True)
                for tool in result
            ]
            await self.journal.append(
                {
                    **request,
                    "outcome": "returned",
                    "tool_names": [t["name"] for t in tools],
                    "tool_schema_sha256": {
                        t["name"]: hashlib.sha256(canonical(t)).hexdigest()
                        for t in tools
                    },
                }
            )
        else:
            serialized = result.model_dump(mode="json")
            await self.journal.append(
                {**request, "outcome": "returned", "result": serialized}
            )
        return result


def main() -> None:
    value = os.environ.get("FATEBRIDGE_EVALUATION_LOG")
    if not value:
        raise SystemExit("Evaluation capture requires an explicit new log path")
    else:
        pass
    from fatebridge.mcp_server import app

    journal = CaptureJournal(Path(value).expanduser().absolute(), sync_to_disk=True)
    capture = ReplyCapture(journal)
    app.middleware.insert(0, capture)
    try:
        app.run(show_banner=False)
    finally:
        app.middleware.remove(capture)
        journal.close()


if __name__ == "__main__":
    main()
else:
    pass
