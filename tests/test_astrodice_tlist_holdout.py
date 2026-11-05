"""Frozen source identities pass; all four rate-reference failures stay failed."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_astrodice_horizons_wide_reference import validate

FIXTURE = (
    Path(__file__).parent
    / "data/astrodice/reference_sets/fixture-tlist-guard-holdout-v1"
)


def test_independent_guard_holdout_keeps_auxiliaries_and_failed_rate_templates():
    result = validate(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "source-identity.json",
    )
    assert result == json.loads((FIXTURE / "first-quality.json").read_text())
    assert result["position_probes"] == 76 and result["complete_cases"] == 4
    assert result["raw_failed_attempts"] == []
    assert (
        result["first_tlist_epoch_guard"]["batches_with_validated_auxiliary_epoch"] == 6
    )
    assert result["exit_code"] == 2
    assert len(result["failures"]) == 4
    assert all(v["reason"] == "step_nonconvergence" for v in result["failures"])


@pytest.mark.parametrize("mutation", ["auxiliary", "primary", "budget", "method"])
def test_resealed_metadata_cannot_hide_a_missing_primary_or_changed_guard(
    tmp_path, mutation
):
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    reference = json.loads((FIXTURE / "reference.json").read_text())
    if mutation == "auxiliary":
        reference["batches"][0]["first_tlist_epoch_guard"]["auxiliary_rows"] = []
    elif mutation == "primary":
        reference["rows"][0]["samples"]["0"] = None
    elif mutation == "budget":
        protocol["maximum_labels_per_batch"] = 18
    else:
        protocol["first_tlist_epoch_guard"]["method_id"] = "unverified"
    p, r, s = (tmp_path / n for n in ["protocol.json", "reference.json", "seal.json"])
    p.write_text(json.dumps(protocol))
    reference["protocol_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    r.write_text(json.dumps(reference))
    s.write_text(
        json.dumps(
            {
                "protocol_sha256": reference["protocol_sha256"],
                "reference_sha256": hashlib.sha256(r.read_bytes()).hexdigest(),
            }
        )
    )
    with pytest.raises(
        ValueError,
        match="Auxiliary integer-JD|Omitted available raw probe|Changed first-TLIST",
    ):
        validate(p, r, FIXTURE / "raw", s)
