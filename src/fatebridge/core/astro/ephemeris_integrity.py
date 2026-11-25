"""Content identity of separately acquired ephemeris data.

SHA-256 fingerprints pin a file to a named source edition. They certify
neither the astronomical model nor future Earth rotation or civil time.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, Optional, cast


def validate_file_name(name: str) -> None:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.se1", name):
        raise ValueError("Ephemeris file name must be one .se1 basename")


def _validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("Ephemeris manifest must be an object")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise ValueError("Unsupported ephemeris manifest schema")
    if not isinstance(manifest.get("base_url"), str) or not manifest["base_url"]:
        raise ValueError("Ephemeris manifest requires a base_url")
    records = manifest.get("files")
    if not isinstance(records, dict) or not records:
        raise ValueError("Ephemeris manifest requires file fingerprints")
    for name, record in records.items():
        validate_file_name(name)
        if not isinstance(record, dict):
            raise ValueError(f"{name}: invalid fingerprint record")
        size, digest = record.get("bytes"), record.get("sha256")
        if type(size) is not int or size < 2:
            raise ValueError(f"{name}: invalid expected byte count")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{name}: invalid SHA-256 fingerprint")
    return manifest


@lru_cache(maxsize=1)
def _packaged_manifest() -> Dict[str, Any]:
    source = files("fatebridge.data").joinpath("astro/ephemeris-manifest-v1.json")
    return _validate_manifest(
        cast(Dict[str, Any], json.loads(source.read_text("utf-8")))
    )


def load_ephemeris_manifest(path: Optional[Path] = None) -> Dict[str, Any]:
    if path is not None:
        return _validate_manifest(
            cast(Dict[str, Any], json.loads(path.read_text("utf-8")))
        )
    return copy.deepcopy(_packaged_manifest())


def verify_ephemeris_bytes(name: str, data: bytes, manifest: Dict[str, Any]) -> None:
    validate_file_name(name)
    record = manifest["files"].get(name)
    if record is None:
        raise ValueError(
            f"{name}: no fingerprint in the selected edition; provide a manifest for custom data"
        )
    if not data.startswith(b"SW"):
        raise ValueError(f"{name}: content is not Swiss Ephemeris data")
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != record["bytes"] or actual != record["sha256"]:
        raise ValueError(
            f"{name}: content does not match the selected edition's byte count and SHA-256"
        )
