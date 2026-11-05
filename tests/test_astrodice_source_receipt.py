"""Actual source receipts and unresolved-ID counterexamples remain explicit."""

import copy
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from scripts.verify_astrodice_source_receipt import verify

RUN = Path("tests/data/astrodice/reference_sets/study-motion-text")


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


@pytest.fixture(scope="module")
def current_source_result():
    import hashlib
    import os

    previous_path = e.configured_ephemeris_path()
    previous_jpl = os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    previous_environment = os.environ.get("SE_EPHE_PATH")
    os.environ["SE_EPHE_PATH"] = str(Path("ephe").resolve())
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
        )
        allowed = {
            hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("ephe").glob("*.se1")
        }
        yield result, allowed
    finally:
        if previous_jpl is not None:
            os.environ["FATEBRIDGE_JPL_FILE"] = previous_jpl
        if previous_environment is None:
            os.environ.pop("SE_EPHE_PATH", None)
        else:
            os.environ["SE_EPHE_PATH"] = previous_environment
        e.configure_ephemeris_path(previous_path or "")


def test_current_missing_source_receipt_is_rejected(current_source_result):
    result, allowed = copy.deepcopy(current_source_result)
    assert verify(result, "swieph", allowed)["physical_factors"] == 10
    del result["chart"]["params"]["chart_profile"]["physical_ephemeris_source"]
    with pytest.raises(ValueError, match="Physical source receipt missing"):
        verify(result, "swieph", allowed)


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "hash", "unresolved", "factor", "accuracy"]
)
def test_independent_source_reader_rejects_false_provenance(
    mutation, current_source_result
):
    result, allowed = copy.deepcopy(current_source_result)
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
        verify(result, "swieph", allowed)
