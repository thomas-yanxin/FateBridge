"""Actual source receipts and unresolved-ID counterexamples remain explicit."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from scripts.verify_astrodice_source_receipt import verify

RUN = Path("docs/validation/astrodice-motion-text-run-2026-10-28")


@pytest.mark.parametrize("frame", [0, 1])
def test_actual_swiss_context_exposes_resolvable_source_receipt(monkeypatch, frame):
    import hashlib

    previous = e.configured_ephemeris_path()
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(Path("ephe").resolve()))
    try:
        e.configure_ephemeris_path()
        result = build_otherbu_result(
            planet="Mercury",
            sign="Pisces",
            house=0,
            date="2024-03-20",
            time="06:30:00",
            zone="UTC",
            gps_lat=0,
            gps_lon=0,
            zodiacal=frame,
        )
        allowed = {
            hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("ephe").glob("*.se1")
        }
        checked = verify(result, "swieph", allowed)
        assert checked["physical_factors"] == 10
        assert checked["resolved_contexts"] > 10
    finally:
        monkeypatch.undo()
        e.configure_ephemeris_path(previous or "")


def fixture():
    result = json.loads((RUN / "heldout-0-0-jpl_record_window-first.json").read_text())[
        "result"
    ]
    allowed = {
        json.loads((RUN / "kernel-source-before-capture.json").read_text())["windows"][
            "heldout-0"
        ]["sha256"]
    }
    return result, allowed


def test_original_swiss_source_omission_is_not_regraded():
    for frame in (0, 1):
        result = json.loads((RUN / f"heldout-0-{frame}-swieph-first.json").read_text())[
            "result"
        ]
        with pytest.raises(ValueError, match="Physical source receipt missing"):
            verify(result, "swieph", set())
    result, allowed = fixture()
    assert verify(result, "jpl", allowed)["physical_factors"] == 10


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "hash", "unresolved", "factor", "accuracy"]
)
def test_independent_source_reader_rejects_false_provenance(mutation):
    result, allowed = copy.deepcopy(fixture())
    profile = result["chart"]["params"]["chart_profile"]
    source = profile["physical_ephemeris_source"]
    if mutation == "missing":
        del profile["physical_ephemeris_source"]
    elif mutation == "duplicate":
        source["files"].append(copy.deepcopy(source["files"][0]))
    elif mutation == "hash":
        source["files"][0]["sha256"] = "0" * 64
    elif mutation == "unresolved":
        source["by_factor"]["Sun"]["file_ids"].append("unresolved")
    elif mutation == "factor":
        del source["by_factor"]["Venus"]
    else:
        source["accuracy_certified"] = True
    with pytest.raises(ValueError):
        verify(result, "jpl", allowed)
