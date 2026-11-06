"""Bounded, lossless delivery of large results without recalculating them."""

import hashlib
import json
import math
import os
import re
import secrets
import struct
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from pydantic import JsonValue

from fatebridge.core.public_output import public_payload
from fatebridge.utils.errors import ParameterError
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
        self._directory_path = directory

    @property
    def directory(self) -> Path:
        # Writers retain tempfile's normal writable-location selection. A reader
        # must not trigger that probe merely by importing this module.
        if self._directory_path is None:
            self._directory_path = default_result_directory()
        return self._directory_path

    @directory.setter
    def directory(self, value: Path) -> None:
        self._directory_path = value

    def _published_directory(self, result_id: str) -> Path:
        if not _RESULT_ID.fullmatch(result_id):
            raise _invalid("无效结果引用", "result_id", "invalid_result_id")
        directory = self._directory_path
        if directory is None:
            matches: dict[tuple[int, int], Path] = {}
            for candidate in result_directory_candidates():
                try:
                    info = candidate.lstat()
                    primary = candidate / f"{result_id}.json"
                    if primary.exists() or primary.is_symlink():
                        matches.setdefault((info.st_dev, info.st_ino), candidate)
                except OSError:
                    continue
            if len(matches) > 1:
                raise _invalid(
                    "结果引用匹配多个目录，请用 --directory 指定原交付文件所在目录",
                    "result_id",
                    "result_directory_ambiguous",
                )
            if not matches:
                raise _invalid(
                    "结果引用不存在或已过期", "result_id", "result_unavailable"
                )
            directory = next(iter(matches.values()))
        try:
            return validate_private_directory(directory)
        except (OSError, RuntimeError) as exc:
            raise _invalid(
                "结果目录不可用或不满足私有文件要求", "result_id", "result_unavailable"
            ) from exc

    def _directory(self) -> Path:
        return ensure_private_directory(self.directory)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        # Writers and indexed/raw-page readers retain the directory lock.
        # Verified snapshots use full-payload identity checks without a write lock.
        with locked_private_file(self._directory() / ".lock"):
            yield

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
            fd = open_private_file(path, os.O_RDONLY)
            with os.fdopen(fd, encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                return value
        except (OSError, ValueError, RuntimeError):
            pass
        raise _invalid("结果引用不存在或已损坏", "result_id", "result_unavailable")

    def _record(
        self, result_id: str, *, published_directory: Optional[Path] = None
    ) -> Dict[str, Any]:
        path = (
            self._path(result_id)
            if published_directory is None
            else published_directory / f"{result_id}.json"
        )
        record = self._read_json(path)
        if not isinstance(record.get("payload"), dict):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")
        self._check_expiry(
            result_id, record, remove_expired=published_directory is None
        )
        return record

    def _check_expiry(
        self, result_id: str, metadata: Dict[str, Any], *, remove_expired: bool = True
    ) -> None:
        expires_at = metadata.get("expires_at")
        if not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at):
            raise _invalid("结果引用已损坏", "result_id", "result_unavailable")
        if expires_at <= time.time():
            if remove_expired:
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
                fd = open_private_file(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
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
            "format": 2,
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

    def _metadata(
        self, result_id: str, *, published_directory: Optional[Path] = None
    ) -> Dict[str, Any]:
        primary = (
            self._path(result_id)
            if published_directory is None
            else published_directory / f"{result_id}.json"
        )
        if not primary.exists() or primary.is_symlink():
            raise _invalid("结果引用不存在或已过期", "result_id", "result_unavailable")
        sidecar = (
            self._path(result_id, "meta")
            if published_directory is None
            else published_directory / f"{result_id}.meta"
        )
        metadata = self._read_json(sidecar)
        if metadata.get("format") != 2:
            raise _invalid("结果引用格式不受支持", "result_id", "result_unavailable")
        self._check_expiry(
            result_id, metadata, remove_expired=published_directory is None
        )
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
        payload = public_payload(payload)
        result_id = secrets.token_hex(24)
        expires_at = time.time() + RETENTION_SECONDS
        with self._locked():
            metadata = self._store_main(result_id, payload, expires_at)
        return {
            "mode": "paged",
            "result_id": result_id,
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

    def verified_page(
        self,
        result_id: str,
        expected_run_id: str,
        offset: int = 0,
        path: Optional[str] = None,
        *,
        allowed_tools: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        """Verify the entire retained payload, then read a bounded part of it.

        The caller supplies the original run ID from its receipt. The stored
        checksum stays private and detects corruption against the manifest.
        Verification and selection use one immutable payload snapshot, without
        recalculation or trusting a field-sidecar digest. Concurrent pruning may
        make a result unavailable; mismatched snapshots never gain verification.
        This does not attest that a consumer has
        read every page or understood the returned business facts.
        """
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", expected_run_id):
            raise _invalid("需要原回执的 run_id", "expected_run_id", "invalid_run_id")
        if offset < 0:
            raise _invalid("分页 offset 不能为负数", "offset", "invalid_offset")
        if path is not None and (len(path) > 1000 or len(path.split(".")) > 64):
            raise _invalid("结果字段路径过长", "path", "invalid_result_path")
        directory = self._published_directory(result_id)
        metadata = self._metadata(result_id, published_directory=directory)
        if allowed_tools is not None:
            self._check_scope(metadata, allowed_tools)
        payload = self._record(result_id, published_directory=directory)["payload"]
        encoded = _json(payload).encode("utf-8")
        actual_digest = hashlib.sha256(encoded).hexdigest()
        if actual_digest != metadata["sha256"]:
            raise _invalid(
                "原结果完整性核验失败", "result_id", "result_digest_mismatch"
            )
        run = payload.get("run_metadata") or {}
        if not isinstance(run, dict) or run.get("run_id") != expected_run_id:
            raise _invalid(
                "结果不属于指定原 run", "expected_run_id", "result_run_mismatch"
            )
        if (
            run != metadata["run_metadata"]
            or metadata["total_bytes"] != len(encoded)
            or metadata["total_chars"] != len(encoded.decode("utf-8"))
            or metadata["available_fields"] != list(payload)
        ):
            raise _invalid(
                "结果与交付清单不一致", "result_id", "result_metadata_mismatch"
            )
        if allowed_tools is not None:
            self._check_scope({"run_metadata": run}, allowed_tools)
        value: Any = payload
        if path is not None:
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
                    raise _invalid("结果字段路径不存在", "path", "unknown_result_path")
        text = _json(value)
        if offset > len(text):
            raise _invalid("分页 offset 超出结果长度", "offset", "invalid_offset")
        end = min(offset + PAGE_CHARS, len(text))
        return {
            "result_id": result_id,
            "path": path,
            "offset": offset,
            "next_offset": end if end < len(text) else None,
            "total_chars": len(text),
            "text": text[offset:end],
            "verification": {
                "method": "retained_payload_integrity_v2",
                "scope": "entire_retained_payload",
                "run_id": run["run_id"],
                "tool_name": run.get("tool_name"),
                "serialization": 'UTF-8 json.dumps(ensure_ascii=False,separators=(",",":")); insertion order',
                "calculation_repeated": False,
            },
        }

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
            "file_path": str(self._path(result_id)),
            "rest_manifest_path": f"/api/results/{result_id}",
            "first_page_uri": f"fatebridge://results/{result_id}/pages/0",
            "total_chars": metadata["total_chars"],
            "total_bytes": metadata["total_bytes"],
            "page_chars": PAGE_CHARS,
            "file_payload_path": "payload",
            "available_fields": metadata["available_fields"],
            "fields": [
                {
                    "path": name,
                    "first_page_uri": f"fatebridge://results/{result_id}/fields/{name}/0",
                }
                for name in metadata["available_fields"]
            ],
            "note": (
                "按所需点路径读取字段，也支持数组数字索引；分页 text 是 JSON 文档片段，"
                "完整读取需按 next_offset 拼接；核验读取同时检查原 run 与存储完整性。"
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
            fd = open_private_file(self._path(result_id, index_suffix), os.O_RDONLY)
            with os.fdopen(fd, "rb") as handle:
                handle.seek(start_block * _INDEX_ENTRY.size)
                start_byte = _INDEX_ENTRY.unpack(handle.read(_INDEX_ENTRY.size))[0]
                handle.seek(stop_block * _INDEX_ENTRY.size)
                stop_byte = _INDEX_ENTRY.unpack(handle.read(_INDEX_ENTRY.size))[0]
            if not 0 <= start_byte <= stop_byte <= metadata["total_bytes"]:
                raise ValueError("Invalid result page index")
            fd = open_private_file(self._path(result_id), os.O_RDONLY)
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
    payload = public_payload(payload)
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
    metadata = payload.get("run_metadata")
    deferred_metadata = []
    # Runtime details can crowd out the analysis even with an empty file
    # inventory. Keep their identity/count inline and their exact bytes in
    # the already-stored SAME run, without mutating the original receipt.
    if isinstance(metadata, dict):
        evidence = metadata.get("calculation_evidence")
        if isinstance(evidence, dict) and len(_json(evidence, compact)) > 512:
            path = "run_metadata.calculation_evidence"
            metadata = {
                **metadata,
                "calculation_evidence": {
                    "delivery_path": path,
                    "coverage": evidence.get("coverage"),
                },
            }
            deferred_metadata.append(path)
        runtime = metadata.get("runtime")
        ephemeris = runtime.get("ephemeris") if isinstance(runtime, dict) else None
        files = ephemeris.get("files") if isinstance(ephemeris, dict) else None
        if (
            isinstance(runtime, dict)
            and isinstance(ephemeris, dict)
            and isinstance(files, list)
            and len(_json(runtime, compact)) > 512
        ):
            path = "run_metadata.runtime"
            runtime_summary: dict[str, JsonValue] = {
                "delivery_path": path,
                "ephemeris_files_count": len(files),
            }
            metadata = {**metadata, "runtime": runtime_summary}
            deferred_metadata.append(path)
    output: Dict[str, Any] = {
        "run_metadata": metadata,
        "result_delivery": delivery,
    }
    fields = [key for key in payload if key != "run_metadata"]
    delivery["deferred_fields"] = [*fields, *deferred_metadata]
    # Optional duplicate reference details need not displace a complete
    # first business response. They remain available in this SAME manifest;
    # identity, expiry and page URIs remain inline. Large business
    # results retain the full existing reference and normal pagination.
    if deferred_metadata and isinstance(metadata, dict):
        complete_with_full_reference = {
            **payload,
            "run_metadata": metadata,
            "result_delivery": {**delivery, "deferred_fields": deferred_metadata},
        }
        compact_reference = {
            key: value
            for key, value in delivery.items()
            if key
            not in {
                "available_fields",
                "total_bytes",
                "page_chars",
                "rest_manifest_path",
            }
        }
        compact_reference.update(
            compact_reference=True, deferred_fields=deferred_metadata
        )
        complete_business = {
            **payload,
            "run_metadata": metadata,
            "result_delivery": compact_reference,
        }
        # Preserve the entire receipt whenever it fits. Supplementary fields
        # must not be deferred merely because that fallback is available.
        if len(_json(complete_with_full_reference, compact)) <= response_char_limit:
            return complete_with_full_reference
        if len(_json(complete_business, compact)) <= response_char_limit:
            return complete_business
        # The first-page URI repeats the manifest URI plus '/pages/0'. Before
        # deferring any receipt facts, let the same manifest supply this one
        # duplicate locator. Its result ID, expiry and file access remain
        # inline, and the immutable artifact still retains the complete receipt.
        manifest_page_reference = dict(compact_reference)
        manifest_page_reference.pop("first_page_uri", None)
        complete_without_page_locator = {
            **complete_business,
            "result_delivery": manifest_page_reference,
        }
        if len(_json(complete_without_page_locator, compact)) <= response_char_limit:
            return complete_without_page_locator
        # Local file locators also duplicate the same immutable manifest. A
        # longer provenance list should not displace source facts while these
        # optional duplicate locators still occupy the response budget. Keep
        # the manifest URI, result identity, expiry and total characters;
        # the manifest retains the exact file path and payload key.
        manifest_only_reference = dict(manifest_page_reference)
        manifest_only_reference.pop("file_path", None)
        manifest_only_reference.pop("file_payload_path", None)
        complete_with_manifest_locator = {
            **complete_business,
            "result_delivery": manifest_only_reference,
        }
        if len(_json(complete_with_manifest_locator, compact)) <= response_char_limit:
            return complete_with_manifest_locator
        # A larger analysis can still fit when supplementary receipt details
        # stay in the same immutable artifact. Keep run identities and the runtime inventory count inline; never remove facts or
        # manufacture a smaller original receipt to make the budget pass.
        receipt = dict(metadata)
        receipt_paths = list(deferred_metadata)
        for key in ("provenance", "determinism"):
            if key not in receipt:
                continue
            receipt.pop(key)
            receipt_paths.append("run_metadata." + key)
            candidate = {
                **payload,
                "run_metadata": receipt,
                "result_delivery": {
                    **manifest_only_reference,
                    "deferred_fields": list(receipt_paths),
                },
            }
            if len(_json(candidate, compact)) <= response_char_limit:
                return candidate
        # If complete business plus the essential receipt cannot fit, keep
        # the receipt and explicitly page business from the same artifact.
        # Never hide run identities behind a
        # root run_metadata reference merely to keep more business inline.
        # For paging, retain supplementary receipt details whenever they fit;
        # defer those details only if the receipt itself exceeds the budget.
        if len(_json(output, compact)) > response_char_limit:
            receipt = dict(metadata)
            for key in ("provenance", "determinism"):
                if key not in receipt:
                    continue
                receipt.pop(key)
                delivery = {
                    **delivery,
                    "deferred_fields": [
                        *delivery["deferred_fields"],
                        "run_metadata." + key,
                    ],
                }
                output = {"run_metadata": receipt, "result_delivery": delivery}
                if len(_json(output, compact)) <= response_char_limit:
                    break
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
        next_delivery = {
            **delivery,
            "deferred_fields": [
                name for name in delivery["deferred_fields"] if name != key
            ],
        }
        candidate["result_delivery"] = next_delivery
        if len(_json(candidate, compact)) <= response_char_limit:
            output = candidate
            delivery = next_delivery
    # A projected first_view is already the caller's current-period card.
    # When one large child prevents that whole card from fitting, retain its
    # other exact children and declare each deferred child separately. The
    # immutable artifact above still contains the complete selected result.
    # This keeps partial statuses and current facts ahead of an all-or-nothing
    # parent fallback without changing any calculation or silently dropping data.
    for key in fields:
        value = payload[key]
        if (
            key in output
            or not isinstance(value, dict)
            or set(value) != {"first_view"}
            or not isinstance(value["first_view"], dict)
        ):
            continue
        view = value["first_view"]
        view_delivery = output["result_delivery"]
        parent_deferred = [
            name for name in view_delivery["deferred_fields"] if name != key
        ]
        selected: Dict[str, Any] = {}
        for child, fact in view.items():
            trial = {**selected, child: fact}
            deferred = list(parent_deferred)
            deferred.extend(
                f"{key}.first_view.{name}" for name in view if name not in trial
            )
            candidate = {
                **output,
                key: {"first_view": trial},
                "result_delivery": {**view_delivery, "deferred_fields": deferred},
            }
            if len(_json(candidate, compact)) <= response_char_limit:
                selected = trial
                output = candidate
    return output
