"""Retain a single immutable JSON artifact when the selected response overflows."""

import json
import math
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue

from fatebridge.application.result_budget import overflow_response
from fatebridge.core.public_output import public_payload
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.private_files import (
    default_result_directory,
    ensure_private_directory,
    locked_private_file,
    open_private_file,
    result_directory_candidates,
    validate_private_directory,
)

DEFAULT_MCP_RESPONSE_CHARS = 8192
PAGE_CHARS = 2048
RETENTION_SECONDS = 3600
MAX_STORED_BYTES = 64 * 1024 * 1024
MIN_RESPONSE_LIMIT_CHARS = 4096
MAX_RESPONSE_LIMIT_CHARS = 65536
RESULT_ID_PATTERN = re.compile(r"[0-9a-f]{48}")
PAYLOAD_MEMBER = ',"payload":'


def invalid_parameter(message: str, path: str, code: str) -> ParameterError:
    return ParameterError(message, [{"path": path, "code": code}])


@dataclass(frozen=True, kw_only=True)
class RetainedResult:
    path: Path
    payload_text: str | None
    payload: dict[str, JsonValue]


@dataclass(frozen=True, kw_only=True)
class ResultReference:
    result_id: str
    expires_at: float
    path: Path
    total_chars: int
    total_bytes: int
    available_fields: list[str]

    def as_result(self) -> dict[str, JsonValue]:
        return {
            "mode": "paged",
            "result_id": self.result_id,
            "total_chars": self.total_chars,
            "total_bytes": self.total_bytes,
            "expires_at": self.expires_at,
            "page_chars": PAGE_CHARS,
            "manifest_uri": f"fatebridge://results/{self.result_id}",
            "first_page_uri": f"fatebridge://results/{self.result_id}/pages/0",
            "rest_manifest_path": f"/api/results/{self.result_id}",
            "file_path": str(self.path),
            "file_payload_path": "payload",
            "available_fields": [*self.available_fields],
            "deferred_fields": [],
        }


