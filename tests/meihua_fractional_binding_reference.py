"""Frozen pre-edit literals, portable packets, and manual UTC expectations."""

import gzip
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_fractional_binding_v1"
MANIFEST_SHA256 = "84c6a46bdfc2e4b832c536f914d730982a02809f2e9321c1b1bdb3d94e5e8bb7"


def load():
    raw = (FOLDER / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Fractional input manifest changed")
    data = json.loads(raw)
    for name, digest in data["files"].items():
        if hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Fractional input reference changed: " + name)
    packets = json.loads(gzip.decompress((FOLDER / "packets74.json.gz").read_bytes()))
    parser = json.loads((FOLDER / "parser16.json").read_bytes())
    assert len(packets) == 74 and len(parser) == 16
    assert len({p["id"] for p in packets}) == 74
    assert sum(not r["should_succeed"] for r in packets) == 56
    assert data["phase"] == "before_v65_production_edit"
    assert not data["aware_fromisoformat_used_as_expected_oracle"]
    return packets, parser
