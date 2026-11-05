"""Source readings and role geometry frozen before the new implementation."""

import gzip
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_qualified_motion_v1"
MANIFEST_SHA256 = "cc5adb77c46cc9faee9c1175084fcf252f1ed35756c4b4e5bc1f6119455c3fde"


def load():
    raw = (FOLDER / "final-preimplementation-manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    for name, h in json.loads(raw)["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == h, name
    pdf = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/meihua_observation_v1/nlc-original.pdf"
    )
    assert (
        hashlib.sha256(pdf.read_bytes()).hexdigest()
        == "af608094ab11ae209eae91a9365565e7c9cff604aac3da5e753e04d1cc4598c0"
    )
    geometry = json.loads(
        gzip.decompress((FOLDER / "geometry768.json.gz").read_bytes())
    )
    counting = json.loads((FOLDER / "expected-counting12.json").read_bytes())
    reading = json.loads((FOLDER / "selected-reading-before.json").read_bytes())
    templates = json.loads((FOLDER / "editorial-summary-templates.json").read_bytes())
    assert len(geometry) == 768 and len(counting) == 12
    return geometry, counting, reading, templates


def path_get(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def expected_summary(case, reading, templates):
    role = case.get("selected_role", "body" if case["topic"] == "travel" else "use")
    values = {
        "role_label": "初体" if role == "body" else "初用",
        "trigram": case["selected_trigram"],
    }
    matches = case["matched_clause_ids"]
    if matches:
        row = next(r for r in reading["rows"] if r["id"] == matches[0])
        values.update(
            quote=row["quote"], qualified_predicate=row["qualified_predicate"]
        )
    return templates["matched" if matches else "not_matched"].format(**values)
