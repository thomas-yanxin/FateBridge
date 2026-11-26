"""Manifest validation for separately acquired Swiss Ephemeris data."""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, cast


def validate_file_name(name: str) -> None:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.se1", name):
        raise ValueError("Ephemeris file name must be one .se1 basename")


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
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
        raise ValueError("Ephemeris manifest requires file records")
    for name, record in records.items():
        validate_file_name(name)
        if not isinstance(record, dict):
            raise ValueError(f"{name}: invalid file record")
        size = record.get("bytes")
        if type(size) is not int or size < 2:
            raise ValueError(f"{name}: invalid expected byte count")
    return manifest


@lru_cache(maxsize=1)
def _packaged_manifest() -> dict[str, Any]:
    source = files("fatebridge.data").joinpath("astro/ephemeris-manifest-v1.json")
    return _validate_manifest(
        cast(dict[str, Any], json.loads(source.read_text("utf-8")))
    )


def load_ephemeris_manifest(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        return _validate_manifest(
            cast(dict[str, Any], json.loads(path.read_text("utf-8")))
        )
    return copy.deepcopy(_packaged_manifest())


def verify_ephemeris_bytes(name: str, data: bytes, manifest: dict[str, Any]) -> None:
    validate_file_name(name)
    record = manifest["files"].get(name)
    if record is None:
        raise ValueError(
            f"{name}: not listed in the selected edition; provide a manifest for custom data"
        )
    if not data.startswith(b"SW"):
        raise ValueError(f"{name}: content is not Swiss Ephemeris data")
    if len(data) != record["bytes"]:
        raise ValueError(
            f"{name}: content does not match the selected edition's byte count"
        )
