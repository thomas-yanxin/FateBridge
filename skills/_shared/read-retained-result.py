"""Read one bounded field page after checking an original local delivery receipt.

Standard library only; never imports FateBridge, recalculates, or writes files.
The expected digest and run must come from the original response, not this file.
"""

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import stat
import sys
import time
from pathlib import Path

PAGE_CHARS = 2048


class ReadingError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(code, message):
    raise ReadingError(code, message)


def read_page(record_path, expected_sha256, expected_run_id, path=None, offset=0):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        fail("invalid_digest", "需要原回执的完整 SHA-256。")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", expected_run_id):
        fail("invalid_run_id", "需要原回执的 run_id。")
    if offset < 0:
        fail("invalid_offset", "分页 offset 不能为负数。")
    if path is not None and (len(path) > 1000 or len(path.split(".")) > 64):
        fail("invalid_result_path", "字段路径过长。")
    record_path = Path(record_path)
    try:
        if record_path.is_symlink():
            fail("result_file_unavailable", "不能读取符号链接交付文件。")
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        fd = os.open(record_path, flags)
        with os.fdopen(fd, encoding="utf-8") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                fail("result_file_unavailable", "交付记录必须是普通文件。")
            record = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReadingError(
            "result_file_unavailable", "交付文件不可读或不是完整 JSON。"
        ) from error
    if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
        fail("invalid_result_record", "交付记录缺少对象型 payload。")
    expiry = record.get("expires_at")
    try:
        valid_expiry = type(expiry) in (int, float) and math.isfinite(expiry)
    except OverflowError:
        valid_expiry = False
    if not valid_expiry:
        fail("invalid_result_record", "交付记录缺少有效过期时刻。")
    if expiry <= time.time():
        fail("result_expired", "交付引用已过期，不能冒充仍有效的原引用。")
    payload = record["payload"]
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise ReadingError(
            "invalid_result_record", "payload不能按原序UTF-8编码。"
        ) from error
    actual_sha256 = hashlib.sha256(encoded).hexdigest()
    if not hmac.compare_digest(actual_sha256, expected_sha256):
        fail("result_digest_mismatch", "原 payload 散列核验失败。")
    run = payload.get("run_metadata")
    if not isinstance(run, dict) or run.get("run_id") != expected_run_id:
        fail("result_run_mismatch", "结果不属于原回执指定的 run。")
    value = payload
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
                fail("unknown_result_path", "原结果中不存在所需字段。")
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if offset > len(text):
        fail("invalid_offset", "分页 offset 超出字段长度。")
    end = min(offset + PAGE_CHARS, len(text))
    return {
        "path": path,
        "offset": offset,
        "next_offset": end if end < len(text) else None,
        "total_chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text[offset:end],
        "verification": {
            "method": "local_record_payload_sha256_v1",
            "scope": "entire_retained_payload",
            "payload_sha256": actual_sha256,
            "run_id": run["run_id"],
            "tool_name": run.get("tool_name"),
            "serialization": 'UTF-8 json.dumps(ensure_ascii=False,separators=(",",":")); insertion order',
            "calculation_repeated": False,
            "service_reference_status_checked": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="原 result_delivery.file_path")
    parser.add_argument("--sha256", required=True, help="原 result_delivery.sha256")
    parser.add_argument("--run-id", required=True, help="原 run_metadata.run_id")
    parser.add_argument(
        "--path", default=None, help="同次结果的点路径，支持数组数字索引"
    )
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        result = read_page(
            args.record, args.sha256, args.run_id, args.path, args.offset
        )
    except ReadingError as error:
        print(
            json.dumps(
                {"error": str(error), "error_code": error.code, "retryable": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