class ResultStore:
    """Private JSON artifacts. Only publication and retention require a lock."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory_path: Path | None = directory

    @property
    def directory(self) -> Path:
        return self._directory_path or default_result_directory()

    def _published_path(self, result_id: str) -> Path:
        if not RESULT_ID_PATTERN.fullmatch(result_id):
            raise invalid_parameter("无效结果引用", "result_id", "invalid_result_id")
        name = f"{result_id}.json"
        directory = self._directory_path
        if directory is None:
            matches: dict[tuple[int, int], Path] = {}
            for candidate in result_directory_candidates():
                try:
                    (candidate / name).lstat()
                    info = candidate.lstat()
                except OSError:
                    continue
                matches.setdefault((info.st_dev, info.st_ino), candidate)
            if len(matches) > 1:
                raise invalid_parameter(
                    "结果引用匹配多个目录，请用 --directory 指定原交付文件所在目录",
                    "result_id",
                    "result_directory_ambiguous",
                )
            if matches:
                directory = next(iter(matches.values()))
        if directory is None:
            raise invalid_parameter(
                "结果引用不存在或已过期", "result_id", "result_unavailable"
            )
        try:
            return validate_private_directory(directory) / name
        except (OSError, RuntimeError) as exc:
            raise invalid_parameter(
                "结果目录不可用或不满足私有文件要求", "result_id", "result_unavailable"
            ) from exc

    def _record(
        self, result_id: str, allowed_tools: set[str] | None = None
    ) -> RetainedResult:
        path = self._published_path(result_id)
        try:
            fd = open_private_file(path, os.O_RDONLY)
            with os.fdopen(fd, encoding="utf-8") as handle:
                raw = handle.read()
                record: JsonValue = json.loads(raw)
        except (OSError, ValueError, RuntimeError) as exc:
            raise invalid_parameter(
                "结果引用不存在或已损坏", "result_id", "result_unavailable"
            ) from exc
        if not isinstance(record, dict):
            raise invalid_parameter("结果引用已损坏", "result_id", "result_unavailable")
        expires_at = record.get("expires_at")
        payload = record.get("payload")
        if (
            not isinstance(expires_at, (int, float))
            or not math.isfinite(expires_at)
            or not isinstance(payload, dict)
        ):
            raise invalid_parameter("结果引用已损坏", "result_id", "result_unavailable")
        if expires_at <= time.time():
            raise invalid_parameter(
                "结果引用已过期，请重新计算", "result_id", "result_expired"
            )
        if allowed_tools is not None:
            receipt = payload.get("run_metadata")
            tool_name = receipt.get("tool_name") if isinstance(receipt, dict) else None
            if not isinstance(tool_name, str) or tool_name not in allowed_tools:
                raise ValueError("结果所属工具未在当前 MCP 配置中公开")
        prefix = format_json_response({"expires_at": expires_at})[:-1]
        prefix += PAYLOAD_MEMBER
        text = (
            raw[len(prefix) : -1]
            if raw.startswith(prefix) and raw.endswith("}")
            else None
        )
        return RetainedResult(path=path, payload_text=text, payload=payload)

    def put(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        payload = public_payload(payload)
        text = format_json_response(payload)
        body = text.encode("utf-8")
        reference = self._reference(payload, len(text), len(body))
        self._publish(reference, body)
        return reference.as_result()

    def _reference(
        self, payload: dict[str, JsonValue], total_chars: int, total_bytes: int
    ) -> ResultReference:
        result_id = secrets.token_hex(24)
        expires_at = time.time() + RETENTION_SECONDS
        return ResultReference(
            result_id=result_id,
            expires_at=expires_at,
            path=self.directory / f"{result_id}.json",
            total_chars=total_chars,
            total_bytes=total_bytes,
            available_fields=list(payload),
        )

    def _publish(self, reference: ResultReference, body: bytes) -> None:
        header = format_json_response({"expires_at": reference.expires_at}).encode(
            "utf-8"
        )
        record = header[:-1] + PAYLOAD_MEMBER.encode("ascii") + body + b"}"
        if len(record) > MAX_STORED_BYTES:
            raise invalid_parameter(
                "结果超过本地交付存储容量，请缩小 fields", "fields", "result_too_large"
            )
        path = reference.path
        directory = ensure_private_directory(path.parent)
        pending = path.with_suffix(".pending")
        with locked_private_file(directory / ".lock"):
            remaining_bytes = MAX_STORED_BYTES - len(record)
            cutoff = time.time() - RETENTION_SECONDS
            retained: list[tuple[float, Path, int]] = []
            for artifact in directory.iterdir():
                if artifact.suffix not in {".json", ".pending"}:
                    continue
                if (
                    not RESULT_ID_PATTERN.fullmatch(artifact.stem)
                    or artifact.is_symlink()
                ):
                    continue
                info = artifact.stat()
                if artifact.suffix == ".pending" or info.st_mtime <= cutoff:
                    artifact.unlink()
                else:
                    retained.append((info.st_mtime, artifact, info.st_size))
                    remaining_bytes -= info.st_size
            try:
                fd = open_private_file(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(record)
                created_at = reference.expires_at - RETENTION_SECONDS
                os.utime(pending, (created_at, created_at))
                for _, artifact, size in sorted(retained):
                    if remaining_bytes >= 0:
                        break
                    artifact.unlink()
                    remaining_bytes += size
                pending.replace(path)
            finally:
                pending.unlink(missing_ok=True)

    def get(self, result_id: str) -> dict[str, JsonValue]:
        return self._record(result_id).payload

    def manifest(
        self, result_id: str, *, allowed_tools: set[str] | None = None
    ) -> dict[str, JsonValue]:
        retained_result = self._record(result_id, allowed_tools)
        payload = retained_result.payload
        text = retained_result.payload_text or format_json_response(payload)
        resource = f"fatebridge://results/{result_id}"
        return {
            "result_id": result_id,
            "run_metadata": payload.get("run_metadata"),
            "file_path": str(retained_result.path),
            "rest_manifest_path": f"/api/results/{result_id}",
            "rest_export_path": f"/api/results/{result_id}/payload",
            "first_page_uri": f"{resource}/pages/0",
            "total_chars": len(text),
            "total_bytes": len(text.encode("utf-8")),
            "page_chars": PAGE_CHARS,
            "file_payload_path": "payload",
            "available_fields": list(payload),
            "fields": [
                {"path": name, "first_page_uri": f"{resource}/fields/{name}/0"}
                for name in payload
            ],
            "note": "逐页读取所需 JSON 字段。完整导出可一次读取 REST payload 或本地 JSON。",
        }

    def verified_page(
        self,
        result_id: str,
        expected_run_id: str,
        offset: int = 0,
        path: str | None = None,
        *,
        allowed_tools: set[str] | None = None,
    ) -> dict[str, JsonValue]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", expected_run_id):
            raise invalid_parameter(
                "需要原回执的 run_id", "expected_run_id", "invalid_run_id"
            )
        return self.page(
            result_id,
            offset,
            path,
            allowed_tools=allowed_tools,
            expected_run_id=expected_run_id,
        )

    def page(
        self,
        result_id: str,
        offset: int = 0,
        path: str | None = None,
        *,
        allowed_tools: set[str] | None = None,
        expected_run_id: str | None = None,
        verify_integrity: bool = False,
    ) -> dict[str, JsonValue]:
        if offset < 0:
            raise invalid_parameter(
                "分页 offset 不能为负数", "offset", "invalid_offset"
            )
        if path is not None and (len(path) > 1000 or len(path.split(".")) > 64):
            raise invalid_parameter("结果字段路径过长", "path", "invalid_result_path")
        retained_result = self._record(result_id, allowed_tools)
        text = retained_result.payload_text
        payload = retained_result.payload
        verification: dict[str, JsonValue] = {}
        if verify_integrity and expected_run_id is None and "run_metadata" in payload:
            raise invalid_parameter(
                "需要原回执的 run_id", "expected_run_id", "invalid_run_id"
            )
        if expected_run_id is not None:
            run = payload.get("run_metadata") or {}
            if not isinstance(run, dict) or run.get("run_id") != expected_run_id:
                raise invalid_parameter(
                    "结果不属于指定原 run", "expected_run_id", "result_run_mismatch"
                )
            verification = {
                "verification": {
                    "method": "retained_payload_integrity_v2",
                    "scope": "entire_retained_payload",
                    "run_id": expected_run_id,
                    "tool_name": run.get("tool_name"),
                    "serialization": 'UTF-8 json.dumps(ensure_ascii=False,separators=(",",":")); insertion order',
                    "calculation_repeated": False,
                }
            }
        if path is not None:
            value: JsonValue = payload
            for part in path.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                elif (
                    isinstance(value, list)
                    and part.isdecimal()
                    and len(part) < 10
                    and int(part) < len(value)
                ):
                    value = value[int(part)]
                else:
                    raise invalid_parameter(
                        "结果字段路径不存在", "path", "unknown_result_path"
                    )
            text = format_json_response(value)
        elif text is None:
            text = format_json_response(payload)
        if offset > len(text):
            raise invalid_parameter(
                "分页 offset 超出结果长度", "offset", "invalid_offset"
            )
        end = min(offset + PAGE_CHARS, len(text))
        next_offset = end if end < len(text) else None
        base = f"fatebridge://results/{result_id}"
        locator = f"{base}/pages" if path is None else f"{base}/fields/{path}"
        return {
            "result_id": result_id,
            "path": path,
            "offset": offset,
            "next_offset": next_offset,
            "total_chars": len(text),
            "text": text[offset:end],
            **verification,
            **(
                {
                    "next_uri": (
                        f"{locator}/{next_offset}" if next_offset is not None else None
                    )
                }
                if expected_run_id is None
                else {}
            ),
        }


RESULT_STORE = ResultStore()


def bound_response(
    payload: dict[str, JsonValue],
    response_char_limit: int = 0,
    *,
    compact: bool = True,
    selected_fields: list[str] | None = None,
) -> dict[str, JsonValue]:
    return bound_public_response(
        public_payload(payload),
        response_char_limit,
        compact=compact,
        selected_fields=selected_fields,
    )


def bound_public_response(
    payload: dict[str, JsonValue],
    response_char_limit: int = 0,
    *,
    compact: bool = True,
    selected_fields: list[str] | None = None,
) -> dict[str, JsonValue]:
    """Keep whole facts inline when possible and retain the exact selected result."""
    if response_char_limit == 0:
        return payload
    if not MIN_RESPONSE_LIMIT_CHARS <= response_char_limit <= MAX_RESPONSE_LIMIT_CHARS:
        raise invalid_parameter(
            "response_char_limit 须为 0 或 4096–65536",
            "response_char_limit",
            "invalid_response_limit",
        )

    text = format_json_response(payload, compact=compact)
    if len(text) <= response_char_limit:
        return payload
    body_text = text if compact else format_json_response(payload)
    body = body_text.encode("utf-8")
    reference = RESULT_STORE._reference(payload, len(body_text), len(body))
    output = overflow_response(
        payload,
        reference.as_result(),
        selected_fields,
        compact,
        len(text),
        response_char_limit,
    )
    RESULT_STORE._publish(reference, body)
    return output
