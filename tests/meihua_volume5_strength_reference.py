"""Visually read, preimplementation NLC table cells and reused role contexts."""

import gzip
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_volume5_strength_v1"
MANIFEST_SHA256 = "90964bebd6127adc8e1e78acb0eafaf4ed14021321aa45aa20f8243abc49bb97"


def load():
    raw = (FOLDER / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Volume-five source reference manifest changed")
    manifest = json.loads(raw)
    for name, expected in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        if hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Volume-five source reference bytes changed: " + name)
    source = json.loads((FOLDER / "source-binding.json").read_bytes())
    pdf = Path(__file__).resolve().parents[1] / source["existing_original_pdf_path"]
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("Volume-five original PDF identity changed")
    assert manifest["phase"] == "before_new_production_module_data_or_integration"
    cells = json.loads((FOLDER / "literal25.json").read_bytes())
    rows = json.loads(gzip.decompress((FOLDER / "expected4992.json.gz").read_bytes()))
    assert len(cells) == 25 and len(rows) == 4992
    assert sum(c["expected_state"] is not None for c in cells) == 20
    return cells, rows
