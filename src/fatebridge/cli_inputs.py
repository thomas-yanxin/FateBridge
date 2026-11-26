"""Load CLI JSON request files before argparse dispatch."""

from __future__ import annotations

import argparse
import json
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
        data = json.loads(
            Path(args.request_file).expanduser().read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("request-file 必须为可读的合法 JSON 文件") from exc
    if not isinstance(data, dict):
        raise ValueError("request-file 顶层必须是 JSON 对象")
    return data
