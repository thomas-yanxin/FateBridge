"""Deliver separately bound apparatus coverage without changing textual readings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_apparatus_scope.json"
DATA_SHA256 = "36fa479a3fb57fa90e51644f5ef582dcb218f334cd960b0d0be77ef1920927ec"
FACTS_SHA256 = "6401f4a470c60793552c1ce3ed8c03799b9877ca672eb36a41b6787bb8d2650d"
REFERENCE_SHA256 = "55cd0e1a524680a76bb6022837ed8c0bd6e9ec9547edd0ef277bdcdda01fb425"


def validate_apparatus_reference(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("校注关联、范围或未定控制改变，须重新核验")


def apparatus_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("校注覆盖资料身份改变，须重新冻结来源")
    validate_apparatus_reference(loaded.data)
    return {
        "source_data": loaded.data,
        "source_bundle_sha256": loaded.sha256,
        "before_code_reference_sha256": REFERENCE_SHA256,
        "hash_scope": "apparatus_coverage_only_v77",
        "record_nodes_are_independent_witnesses": False,
    }
