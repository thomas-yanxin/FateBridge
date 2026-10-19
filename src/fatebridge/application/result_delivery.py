"""Bounded, lossless delivery of large results without recalculating them."""

import hashlib
import json
import math
import os
import re
import secrets
import struct
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from fatebridge.utils.errors import ParameterError

DEFAULT_MCP_RESPONSE_CHARS = 8192
PAGE_CHARS = 2048
RETENTION_SECONDS = 3600
MAX_STORED_BYTES = 64 * 1024 * 1024
_RESULT_ID = re.compile(r"[0-9a-f]{48}\Z")
_ARTIFACT = re.compile(
    r"([0-9a-f]{48})\.(?:json|meta|idx|field-[0-9a-f]{64}\.(?:meta|idx))(?:\.pending)?\Z"
)
_INDEX_ENTRY = struct.Struct("!Q")


def _invalid(message: str, path: str, code: str) -> ParameterError:
    return ParameterError(message, [{"path": path, "code": code}])


def _json(value: Any, compact: bool = True) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        **({"separators": (",", ":")} if compact else {"indent": 2}),
    )


class ResultStore:
    """Private, process-safe immutable artifacts with indexed character pages.

    The JSON record exposes its result at ``file_payload_path=payload``.
    Small sidecars hold receipts and UTF-8 byte positions at character boundaries;
    pages never deserialize or hash the complete result. Field sidecars point into
    that same JSON record, rather than copying or caching personal result bodies.
    """

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or Path(tempfile.gettempdir()) / (
            f"fatebridge-results-{os.getuid()}"
        )

    def _directory(self) -> Path:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if self.directory.is_symlink() or info.st_uid != os.getuid():
            raise RuntimeError("Result artifact directory is not owned by this user")
        if info.st_mode & 0o077:
            raise RuntimeError("Result artifact directory must be private")
        return self.directory

    @contextmanager
    def _locked(self) -> Iterator[None]:
        # flock coordinates separate REST/MCP/CLI processes and threads. Readers
        # hold the lock through seek/read, so pruning cannot remove their source.
        import fcntl

        fd = os.open(
            self._directory() / ".lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RuntimeError("Result artifact lock must be private")
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _path(self, result_id: str, suffix: str = "json") -> Path:
        if not _RESULT_ID.fullmatch(result_id):
            raise _invalid("无效结果引用", "result_id", "invalid_result_id")
        return self._directory() / f"{result_id}.{suffix}"

    def _files(self) -> Dict[str, list[Path]]:
        groups: Dict[str, list[Path]] = {}
        for path in self._directory().iterdir():
            match = _ARTIFACT.fullmatch(path.name)
            if match and path.name.endswith(".pending") and not path.is_symlink():
                # A writer that died cannot still hold the acquired process lock.
                path.unlink(missing_ok=True)
                continue
            if match and not path.is_symlink():
                groups.setdefault(match[1], []).append(path)
        return groups

    def _remove(self, result_id: str) -> None:
        for path in self._files().get(result_id, []):
            path.unlink(missing_ok=True)

    def _prune(self, reserve_bytes: int = 0, keep_id: Optional[str] = None) -> None:
        """Called under the directory lock; count every committed sidecar byte."""
        groups = self._files()
        records = []
        now = time.time()
        for result_id, paths in groups.items():
            primary = self._path(result_id)
            if not primary.exists():
                for path in paths:
                    path.unlink(missing_ok=True)
                continue
            info = primary.stat()
            if result_id != keep_id and info.st_mtime + RETENTION_SECONDS <= now:
                for path in paths:
                    path.unlink(missing_ok=True)
                continue
            records.append((info.st_mtime, result_id, paths))
        total = sum(path.stat().st_size for _, _, paths in records for path in paths)
        for _, result_id, paths in sorted(records):
            if total + reserve_bytes <= MAX_STORED_BYTES:
                break
            if result_id == keep_id:
                continue
            for path in paths:
                total -= path.stat().st_size
                path.unlink(missing_ok=True)
        if total + reserve_bytes > MAX_STORED_BYTES:
            raise _invalid(
                "结果超过本地交付存储容量，请缩小 fields", "fields", "result_too_large"
            )

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                return value
        except (OSError, ValueError):
            pass
        raise _invalid("结果引用不存在或已损坏", "result_id", "result_unavailable")

    def _record(self, result_id: str) -> Dict[str, Any]:
        record = self._read_json(self._path(result_id))
        if not isinstance(record.get("payload"), dict):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")
        self._check_expiry(result_id, record)
        return record

    def _check_expiry(self, result_id: str, metadata: Dict[str, Any]) -> None:
        expires_at = metadata.get("expires_at")
        if not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")
        if expires_at <= time.time():
            self._remove(result_id)
            raise _invalid("结果引用已过期，请重新计算", "result_id", "result_expired")

    @staticmethod
    def _index(text: str) -> bytes:
        positions = [0]
        offset = 0
        for start in range(0, len(text), PAGE_CHARS):
            offset += len(text[start : start + PAGE_CHARS].encode("utf-8"))
            positions.append(offset)
        return b"".join(_INDEX_ENTRY.pack(position) for position in positions)

    def _commit(self, files: Dict[Path, bytes]) -> None:
        staging = []
        try:
            for path, content in files.items():
                pending = path.with_name(path.name + ".pending")
                staging.append(pending)
                fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
            # Publish metadata last; incomplete writes stay unavailable to readers.
            for path, pending in zip(files, staging):
                pending.replace(path)
        finally:
            for pending in staging:
                pending.unlink(missing_ok=True)

    def _store_main(
        self, result_id: str, payload: Dict[str, Any], expires_at: float
    ) -> Dict[str, Any]:
        text = _json(payload)
        encoded = text.encode("utf-8")
        prefix = ('{"expires_at":' + _json(expires_at) + ',"payload":').encode()
        metadata = {
            "format": 1,
            "expires_at": expires_at,
            "body_offset": len(prefix),
            "total_chars": len(text),
            "total_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "run_metadata": payload.get("run_metadata"),
            "available_fields": list(payload),
        }
        files = {
            self._path(result_id, "idx"): self._index(text),
            self._path(result_id): prefix + encoded + b"}",
            self._path(result_id, "meta"): _json(metadata).encode("utf-8"),
        }
        if sum(map(len, files.values())) > MAX_STORED_BYTES:
            raise _invalid(
                "结果超过本地交付存储容量，请缩小 fields", "fields", "result_too_large"
            )
        self._prune(sum(map(len, files.values())), keep_id=result_id)
        self._commit(files)
        # Derive creation time from the immutable receipt expiry for pruning.
        created_at = expires_at - RETENTION_SECONDS
        os.utime(self._path(result_id), (created_at, created_at))
        return metadata

    @staticmethod
    def _validate_index_metadata(metadata: Dict[str, Any]) -> None:
        if (
            any(
                type(metadata.get(key)) is not int or metadata[key] < 0
                for key in ("body_offset", "total_chars", "total_bytes")
            )
            or not isinstance(metadata.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
        ):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")

    def _metadata(self, result_id: str) -> Dict[str, Any]:
        primary = self._path(result_id)
        if not primary.exists() or primary.is_symlink():
            raise _invalid("结果引用不存在或已过期", "result_id", "result_unavailable")
        sidecar = self._path(result_id, "meta")
        metadata = self._read_json(sidecar)
        if metadata.get("format") != 1:
            raise _invalid("结果引用格式不受支持", "result_id", "result_unavailable")
        self._check_expiry(result_id, metadata)
        self._validate_index_metadata(metadata)
        if (
            not isinstance(metadata.get("available_fields"), list)
            or not all(isinstance(name, str) for name in metadata["available_fields"])
            or not (
                metadata.get("run_metadata") is None
                or isinstance(metadata["run_metadata"], dict)
            )
        ):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")
        return metadata

    def put(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result_id = secrets.token_hex(24)
        expires_at = time.time() + RETENTION_SECONDS
        with self._locked():
            metadata = self._store_main(result_id, payload, expires_at)
        return {
            "mode": "paged",
            "result_id": result_id,
            "sha256": metadata["sha256"],
            "total_chars": metadata["total_chars"],
            "total_bytes": metadata["total_bytes"],
            "expires_at": expires_at,
            "page_chars": PAGE_CHARS,
            "manifest_uri": f"fatebridge://results/{result_id}",
            "first_page_uri": f"fatebridge://results/{result_id}/pages/0",
            "rest_manifest_path": f"/api/results/{result_id}",
            "file_path": str(self._path(result_id)),
            "file_payload_path": "payload",
            "available_fields": metadata["available_fields"],
            "deferred_fields": [],
        }

    def get(self, result_id: str) -> Dict[str, Any]:
        with self._locked():
            payload: Dict[str, Any] = self._record(result_id)["payload"]
            return payload

    def manifest(
        self, result_id: str, *, allowed_tools: Optional[set[str]] = None
    ) -> Dict[str, Any]:
        with self._locked():
            metadata = self._metadata(result_id)
            if allowed_tools is not None:
                self._check_scope(metadata, allowed_tools)
        return {
            "result_id": result_id,
            "run_metadata": metadata["run_metadata"],
            "sha256": metadata["sha256"],
            "total_chars": metadata["total_chars"],
            "page_chars": PAGE_CHARS,
            "file_payload_path": "payload",
            "fields": [
                {
                    "path": name,
                    "first_page_uri": f"fatebridge://results/{result_id}/fields/{name}/0",
                }
                for name in metadata["available_fields"]
            ],
            "note": (
                "按所需点路径读取字段，也支持数组数字索引；分页 text 是 JSON 文档片段，"
                "完整读取需按 next_offset 拼接并核对 sha256，不要把单页当全文解析。"
            ),
        }

    def _field(
        self, result_id: str, path: str, metadata: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        suffix = "field-" + hashlib.sha256(path.encode("utf-8")).hexdigest()
        sidecar = self._path(result_id, suffix + ".meta")
        if sidecar.exists():
            field = self._read_json(sidecar)
            self._validate_index_metadata(field)
            return field, suffix + ".idx"
        value: Any = self._record(result_id)["payload"]
        byte_offset = metadata["body_offset"]
        # Canonical JSON subvalues are contiguous substrings of the stored body.
        # Earlier siblings along the selected path are disjoint: computing the
        # first index visits at most one full result, rather than once per page.
        for part in path.split("."):
            byte_offset += 1  # opening object/array delimiter
            if isinstance(value, dict) and part in value:
                for key, sibling in value.items():
                    byte_offset += len(_json(key).encode("utf-8")) + 1
                    if key == part:
                        value = sibling
                        break
                    byte_offset += len(_json(sibling).encode("utf-8")) + 1
            elif (
                isinstance(value, list)
                and part.isdecimal()
                and len(part) < 10
                and int(part) < len(value)
            ):
                index = int(part)
                for sibling in value[:index]:
                    byte_offset += len(_json(sibling).encode("utf-8")) + 1
                value = value[index]
            else:
                raise _invalid("结果字段路径不存在", "path", "unknown_result_path")
        text = _json(value)
        encoded = text.encode("utf-8")
        field = {
            "body_offset": byte_offset,
            "total_chars": len(text),
            "total_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        files = {
            self._path(result_id, suffix + ".idx"): self._index(text),
            sidecar: _json(field).encode("utf-8"),
        }
        replaced = sum(path.stat().st_size for path in files if path.exists())
        self._prune(sum(map(len, files.values())) - replaced, keep_id=result_id)
        self._commit(files)
        return field, suffix + ".idx"

    def _slice(
        self, result_id: str, metadata: Dict[str, Any], index_suffix: str, offset: int
    ) -> str:
        total = metadata["total_chars"]
        end = min(offset + PAGE_CHARS, total)
        if offset == total:
            return ""
        start_block = offset // PAGE_CHARS
        stop_block = (end + PAGE_CHARS - 1) // PAGE_CHARS
        try:
            fd = os.open(
                self._path(result_id, index_suffix), os.O_RDONLY | os.O_NOFOLLOW
            )
            with os.fdopen(fd, "rb") as handle:
                handle.seek(start_block * _INDEX_ENTRY.size)
                start_byte = _INDEX_ENTRY.unpack(handle.read(_INDEX_ENTRY.size))[0]
                handle.seek(stop_block * _INDEX_ENTRY.size)
                stop_byte = _INDEX_ENTRY.unpack(handle.read(_INDEX_ENTRY.size))[0]
            if not 0 <= start_byte <= stop_byte <= metadata["total_bytes"]:
                raise ValueError("Invalid result page index")
            fd = os.open(self._path(result_id), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                handle.seek(metadata["body_offset"] + start_byte)
                encoded = handle.read(stop_byte - start_byte)
            if len(encoded) != stop_byte - start_byte:
                raise ValueError("Incomplete result page")
            text = encoded.decode("utf-8")
            start = offset - start_block * PAGE_CHARS
            selected = text[start : start + end - offset]
            if len(selected) != end - offset:
                raise ValueError("Incomplete result character page")
            return selected
        except (OSError, ValueError, struct.error):
            raise _invalid(
                "结果引用已损坏", "result_id", "result_unavailable"
            ) from None

    def page(
        self,
        result_id: str,
        offset: int = 0,
        path: Optional[str] = None,
        *,
        allowed_tools: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        if offset < 0:
            raise _invalid("分页 offset 不能为负数", "offset", "invalid_offset")
        if path is not None and (len(path) > 1000 or len(path.split(".")) > 64):
            raise _invalid("结果字段路径过长", "path", "invalid_result_path")
        with self._locked():
            metadata = self._metadata(result_id)
            if allowed_tools is not None:
                self._check_scope(metadata, allowed_tools)
            index_suffix = "idx"
            if path is not None:
                metadata, index_suffix = self._field(result_id, path, metadata)
            total = metadata["total_chars"]
            if offset > total:
                raise _invalid("分页 offset 超出结果长度", "offset", "invalid_offset")
            text = self._slice(result_id, metadata, index_suffix, offset)
        end = min(offset + PAGE_CHARS, total)
        next_offset = end if end < total else None
        uri_base = (
            f"fatebridge://results/{result_id}/fields/{path}"
            if path is not None
            else f"fatebridge://results/{result_id}/pages"
        )
        return {
            "result_id": result_id,
            "path": path,
            "offset": offset,
            "next_offset": next_offset,
            "next_uri": (
                f"{uri_base}/{next_offset}" if next_offset is not None else None
            ),
            "total_chars": total,
            "sha256": metadata["sha256"],
            "text": text,
        }

    @staticmethod
    def _check_scope(metadata: Dict[str, Any], allowed_tools: set[str]) -> None:
        if (metadata.get("run_metadata") or {}).get("tool_name") not in allowed_tools:
            raise ValueError("结果所属工具未在当前 MCP 配置中公开")


RESULT_STORE = ResultStore()


def bound_response(
    payload: Dict[str, Any], response_char_limit: int = 0, *, compact: bool = True
) -> Dict[str, Any]:
    """Return either an intact payload or an explicit lossless delivery envelope."""
    if response_char_limit == 0:
        return payload
    if not 4096 <= response_char_limit <= 65536:
        raise _invalid(
            "response_char_limit 须为 0 或 4096–65536",
            "response_char_limit",
            "invalid_response_limit",
        )
    if len(_json(payload, compact)) <= response_char_limit:
        return payload
    delivery = RESULT_STORE.put(payload)
    output: Dict[str, Any] = {
        "run_metadata": payload.get("run_metadata"),
        "result_delivery": delivery,
    }
    fields = [key for key in payload if key != "run_metadata"]
    delivery["deferred_fields"] = list(fields)
    if len(_json(output, compact)) > response_char_limit:
        raise _invalid(
            "回执超过响应预算，请增大 response_char_limit",
            "response_char_limit",
            "response_limit_too_small",
        )
    priority = ["summary", "analysis_context", "status", "comprehensive_summary"]
    for key in dict.fromkeys([*priority, *fields]):
        if key not in payload or key == "run_metadata":
            continue
        candidate = dict(output)
        candidate[key] = payload[key]
        candidate["result_delivery"] = {
            **delivery,
            "deferred_fields": [
                name for name in delivery["deferred_fields"] if name != key
            ],
        }
        if len(_json(candidate, compact)) <= response_char_limit:
            output = candidate
            delivery = output["result_delivery"]
    return output
