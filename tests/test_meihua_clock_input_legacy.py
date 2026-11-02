"""Frozen default-zero request code must preserve original presence on every surface."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import fatebridge
from tests.meihua_clock_input_reference import FOLDER, cases


@pytest.fixture(scope="module")
def legacy_results():
    source = Path(fatebridge.__file__).resolve().parent.parent
    driver = Path(__file__).with_name("meihua_clock_input_legacy_probe.py")
    original = FOLDER / "before-request-divination.py"
    proc = subprocess.run(
        [sys.executable, str(driver), str(source), str(original)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    value = json.loads(proc.stdout.splitlines()[-1])
    assert value["original_request_default_minute"] == 0
    assert (
        value["original_request_sha256"]
        == hashlib.sha256(original.read_bytes()).hexdigest()
    )
    assert Path(value["package"]).resolve().parent == source / "fatebridge"
    return value


@pytest.mark.parametrize("surface", ["REST", "MCP", "CLI"])
def test_legacy_zero_default_is_not_misreported_as_supplied(surface, legacy_results):
    rows = [r for r in legacy_results["rows"] if r["surface"] == surface]
    omitted = next(r for r in rows if r["kind"] == "omitted")
    zero = next(r for r in rows if r["kind"] == "zero")
    a = omitted["clock"]["input_components"]
    z = zero["clock"]["input_components"]
    assert a["supplied_components"] == ["year", "month", "day", "hour"]
    assert a["omitted_components"] == ["minute", "second"]
    assert a["calculation_defaults"] == {"minute": 0, "second": 0}
    assert z["supplied_components"] == ["year", "month", "day", "hour", "minute"]
    assert z["omitted_components"] == ["second"] and z["calculation_defaults"] == {
        "second": 0
    }
    assert a["provenance"] == z["provenance"] == "bound_request_model_fields_set"
    assert (
        a["nominal_civil_datetime"]
        == z["nominal_civil_datetime"]
        == "2000-01-06T09:00:00+08:00"
    )
    assert omitted["input_sha256"] != zero["input_sha256"]
    assert a["uncertainty_interval"] is z["uncertainty_interval"] is None
    assert (
        not a["observed_precision_certified"] and not z["observed_precision_certified"]
    )


def test_legacy_presence_input_hashes_match_across_all_surfaces(legacy_results):
    for kind in ["omitted", "zero"]:
        rows = [r for r in legacy_results["rows"] if r["kind"] == kind]
        assert len(rows) == 3 and len({r["input_sha256"] for r in rows}) == 1
