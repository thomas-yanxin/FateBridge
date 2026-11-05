"""Acceptance references must expose their own failed quality controls."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.audit_astrodice_lunar_endpoints import validate_reference

FIXTURES = Path(__file__).parent / "data/astrodice/tables"


def inputs():
    return [
        json.loads((FIXTURES / f"lunar-endpoint-{name}.json").read_text())
        for name in ["protocol", "reference"]
    ]


def test_first_endpoint_study_keeps_all_four_failed_template_checks():
    protocol, reference = inputs()
    assert (
        hashlib.sha256(
            (FIXTURES / "lunar-endpoint-reference.json").read_bytes()
        ).hexdigest()
        == "083cc2b6ef8da612aed3a93fc4776dcf8391b38f9e818c25a582cbd4c428a19d"
    )
    result = validate_reference(protocol, reference)
    assert result["centers"] == result["available"] == 10
    assert result["position_probes"] == 370
    assert len(result["template_failures"]) == 4
    assert result["max_template_step_difference_arcsec_per_day"] > 0.002
    assert result["exact_polynomial_moments_and_minimum_norm_verified"]
    assert not reference["candidate_imported"]


def test_second_endpoint_study_preserves_its_failed_controls_and_new_cohort():
    first, _ = inputs()
    protocol, reference = [
        json.loads((FIXTURES / f"lunar-endpoint-v2-{name}.json").read_text())
        for name in ["protocol", "reference"]
    ]
    assert (
        hashlib.sha256(
            (FIXTURES / "lunar-endpoint-v2-reference.json").read_bytes()
        ).hexdigest()
        == "f29f59a60c5ea758d0f98d0fc7a53f4fc3ec48e9abf1413af76760ede366ccdc"
    )
    assert not set(first["holdout_dates_tt"]) & set(protocol["holdout_dates_tt"])
    result = validate_reference(protocol, reference)
    assert result["centers"] == result["available"] == 10
    assert result["position_probes"] == 730
    assert len(result["template_failures"]) == 4
    assert result["max_template_step_difference_arcsec_per_day"] > 0.002


def test_endpoint_validation_cli_exits_unresolved_for_failed_reference(tmp_path):
    output = tmp_path / "validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.audit_astrodice_lunar_endpoints",
            "--protocol",
            str(FIXTURES / "lunar-endpoint-v2-protocol.json"),
            "--reference",
            str(FIXTURES / "lunar-endpoint-v2-reference.json"),
            "--validate-only",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
    receipt = json.loads(output.read_text())
    assert receipt["candidate_compared"] is False
    assert receipt["status"] == "reference_evidence_unresolved"
    assert len(receipt["validation"]["template_failures"]) == 4


@pytest.mark.parametrize(
    "change",
    [
        "weights",
        "raw_response",
        "raw_angle",
        "derivative",
        "calendar",
        "incomplete",
        "collection",
    ],
)
def test_endpoint_reference_rejects_mutated_evidence(change):
    protocol, reference = copy.deepcopy(inputs())
    if change == "weights":
        protocol["rational_weights"][2][0] += 1
    elif change == "raw_response":
        reference["batches"][0]["raw_response_utf8"] += " "
    elif change == "raw_angle":
        reference["batches"][0]["rows"][0]["ra_degrees"] += 1e-5
    elif change == "derivative":
        reference["rows"][0]["icrf_direction_derivative_per_day"][0] += 0.001
    elif change == "calendar":
        reference["rows"][0]["jd_tt"] += 1 / 86400
    elif change == "incomplete":
        reference["rows"][0]["missing_probes"].append("0001-01-02T00:00:00")
    else:
        reference["candidate_imported"] = True
    with pytest.raises(ValueError):
        validate_reference(protocol, reference)
