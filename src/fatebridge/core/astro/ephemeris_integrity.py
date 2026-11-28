"""Manifest validation for separately acquired Swiss Ephemeris data."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import TypedDict

from pydantic import TypeAdapter
from typing_extensions import NotRequired


class EphemerisFileRecord(TypedDict):
    bytes: int


class EphemerisManifest(TypedDict):
    schema_version: int
    base_url: str
    files: dict[str, EphemerisFileRecord]
    id: NotRequired[str]
    source_repository: NotRequired[str]
    source_commit: NotRequired[str]
    source_tree_url: NotRequired[str]
    scope: NotRequired[str]


class PackagedEphemerisManifest(TypedDict):
    schema_version: int
    id: str
    source_repository: str
    source_commit: str
    source_tree_url: str
    base_url: str
    scope: str
    files: dict[str, EphemerisFileRecord]


_PACKAGED_MANIFEST_ADAPTER = TypeAdapter(PackagedEphemerisManifest)


def validate_file_name(name: str) -> None:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.se1", name):
        raise ValueError("Ephemeris file name must be one .se1 basename")


def _validate_manifest(manifest: object) -> EphemerisManifest:
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
    validated_files: dict[str, EphemerisFileRecord] = {}
    for name, record in records.items():
        if not isinstance(name, str):
            raise ValueError("Ephemeris file name must be one .se1 basename")
        validate_file_name(name)
        if not isinstance(record, dict):
            raise ValueError(f"{name}: invalid file record")
        size = record.get("bytes")
        if type(size) is not int or size < 2:
            raise ValueError(f"{name}: invalid expected byte count")
        validated_files[name] = {"bytes": size}
    validated: EphemerisManifest = {
        "schema_version": 1,
        "base_url": manifest["base_url"],
        "files": validated_files,
    }
    manifest_id = manifest.get("id")
    if isinstance(manifest_id, str):
        validated["id"] = manifest_id
    source_repository = manifest.get("source_repository")
    if isinstance(source_repository, str):
        validated["source_repository"] = source_repository
    source_commit = manifest.get("source_commit")
    if isinstance(source_commit, str):
        validated["source_commit"] = source_commit
    source_tree_url = manifest.get("source_tree_url")
    if isinstance(source_tree_url, str):
        validated["source_tree_url"] = source_tree_url
    scope = manifest.get("scope")
    if isinstance(scope, str):
        validated["scope"] = scope
    return validated


@lru_cache(maxsize=1)
def _packaged_manifest() -> PackagedEphemerisManifest:
    source = files("fatebridge.data").joinpath("astro/ephemeris-manifest-v1.json")
    manifest = _PACKAGED_MANIFEST_ADAPTER.validate_json(source.read_bytes())
    _validate_manifest(manifest)
    return manifest


def load_ephemeris_manifest(path: Path | None = None) -> EphemerisManifest:
    if path is not None:
        raw: object = json.loads(path.read_text("utf-8"))
        return _validate_manifest(raw)
    return _validate_manifest(_packaged_manifest())


def verify_ephemeris_bytes(name: str, data: bytes, manifest: EphemerisManifest) -> None:
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
