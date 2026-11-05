"""The independent range and gate cannot shrink to exclude failed crossings."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.fengshui_monthly_calendar import (
    audit_monthly_calendar_reference,
)

FOLDER = Path(__file__).parent / "data/fengshui_monthly_v1"
RAW = gzip.decompress((FOLDER / "jie-de440-tt.json.gz").read_bytes())
REFERENCE = json.loads(RAW)


def test_complete_independent_tt_reference_and_collector_identity():
    manifest = json.loads((FOLDER / "calendar-reference.json").read_text())
    assert hashlib.sha256(RAW).hexdigest() == manifest["raw_sha256"]
    assert len(REFERENCE["rows"]) == 4812
    assert not REFERENCE["fatebridge_imported"]
    assert REFERENCE["protocol"]["numeric_implementation_tolerance_seconds"] == 1.0
    source = Path(__file__).parents[1] / "scripts/collect_fengshui_monthly_reference.py"
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest() == REFERENCE["collector_sha256"]
    )
    assert all(0 <= r["bracket_width_seconds"] <= 0.001 for r in REFERENCE["rows"])


@pytest.mark.parametrize(
    "change",
    [
        "drop",
        "extra",
        "year_bool",
        "float_longitude",
        "widen_gate",
        "move_start",
        "swap_term",
        "wide_bracket",
    ],
)
def test_corrupted_or_easier_protocols_are_rejected_before_calculation(change):
    bad = deepcopy(REFERENCE)
    if change == "drop":
        bad["rows"].pop()
    elif change == "extra":
        bad["rows"].append(deepcopy(bad["rows"][-1]))
    elif change == "year_bool":
        bad["rows"][0]["year"] = True
    elif change == "float_longitude":
        bad["rows"][0]["longitude_degrees"] = 285.0
    elif change == "widen_gate":
        bad["protocol"]["numeric_implementation_tolerance_seconds"] = 3.0
    elif change == "move_start":
        bad["protocol"]["year_min"] = 1900
    elif change == "swap_term":
        bad["rows"][0]["term"] = "立春"
    elif change == "wide_bracket":
        bad["rows"][0]["bracket_width_seconds"] = 1.1
    with pytest.raises(ValueError):
        audit_monthly_calendar_reference(bad)
