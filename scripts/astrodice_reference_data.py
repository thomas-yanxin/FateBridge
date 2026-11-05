"""Read the current, raw-only Astrodice reference bill of materials.

The registry binds original physical records and independent numerical reference
values. Maintained Python code and native binaries are not reference outputs.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tests/data/astrodice/reference-material.json"


def verify_material(path):
    """Verify one current resource, with no historical-root fallback."""
    resource = path.resolve()
    name = resource.relative_to(ROOT).as_posix()
    entries = json.loads(REGISTRY.read_text())["files"]
    if name not in entries:
        raise ValueError("Unregistered current reference resource: " + name)
    entry = entries[name]
    if hashlib.sha256(resource.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("Independent reference material changed: " + name)
    return resource


def verify_bindings(bindings):
    """Check only raw resources present in the current reference registry."""
    files = json.loads(REGISTRY.read_text())["files"]
    for name in bindings:
        if name in files:
            verify_material(ROOT / name)
