"""Preimplementation clock-label literals and complete controlled packets."""

import gzip
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_iso_clock_v1"
MANIFEST_SHA256 = "1406ebf25bb903570699a0de224c7e812bf55b2e8fb4d0e4fab26bd15803db56"
SUPPLEMENT_FOLDER = Path(__file__).parent / "fixtures/meihua_iso_clock_supplement_v66"
SUPPLEMENT_SHA256 = "31995a5a453b8b20765f3662770ebc44ef16f293456360f5acb2c634ca9369c7"


def fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Clock ISO manifest changed")
    data = json.loads(raw)
    for name, h in data["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        if hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() != h:
            raise ValueError("Clock ISO reference changed: " + name)
    if data["phase"] != "before_v66_production_parser_implementation":
        raise ValueError("Clock ISO reference chronology changed")
    return data


def load():
    fingerprints()
    cases = json.loads((FOLDER / "parser-cases.json").read_bytes())
    packets = json.loads(gzip.decompress((FOLDER / "packets126.json.gz").read_bytes()))
    assert len(cases) == 255 and len(packets) == 126
    assert (
        len({r["id"] for r in cases}) == 255 and len({r["id"] for r in packets}) == 126
    )
    return cases, packets


def load_supplement():
    raw = (SUPPLEMENT_FOLDER / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != SUPPLEMENT_SHA256:
        raise ValueError("Clock ISO supplement manifest changed")
    data = json.loads(raw)
    for name, h in data["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        if hashlib.sha256((SUPPLEMENT_FOLDER / name).read_bytes()).hexdigest() != h:
            raise ValueError("Clock ISO supplement changed")
    assert (
        data["phase"]
        == "after_parser_implementation_engineering_supplement_not_preimplementation_oracle"
    )
    rows = json.loads(
        gzip.decompress((SUPPLEMENT_FOLDER / "packets8.json.gz").read_bytes())
    )
    assert len(rows) == 8
    return rows
