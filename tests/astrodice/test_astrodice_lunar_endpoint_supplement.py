"""New raw endpoint evidence cannot rewrite the original missing cohort."""

import json
import shutil
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.astrodice.audit_astrodice_lunar_endpoint_supplement import validate
from scripts.astrodice.gen_astrodice_lunar_endpoint_supplement import calendar_label

DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "tests/data/astrodice/original-endpoint-supplement"
)


def test_independent_supplement_preserves_the_complete_original_stencil_and_hard_boundary():
    protocol, reference, checked = validate(DIRECTORY)
    assert checked["original_reference_bytes_unchanged"]
    assert checked["centers"] == 2 and checked["available"] == 1
    assert checked["available_position_probes"] == 32
    first, last = reference["rows"]
    assert first["date_tt"] == "0001-01-01T12:00:00"
    assert first["status"] == "available" and not first["missing_probes"]
    assert first["step_difference_arcsec_per_day"] < 0.002
    assert last["date_tt"] == "9999-12-29T12:00:00"
    assert last["status"] == "incomplete"
    assert [row["offset_seconds"] for row in last["missing_probes"]] == [
        86400,
        108000,
        129600,
        172800,
        216000,
        259200,
    ]
    assert any(
        "9999-DEC-30 12:00:00.0011 TT" in row.get("error", "")
        for row in reference["requests"]
    )
    assert protocol["reference_parameters"]["TIME_TYPE"] == "'TT'"


@pytest.mark.parametrize(
    "epoch,label",
    [
        (Fraction(3442845, 2), "1bc-Dec-29 00:00:00"),
        (Fraction(1721426), "1ad-Jan-01 12:00:00"),
        (Fraction(5373485), "10000ad-Jan-01 12:00:00"),
    ],
)
def test_julian_days_cross_both_python_calendar_boundaries(epoch, label):
    assert calendar_label(epoch) == label


@pytest.mark.parametrize("fault", ["raw", "source_direction", "missing_status"])
def test_supplement_tampering_is_rejected_without_a_candidate_oracle(tmp_path, fault):
    directory = tmp_path / "supplement"
    shutil.copytree(DIRECTORY, directory)
    reference_path = directory / "reference.json"
    reference = json.loads(reference_path.read_text())
    if fault == "raw":
        raw = directory / reference["requests"][0]["raw_path"]
        raw.write_bytes(raw.read_bytes() + b" ")
    elif fault == "source_direction":
        reference["requests"][0]["rows"][0]["icrf_unit_direction"][0] += 0.001
    else:
        reference["rows"][1]["status"] = "available"
    reference_path.write_text(json.dumps(reference))
    with pytest.raises(ValueError):
        validate(directory)
