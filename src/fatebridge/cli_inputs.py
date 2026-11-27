"""Load CLI JSON request files before argparse dispatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def preload_request(argv: list[str] | None) -> dict[str, object] | None:
    """Load a complete JSON request for subsequent model validation."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--request-file", default=None)
    try:
        args, _ = pre.parse_known_args(argv)
    except SystemExit:
        return None
    if not args.request_file:
        return None
    try:
        raw_text = (
            sys.stdin.read()
            if args.request_file == "-"
            else Path(args.request_file).expanduser().read_text(encoding="utf-8")
        )
        data = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("request-file 必须为可读的合法 JSON 文件或标准输入") from exc
    if not isinstance(data, dict):
        raise ValueError("request-file 顶层必须是 JSON 对象")
    return data
