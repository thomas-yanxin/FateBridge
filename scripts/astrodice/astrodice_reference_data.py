"""Verify original physical records and independent numerical references."""

import hashlib
from pathlib import Path

from pydantic import TypeAdapter
from typing_extensions import TypedDict

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "tests/data/astrodice/reference-material.json"


class ReferenceMaterialDigest(TypedDict):
    sha256: str


class ReferenceMaterialManifest(TypedDict):
    files: dict[str, ReferenceMaterialDigest]


REFERENCE_MANIFEST: TypeAdapter[ReferenceMaterialManifest] = TypeAdapter(
    ReferenceMaterialManifest
)


def verify_material(path: Path) -> Path:
    """Verify one current resource, with no historical-root fallback."""
    resource = path.resolve()
    repository_path = resource.relative_to(ROOT).as_posix()
    entries = REFERENCE_MANIFEST.validate_json(REGISTRY.read_bytes(), strict=True)[
        "files"
    ]
    if repository_path not in entries:
        raise ValueError(f"Unregistered current reference resource: {repository_path}")
    elif (
        hashlib.sha256(resource.read_bytes()).hexdigest()
        != entries[repository_path]["sha256"]
    ):
        raise ValueError(f"Independent reference material changed: {repository_path}")
    else:
        return resource
