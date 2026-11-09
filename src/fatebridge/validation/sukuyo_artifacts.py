"""Read and verify exact JSON bytes for current Sukuyo source audits."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str
    source_version: str


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in evidence")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite JSON number: {value}")
    return parsed


def read_artifact(artifact: Artifact) -> tuple[dict[str, object], bytes]:
    if (
        re.fullmatch(r"[0-9a-f]{64}", artifact.sha256) is None
        or not artifact.source_version.strip()
    ):
        raise ValueError("Artifact SHA and declared source version required")
    path = artifact.path.resolve()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != artifact.sha256:
        raise ValueError(f"Artifact SHA mismatch: {path}")
    value = json.loads(
        raw,
        object_pairs_hook=_object,
        parse_constant=_nonfinite,
        parse_float=_finite_float,
    )
    return {
        "path": str(path),
        "sha256": artifact.sha256,
        "source_version": artifact.source_version,
        "pointer": "",
        "value": value,
    }, raw
