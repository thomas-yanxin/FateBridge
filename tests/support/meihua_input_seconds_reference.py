"""Frozen modern UTC endpoints derived without FateBridge clock code."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

FOLDER = Path(__file__).parents[1] / "fixtures/meihua_input_seconds_v1"
MANIFEST_SHA256 = "71d5ec6772639479dfed682fe7c023454215eac60f3382dd67e377dd4cf150a0"


def cases():
    raw = (FOLDER / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
    result = json.loads((FOLDER / "boundary-cases.json").read_bytes())
    assert len(result) == 48
    assert {(r["year"], r["index"]) for r in result} == {
        (year, index) for year in [2000, 2025] for index in range(24)
    }
    return result


def parameters(clock):
    at = datetime.fromisoformat(clock)
    return {
        "analysis_year": at.year,
        "analysis_month": at.month,
        "analysis_day": at.day,
        "analysis_hour": at.hour,
        "analysis_minute": at.minute,
        "analysis_second": at.second,
        "analysis_timezone": "+08:00",
    }
