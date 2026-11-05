"""Reject removal, rebinding and promotion of the first real development evidence."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.verify_astrodice_compressed_curve import verify

RUN = Path("tests/data/astrodice/reference_sets/study-compressed-curve")
INPUT = RUN / "development-0-first.json"
pytestmark = pytest.mark.skipif(
    not INPUT.exists(), reason="Frozen local evidence absent"
)


@pytest.fixture(scope="module")
def original():
    return json.loads(INPUT.read_text())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_cell", "full-domain population"),
        ("missing_body", "Body/cell population"),
        ("missing_profile", "Retention profile population"),
        ("promote_physical_clock", "binding/claim"),
        ("missing_leaf", "fixed leaf population"),
        ("different_source_id", "physical source segment"),
        ("different_polynomial", "full-polynomial identity"),
    ],
)
def test_independent_verifier_rejects_corrupted_real_evidence(
    original, tmp_path, mutation, message
):
    # Copy only the path being changed; all other evidence bytes stay intact.
    report = dict(original)
    report["cells"] = list(original["cells"])
    if mutation == "missing_cell":
        report["cells"].pop()
    elif mutation == "promote_physical_clock":
        report["physical_TT_TDB_equivalence_certified"] = True
    else:
        cell = dict(report["cells"][0])
        report["cells"][0] = cell
        cell["bodies"] = dict(cell["bodies"])
        if mutation == "missing_body":
            cell["bodies"].pop("Venus")
        else:
            cell["bodies"]["Moon"] = dict(cell["bodies"]["Moon"])
            profiles = cell["bodies"]["Moon"]
            if mutation == "missing_profile":
                profiles.pop("all_coefficients")
            else:
                branch = dict(profiles["rebuilt_original"])
                profiles["rebuilt_original"] = branch
                if mutation == "missing_leaf":
                    branch["leaves"] = branch["leaves"][:-1]
                elif mutation == "different_source_id":
                    branch["source_segment_ids"] = ["wrong-source:1:14"]
                elif mutation == "different_polynomial":
                    branch["error_bernstein"] = [
                        list(axis) for axis in branch["error_bernstein"]
                    ]
                    axis = branch["error_bernstein"][0]
                    axis[0] = str(Fraction(axis[0]) + Fraction(1, 10**8))
                else:
                    raise AssertionError(mutation)
    path = tmp_path / f"{mutation}.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match=message):
        verify(RUN, path)
